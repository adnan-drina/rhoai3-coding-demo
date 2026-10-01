#!/usr/bin/env python3
"""advance._recorded_verdict on an outcome board (v30 t_e1242a11, 2026-10-01).

The first advance of the card accepted and committed, then admission refused, so
the outcome was never judged; the next run's issue RECOVERED that commit. Every
later advance answered CHECKPOINT ALREADY RECORDED and then ran the serial-loop
tail -- rebuild, re-admit, K4 mint -- which on an outcome board mints nothing:
REFUSE: LOOP_NO_SUCCESSOR, the card blocked twice and went to triage while 13
cards waited. The recovered acceptance must finish on the outcome record
(resume_recovered); the serial mint must not run on an outcome board.

The real _recorded_verdict runs; the work-list rebuild, admission, publication,
the outcome bridge and the serial continuation are recorded stubs."""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
spec = importlib.util.spec_from_file_location("advance_under_test", HERE / "advance.py")
adv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adv)  # type: ignore[union-attr]


def run_case(*, board: bool, admitted: bool, recovered: int | None) -> tuple[int | None, list[str]]:
    import contextlib
    import io
    calls: list[str] = []
    out = io.StringIO()
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / adv.WORKLIST).parent.mkdir(parents=True, exist_ok=True)
        (root / adv.WORKLIST).write_text(json.dumps({"clusters": []}))
        saved = {k: getattr(adv, k) for k in ("build_worklist", "publish_loop_state", "_finish_continuation", "load_issued")}
        saved_admit, saved_active, saved_resume = adv.pipeline.admit, adv._outcome_bridge.active, adv._outcome_bridge.resume_recovered
        try:
            adv.build_worklist = lambda r: calls.append("rebuild") or {"clusters": []}
            adv.publish_loop_state = lambda r, w: calls.append("publish")
            adv.pipeline.admit = lambda r: calls.append("admit") or {"status": "ADMITTED" if admitted else "INCONCLUSIVE", "reasons": ["x"]}
            adv._outcome_bridge.active = lambda r: board
            adv._outcome_bridge.resume_recovered = lambda r, w, run: calls.append("resume_recovered") or recovered
            adv._finish_continuation = lambda *a, **k: calls.append("serial-mint") or 1
            adv.load_issued = lambda r: {}
            steps = {"steps": [{"card": "t_x", "verdict": "accepted", "commit": "2db1bb06de56", "candidate_sha256": "tree"}]}
            with contextlib.redirect_stdout(out):
                rc = adv._recorded_verdict(root, steps, "t_x", "tree", mint=True, hermes="hermes")
        finally:
            for k, v in saved.items():
                setattr(adv, k, v)
            adv.pipeline.admit, adv._outcome_bridge.active, adv._outcome_bridge.resume_recovered = saved_admit, saved_active, saved_resume
    return rc, calls + ["stdout:" + out.getvalue()]


def main() -> int:
    ok = True

    def check(cond: bool, what: str, detail: object) -> None:
        nonlocal ok
        print(("ok " if cond else "FAIL ") + what + ("" if cond else ": %r" % (detail,)))
        ok = ok and cond

    rc, calls = run_case(board=True, admitted=True, recovered=0)
    check(rc == 0 and "resume_recovered" in calls and "serial-mint" not in calls,
          "outcome board, admitted, recovered commit: the acceptance finishes on the outcome record, no serial mint", (rc, calls))
    rc, calls = run_case(board=True, admitted=True, recovered=None)
    check(rc == 0 and "serial-mint" not in calls,
          "outcome board, nothing recovered: no serial mint (the board holds every successor)", (rc, calls))
    text = calls[-1]
    check("does not accept the outcome" in text and "do not kanban_complete" in text and "ACCEPTED" not in text.replace("ALREADY RECORDED", ""),
          "nothing recovered: idempotent, and says plainly that no acceptance was made", text)
    rc, calls = run_case(board=True, admitted=True, recovered=3)
    check(rc == 3 and "serial-mint" not in calls,
          "outcome board, recovered but the outcome is NOT accepted: the reissue answer passes through, no completion", (rc, calls))
    rc, calls = run_case(board=True, admitted=False, recovered=0)
    check(rc == 1 and "serial-mint" in calls and "resume_recovered" not in calls,
          "outcome board, admission refused: the continuation still refuses with the admission reason", (rc, calls))
    rc, calls = run_case(board=False, admitted=True, recovered=0)
    check(rc == 1 and "serial-mint" in calls and "resume_recovered" not in calls,
          "serial board: the tail continues with the serial mint, unchanged", (rc, calls))
    print("OK: advance recorded verdict on an outcome board" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
