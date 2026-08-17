#!/usr/bin/env python3
"""Z3-a / A-6 — refuse a provisioned seat whose migration.yaml lacks package stamp.

Golden tip ships empty `legacyRepoUrl` + empty package fields (specimen-agnostic).
That state is **idle**: this assert exits 0.

Once `legacyRepoUrl` is non-empty (RHDH app-migration stamp / per-run seat),
at least one of `legacyBasePackage` / `legacyPackage` must be non-empty.
Otherwise stamp-body-dependencies starves → DEPENDENCY_STAMP_VACUOUS at M2
(Deputy E-20260814T135138Z — A-6 root cause was provisioning, not the stamper).

Usage:
  python3 assert-migration-yaml-stamp.py [ROOT]
"""
from __future__ import annotations

import sys
from pathlib import Path

# Local import (same package dir)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from specimen_agnostic import load_migration_yaml  # noqa: E402


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    path = root / "migration.yaml"
    if not path.is_file():
        print(f"FAIL: missing {path}", file=sys.stderr)
        return 1
    doc = load_migration_yaml(root)
    mig = doc.get("migration") if isinstance(doc, dict) else {}
    if not isinstance(mig, dict):
        mig = {}
    url = str(mig.get("legacyRepoUrl") or "").strip()
    pkg = str(
        mig.get("legacyBasePackage")
        or mig.get("legacy_base_package")
        or mig.get("legacyPackage")
        or ""
    ).strip()
    if not url:
        print("OK: migration.yaml stamp idle (empty legacyRepoUrl — golden tip)")
        return 0
    if not pkg:
        print(
            "FAIL: MIGRATION_YAML_STAMP_VACUOUS — legacyRepoUrl is set but "
            "legacyBasePackage/legacyPackage is empty (A-6 / Z3-a). "
            "RHDH app-migration skeleton must stamp the package before M2.",
            file=sys.stderr,
        )
        return 1
    print(f"OK: migration.yaml stamp present (legacy package={pkg})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
