#!/usr/bin/env python3
"""M4 parity, run as a tool: every scenario, every read oracle, one receipt.

The parity phase used to be a worker's judgement. Measured on destination v9's
first M4 card (t_32c82390, 2026-09-15): the worker composed the receipt BEFORE
any comparison, never ran compare-runtime-parity.py for a single one of the 34
admitted entry points (24 of them ended "no parity record"), and wrote floor
receipts by hand. Nothing about that is a model failure -- a phase whose order
and completeness live in prose is a phase that will be run in the wrong order
and incompletely. So the order and the completeness move here:

  1. every scenario the approved corpus declares, in CORPUS ORDER, with the
     reset command, through compare-scenario-parity.py
  2. every admitted entry point that has a CAPTURED http read oracle, through
     compare-runtime-parity.py
  3. compose-parity-receipt.py, once, last

--scenario (repeatable) scopes step 1 to the named corpus scenarios and skips
step 2: that is how the fix-until-green acceptance path re-measures ONE parity
card's obligation without paying for the whole phase. Step 3 still runs, over
every record on disk, so the receipt a scoped run composes still states the
verdict of every entry point -- the scoped ones from this run, the rest from
the records their last full run left. The record says what was skipped and why.

The admitted entry points are the ones the composer itself counts: the
evidence bundle's entry_points (_oracle_common.entry_points), and the
scenarios the corpus requires of them (_scenarios.load_corpus). Nothing is
recomputed here; this runner calls the same source of truth so the set it
compares and the set the receipt judges cannot drift apart.

With no --dest-url the runner packages nothing but starts what packaging
produced: target/quarkus-app/quarkus-run.jar against the decided datasource
(decisions.yaml), waits for readiness the way the capture skill waits for the
source, and stops what it started. A destination someone else is running is
passed in with --dest-url and is never stopped.

Writes verification/parity/_run.json (rhoai3.parity-run/v1) beside the receipt:
what ran, in what order, with each child's exit code.

Exit 0 when every child RAN and the receipt was composed. The receipt's own
verdict is the measurement, not this runner's grade: a FAIL or INCONCLUSIVE
receipt exits 0 here and refuses at compose-m4-verdict, where a refusal is a
verdict. Exit 1 only when a child could not run: no corpus, a destination that
never became ready, a child that produced no record, or a composer that
refused to compose. Exit 2 usage.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import shlex
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def _hermes_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "lib" / ".hermes-lib").is_file():
            return parent
    raise SystemExit("FAIL: PARITY_RUN .hermes/lib marker missing")


HERMES = _hermes_dir()
CAPTURE = HERMES / "skills" / "gates" / "capture-source-oracles" / "scripts"
RUNTIME_GATE = HERMES / "skills" / "migration" / "fix-until-green" / "scripts" / "verify-runtime.py"
COMPARE_SCENARIO = CAPTURE / "compare-scenario-parity.py"
COMPARE_RUNTIME = CAPTURE / "compare-runtime-parity.py"
COMPOSE_RECEIPT = CAPTURE / "compose-parity-receipt.py"
RESET_SCRIPT = CAPTURE / "reset-parity-db.sh"

sys.path.insert(0, str(CAPTURE))
sys.path.insert(0, str(HERMES / "lib"))
from _oracle_common import ORACLES, PARITY, entry_points, slug  # noqa: E402
from _scenarios import CORPUS, CorpusError, SCENARIO_PARITY, corpus_digest, load_corpus, scenario_slug  # noqa: E402
from planner.admission import verify_receipt  # noqa: E402
from planner.canonical import load_json, write_canonical  # noqa: E402

SCHEMA = "rhoai3.parity-run/v1"
RUN_RECORD = PARITY / "_run.json"
READ_METHODS = ("GET", "HEAD")
# What a scoped run does NOT measure, named in the record rather than left to
# be inferred from a count: a filtered run is a re-measurement of one card's
# obligation, and the read oracles of every other entry point keep the verdicts
# their last full run recorded (the composer reads those records, not this run).
READ_ORACLES_FILTERED = ("skipped: this run compares only the scenarios it was scoped to (%s); the read-oracle verdicts "
                         "on disk are the ones the last unfiltered run recorded")


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit("FAIL: PARITY_RUN cannot load %s" % path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _verdict_of(path: Path) -> tuple[str, str]:
    """The verdict a comparator recorded, or ("", "") when it recorded none.

    A comparator exits 1 for a FAIL and for an INCONCLUSIVE alike; the record
    is what says which, and its ABSENCE is what says the child could not run."""
    if not path.is_file():
        return "", ""
    try:
        doc = load_json(path)
    except (OSError, ValueError):
        return "", "unreadable record %s" % path.name
    if not isinstance(doc, dict):
        return "", "record %s is not an object" % path.name
    return str(doc.get("verdict") or ""), str(doc.get("reason") or "")


def _run_child(argv: list[str], label: str) -> subprocess.CompletedProcess:
    """One child, one line of log. The v9 card's 77 KB worker log is the reason
    this prints a summary rather than the child's whole output."""
    proc = subprocess.run(argv, text=True, capture_output=True)
    tail = [ln for ln in ((proc.stdout or "") + (proc.stderr or "")).splitlines() if ln.strip()]
    print("  [%d] %s%s" % (proc.returncode, label, (" :: " + tail[-1][:200]) if tail else ""))
    return proc


# --- the destination this runner starts, when nobody handed it one ----------

def _wait_ready(url: str, timeout: int, proc: subprocess.Popen | None) -> tuple[bool, str]:
    """Readiness as the capture skill defines it for the source: any answer
    below 500 from the process we started, within a bounded time."""
    started = time.time()
    last = ""
    while time.time() - started < timeout:
        if proc is not None and proc.poll() is not None:
            return False, "the destination exited with %d before answering" % proc.returncode
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:  # noqa: S310 - our own application
                if int(resp.status) < 500:
                    return True, ""
        except urllib.error.HTTPError as exc:
            if int(exc.code) < 500:
                return True, ""
            last = "HTTP %s" % exc.code
        except Exception as exc:  # noqa: BLE001 - any transport error is "not yet"
            last = str(exc)
        time.sleep(1.0)
    return False, last or "no answer within %ds" % timeout


class Destination:
    """The packaged destination, started against the decided database.

    Packaging is NOT done here: the packaging gate (verify-runtime.py --gate
    package) owns that, and a parity run that rebuilt the tree would be
    comparing something other than what was verified. This starts the artifact
    that gate produced, and stops it again."""

    def __init__(self, root: Path, port: int, java: str, timeout: int) -> None:
        self.root = root
        self.port = port
        self.java = java
        self.timeout = timeout
        self.proc: subprocess.Popen | None = None
        self.log = root / PARITY / "logs" / "destination.log"
        self.gate = _load_module(RUNTIME_GATE, "verify_runtime_gate")
        self.root_path = self.gate.root_path_of(root)
        self.ds: dict[str, Any] = {}
        self.profiles: list[str] = []

    @property
    def base_url(self) -> str:
        rp = self.root_path if self.root_path.startswith("/") else "/" + self.root_path
        return "http://127.0.0.1:%d%s" % (self.port, rp.rstrip("/") if rp != "/" else "")

    def start(self) -> str:
        from planner.decisions import DecisionsError, build_profiles, datasource, load_decisions

        try:
            decisions = load_decisions(self.root)
            self.ds = datasource(decisions) or {}
            self.profiles = [str(x) for x in (build_profiles(decisions).get("active") or [])]
        except DecisionsError as exc:
            return str(exc)
        if not self.ds:
            return ("the effective datasource is not decided (decisions.yaml datasource under an accepted ADR); "
                    "there is no database to compare the destination against")
        runner = self.root / self.gate.RUNNER
        if not runner.is_file():
            return ("the destination is not packaged (%s is absent); the packaging gate produces what parity starts"
                    % self.gate.RUNNER.as_posix())
        missing = [str(self.ds[k]) for k in ("jdbc_url_env", "username_env", "password_env")
                   if self.ds.get(k) and not os.environ.get(str(self.ds[k]))]
        if missing:
            return ("environment: %s not set; the decided datasource (%s, instance %s) is not reachable from here"
                    % (", ".join(missing), self.ds.get("db_kind"), self.ds.get("instance")))
        ok, _ = _wait_ready(self.base_url, 1, None)
        if ok:
            return ("port %d is already answering before anything was started; a parity reading there would not be "
                    "about this application (pass --dest-url to compare against a destination someone else runs)" % self.port)
        self.log.parent.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ)
        env["QUARKUS_HTTP_PORT"] = str(self.port)
        if self.profiles:
            env["QUARKUS_PROFILE"] = ",".join(self.profiles)
        sink = self.log.open("wb")
        self.proc = subprocess.Popen([self.java, "-jar", str(self.gate.RUNNER)], cwd=str(self.root),
                                     stdout=sink, stderr=subprocess.STDOUT, env=env, start_new_session=True)
        ready, why = _wait_ready(self.base_url, self.timeout, self.proc)
        text = self.log.read_text(encoding="utf-8", errors="replace") if self.log.is_file() else ""
        if not ready:
            return "the destination did not become ready: %s (see %s)" % (why, self.log.name)
        db_ok, db_why = self.gate.database_ready(text, self.ds)
        if not db_ok:
            return "the destination answered but its datasource did not start: %s (see %s)" % (db_why, self.log.name)
        return ""

    def stop(self) -> None:
        if self.proc is None:
            return
        if self.proc.poll() is None:
            try:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)
                self.proc.wait(timeout=25)
            except Exception:  # noqa: BLE001
                try:
                    os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
                except Exception:  # noqa: BLE001
                    pass
        self.proc = None


# --- what gets compared ------------------------------------------------------

def read_oracle_gap(root: Path, ep: str) -> str:
    """"" when this entry point has a CAPTURED http read oracle, else why not.

    compare-runtime-parity.py replays a method and a path: that is a read, and
    provably not a write (it sends no body). The gap is NAMED rather than
    passed over in silence -- an entry point nobody could compare is a coverage
    gap the receipt reports, not an absence nobody wrote down."""
    p = root / ORACLES / (slug(ep) + ".json")
    if not p.is_file():
        return "no source oracle captured at M1"
    try:
        oracle = load_json(p)
    except (OSError, ValueError):
        return "the source oracle is unreadable"
    if str(oracle.get("status") or "") != "CAPTURED":
        return "the source oracle is %s: %s" % (oracle.get("status"), str(oracle.get("reason") or "")[:120])
    kind = str(oracle.get("kind") or "")
    if kind != "http":
        return "a %s entry point is compared from a captured destination observation (--dest-observation), not over HTTP" % (kind or "non-http")
    method = str((oracle.get("oracle") or {}).get("method") or "GET").upper()
    if method not in READ_METHODS:
        return "a %s entry point is compared through the scenario corpus, not by replaying a method and a path" % method
    return ""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True, help="the destination product root")
    ap.add_argument("--dest-url", default="", help="a destination someone else is running; without it the packaged one is started here and stopped again")
    ap.add_argument("--reset-cmd", default="", help="the command that restores the declared initial state (default: the reset script beside the capture skill)")
    ap.add_argument("--scenario", action="append", default=[], metavar="ID",
                    help="repeatable: compare ONLY these corpus scenarios (the fix-until-green acceptance path scopes the "
                         "comparison to the scenarios the issued parity card is made of). The read-oracle phase is skipped "
                         "under the filter and said so in _run.json; the composer still runs, over every record on disk")
    ap.add_argument("--port", type=int, default=8081, help="the port the destination this runner starts listens on")
    ap.add_argument("--ready-timeout", type=int, default=180)
    ap.add_argument("--java", default="java")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    if not root.is_dir():
        print("FAIL: PARITY_RUN --root must be an existing directory", file=sys.stderr)
        return 2
    reset_cmd = args.reset_cmd or shlex.join(["bash", str(RESET_SCRIPT), "--root", str(root)])

    receipt, receipt_gaps = verify_receipt(root, require_admitted=True)
    wanted = sorted(str(e.get("id")) for e in entry_points(root) if e.get("id"))
    corpus: dict[str, Any] = {}
    corpus_error = ""
    try:
        corpus = load_corpus(root)
    except CorpusError as exc:
        corpus_error = str(exc)
    corpus_sha = corpus_digest(corpus) if corpus else ""
    declared = [sc for sc in (corpus.get("scenarios") or []) if str(sc.get("id") or "")]
    # The filter SELECTS from the corpus; it never invents a scenario. An id
    # nobody declared is a caller asking for a comparison that cannot be made,
    # and it refuses rather than running a smaller set in silence.
    wanted_ids = sorted({str(s) for s in (args.scenario or []) if str(s)})
    unknown_ids = [s for s in wanted_ids if s not in {str(sc["id"]) for sc in declared}]
    scenarios = [sc for sc in declared if str(sc["id"]) in set(wanted_ids)] if wanted_ids else declared

    doc: dict[str, Any] = {
        "schema": SCHEMA, "producer": "run-parity.py", "at": _now(), "root": str(root),
        "dest_url": "", "started_by_runner": False, "reset_cmd": reset_cmd,
        "receipt_sha256": receipt["receipt_digest"] if receipt else "",
        "receipt_gaps": list(receipt_gaps or []),
        "corpus": str(CORPUS.as_posix()), "corpus_sha256": corpus_sha, "corpus_error": corpus_error,
        "scenario_filter": list(wanted_ids),
        "scenarios": {"declared": len(declared), "selected": len(scenarios), "run": 0, "passed": 0, "failed": 0,
                      "inconclusive": 0, "results": []},
        "read_oracles": {"ran": not wanted_ids,
                         "reason": (READ_ORACLES_FILTERED % ", ".join(wanted_ids)) if wanted_ids else ""},
        "entry_points": {"admitted": len(wanted), "compared": 0, "passed": 0, "failed": 0, "inconclusive": 0,
                         "skipped": 0, "results": [], "not_compared": []},
        "compose": {"rc": None, "argv": []},
        "receipt_verdict": "", "failures": [], "ok": False,
    }
    out = root / RUN_RECORD
    failures: list[str] = doc["failures"]
    if corpus_error:
        # The corpus is the only source of a write comparison. Its absence is
        # not an idle phase at M4: the scenario child could not run at all.
        failures.append("corpus: %s" % corpus_error)
    if unknown_ids:
        failures.append("scenario filter: %s is not declared by the corpus (%s); nothing was compared for it"
                        % (", ".join(unknown_ids), CORPUS.as_posix()))

    dest = None
    try:
        if args.dest_url:
            doc["dest_url"] = args.dest_url
        else:
            dest = Destination(root, args.port, args.java, args.ready_timeout)
            print("starting the packaged destination on port %d ..." % args.port)
            err = dest.start()
            doc["dest_url"] = dest.base_url
            doc["started_by_runner"] = True
            doc["destination"] = {"port": args.port, "root_path": dest.root_path,
                                  "log": str(dest.log.relative_to(root)) if dest.log.is_file() else "",
                                  "profiles": list(dest.profiles), "db_kind": str(dest.ds.get("db_kind") or "")}
            if err:
                failures.append("destination: %s" % err)
                doc["destination"]["error"] = err
                write_canonical(out, doc)
                print("REFUSE: PARITY_RUN %s → %s" % (err, out), file=sys.stderr)
                return 1

        dest_url = doc["dest_url"]

        # 1. every scenario the corpus declares, in corpus order
        for sc in scenarios:
            sid = str(sc["id"])
            argv_sc = [sys.executable, str(COMPARE_SCENARIO), "--root", str(root), "--scenario", sid,
                       "--dest-url", dest_url, "--reset-cmd", reset_cmd]
            proc = _run_child(argv_sc, "scenario %s" % sid)
            verdict, reason = _verdict_of(root / SCENARIO_PARITY / (scenario_slug(sid) + ".json"))
            row = {"id": sid, "entry_point": str(sc.get("entry_point") or ""), "rc": proc.returncode,
                   "verdict": verdict, "reason": reason[:300]}
            doc["scenarios"]["results"].append(row)
            if not verdict:
                failures.append("scenario %s recorded no verdict (rc %d): %s"
                                % (sid, proc.returncode, ((proc.stderr or proc.stdout or "").strip()[-200:])))
                continue
            doc["scenarios"]["run"] += 1
            key = {"PASS": "passed", "FAIL": "failed"}.get(verdict, "inconclusive")
            doc["scenarios"][key] += 1

        # 2. every admitted entry point that has a captured read oracle -- unless
        #    this run was scoped to named scenarios, when the read oracles are
        #    not what is being re-measured and every entry point is named as
        #    not compared, with the reason
        for ep in (wanted if not wanted_ids else []):
            gap = read_oracle_gap(root, ep)
            if gap:
                doc["entry_points"]["skipped"] += 1
                doc["entry_points"]["not_compared"].append({"entry_point": ep, "reason": gap})
                continue
            argv_ep = [sys.executable, str(COMPARE_RUNTIME), "--root", str(root), "--entry-point", ep,
                       "--dest-url", dest_url]
            proc = _run_child(argv_ep, "entry point %s" % ep)
            verdict, reason = _verdict_of(root / PARITY / (slug(ep) + ".json"))
            doc["entry_points"]["results"].append({"entry_point": ep, "rc": proc.returncode,
                                                   "verdict": verdict, "reason": reason[:300]})
            if not verdict:
                failures.append("entry point %s recorded no verdict (rc %d): %s"
                                % (ep, proc.returncode, ((proc.stderr or proc.stdout or "").strip()[-200:])))
                continue
            doc["entry_points"]["compared"] += 1
            key = {"PASS": "passed", "FAIL": "failed"}.get(verdict, "inconclusive")
            doc["entry_points"][key] += 1
        if wanted_ids:
            for ep in wanted:
                doc["entry_points"]["skipped"] += 1
                doc["entry_points"]["not_compared"].append({"entry_point": ep, "reason": doc["read_oracles"]["reason"]})
    finally:
        if dest is not None:
            dest.stop()

    # 3. the receipt, once, last
    argv_rc = [sys.executable, str(COMPOSE_RECEIPT), "--root", str(root)]
    proc = _run_child(argv_rc, "compose-parity-receipt")
    doc["compose"] = {"rc": proc.returncode, "argv": argv_rc[1:]}
    receipt_p = root / PARITY / "receipt.json"
    verdict, _ = _verdict_of(receipt_p)
    doc["receipt_verdict"] = verdict
    if not verdict:
        failures.append("compose-parity-receipt.py composed no receipt (rc %d): %s"
                        % (proc.returncode, ((proc.stderr or proc.stdout or "").strip()[-300:])))

    doc["ok"] = not failures
    write_canonical(out, doc)
    summary = ("%s%d/%d scenario(s) run (%d PASS, %d FAIL, %d INCONCLUSIVE); %d/%d entry point(s) compared "
               "(%d not compared); receipt %s"
               % (("scoped to %s: " % ", ".join(wanted_ids)) if wanted_ids else "",
                  doc["scenarios"]["run"], doc["scenarios"]["selected"], doc["scenarios"]["passed"],
                  doc["scenarios"]["failed"], doc["scenarios"]["inconclusive"], doc["entry_points"]["compared"],
                  doc["entry_points"]["admitted"], doc["entry_points"]["skipped"], verdict or "NOT COMPOSED"))
    for row in doc["entry_points"]["not_compared"]:
        print("  - not compared: %s (%s)" % (row["entry_point"], row["reason"]))
    if failures:
        for f in failures:
            print("  - %s" % f, file=sys.stderr)
        print("REFUSE: PARITY_RUN %s → %s" % (summary, out), file=sys.stderr)
        return 1
    # The receipt's verdict is the measurement, not this runner's grade.
    print("OK: PARITY_RUN %s → %s" % (summary, out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
