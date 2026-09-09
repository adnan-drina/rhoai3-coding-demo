#!/usr/bin/env python3
"""Capture expected runtime behaviour from the running SOURCE system.

Writes verification/source-oracles/<slug>.json per admitted entry point.
HTTP GET/HEAD are requested mechanically; other HTTP methods need
--request-file <id>=<file>; non-HTTP kinds need --observation <id>=<file>.
Anything not captured is recorded UNCAPTURED (never invented).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _oracle_common import IDEMPOTENT, ORACLES, entry_points, http_observe, normalize_observation, slug  # noqa: E402
from planner.admission import verify_receipt  # noqa: E402
from planner.canonical import sha256_file, write_canonical  # noqa: E402


def _pairs(items: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for it in items:
        if "=" in it:
            k, v = it.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True)
    ap.add_argument("--base-url", default="")
    ap.add_argument("--entry-point", action="append", default=[])
    ap.add_argument("--observation", action="append", default=[], help="<entry point id>=<captured file>")
    ap.add_argument("--request-file", action="append", default=[], help="<entry point id>=<recorded request body file>")
    ap.add_argument("--any-status", action="store_true", help="allow a non-ADMITTED receipt (capture may precede admission)")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    receipt, gaps = verify_receipt(root, require_admitted=not args.any_status)
    if gaps or receipt is None:
        for g in gaps:
            print("  - " + g, file=sys.stderr)
        print("REFUSE: ORACLES receipt not authoritative", file=sys.stderr)
        return 1
    obs = _pairs(args.observation)
    reqs = _pairs(args.request_file)
    eps = entry_points(root)
    if args.entry_point:
        eps = [e for e in eps if e["id"] in set(args.entry_point)]
    if not eps:
        print("REFUSE: ORACLES no entry points selected", file=sys.stderr)
        return 1
    captured = 0
    for ep in eps:
        rec = {"schema": "rhoai3.source-oracle/v1", "entry_point": ep["id"], "kind": ep["kind"], "receipt_sha256": receipt["receipt_digest"], "status": "UNCAPTURED", "reason": "", "oracle": {}}
        if ep["kind"] == "http":
            method = ep.get("http_method") or "GET"
            path = ep.get("http_path") or "/"
            if not args.base_url:
                rec["reason"] = "no --base-url"
            elif method in IDEMPOTENT:
                o = http_observe(args.base_url, method, path)
                rec["oracle"] = {"method": method, "path": path, **o}
                rec["status"] = "CAPTURED" if o.get("status") else "UNCAPTURED"
                rec["reason"] = o.get("error", "")
            elif ep["id"] in reqs and Path(reqs[ep["id"]]).is_file():
                body = Path(reqs[ep["id"]]).read_bytes()
                o = http_observe(args.base_url, method, path, body=body)
                rec["oracle"] = {"method": method, "path": path, "request_sha256": sha256_file(Path(reqs[ep["id"]])), **o}
                rec["status"] = "CAPTURED" if o.get("status") else "UNCAPTURED"
            else:
                rec["status"] = "INCONCLUSIVE"
                rec["reason"] = "non-idempotent %s needs --request-file with a recorded request body" % method
        else:
            f = obs.get(ep["id"])
            if f and Path(f).is_file():
                sha, n = normalize_observation(Path(f))
                rec["oracle"] = {"observation_sha256": sha, "lines": n, "source_file_sha256": sha256_file(Path(f))}
                rec["status"] = "CAPTURED"
            else:
                rec["reason"] = "%s entry point needs --observation <id>=<file> captured from the source system" % ep["kind"]
        if rec["status"] == "CAPTURED":
            captured += 1
        write_canonical(root / ORACLES / (slug(ep["id"]) + ".json"), rec)
    print("OK: oracles captured=%d of %d → %s" % (captured, len(eps), ORACLES))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
