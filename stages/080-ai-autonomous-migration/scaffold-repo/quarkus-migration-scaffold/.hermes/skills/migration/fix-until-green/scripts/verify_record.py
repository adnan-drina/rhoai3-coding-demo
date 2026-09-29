#!/usr/bin/env python3
"""run-verify.sh's own record of its latest execution (V26-6 item 3).

A worker's terminal command reports the exit of its LAST command:
`run-verify.sh | tail -40` reports tail, `...; echo done` reports echo (v26:
three cards). The terminal line and the execution ledger therefore say nothing
about the verifier. run-verify.sh calls this twice:

  start   when it begins: status started, the card, the native run and the
          terminal call that runs it (tool_call_id: the execution ledger's
          latest run-verify START row of this card and run, which the K2 pre
          hook writes before the command executes -- the identity advance.py's
          receipt uses). A newer invocation that is interrupted leaves status
          started; one that never reached the verifier (`false && run-verify.sh`)
          leaves the older call's id: either way an older success cannot stand
          for it.
  finish  on every exit path (EXIT trap): status finished and three separate
          facts, never collapsed into one:
            procedure    the verification procedure completed (rc 0) or not
            compilation  passed / failed / unknown, from the measure and the
                         Maven compile check this execution wrote
            tests        ran (with Maven's rc) / not-run (why) / unknown

It prints one line naming all three, so a worker reading `| tail -1` sees them.
Consumers: the paved-road audit (verifier_record_gap), brief.py (LAST
VERIFICATION) and the run report. advance.py's verdict stays the acceptance
authority; this record never accepts anything.

Records only: it never repairs, re-runs or edits the product tree.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "rhoai3.last-verify/v2"
REL = Path("verification") / "loop" / "last-verify.json"
RUN_JSON = Path("verification") / "build" / "run.json"
STATE_JSON = Path("verification") / "loop" / "state.json"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read(path: Path) -> dict:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _write(root: Path, doc: dict) -> None:
    path = root / REL
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp.%d" % os.getpid())
    tmp.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _identity() -> tuple[str, str]:
    return ((os.environ.get("HERMES_KANBAN_TASK") or "").strip(), (os.environ.get("HERMES_KANBAN_RUN_ID") or "").strip())


NEEDLE = "fix-until-green/scripts/run-verify"


def ledger_path(card: str) -> Path | None:
    """<kanban root>/kanban/logs/<card>.exec.jsonl (HERMES_HOME may be a named profile's home)."""
    home = (os.environ.get("HERMES_HOME") or "").strip().rstrip("/")
    if not home or not card:
        return None
    parent, name = os.path.split(home)
    base, profiles = os.path.split(parent)
    base = base if profiles == "profiles" and name and base else home
    return Path(base) / "kanban" / "logs" / ("%s.exec.jsonl" % card)


def this_invocation(card: str, run: str) -> str:
    p = ledger_path(card)
    if p is None or not p.is_file():
        return ""
    call = ""
    for raw in p.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(raw)
        except ValueError:
            continue
        if (isinstance(row, dict) and row.get("phase") == "start" and str(row.get("task") or "") == card
                and str(row.get("run") or "") == run and NEEDLE in str(row.get("command") or "")):
            call = str(row.get("tool_call_id") or "")
    return call


def start(root: Path, mode: str) -> dict:
    card, run = _identity()
    integration = os.environ.get("RHOAI3_PILOT_INTEGRATION") == "1"
    prev = _read(root / REL)
    same = prev.get("schema") == SCHEMA and str(prev.get("card") or "") == card and str(prev.get("run") or "") == run
    try:
        seq = int(prev.get("seq")) + 1 if same else 1
    except (TypeError, ValueError):
        seq = 1
    doc = {"schema": SCHEMA, "status": "started", "card": card, "run": run, "seq": seq, "mode": mode,
           # an integration's verification runs inside native_gate.py integrate, not in a terminal call of its own
           "tool_call_id": ("integration:%s" % (os.environ.get("RHOAI3_PILOT_WT_COMMIT") or "")[:12]) if integration
                           else this_invocation(card, run),
           "started_at": _now(), "pid": os.getpid()}
    _write(root, doc)
    return doc


def outcome(root: Path, rc: int, started_at: str) -> dict:
    """compilation and tests of THIS execution: run-verify.sh removes the build
    work directory first, so a run.json there was written by this execution;
    one that is absent, or older than the start, is no evidence."""
    run_doc = _read(root / RUN_JSON)
    fresh = bool(run_doc)
    try:
        started = datetime.strptime(started_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
        fresh = fresh and (root / RUN_JSON).stat().st_mtime >= started - 1
    except (OSError, ValueError):
        fresh = False
    measure = (_read(root / STATE_JSON).get("measure") or {}) if fresh and rc == 0 else {}
    tup = list(measure.get("tuple") or [])
    known = bool(measure.get("known"))
    mvn_failed = ((run_doc.get("maven_compile") or {}).get("failed")) if fresh else None
    compile_errors = tup[1] if known and len(tup) > 1 and isinstance(tup[1], int) else None
    if not fresh or rc != 0:
        compilation, why = "unknown", ("the procedure did not complete (exit %d)" % rc if rc != 0 else "no build record from this execution")
    elif mvn_failed is True:
        compilation, why = "failed", "Maven reported a compilation failure (%s)" % ((run_doc.get("maven_compile") or {}).get("goal") or "compile")
    elif compile_errors is None:
        compilation, why = "unknown", "the compile count is not known: %s" % ("; ".join(map(str, measure.get("blocked") or [])) or "measure unknown")
    elif compile_errors > 0:
        compilation, why = "failed", "%d compile error(s)" % compile_errors
    else:
        compilation, why = "passed", "0 compile errors and Maven compiled"
    tests_doc = run_doc.get("tests") if fresh else None
    if not isinstance(tests_doc, dict):
        tests, tests_rc, tests_why = "unknown", None, "no build record from this execution"
    elif tests_doc.get("ran"):
        tests, tests_rc, tests_why = "ran", tests_doc.get("rc"), "Maven test exited %s" % tests_doc.get("rc")
    else:
        tests, tests_rc = "not-run", None
        tests_why = ("the procedure did not complete (exit %d)" % rc if rc != 0
                     else "diagnostic mode" if run_doc.get("mode") == "diagnostic"
                     else "compilation is not clean" if compilation != "passed" else "not run by this execution")
    return {"procedure": "completed" if rc == 0 else "failed", "compilation": compilation, "compilation_detail": why,
            "compile_errors": compile_errors, "tests": tests, "tests_rc": tests_rc, "tests_detail": tests_why,
            "measure": tup if known else None, "measure_known": known if fresh and rc == 0 else False,
            "candidate_sha256": str(run_doc.get("candidate_sha256") or "") if fresh else ""}


def finish(root: Path, rc: int) -> dict:
    card, run = _identity()
    prev = _read(root / REL)
    if not (prev.get("schema") == SCHEMA and str(prev.get("card") or "") == card and str(prev.get("run") or "") == run
            and prev.get("status") == "started"):
        # no start of ours to finish (it was refused before start, or another execution
        # overwrote it): record this exit as its own execution rather than guess a count
        prev = start(root, str(prev.get("mode") or "acceptance"))
    doc = dict(prev, status="finished", rc=int(rc), finished_at=_now())
    doc.update(outcome(root, int(rc), str(prev.get("started_at") or "")))
    _write(root, doc)
    return doc


def line(doc: dict) -> str:
    tests = doc.get("tests")
    tests_txt = ("tests ran (Maven exit %s)" % doc.get("tests_rc")) if tests == "ran" else \
        ("tests not run: %s" % doc.get("tests_detail")) if tests == "not-run" else "tests unknown"
    return ("VERIFY EXIT %s: procedure %s; compilation %s (%s); %s. The verifier's own status: a filter or echo "
            "after it does not change it (%s)." % (doc.get("rc"), doc.get("procedure"), str(doc.get("compilation")).upper(),
                                                   doc.get("compilation_detail"), tests_txt, REL))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("action", choices=("start", "finish"))
    ap.add_argument("--root", required=True, type=Path)
    ap.add_argument("--mode", default="acceptance")
    ap.add_argument("--rc", type=int, default=0)
    a = ap.parse_args(argv)
    root = a.root.resolve()
    if a.action == "start":
        start(root, a.mode)
        return 0
    print(line(finish(root, a.rc)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
