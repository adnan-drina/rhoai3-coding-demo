#!/usr/bin/env python3
"""W2 §11.1 — dedicated persisted-data checks (external review finding 8).

Requires two explicit check records when a specimen claims pre-existing DB:
  1) schema_compat — referent-anchored schema compatibility
  2) quarkus_db_copy_read_all — Quarkus boot against DB copy reading mapped entities

Seeded-fixture runs without these records must NOT claim §11.1 DEMONSTRATED.
Idle (exit 0) when no `migration/persisted-data/claim.json` with
`pre_existing_db=true`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    claim_path = root / "migration" / "persisted-data" / "claim.json"
    if not claim_path.is_file():
        print("OK: no persisted-data claim — §11.1 dedicated checks idle")
        return 0
    claim = json.loads(claim_path.read_text(encoding="utf-8"))
    if claim.get("pre_existing_db") not in (True, "true", "yes", 1):
        print("OK: persisted-data claim without pre_existing_db — idle")
        return 0

    checks_dir = root / "migration" / "persisted-data" / "checks"
    needed = {"schema_compat", "quarkus_db_copy_read_all"}
    found: set[str] = set()
    if checks_dir.is_dir():
        for path in checks_dir.glob("*.json"):
            try:
                obj = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            kind = str(obj.get("kind") or path.stem)
            result = str(obj.get("result") or "").lower()
            if kind in needed and result in {"pass", "ok", "green"}:
                found.add(kind)

    missing = sorted(needed - found)
    if missing:
        print(
            f"FAIL: pre_existing_db claim without dedicated pass records: "
            f"{missing} (W2 §11.1 / finding 8 — G-4 incidental ≠ enforcement)",
            file=sys.stderr,
        )
        return 1
    print("OK: persisted-data dedicated checks present (schema_compat + db_copy_read_all)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
