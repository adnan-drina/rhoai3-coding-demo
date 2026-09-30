#!/usr/bin/env python3
"""Apply the catalog's typed repair to THIS card's issued unit (V26-1).

    python3 .hermes/skills/migration/fix-until-green/scripts/typed-repair.py --root . --cluster <id>

brief.py prints this as the unit's FIRST ACTION when a `typed-repair` recipe
(compat-mapping migration_recipes) applies to the issued unit. It plans the
executor requests from the sealed scope and the requirements the card owns,
runs the pinned harness executor (OpenRewrite LST, our own recipes) against the
current candidate, inspects the complete staged diff against the issued write
set, applies it whole or not at all, and records every attempt under
verification/loop/typed-repair/. It never widens the write set, never runs
run-verify.sh or advance.py, never completes, blocks or retries a card, and
grants no attempt. After it: run-verify.sh --mode acceptance, then advance.py.
An unresolved result sends the unit back to the bounded agent repair with the
reason (brief.py shows it).

--plan prints the requests without running anything. Exit 0 whenever records
were written (the outcome is in them); 1 when the card or cluster cannot be
identified.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _typed_repair as TR  # noqa: E402
from brief import issued_ownership, select_cluster  # noqa: E402
from planner.canonical import load_json  # noqa: E402
from planner.paths import WORKLIST  # noqa: E402


def unit(root: Path, cluster_arg: str) -> tuple[dict | None, dict | None, str]:
    doc = load_json(root / WORKLIST) if (root / WORKLIST).is_file() else {"clusters": []}
    cluster, code, detail = select_cluster(doc, root, cluster_arg, os.environ.get("HERMES_KANBAN_TASK") or "")
    if cluster is None:
        return None, None, "%s %s" % (code, detail)
    ref = cluster.get("batch_scope") or {}
    scope = None
    if ref.get("path") and (root / str(ref["path"])).is_file():
        scope = load_json(root / str(ref["path"]))
    return cluster, scope, ""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True)
    ap.add_argument("--cluster", default="")
    ap.add_argument("--plan", action="store_true", help="print the planned requests; run nothing")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    rec = TR.recover(root)
    if rec:
        print("RECOVERED: %s (restored %s)" % (rec["detail"], ", ".join(rec["restored"]) or "nothing"))
    cluster, scope, err = unit(root, args.cluster)
    if cluster is None:
        print("REFUSE: %s" % err, file=sys.stderr)
        return 1
    write_set = [str(w) for w in cluster.get("write_set") or []]
    reqs = TR.owned_requirements(root, write_set, issued_ownership(root))
    requests, skipped = TR.plan(root, scope, write_set, reqs)
    if args.plan:
        print(json.dumps({"cluster": cluster["id"], "requests": requests, "skipped": skipped}, indent=2, sort_keys=True))
        return 0
    for s in skipped:
        print("NOT REQUESTED (%s): %s" % (s["recipe"], s["reason"]))
    if not requests:
        print("NOT APPLICABLE: no typed repair applies to %s; continue with the brief's documented actions" % cluster["id"])
        return 0
    for r in TR.execute(root, str(cluster["id"]), requests, write_set):
        line = "%s %s: %s" % (r["recipe"]["id"], r["outcome"].upper(), "; ".join(r["reasons"])[:700] or "-")
        print(line)
        if r["outcome"] == "applied":
            print("  changed: %s" % ", ".join(r["changed_files"]))
    print("NEXT: bash .hermes/skills/migration/fix-until-green/scripts/run-verify.sh --root . --mode acceptance, then "
          "advance.py --root . --cluster %s --card \"$HERMES_KANBAN_TASK\". An UNRESOLVED or FAILED line above is the "
          "bounded agent repair's to finish (brief.py shows the reason and the required shape)." % cluster["id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
