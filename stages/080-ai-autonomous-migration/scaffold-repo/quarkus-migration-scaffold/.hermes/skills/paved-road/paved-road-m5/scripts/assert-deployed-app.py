#!/usr/bin/env python3
"""M5-B: require a ready Deployment, Service endpoints, and HTTPS Route."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from _cli import dump, ensure_hermes_lib, root_parser

ensure_hermes_lib()
from m5_delivery import assert_deployed, load_delivery_contract  # noqa: E402
from planner.canonical import load_json  # noqa: E402
from planner.paths import DELIVERY_CANDIDATE  # noqa: E402


def _get(ns: str, kind: str, name: str) -> dict:
    proc = subprocess.run(["oc", "-n", ns, "get", kind, name, "-o", "json"], text=True, capture_output=True)
    if proc.returncode != 0:
        return {}
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {}


def main(argv: list[str] | None = None) -> int:
    ap = root_parser(__doc__)
    ap.add_argument("--namespace", default="")
    ap.add_argument("--name", default="")
    args = ap.parse_args(argv)
    root = args.root.resolve()
    contract = load_delivery_contract(root)
    cand = load_json(root / DELIVERY_CANDIDATE) if (root / DELIVERY_CANDIDATE).is_file() else {}
    name = args.name or contract.get("name") or contract.get("repo") or (cand.get("contract") or {}).get("repo") or ""
    ns = args.namespace or contract.get("namespace") or ("%s-dev" % name if name else "")
    if not name or not ns:
        print("BLOCKED M5-B: application name/namespace missing (delivery.yaml)", file=sys.stderr)
        return 2
    doc = assert_deployed(
        root,
        deployment=_get(ns, "deployment", name),
        service=_get(ns, "service", name),
        route=_get(ns, "route", name),
        endpoints=_get(ns, "endpoints", name),
    )
    dump(doc)
    if not doc.get("ok"):
        print("BLOCKED M5-B: %s" % ", ".join(doc.get("issues") or []), file=sys.stderr)
        return 2
    print("OK: deployed %s at %s" % (doc.get("deployed_image"), doc.get("route_url")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
