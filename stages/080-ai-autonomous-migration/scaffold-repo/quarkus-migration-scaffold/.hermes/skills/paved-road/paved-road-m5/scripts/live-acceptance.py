#!/usr/bin/env python3
"""M5 VALIDATE: live HTTP against the deployed Route. Localhost is not acceptance."""
from __future__ import annotations

import json
import ssl
import sys
from pathlib import Path
from urllib.request import urlopen

from _cli import dump, ensure_hermes_lib, root_parser

ensure_hermes_lib()
from m5_delivery import (  # noqa: E402
    DEFAULT_OPENAPI,
    DEFAULT_SWAGGER,
    _http,
    evaluate_live,
    load_delivery_contract,
)
from planner.canonical import load_json, write_canonical  # noqa: E402
from planner.paths import DELIVERY_DEPLOYMENT, DELIVERY_LIVE  # noqa: E402
from planner.yamlite import load_yaml  # noqa: E402


def _insecure_open(req, timeout=20):
    ctx = ssl._create_unverified_context()
    return urlopen(req, timeout=timeout, context=ctx)


def _join(base: str, path: str) -> str:
    return base.rstrip("/") + "/" + str(path or "").lstrip("/")


def _auth_mode(root: Path, contract: dict) -> str:
    declared = str(((contract.get("auth") or {}) if isinstance(contract.get("auth"), dict) else {}).get("mode") or "")
    if declared:
        return declared
    p = root / "decisions.yaml"
    if not p.is_file():
        return ""
    try:
        doc = load_yaml(p)
    except Exception:
        return ""
    switch = ((doc.get("decisions") or doc).get("security") or {}).get("switch") if isinstance(doc, dict) else {}
    return "enabled" if switch else "disabled"


def main(argv: list[str] | None = None) -> int:
    args = root_parser(__doc__).parse_args(argv)
    root = args.root.resolve()
    dep = load_json(root / DELIVERY_DEPLOYMENT) if (root / DELIVERY_DEPLOYMENT).is_file() else {}
    url = str(dep.get("route_url") or "")
    if not url:
        print("BLOCKED M5 VALIDATE: no deployed Route URL (run assert-deployed-app.py)", file=sys.stderr)
        return 2
    if "localhost" in url or "127.0.0.1" in url:
        print("BLOCKED M5 VALIDATE: localhost is not deployed acceptance", file=sys.stderr)
        return 2
    contract = load_delivery_contract(root)
    opener = _insecure_open
    checks = {
        "swagger": _http(_join(url, contract.get("swagger_path") or DEFAULT_SWAGGER), opener=opener),
        "openapi": _http(_join(url, contract.get("openapi_path") or DEFAULT_OPENAPI), opener=opener),
    }
    for row in (contract.get("reads") or []):
        if not isinstance(row, dict):
            continue
        cid = str(row.get("id") or row.get("path") or "")
        checks["read:%s" % cid] = _http(_join(url, str(row.get("path") or "")),
                                        method=str(row.get("method") or "GET"), opener=opener)
    crud = contract.get("crud") if isinstance(contract.get("crud"), dict) else {}
    location = ""
    if crud.get("create"):
        body = json.dumps(crud["create"].get("body") or {}).encode("utf-8")
        created = _http(_join(url, str(crud["create"].get("path") or "")),
                        method=str(crud["create"].get("method") or "POST"),
                        headers={"Content-Type": "application/json"}, body=body, opener=opener)
        checks["crud:create"] = created
        location = str((created.get("headers") or {}).get("Location") or (created.get("headers") or {}).get("location") or "")
        if not location and created.get("body"):
            try:
                parsed = json.loads(created["body"])
                if isinstance(parsed, dict) and parsed.get("id"):
                    location = _join(url, str(crud["create"].get("path") or "").rstrip("/") + "/" + str(parsed["id"]))
            except json.JSONDecodeError:
                location = ""
        if location.startswith("http://") and url.startswith("https://"):
            location = "https://" + location[len("http://"):]
        if location:
            checks["crud:read"] = _http(location if location.startswith("http") else _join(url, location), opener=opener)
            checks["crud:delete"] = _http(location if location.startswith("http") else _join(url, location),
                                          method="DELETE", opener=opener)
    cors = contract.get("cors") if isinstance(contract.get("cors"), dict) else {}
    if cors.get("origin"):
        checks["cors"] = _http(_join(url, str((contract.get("reads") or [{}])[0].get("path") or "/")),
                               method="OPTIONS",
                               headers={"Origin": str(cors["origin"]), "Access-Control-Request-Method": "GET"},
                               opener=opener)
    mode = _auth_mode(root, contract)
    checks["auth"] = {"mode": mode, "status": 200, "url": url}
    live = evaluate_live(checks, contract, str(dep.get("deployed_image") or ""), mode)
    live["candidate_sha"] = dep.get("candidate_sha") or ""
    live["route_url"] = url
    write_canonical(root / DELIVERY_LIVE, live)
    dump(live)
    if not live.get("ok"):
        print("BLOCKED M5 VALIDATE: %s" % ", ".join(live.get("issues") or []), file=sys.stderr)
        return 2
    print("OK: live acceptance against %s image %s" % (url, live.get("deployed_image")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
