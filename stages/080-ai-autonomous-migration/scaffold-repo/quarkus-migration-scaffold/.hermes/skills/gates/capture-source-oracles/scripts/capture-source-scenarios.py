#!/usr/bin/env python3
"""M1 producer: stand the frozen source up and capture the approved scenarios.

Starting the source is not an Operator rescue. For a migration to claim it
preserves behaviour, recording that behaviour has to be part of the trusted
evidence the run produces: this script packages the frozen source, starts its
isolated runtime, restores the initial state before each scenario that asks
for it, replays the approved corpus, records what the source answered and what
changed, and stops what it started.

Ownership stays where it belongs. The Operator owns scenario intent and
environment authorization (the corpus, and its approver). This producer owns
execution. Implementation workers own neither: they never see an expected
value, and nothing here reads the destination.

Writes verification/source-oracles/scenarios/<slug>.json per scenario, each
bound to the corpus digest, the frozen source digest and the runtime it ran
against. Exit 0 when every selected scenario was captured, 1 otherwise, 2 usage.
"""
from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _oracle_common import ensure_hermes_lib, http_observe  # noqa: E402
from _scenarios import CorpusError, SCENARIO_ORACLES, auth_headers, corpus_digest, load_corpus, request_of, scenario_slug  # noqa: E402

ensure_hermes_lib()
from planner.admission import verify_receipt  # noqa: E402
from planner.canonical import load_json, write_canonical  # noqa: E402
from planner.canonical import digest  # noqa: E402
from planner.paths import EVIDENCE_BUNDLE, producer_receipt  # noqa: E402


def _archive_prior(receipt_p: Path) -> None:
    """Keep the receipt this run is about to replace. An idle receipt ("no
    corpus") is evidence of what the run did before a corpus existed; the
    producer used to overwrite it."""
    if receipt_p.is_file():
        try:
            at = str(load_json(receipt_p).get("at") or "").replace(":", "").replace("-", "") or "undated"
        except Exception:
            at = "unreadable"
        dest = receipt_p.with_name("%s.%s%s" % (receipt_p.stem, at, receipt_p.suffix))
        if not dest.exists():
            receipt_p.replace(dest)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _fail(msg: str) -> int:
    print("FAIL: SOURCE_SCENARIOS %s" % msg, file=sys.stderr)
    return 1


def _wait_ready(url: str, timeout: int, proc: subprocess.Popen | None) -> tuple[bool, str]:
    started = time.time()
    last = ""
    while time.time() - started < timeout:
        if proc is not None and proc.poll() is not None:
            return False, "the source exited with %d before answering" % proc.returncode
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:  # noqa: S310 - our own source app
                if int(resp.status) < 500:
                    return True, ""
        except urllib.error.HTTPError as exc:
            if int(exc.code) < 500:
                return True, ""
            last = "HTTP %s" % exc.code
        except Exception as exc:
            last = str(exc)
        time.sleep(1.0)
    return False, last or "no answer within %ds" % timeout


class SourceRuntime:
    """The frozen source, packaged once and started on demand.

    An in-memory source database is restored by restarting the process, which
    is why the runtime is owned here: a scenario that declares reset_before
    gets a fresh one, so the initial state the corpus names is the state the
    source actually saw."""

    def __init__(self, copy: Path, port: int, base_path: str, timeout: int, java: str, mvn: str, log_dir: Path) -> None:
        self.copy = copy
        self.port = port
        self.base_path = base_path
        self.timeout = timeout
        self.java = java
        self.mvn = mvn
        self.log_dir = log_dir
        self.jar: Path | None = None
        self.proc: subprocess.Popen | None = None
        self.starts = 0

    @property
    def base_url(self) -> str:
        return "http://127.0.0.1:%d%s" % (self.port, self.base_path)

    def package(self) -> str:
        log = self.log_dir / "source-package.log"
        proc = subprocess.run([self.mvn, "-B", "-DskipTests", "package"], cwd=str(self.copy), text=True, capture_output=True)
        log.write_text(proc.stdout + proc.stderr, encoding="utf-8")
        if proc.returncode != 0:
            return "packaging the frozen source failed (%s); see %s" % (proc.returncode, log.name)
        jars = sorted((self.copy / "target").glob("*.jar"))
        jars = [j for j in jars if not j.name.endswith("-sources.jar")]
        if not jars:
            return "packaging the frozen source produced no jar"
        self.jar = jars[-1]
        return ""

    def start(self) -> str:
        if self.jar is None:
            err = self.package()
            if err:
                return err
        self.stop()
        self.starts += 1
        log = self.log_dir / ("source-run-%d.log" % self.starts)
        sink = log.open("wb")
        env = dict(os.environ)
        env.setdefault("SERVER_PORT", str(self.port))
        self.proc = subprocess.Popen([self.java, "-jar", str(self.jar), "--server.port=%d" % self.port],
                                     cwd=str(self.copy), stdout=sink, stderr=subprocess.STDOUT, env=env, start_new_session=True)
        ok, why = _wait_ready(self.base_url, self.timeout, self.proc)
        return "" if ok else "the frozen source did not become ready: %s (see %s)" % (why, log.name)

    def stop(self) -> None:
        if self.proc is None:
            return
        if self.proc.poll() is None:
            try:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)
                self.proc.wait(timeout=25)
            except Exception:
                try:
                    os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
                except Exception:
                    pass
        self.proc = None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True)
    ap.add_argument("--scenario", action="append", default=[], help="capture only these scenario ids (default: all)")
    ap.add_argument("--port", type=int, default=9966)
    ap.add_argument("--base-path", default="", help="the source's context path (e.g. /petclinic); read from its own configuration when omitted")
    ap.add_argument("--ready-timeout", type=int, default=180)
    ap.add_argument("--java", default="java")
    ap.add_argument("--mvn", default="mvn")
    ap.add_argument("--any-status", action="store_true", help="allow a non-ADMITTED receipt (capture may precede admission)")
    ap.add_argument("--no-reads", action="store_true", help="skip the idempotent reads; by default they are captured through the same running source, so nobody has to start it twice")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    # The capture belongs to M1: it records what the FROZEN SOURCE does, so it
    # is bound to the evidence bundle (which exists then) and to the corpus.
    # An admission receipt may not exist yet; when it does, it is recorded too.
    # The destination verdicts are receipt-bound -- they are written at M4 --
    # so a destination repair never obliges anyone to re-capture the source.
    bundle_p = root / EVIDENCE_BUNDLE
    if not bundle_p.is_file():
        return _fail("missing %s; the scenarios are captured from the frozen source the bundle describes" % EVIDENCE_BUNDLE)
    bundle_sha = digest(load_json(bundle_p))
    receipt, gaps = verify_receipt(root, require_admitted=False)
    if gaps and receipt is not None:
        for g in gaps:
            print("  - " + g, file=sys.stderr)
        return _fail("the admission receipt on disk is not authoritative")
    receipt_p = root / SCENARIO_ORACLES / "_capture.json"
    try:
        corpus = load_corpus(root)
    except CorpusError as exc:
        # No corpus is a recorded gap, not a failure: a specimen may have no
        # approved write scenarios yet, and M1 still has to finish. What must
        # never happen is silence -- the receipt says plainly that nothing was
        # captured and why, so the absence is visible at M4.
        if "missing" in str(exc):
            _archive_prior(receipt_p)
            write_canonical(receipt_p, {
                "schema": "rhoai3.source-capture/v1", "producer": "capture-source-scenarios.py",
                "at": _now(), "status": "idle", "reason": str(exc),
                "evidence_bundle_sha256": bundle_sha, "corpus_sha256": "", "captured": 0, "scenarios": [],
            })
            print("OK: no scenario corpus (%s); nothing captured, and the receipt says so → %s" % (exc, receipt_p.relative_to(root)))
            return 0
        return _fail(str(exc))
    freeze_p = producer_receipt(root, "freeze")
    if not freeze_p.is_file():
        return _fail("no freeze receipt; the frozen source is what gets started, never the destination")
    freeze = load_json(freeze_p)
    copy = Path(str(freeze.get("analysis_copy") or ""))
    if not copy.is_dir() or not (copy / "pom.xml").is_file():
        return _fail("the freeze receipt's analysis_copy %s is not a source tree" % copy)
    base_path = args.base_path or _context_path(copy)
    log_dir = root / "verification" / "scenarios" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    wanted = [sc for sc in corpus["scenarios"] if not args.scenario or str(sc["id"]) in set(args.scenario)]
    if not wanted:
        return _fail("no scenario selected")
    corpus_sha = corpus_digest(corpus)
    runtime = SourceRuntime(copy, args.port, base_path, args.ready_timeout, args.java, args.mvn, log_dir)
    captured = 0
    failures: list[str] = []
    try:
        err = runtime.start()
        if err:
            return _fail(err)
        for sc in wanted:
            rec = {
                "schema": "rhoai3.source-scenario/v1", "scenario": str(sc["id"]), "entry_point": str(sc["entry_point"]),
                "receipt_sha256": receipt["receipt_digest"] if receipt else "",
                "evidence_bundle_sha256": bundle_sha, "corpus_sha256": corpus_sha,
                "source": {"analysis_copy_digest": str(freeze.get("source_digest") or ""), "base_url": runtime.base_url,
                           "artifact": runtime.jar.name if runtime.jar else "", "starts": runtime.starts},
                "initial_state": dict(corpus.get("initial_state") or {}),
                "normalization": list(sc.get("normalization") or []),
                "reset_before": bool(sc.get("reset_before", True)),
                "status": "UNCAPTURED", "reason": "", "request": {}, "response": {}, "before": [], "effects": [],
            }
            out = root / SCENARIO_ORACLES / (scenario_slug(sc["id"]) + ".json")
            try:
                req = request_of(root, sc)
            except CorpusError as exc:
                rec["reason"] = str(exc)
                write_canonical(out, rec)
                failures.append("%s: %s" % (sc["id"], exc))
                continue
            headers, gap = auth_headers(req["identity"])
            if gap:
                rec["status"] = "INCONCLUSIVE"
                rec["reason"] = gap
                write_canonical(out, rec)
                failures.append("%s: %s" % (sc["id"], gap))
                continue
            if sc.get("reset_before", True):
                err = runtime.start()
                if err:
                    rec["reason"] = err
                    write_canonical(out, rec)
                    failures.append("%s: %s" % (sc["id"], err))
                    continue
                rec["source"]["starts"] = runtime.starts
            rec["request"] = {k: req[k] for k in ("method", "path", "headers", "identity", "body_sha256", "body_absent", "request_sha256")}
            # What the source saw BEFORE the request. The destination has to
            # start from the same place or the comparison is meaningless: a
            # delete that removes nothing passes trivially against a
            # destination where the row was already absent.
            for eff in sc.get("effects") or []:
                probe = http_observe(runtime.base_url, str(eff.get("method") or "GET"), str(eff.get("path") or "/"), headers=headers)
                rec["before"].append({"id": str(eff.get("id") or eff.get("path")), "method": str(eff.get("method") or "GET"),
                                      "path": str(eff.get("path") or "/"), "status": probe.get("status"),
                                      "body_kind": probe.get("body_kind"), "body_sha256": probe.get("body_sha256"),
                                      "body_sample": probe.get("body_sample", "")})
            obs = http_observe(runtime.base_url, req["method"], req["path"], body=req["body"], headers={**req["headers"], **headers})
            rec["response"] = obs
            if not obs.get("status"):
                rec["reason"] = "the source did not answer: %s" % obs.get("error")
                write_canonical(out, rec)
                failures.append("%s: %s" % (sc["id"], rec["reason"]))
                continue
            for eff in sc.get("effects") or []:
                probe = http_observe(runtime.base_url, str(eff.get("method") or "GET"), str(eff.get("path") or "/"), headers=headers)
                rec["effects"].append({"id": str(eff.get("id") or eff.get("path")), "method": str(eff.get("method") or "GET"),
                                       "path": str(eff.get("path") or "/"), "status": probe.get("status"),
                                       "body_kind": probe.get("body_kind"), "body_sha256": probe.get("body_sha256"),
                                       "body_sample": probe.get("body_sample", "")})
            rec["status"] = "CAPTURED"
            write_canonical(out, rec)
            captured += 1
        # The reads, through the same runtime this producer owns. Capturing
        # them separately meant starting the source a second time by hand,
        # which is exactly the Operator rescue this step replaces.
        if not args.no_reads:
            err = runtime.start()
            if err:
                failures.append("reads: %s" % err)
            else:
                argv = [sys.executable, str(Path(__file__).resolve().parent / "capture-source-oracles.py"),
                        "--root", str(root), "--base-url", runtime.base_url, "--any-status"]
                for name, value in sorted((corpus.get("path_vars") or {}).items()):
                    argv += ["--path-var", "%s=%s" % (name, value)]
                proc = subprocess.run(argv, text=True, capture_output=True)
                reads = (proc.stdout + proc.stderr).strip().splitlines()[-1:] or [""]
                print("  reads: %s" % reads[0])
                if proc.returncode != 0:
                    failures.append("reads: %s" % reads[0])
    finally:
        runtime.stop()
    _archive_prior(receipt_p)
    write_canonical(receipt_p, {
        "schema": "rhoai3.source-capture/v1", "producer": "capture-source-scenarios.py", "at": _now(),
        "status": "ok" if not failures else "blocked",
        "reason": "; ".join(failures)[:400],
        "evidence_bundle_sha256": bundle_sha, "corpus_sha256": corpus_sha,
        "captured": captured, "requested": len(wanted),
        "scenarios": sorted(str(sc["id"]) for sc in wanted),
        "reads": bool(not args.no_reads),
        "source": {"analysis_copy_digest": str(freeze.get("source_digest") or ""), "starts": runtime.starts},
    })
    print("%s: source scenarios captured=%d of %d (corpus %s) → %s"
          % ("OK" if not failures else "REFUSE", captured, len(wanted), corpus_sha[:12], SCENARIO_ORACLES))
    for f in failures:
        print("  - %s" % f, file=sys.stderr)
    return 0 if not failures else 1


def _context_path(copy: Path) -> str:
    """The source's own context path, from its own configuration."""
    p = copy / "src" / "main" / "resources" / "application.properties"
    if p.is_file():
        for raw in p.read_text(encoding="utf-8", errors="replace").splitlines():
            s = raw.strip()
            if s.startswith("server.servlet.context-path="):
                return s.partition("=")[2].strip()
    return ""


if __name__ == "__main__":
    raise SystemExit(main())
