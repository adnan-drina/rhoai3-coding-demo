#!/usr/bin/env python3
"""Stamp destination-inventory receipt + body ref (Operator E-20260811T144200Z).

Writes evidence/receipts/destination-inventory/<story_id>.json with
paths + sha256 digests for each files_writable destination path. Digests prefer
existing modernized content; if missing, hash the legacy referent (baseline).

Attaches refs[] entry key=destination_inventory (path + sha256).

Usage:
  python3 stamp-destination-inventory.py /projects/modernized \
    --body evidence/bodies/m3-s-002a.json --write
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_json(path: Path):
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def norm_rel(path: str) -> str:
    p = path.replace("\\", "/")
    for prefix in (
        "/projects/.derived/legacy-at-3/",
        "/projects/modernized/",
        "/projects/legacy/",
    ):
        if p.startswith(prefix):
            p = p[len(prefix) :]
    return p.lstrip("./")


def writable_dests(body: dict) -> list[str]:
    out: list[str] = []
    for item in body.get("files_writable") or body.get("write_set") or []:
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict):
            for k in ("dest", "dst", "destination", "path", "file"):
                if item.get(k):
                    out.append(str(item[k]))
                    break
    # Prefer modernized absolute forms
    dests: list[str] = []
    for p in out:
        if "/.derived/legacy" in p or "/legacy/" in p:
            rel = norm_rel(p)
            dests.append(f"/projects/modernized/{rel}")
        elif p.startswith("/projects/modernized/"):
            dests.append(p)
        else:
            dests.append(f"/projects/modernized/{norm_rel(p)}")
    # stable unique
    seen: set[str] = set()
    uniq: list[str] = []
    for d in dests:
        if d not in seen:
            seen.add(d)
            uniq.append(d)
    return uniq


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--body", required=True)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    body_path = Path(args.body)
    if not body_path.is_absolute():
        body_path = root / body_path
    body = load_json(body_path)
    if not isinstance(body, dict):
        print(f"FAIL: bad body {body_path}", file=sys.stderr)
        return 1
    ident = body.get("identity") if isinstance(body.get("identity"), dict) else {}
    sid = str(ident.get("story_id") or body.get("story_id") or "unknown").strip()
    legacy_root = Path("/projects/.derived/legacy-at-3")
    if not legacy_root.is_dir():
        alt = root.parent / ".derived" / "legacy-at-3"
        if alt.is_dir():
            legacy_root = alt

    entries = []
    for dest in writable_dests(body):
        rel = norm_rel(dest)
        dest_p = Path(dest) if dest.startswith("/") else root / rel
        legacy_p = legacy_root / rel
        source = "modernized" if dest_p.is_file() else None
        if source is None and legacy_p.is_file():
            source = "legacy_baseline"
            digest = sha256_file(legacy_p)
            exists = False
        elif dest_p.is_file():
            digest = sha256_file(dest_p)
            exists = True
        else:
            digest = sha256_bytes(b"")
            exists = False
            source = "missing"
        entries.append(
            {
                "path": f"/projects/modernized/{rel}",
                "rel": rel,
                "sha256": digest,
                "exists": exists,
                "source": source,
            }
        )

    receipt = {
        "schema": "rhoai3.destination-inventory/v1",
        "story_id": sid,
        "checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "body": str(body_path),
        "entries": entries,
        "operator_bind": "E-20260811T144200Z",
    }
    out_rel = f"evidence/receipts/destination-inventory/{sid}.json"
    out_path = root / out_rel
    receipt_json = json.dumps(receipt, indent=2) + "\n"
    receipt_digest = sha256_bytes(receipt_json.encode("utf-8"))

    refs = body.get("refs")
    if not isinstance(refs, list):
        refs = []
    refs = [r for r in refs if not (isinstance(r, dict) and r.get("key") == "destination_inventory")]
    refs.append(
        {
            "key": "destination_inventory",
            "path": out_rel,
            "sha256": receipt_digest,
        }
    )
    body["refs"] = refs

    if args.write:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        # Write receipt with digest of content excluding self-hash loop:
        # digest is of the receipt as written below (without embedding digest).
        out_path.write_text(receipt_json, encoding="utf-8")
        # Recompute digest of on-disk bytes and refresh body ref
        receipt_digest = sha256_file(out_path)
        for r in body["refs"]:
            if isinstance(r, dict) and r.get("key") == "destination_inventory":
                r["sha256"] = receipt_digest
        body_path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
        print(f"OK: destination-inventory entries={len(entries)} → {out_path}")
        print(f"OK: body ref destination_inventory sha256={receipt_digest}")
    else:
        print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
