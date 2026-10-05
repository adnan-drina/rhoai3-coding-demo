#!/usr/bin/env python3
"""M5 DEPLOY: observe the app-push PipelineRun for the candidate revision.

Does not start a run unless --start is passed, and --start is refused when a
matching run already exists.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from _cli import dump, ensure_hermes_lib, root_parser

ensure_hermes_lib()
from m5_delivery import load_delivery_contract, observe_pipeline  # noqa: E402
from planner.canonical import load_json  # noqa: E402
from planner.paths import DELIVERY_CANDIDATE  # noqa: E402


def _oc_json(argv: list[str]) -> dict:
    proc = subprocess.run(argv, text=True, capture_output=True)
    if proc.returncode != 0:
        raise SystemExit("FAIL: %s: %s" % (" ".join(argv), (proc.stderr or proc.stdout)[:400]))
    return json.loads(proc.stdout)


def main(argv: list[str] | None = None) -> int:
    ap = root_parser(__doc__)
    ap.add_argument("--namespace", default="")
    ap.add_argument("--start", action="store_true", help="refused when a matching run already exists")
    args = ap.parse_args(argv)
    root = args.root.resolve()
    contract = load_delivery_contract(root)
    cand = load_json(root / DELIVERY_CANDIDATE) if (root / DELIVERY_CANDIDATE).is_file() else {}
    ns = args.namespace or contract.get("namespace") or "%s-dev" % (contract.get("repo") or cand.get("contract", {}).get("repo") or "")
    if not ns or ns == "-dev":
        print("BLOCKED M5 DEPLOY: pipeline namespace missing (set delivery.yaml namespace)", file=sys.stderr)
        return 2
    items = _oc_json(["oc", "-n", ns, "get", "pipelinerun", "-l", "tekton.dev/pipeline=app-push", "-o", "json"])
    runs = list(items.get("items") or [])
    if not runs:
        items = _oc_json(["oc", "-n", ns, "get", "pipelinerun", "-o", "json"])
        runs = [r for r in (items.get("items") or []) if str(((r.get("metadata") or {}).get("labels") or {}).get("tekton.dev/pipeline") or r.get("pipeline") or "") in {"app-push", ""} or True]
    for run in runs:
        name = str(((run.get("metadata") or {}).get("name") or ""))
        if not name:
            continue
        try:
            trs = _oc_json(["oc", "-n", ns, "get", "taskrun", "-l", "tekton.dev/pipelineRun=%s" % name, "-o", "json"])
        except SystemExit:
            continue
        merged: list = []
        for tr in (trs.get("items") or []):
            st = tr.get("status") if isinstance(tr.get("status"), dict) else {}
            for row in (st.get("results") or st.get("taskResults") or []):
                if isinstance(row, dict):
                    merged.append(row)
        if merged:
            st = run.setdefault("status", {})
            st["pipelineResults"] = list(st.get("pipelineResults") or []) + merged
    doc = observe_pipeline(root, runs, start_requested=args.start)
    dump(doc)
    if not doc.get("ok"):
        print("BLOCKED M5 DEPLOY: %s %s" % (doc.get("reason"), doc.get("detail")), file=sys.stderr)
        return 2
    print("OK: PipelineRun %s revision %s digest %s" % (doc.get("pipeline_run"), doc.get("revision"), doc.get("image_digest")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
