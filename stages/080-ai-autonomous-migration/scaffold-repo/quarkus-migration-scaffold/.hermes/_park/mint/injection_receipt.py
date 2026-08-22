#!/usr/bin/env python3
"""F2 — stamp an injection/mutation receipt when a gate writes into a body.

Nursing pattern (`--inject` / `--write`) is still allowed at create-time, but
every mutation must leave an auditable receipt: what was written, by which
script, from which source. Agents copying silent body-rewrite have no cover.

Usage (library or CLI):
  python3 injection_receipt.py --root . \\
    --script stamp-body-dependencies.py \\
    --target evidence/bodies/m3-s-002.json \\
    --fields dependencies \\
    --source "import scan of legacy sources via migration.yaml path_rewrites" \\
    --summary "stamped dependencies n=4"

Schema: rhoai3.injection-receipt/v1
Contract: .hermes/skills/sdd/check-spec-readiness/references/body-integrity.md
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


SCHEMA = "rhoai3.injection-receipt/v1"


def write_injection_receipt(
    root: Path,
    *,
    script: str,
    target: str | Path,
    fields: list[str],
    source: str,
    summary: str = "",
    extra: dict | None = None,
) -> Path:
    root = root.resolve()
    target_path = Path(target)
    if not target_path.is_absolute():
        target_path = root / target_path
    try:
        target_rel = str(target_path.relative_to(root))
    except ValueError:
        target_rel = str(target_path)

    story = "unknown"
    if target_path.is_file():
        try:
            raw = json.loads(target_path.read_text(encoding="utf-8"))
            body = raw.get("body") if isinstance(raw.get("body"), dict) else raw
            if isinstance(body, dict):
                ident = body.get("identity") if isinstance(body.get("identity"), dict) else {}
                story = str(ident.get("story_id") or body.get("story_id") or "unknown")
        except Exception:
            pass

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    safe_script = Path(script).stem.replace(" ", "_")
    safe_story = story.replace("/", "_")
    out_dir = root / "evidence" / "receipts" / "injections"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{safe_story}-{safe_script}.json"

    receipt = {
        "schema": SCHEMA,
        "ts": ts,
        "script": script,
        "source": source,
        "target": target_rel,
        "story_id": story,
        "fields_written": list(fields),
        "summary": summary or f"{script} wrote {', '.join(fields)} into {target_rel}",
        "operator_bind": "F2 E-20260814T115900Z",
    }
    if extra:
        receipt["extra"] = extra

    out_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    latest = out_dir / "latest.json"
    latest.write_text(
        json.dumps(
            {
                "schema": "rhoai3.injection-receipt-latest/v1",
                "path": str(out_path.relative_to(root)),
                "ts": ts,
                "story_id": story,
                "script": script,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return out_path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=".")
    ap.add_argument("--script", required=True)
    ap.add_argument("--target", required=True)
    ap.add_argument("--fields", required=True, help="comma-separated field names written")
    ap.add_argument("--source", required=True)
    ap.add_argument("--summary", default="")
    args = ap.parse_args()
    fields = [f.strip() for f in args.fields.split(",") if f.strip()]
    if not fields:
        print("FAIL: --fields empty", file=sys.stderr)
        return 2
    path = write_injection_receipt(
        Path(args.root),
        script=args.script,
        target=args.target,
        fields=fields,
        source=args.source,
        summary=args.summary,
    )
    print(f"OK: injection receipt → {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
