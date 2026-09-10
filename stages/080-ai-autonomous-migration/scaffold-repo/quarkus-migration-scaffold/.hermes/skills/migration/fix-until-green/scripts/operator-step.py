#!/usr/bin/env python3
"""Operator step: record a decided change to the product tree as a loop step.

Some changes are decisions, not card work: an ADR accepted after M2 retires
source files (bootstrap-destination.py --retire-only deletes them). The loop
record must carry that change like any accepted step, or the next card's
baseline is wrong (its measure and obligation keys describe a tree that no
longer exists) and a rewind would restore the retired files.

What it does (every check refuses before it changes anything):
  * refuses with an issued card open (close it: rewind.py --close-card, or
    let it finish) or with nothing changed in the product tree;
  * commits exactly the changed product paths with the operator and reason;
  * RE-MEASURES the tree (run-verify.sh; --verify-cmd overrides for tests);
  * appends a step {verdict: operator, adr, operator, reason, commit,
    measure, obligation_keys} to verification/loop/steps.json, snapshots the
    reports as the accepted state, rebuilds the work list, re-seals
    admission and (unless --no-mint) mints the next card.

Exit 0 recorded; 1 refused; 2 usage.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import shlex
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _loop_common import ensure_hermes_lib, git, load_issued, load_state, load_steps, product_paths_changed, save_steps, snapshot_reports  # noqa: E402

ensure_hermes_lib()
from planner import pipeline  # noqa: E402
from planner.canonical import load_json  # noqa: E402
from planner.paths import WORKLIST  # noqa: E402
from planner.worklist import build_worklist, obligation_keys  # noqa: E402

RUN_VERIFY = Path(__file__).resolve().parent / "run-verify.sh"


def _refuse(msg: str) -> int:
    print("REFUSE: LOOP_OPERATOR_STEP %s" % msg, file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True)
    ap.add_argument("--operator", required=True)
    ap.add_argument("--reason", required=True)
    ap.add_argument("--adr", default="", help="the accepted ADR(s) this change applies, e.g. ADR-004,ADR-005")
    ap.add_argument("--verify-cmd", default="")
    ap.add_argument("--no-mint", action="store_true")
    ap.add_argument("--hermes", default="hermes")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    steps = load_steps(root)
    if not steps.get("steps"):
        return _refuse("no baseline step recorded")
    if load_issued(root) is not None:
        return _refuse("an issued card is open (verification/loop/issued.json); close it before recording an operator step")
    changed = product_paths_changed(root)
    if not changed:
        return _refuse("nothing changed in the product tree")
    git(root, "reset", "-q")
    git(root, "add", "-A", "--", *changed)
    msg = "fix-until-green: operator step by %s%s: %s" % (args.operator, (" (%s)" % args.adr) if args.adr else "", args.reason)
    proc = git(root, "-c", "user.email=fix-until-green@local", "-c", "user.name=fix-until-green", "commit", "-q", "-m", msg)
    if proc.returncode != 0:
        return _refuse("commit failed: %s" % proc.stderr.strip()[:200])
    sha = git(root, "rev-parse", "HEAD").stdout.strip()
    cmd = shlex.split(args.verify_cmd) if args.verify_cmd else ["bash", str(RUN_VERIFY), "--root", str(root)]
    run = subprocess.run(cmd, text=True, capture_output=True)
    sys.stdout.write(run.stdout[-2000:])
    if run.returncode != 0:
        return _refuse("re-measure exited %d after the commit %s (the commit stands; fix the tool and re-run run-verify.sh): %s" % (run.returncode, sha[:12], run.stderr.strip()[-300:]))
    state = load_state(root)
    if not state or not (state.get("measure") or {}).get("known"):
        return _refuse("measure not known after the commit %s: %s" % (sha[:12], (state or {}).get("measure")))
    cur = load_json(root / WORKLIST)
    snapshot_reports(root)
    steps["steps"].append({
        "cluster": "operator", "card": "", "attempt": 0, "verdict": "operator",
        "operator": args.operator, "adr": args.adr, "reason": args.reason,
        "at": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "commit": sha, "candidate_sha256": str(state.get("candidate_sha256") or ""),
        "measure": state["measure"], "obligation_keys": sorted(obligation_keys(cur)), "changed": changed,
    })
    save_steps(root, steps)
    build_worklist(root)
    rec = pipeline.admit(root)
    print("OK: OPERATOR STEP %s (%d path(s), measure %s) admission %s" % (sha[:12], len(changed), state["measure"]["tuple"], rec.get("status")))
    if rec.get("status") != "ADMITTED":
        print("REFUSE: LOOP_ADMISSION %s: %s" % (rec["status"], "; ".join(rec.get("reasons") or [])[:300]), file=sys.stderr)
        return 1
    if args.no_mint:
        return 0
    from advance import _mint  # noqa: E402

    return _mint(root, args.hermes)


if __name__ == "__main__":
    raise SystemExit(main())
