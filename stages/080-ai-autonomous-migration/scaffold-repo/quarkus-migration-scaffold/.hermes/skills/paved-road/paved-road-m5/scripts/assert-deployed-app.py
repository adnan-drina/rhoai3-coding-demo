#!/usr/bin/env python3
"""M5 DEPLOY: require a ready Deployment, Service endpoints, and HTTPS Route."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from _cli import dump, ensure_hermes_lib, root_parser

ensure_hermes_lib()
from m5_delivery import assert_deployed, deployment_from_app_pods, load_delivery_contract  # noqa: E402
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
        print("BLOCKED M5 DEPLOY: application name/namespace missing (delivery.yaml)", file=sys.stderr)
        return 2
    deployment = _get(ns, "deployment", name)
    proc = subprocess.run(["oc", "-n", ns, "get", "pods", "-o", "json"], text=True, capture_output=True)
    pods = []
    if proc.returncode == 0:
        try:
            pods = list((json.loads(proc.stdout) or {}).get("items") or [])
        except json.JSONDecodeError:
            pods = []
    if not deployment:
        deployment = deployment_from_app_pods(pods, name)
    service = _get(ns, "service", name)
    endpoints = _get(ns, "endpoints", name)
    route = _get(ns, "route", name)
    if not service and deployment:
        service = {"metadata": {"name": name, "note": "inferred-from-ready-pods"}}
    if not endpoints:
        addrs = []
        for pod in pods:
            status = pod.get("status") if isinstance(pod.get("status"), dict) else {}
            cs = status.get("containerStatuses") or []
            if name not in [str(c.get("name") or "") for c in cs if isinstance(c, dict)]:
                continue
            if any(isinstance(c, dict) and c.get("ready") and str(c.get("name") or "") == name for c in cs):
                ip = str(status.get("podIP") or "")
                if ip:
                    addrs.append({"ip": ip})
        if addrs:
            endpoints = {"subsets": [{"addresses": addrs}]}
    doc = assert_deployed(
        root,
        deployment=deployment,
        service=service,
        route=route,
        endpoints=endpoints,
    )
    dump(doc)
    if not doc.get("ok"):
        print("BLOCKED M5 DEPLOY: %s" % ", ".join(doc.get("issues") or []), file=sys.stderr)
        return 2
    print("OK: deployed %s at %s" % (doc.get("deployed_image"), doc.get("route_url")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
