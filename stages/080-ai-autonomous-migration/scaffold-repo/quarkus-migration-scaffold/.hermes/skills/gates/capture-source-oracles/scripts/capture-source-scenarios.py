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

Security mode (ADR-014). The source's security switch has two settings and
they are two behaviours, so each is captured SEPARATELY and says which it is:
``--security-mode disabled`` (the default, and the directory above) or
``--security-mode enabled``, which writes
verification/source-oracles/scenarios-enabled/ instead. The switch itself is
the specimen's, not this harness's: it arrives as ``--source-config
KEY=VALUE`` (repeatable), is passed to the runtime as a system property and as
the runner's own argument, and is recorded verbatim on the receipt. Credentials
arrive by REFERENCE -- ``--credential-ref NAME`` names an environment variable
holding ``user:password``, a scenario asks for it by that name
(``identity: {"kind": "basic", "credential_ref": NAME}``), and only the name is
ever written down. A ``--source-config`` value that equals a credential is
refused before the source starts.

Normally none of that is typed: ``--from-decisions`` (the default for
``--security-mode enabled`` when no ``--credential-ref`` is given) reads
``decisions.yaml``'s ``security`` section -- the switch by KEY, each identity
by the NAME of the variable holding its credential -- so the capture starts the
source the way the corpus it replays was derived for, and the declaration an
ADR backs is the only place either of them comes from. A section nobody
declared, or a declared credential this workspace does not hold, captures
NOTHING: ``_capture.json`` is written with ``status: idle`` and a reason naming
the missing environment VARIABLE. That is ADR-014's recorded blocker -- never
an invented identity, and never an empty directory nobody can read.

Binding rule. A capture is bound to the FROZEN SOURCE (the evidence bundle
digest) and to the corpus, never to the admission receipt. Measured on v9
(2026-09-14): this producer refused to start the source because the receipt's
sealed work-list digest (69ea62037d7d) differed from the work list on disk
(14a2507dc2f0) -- a worker's diagnostic verify had rebuilt the list 28 s after
the seal, which is the normal state beside the M3 loop. The source's behaviour
does not change when the destination's admission is re-sealed, and a producer
that could only run between seals could never run beside a loop. So the
receipt digest is recorded only when the receipt is authoritative, the gaps
are noted on the producer receipt (``receipt_note``) so the observation is
honest, and the only refusal is a missing evidence bundle.
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
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _oracle_common import ensure_hermes_lib, http_observe, retain_body  # noqa: E402
from _scenarios import (CorpusError, DEFAULT_SECURITY_MODE, SCENARIO_ORACLES, SECURITY_MODES, auth_headers,  # noqa: E402,F401
                        auth_headers_for, capture_receipt_path, corpus_digest, credential_conflicts, load_corpus,
                        normalize_security_mode, parse_assignments, request_of, scenario_oracles_dir, scenario_slug,
                        source_exposed_headers)

ensure_hermes_lib()
from planner.admission import verify_receipt  # noqa: E402
from planner.canonical import load_json, write_canonical  # noqa: E402
from planner.canonical import digest  # noqa: E402
from planner.decisions import DecisionsError, load_decisions, security, security_gaps  # noqa: E402
from planner.paths import DECISIONS, EVIDENCE_BUNDLE, producer_receipt  # noqa: E402


CAPTURE_SCHEMA = "rhoai3.source-capture/v1"


def decided_security(root: Path) -> tuple[dict[str, Any], str]:
    """(the decided security switch and identities, why-not) for this tree.

    Who the enabled-mode capture authenticates as, and which switch turns the
    source's security on, are DECISIONS an ADR backs -- recorded once, read by
    the derivation and by this capture, so the corpus and the run it is
    replayed in came from the same declaration. A missing section is a
    REASON the caller records; it never becomes an anonymous capture wearing
    the enabled mode's name."""
    try:
        doc = load_decisions(root)
    except (DecisionsError, OSError) as exc:
        return {}, str(exc)
    decided = security(doc)
    if decided:
        return decided, ""
    refusals = security_gaps(doc)
    if refusals:
        return {}, ("%s declares a security section this loader refuses: %s"
                    % (DECISIONS.as_posix(), "; ".join("%s %s" % (g["subject"], g["detail"]) for g in refusals)))
    return {}, ("%s declares no security section (ADR-014: the switch, the seeded identities and the credential REFERENCES "
                "the enabled mode is captured with)" % DECISIONS.as_posix())


def missing_credentials(credential_refs: list[str]) -> list[str]:
    """The declared references the workspace does not hold, by NAME.

    A credential the environment does not carry cannot be invented and must
    not be worked around: the capture stops before starting the source and
    says which VARIABLE is empty. The name is the whole message -- what it
    would have held is never read, printed or written."""
    return [ref for ref in credential_refs if not os.environ.get(ref, "").strip()]


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

    def __init__(self, copy: Path, port: int, base_path: str, timeout: int, java: str, mvn: str, log_dir: Path,
                 source_config: dict[str, str] | None = None) -> None:
        self.copy = copy
        self.port = port
        self.base_path = base_path
        self.timeout = timeout
        self.java = java
        self.mvn = mvn
        self.log_dir = log_dir
        # The configuration this run starts the source WITH (ADR-014): the
        # keys are the caller's, never this harness's -- which property turns
        # the source's security on is a property of the specimen, so it
        # arrives as an argument and is recorded, not named in code.
        self.source_config = dict(source_config or {})
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
        # The runner already configures the source two ways -- an environment
        # variable and a ``--key=value`` argument for the port -- so the
        # caller's configuration goes through the same channels: a JVM system
        # property, which any runtime reads, and the argument form this
        # runner already uses, which the source's own framework binds with the
        # highest precedence. Passing one value twice is harmless; passing it
        # through a channel the source ignores is not.
        self.proc = subprocess.Popen(
            [self.java] + ["-D%s=%s" % (k, v) for k, v in sorted(self.source_config.items())]
            + ["-jar", str(self.jar), "--server.port=%d" % self.port]
            + ["--%s=%s" % (k, v) for k, v in sorted(self.source_config.items())],
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
    ap.add_argument("--security-mode", choices=list(SECURITY_MODES), default=DEFAULT_SECURITY_MODE,
                    help="which setting of the source's security switch this capture is of (ADR-014). The two modes are captured "
                         "separately and into separate directories; the mode is recorded on every file this writes")
    ap.add_argument("--source-config", action="append", default=[], metavar="KEY=VALUE",
                    help="configuration the frozen source is STARTED with (repeatable), passed as a JVM system property and as the "
                         "runner's own --key=value argument. For the enabled mode the caller passes the specimen's own security "
                         "switch, e.g. --source-config petclinic.security.enable=true; the key is recorded, never assumed")
    ap.add_argument("--credential-ref", action="append", default=[], metavar="NAME",
                    help="an environment variable holding user:password (repeatable). A scenario whose identity names it as "
                         "credential_ref is sent with Basic authentication; only the NAME is ever recorded")
    ap.add_argument("--from-decisions", action="store_true",
                    help="enabled mode: take the credential REFERENCES and the source's security switch from decisions.yaml's "
                         "security section (ADR-014) -- --source-config is filled with switch.key=switch.enabled_value. The "
                         "default whenever --security-mode enabled is given with no --credential-ref. A missing section, or a "
                         "declared credential the workspace does not hold, captures nothing and records why")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    try:
        security_mode = normalize_security_mode(args.security_mode)
        source_config = parse_assignments(args.source_config, "--source-config")
    except CorpusError as exc:
        return _fail(str(exc))
    credential_refs = sorted({str(r) for r in (args.credential_ref or []) if str(r).strip()})
    # the decided switch and identities: the same declaration the enabled
    # corpus was derived from, so the run and the corpus agree on who the
    # source is being asked as and which setting it was started with
    from_decisions = bool(security_mode != DEFAULT_SECURITY_MODE and (args.from_decisions or not credential_refs))
    decided_why = ""
    if from_decisions:
        decided, decided_why = decided_security(root)
        if decided:
            credential_refs = sorted({i["credential_ref"] for i in decided["identities"] if i["credential_ref"]}
                                     | ({str(decided["invalid_credential_ref"])} if decided.get("invalid_credential_ref") else set()))
            if not source_config:
                switch = decided["switch"]
                source_config = {switch["key"]: switch["enabled_value"]}
    # A credential passed as configuration would be written verbatim into the
    # capture receipt, which is exactly what ADR-014 forbids. The refusal
    # names the KEY, never the value.
    conflicts = credential_conflicts(source_config, credential_refs)
    if conflicts:
        return _fail("--source-config %s carries the value of a credential (%s); configuration is recorded in the evidence, "
                     "so a credential must be passed by reference (--credential-ref) and never as a property"
                     % (", ".join(conflicts), ", ".join(credential_refs)))
    oracles_dir = scenario_oracles_dir(security_mode)
    read_reads = bool(not args.no_reads and security_mode == DEFAULT_SECURITY_MODE)
    reads_note = "" if read_reads or args.no_reads else (
        "the idempotent read oracles were not captured: they live in an oracle directory that is not mode-scoped, and this "
        "capture is of the %s security mode; capture the reads in the %s mode" % (security_mode, DEFAULT_SECURITY_MODE))
    # The capture belongs to M1: it records what the FROZEN SOURCE does, so it
    # is bound to the evidence bundle (which exists then) and to the corpus.
    # An admission receipt may not exist yet; when it does, it is recorded too.
    # The destination verdicts are receipt-bound -- they are written at M4 --
    # so a destination repair never obliges anyone to re-capture the source.
    bundle_p = root / EVIDENCE_BUNDLE
    if not bundle_p.is_file():
        return _fail("missing %s; the scenarios are captured from the frozen source the bundle describes" % EVIDENCE_BUNDLE)
    bundle_sha = digest(load_json(bundle_p))
    # the receipt digest is recorded only when the receipt is authoritative;
    # a stale one (the work list rebuilt after the seal, beside the loop) is
    # a note, never a refusal -- the frozen source did not change
    receipt, gaps = verify_receipt(root, require_admitted=False)
    receipt_sha = receipt["receipt_digest"] if receipt is not None and not gaps else ""
    receipt_note = "" if not gaps else ("admission receipt not recorded: " + "; ".join(gaps))[:400]
    if receipt_note:
        print("  note: %s" % receipt_note, file=sys.stderr)
    receipt_p = root / capture_receipt_path(security_mode)

    def idle(reason: str) -> int:
        """Nothing was captured, and the receipt says exactly what is missing.

        ADR-014's rule for an absent fixture: record the blocker. Not a
        refusal -- a specimen with no security switch has no enabled mode to
        capture -- and never silence, because an empty directory reads at M4
        as a mode nobody thought about."""
        _archive_prior(receipt_p)
        write_canonical(receipt_p, {
            "schema": CAPTURE_SCHEMA, "producer": "capture-source-scenarios.py",
            "at": _now(), "status": "idle", "reason": reason,
            "evidence_bundle_sha256": bundle_sha, "corpus_sha256": "", "captured": 0, "scenarios": [],
            "receipt_sha256": receipt_sha, "receipt_note": receipt_note,
            "security_mode": security_mode, "source_config": dict(source_config), "credential_refs": list(credential_refs),
        })
        print("OK: nothing captured in the %s security mode (%s); the receipt says so → %s"
              % (security_mode, reason, receipt_p.relative_to(root)))
        return 0

    # the two fixtures ADR-014 says to RECORD rather than work around: a
    # security section nobody declared, and a declared credential this
    # workspace does not hold. The second names the VARIABLE and nothing else
    # -- what it would have held is never read here, printed or written.
    if from_decisions and decided_why:
        return idle(decided_why)
    if from_decisions:
        absent = missing_credentials(credential_refs)
        if absent:
            return idle("the credential reference(s) %s that %s declares are not set in this workspace; a credential is never "
                        "invented and the capture is not attempted without one" % (", ".join(absent), DECISIONS.as_posix()))
    try:
        # the corpus of THIS mode: an enabled-mode capture replays the enabled
        # corpus's authorization probes, not the anonymous requests beside them
        corpus = load_corpus(root, security_mode)
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
                "receipt_sha256": receipt_sha, "receipt_note": receipt_note,
                "security_mode": security_mode, "source_config": dict(source_config), "credential_refs": list(credential_refs),
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
    # the headers the source itself exposes are asserted alongside Location
    # and the CORS set; recorded on every capture so a comparator can see
    # what was asserted rather than assume
    exposed, exposed_gap = source_exposed_headers(root)
    if exposed_gap:
        # fail closed: a capture that could not learn which headers the source
        # exposes would assert too little and read as complete (architect
        # review, 2026-09-14). No source is started for it.
        return _fail("%s; the capture cannot know which headers the source exposes, so nothing is captured" % exposed_gap)
    runtime = SourceRuntime(copy, args.port, base_path, args.ready_timeout, args.java, args.mvn, log_dir,
                            source_config=source_config)
    captured = 0
    failures: list[str] = []
    try:
        err = runtime.start()
        if err:
            return _fail(err)
        for sc in wanted:
            # what THIS scenario asserts, on top of the headers the source
            # exposes to everyone. A refusal's WWW-Authenticate is the source
            # saying how to authenticate; a destination that drops it has
            # changed the behaviour, and a capture that never asked for the
            # header could not show it. The scenario names it (the derivation
            # wrote asserted_headers), the capture records the union it
            # actually asserted, and the comparator reads that union back --
            # so nothing downstream has to know which headers are security's.
            own = [str(h).strip() for h in (sc.get("asserted_headers") or []) if str(h).strip()]
            asserted = list(exposed) + [h for h in dict.fromkeys(own) if h not in exposed]
            rec = {
                "schema": "rhoai3.source-scenario/v1", "scenario": str(sc["id"]), "entry_point": str(sc["entry_point"]),
                "receipt_sha256": receipt_sha,
                "evidence_bundle_sha256": bundle_sha, "corpus_sha256": corpus_sha,
                "source": {"analysis_copy_digest": str(freeze.get("source_digest") or ""), "base_url": runtime.base_url,
                           "artifact": runtime.jar.name if runtime.jar else "", "starts": runtime.starts},
                "initial_state": dict(corpus.get("initial_state") or {}),
                "normalization": list(sc.get("normalization") or []),
                "asserted_headers_extra": list(asserted),
                "asserted_headers_scenario": list(dict.fromkeys(own)),
                "security_mode": security_mode,
                "reset_before": bool(sc.get("reset_before", True)),
                "status": "UNCAPTURED", "reason": "", "request": {}, "response": {}, "before": [], "effects": [],
            }
            out = root / oracles_dir / (scenario_slug(sc["id"]) + ".json")
            try:
                req = request_of(root, sc)
            except CorpusError as exc:
                rec["reason"] = str(exc)
                write_canonical(out, rec)
                failures.append("%s: %s" % (sc["id"], exc))
                continue
            headers, gap = auth_headers_for(req["identity"], credential_refs)
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
            # the full bodies are kept beside the capture, bound by digest, so
            # qualification can SEE the created owner in the list and the
            # rejected one absent -- a sample or a digest alone cannot say
            bodies_dir = root / oracles_dir / "bodies" / scenario_slug(sc["id"])
            for eff in sc.get("effects") or []:
                probe = http_observe(runtime.base_url, str(eff.get("method") or "GET"), str(eff.get("path") or "/"), headers=headers, keep_body=True)
                eid = str(eff.get("id") or eff.get("path"))
                row = {"id": eid, "method": str(eff.get("method") or "GET"),
                       "path": str(eff.get("path") or "/"), "status": probe.get("status"),
                       "body_kind": probe.get("body_kind"), "body_sha256": probe.get("body_sha256"),
                       "body_sample": probe.get("body_sample", "")}
                if probe.get("status"):
                    row["evidence"] = retain_body(bodies_dir, "before-%s" % scenario_slug(eid), probe.get("raw") or b"", str(probe.get("body_sha256") or ""))
                rec["before"].append(row)
            obs = http_observe(runtime.base_url, req["method"], req["path"], body=req["body"], headers={**req["headers"], **headers},
                               assert_headers=asserted, keep_body=True)
            raw = obs.pop("raw", b"")
            rec["response"] = obs
            if obs.get("status"):
                rec["response"]["evidence"] = retain_body(bodies_dir, "response", raw, str(obs.get("body_sha256") or ""))
            if not obs.get("status"):
                rec["reason"] = "the source did not answer: %s" % obs.get("error")
                write_canonical(out, rec)
                failures.append("%s: %s" % (sc["id"], rec["reason"]))
                continue
            for eff in sc.get("effects") or []:
                probe = http_observe(runtime.base_url, str(eff.get("method") or "GET"), str(eff.get("path") or "/"), headers=headers, keep_body=True)
                eid = str(eff.get("id") or eff.get("path"))
                row = {"id": eid, "method": str(eff.get("method") or "GET"),
                       "path": str(eff.get("path") or "/"), "status": probe.get("status"),
                       "body_kind": probe.get("body_kind"), "body_sha256": probe.get("body_sha256"),
                       "body_sample": probe.get("body_sample", "")}
                if probe.get("status"):
                    row["evidence"] = retain_body(bodies_dir, "after-%s" % scenario_slug(eid), probe.get("raw") or b"", str(probe.get("body_sha256") or ""))
                rec["effects"].append(row)
            rec["status"] = "CAPTURED"
            write_canonical(out, rec)
            captured += 1
        # The reads, through the same runtime this producer owns. Capturing
        # them separately meant starting the source a second time by hand,
        # which is exactly the Operator rescue this step replaces.
        # They are captured in the DEFAULT mode only: the read oracles live in
        # verification/source-oracles/, which is not mode-scoped, so capturing
        # them in the enabled mode would overwrite the other mode's expected
        # values with 401s -- the cross-mode reuse ADR-014 forbids, arriving
        # through the back door. The receipt says so rather than staying
        # silent about it.
        if read_reads:
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
        "receipt_sha256": receipt_sha, "receipt_note": receipt_note,
        "security_mode": security_mode, "source_config": dict(source_config), "credential_refs": list(credential_refs),
        "captured": captured, "requested": len(wanted),
        "scenarios": sorted(str(sc["id"]) for sc in wanted),
        "reads": bool(read_reads), "reads_note": reads_note,
        "source": {"analysis_copy_digest": str(freeze.get("source_digest") or ""), "starts": runtime.starts},
    })
    print("%s: source scenarios captured=%d of %d (corpus %s) → %s"
          % ("OK" if not failures else "REFUSE", captured, len(wanted), corpus_sha[:12], oracles_dir))
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
