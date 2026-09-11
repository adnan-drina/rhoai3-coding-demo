#!/usr/bin/env python3
"""Operator rewind: put the loop back at an accepted step and start a new epoch.

Why an Operator needs this: an accepted step can turn out to be a false
green once a measurement defect is fixed (pilot v6: an unresolvable pom
measured [11, 1, 0] and was accepted; the fix that made it resolvable
measured the real 829 errors, was reverted, and the cluster was deferred
on a budget three harness bugs had spent). The loop's own record must
survive that: nothing is deleted, the rewind is appended.

What it does, in order (every step refuses before it changes anything):

  * refuses with an open issued card, a dirty product tree, or a target
    that is not a recorded step;
  * restores the product tree to the target step's commit (paths that
    changed after it: checkout, or rm for paths it did not have), then
    RE-MEASURES it with run-verify.sh (--verify-cmd overrides the tool
    for tests) and refuses unless the tuple equals the step's recorded
    measure — restoring the tree if not;
  * commits the restore, snapshots the reports as the accepted state;
  * moves every later accepted step into `rejected` (marked `rewound`),
    marks the existing rejections `rewound`, clears `attempts` and the
    deferral, and appends a `rewinds` entry (operator, reason, from, to);
    the rejected cards stay expected-closed on the board (K3), and the
    new epoch changes the card keys so K4 cannot hand back an old card;
  * rebuilds the work list, re-seals admission and (unless --no-mint)
    mints the next card.

Exit 0 rewound; 1 refused; 2 usage.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import shlex
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _loop_common import ensure_hermes_lib, git, is_product_path, load_deferred, load_issued, load_state, load_steps, product_paths_changed, revert_paths, save_deferred, save_steps, snapshot_reports  # noqa: E402

ensure_hermes_lib()
from planner import pipeline  # noqa: E402
from planner.paths import LOOP_ISSUED  # noqa: E402
from planner.worklist import build_worklist  # noqa: E402

RUN_VERIFY = Path(__file__).resolve().parent / "run-verify.sh"


def _refuse(msg: str) -> int:
    print("REFUSE: LOOP_REWIND %s" % msg, file=sys.stderr)
    return 1


def _changed_since(root: Path, commit: str) -> list[tuple[str, str]]:
    """(status, path) for product paths that differ between the commit and HEAD."""
    proc = git(root, "diff", "--name-status", commit, "HEAD")
    out: list[tuple[str, str]] = []
    for line in proc.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status, path = parts[0][:1], parts[-1]
        if is_product_path(path):
            out.append((status, path))
    return out


def _restore(root: Path, commit: str, changes: list[tuple[str, str]]) -> list[str]:
    """Working tree + index at the commit for the given paths; returns the paths touched."""
    touched: list[str] = []
    for status, path in changes:
        if status == "A":  # did not exist at the target
            git(root, "rm", "-q", "--cached", "--", path)
            target = root / path
            if target.is_file():
                target.unlink()
        else:
            git(root, "checkout", commit, "--", path)
        touched.append(path)
    return touched


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True)
    ap.add_argument("--to-step", type=int, default=None, help="index into verification/loop/steps.json steps (0 = the bootstrap baseline)")
    ap.add_argument("--to-card", default="", help="rewind to the step that card accepted (its commit stays; later steps go); the readable form of --to-step")
    ap.add_argument("--before-card", default="", help="rewind to the step BEFORE the one that card accepted (undo that card's step)")
    ap.add_argument("--operator", required=True, help="who decided (recorded in the rewind entry)")
    ap.add_argument("--reason", required=True)
    ap.add_argument("--verify-cmd", default="", help="command that re-measures the restored tree (default: run-verify.sh --root ROOT; tests pass a simulator)")
    ap.add_argument("--no-mint", action="store_true")
    ap.add_argument("--remeasure", action="store_true", help="the measure definition changed (harness fix): accept the fresh measurement of the target step instead of refusing on a mismatch; before/after are recorded")
    ap.add_argument("--close-card", action="append", default=[], help="a minted card with no verdict (blocked/refused): record it as rewound so the board expects it closed; repeatable")
    ap.add_argument("--hermes", default="hermes")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    steps = load_steps(root)
    recorded = list(steps.get("steps") or [])
    if not recorded:
        return _refuse("no baseline step recorded")
    table = "; ".join("%d=%s%s" % (i, st.get("card") or "baseline", (" %s" % ((st.get("measure") or {}).get("tuple"))) if st.get("measure") else "") for i, st in enumerate(recorded))
    if sum(1 for x in (args.to_step is not None, bool(args.to_card), bool(args.before_card)) if x) != 1:
        return _refuse("give exactly one of --to-step / --to-card / --before-card; steps: %s" % table)
    if args.to_card or args.before_card:
        cid = args.to_card or args.before_card
        idx = next((i for i, st in enumerate(recorded) if str(st.get("card") or "") == cid), -1)
        if idx < 0:
            return _refuse("card %s accepted no recorded step; steps: %s" % (cid, table))
        args.to_step = idx if args.to_card else idx - 1
    if not 0 <= args.to_step < len(recorded):
        return _refuse("--to-step %d is not a recorded step (0..%d); steps: %s" % (args.to_step, len(recorded) - 1, table))
    print("rewind target: step %d = %s; steps: %s" % (args.to_step, recorded[args.to_step].get("card") or "baseline", table))
    issued = load_issued(root)
    iid = str((issued or {}).get("task_id") or (issued or {}).get("card") or "")
    if issued is not None and not (args.close_card and (not iid or iid in args.close_card)):
        return _refuse("an issued card is open (verification/loop/issued.json%s); pass --close-card <id> for it, or let it finish" % ((": " + iid) if iid else ""))
    dirty = product_paths_changed(root)
    if dirty:
        return _refuse("product tree is not clean: %s" % ",".join(dirty[:5]))
    target = recorded[args.to_step]
    commit = str(target.get("commit") or "")
    if not commit or git(root, "cat-file", "-e", "%s^{commit}" % commit).returncode != 0:
        return _refuse("step %d has no reachable commit (%r)" % (args.to_step, commit))
    from_head = git(root, "rev-parse", "HEAD").stdout.strip()
    changes = _changed_since(root, commit)
    touched = _restore(root, commit, changes)

    cmd = shlex.split(args.verify_cmd) if args.verify_cmd else ["bash", str(RUN_VERIFY), "--root", str(root)]
    proc = subprocess.run(cmd, text=True, capture_output=True)
    sys.stdout.write(proc.stdout[-2000:])
    if proc.returncode != 0:
        revert_paths(root, touched)
        return _refuse("re-measure exited %d on the restored tree: %s" % (proc.returncode, proc.stderr.strip()[-400:]))
    state = load_state(root)
    measured = list(((state or {}).get("measure") or {}).get("tuple") or [])
    expected = list(((target.get("measure") or {}).get("tuple")) or [])
    remeasured = None
    if not state or measured != expected:
        if not (args.remeasure and state):
            revert_paths(root, touched)
            return _refuse("restored tree measures %s, step %d recorded %s; nothing changed (--remeasure if the measure definition changed)" % (measured, args.to_step, expected))
        remeasured = {"before": expected, "after": measured}

    if touched:
        git(root, "add", "-A", "--", *touched)
        proc = git(root, "-c", "user.email=fix-until-green@local", "-c", "user.name=fix-until-green", "commit", "-q", "-m",
                   "fix-until-green: rewind to step %d (%s) by %s: %s" % (args.to_step, commit[:12], args.operator, args.reason))
        if proc.returncode != 0:
            return _refuse("commit failed: %s" % proc.stderr.strip()[:200])
    snapshot_reports(root)

    moved = recorded[args.to_step + 1:]
    rejected = list(steps.get("rejected") or [])
    for r in rejected:
        r["rewound"] = True
    known_cards = {str(s.get("card") or "") for s in recorded} | {str(r.get("card") or "") for r in rejected}
    for cid in args.close_card:
        if cid and cid not in known_cards:
            rejected.append({"cluster": str(state.get("head") or ""), "card": cid, "measure": None, "changed": [], "rewound": True,
                             "reason": "closed by operator %s without a verdict: %s" % (args.operator, args.reason)})
    if issued is not None:
        (root / LOOP_ISSUED).unlink()
    if remeasured:
        target = dict(target)
        target["measure"] = dict(state.get("measure") or {})
        target["remeasured"] = remeasured
        recorded[args.to_step] = target
    for st in moved:
        rejected.append({"cluster": st.get("cluster"), "card": st.get("card"), "measure": st.get("measure"), "changed": [], "rewound": True,
                         "reason": "rewound by operator %s: %s" % (args.operator, args.reason)})
    deferred_before = load_deferred(root)
    entry = {
        "at": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "operator": args.operator,
        "reason": args.reason,
        "from_head": from_head,
        "to_step": args.to_step,
        "to_commit": commit,
        "restored_paths": touched,
        "moved_steps": [str(st.get("card") or "") for st in moved],
        "cleared_attempts": dict(steps.get("attempts") or {}),
        "cleared_deferred": list(deferred_before.get("clusters") or []),
        "closed_cards": list(args.close_card),
        "remeasured": remeasured,
    }
    steps["steps"] = recorded[: args.to_step + 1]
    steps["rejected"] = rejected
    steps["attempts"] = {}
    for row in steps.get("pending") or []:
        if isinstance(row, dict) and not row.get("cleared"):
            row["rewound"] = True
    steps.setdefault("rewinds", []).append(entry)
    save_steps(root, steps)
    save_deferred(root, {"schema": "rhoai3.loop-deferred/v1", "clusters": [], "reasons": {}})

    build_worklist(root)
    rec = pipeline.admit(root)
    print("OK: REWOUND to step %d (%s) epoch %d; %d step(s) moved to rejected, attempts cleared %s, deferral cleared %s; admission %s"
          % (args.to_step, commit[:12], len(steps["rewinds"]), len(moved), entry["cleared_attempts"], entry["cleared_deferred"], rec.get("status")))
    if rec.get("status") != "ADMITTED":
        print("REFUSE: LOOP_ADMISSION %s: %s" % (rec["status"], "; ".join(rec.get("reasons") or [])[:300]), file=sys.stderr)
        return 1
    if args.no_mint:
        return 0
    from advance import _mint  # noqa: E402  (the same trusted continuation advance.py uses)

    return _mint(root, args.hermes)


if __name__ == "__main__":
    raise SystemExit(main())
