#!/usr/bin/env python3
"""O-CHARPROTECT — characterization tips must pin converted code, not legacy FS text.

Reads tip paths from stdin (git show --name-only --pretty= format or
git diff --cached --name-only). For each *Characterization*Test.java /
*CharacterizationTest.java:
  - Refuse if the test only reads /projects/legacy (or legacyPackage path)
    source text without importing/using the target package types.

Exit 0 = ok; exit 1 = refuse.
Optional argv[1] = migration.yaml (else ./migration.yaml) for packages.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Optional, Tuple


def _pkgs(myaml: Path) -> Optional[Tuple[str, str]]:
    """Read packages from migration.yaml — never fail-open to specimen defaults
    (O-NOSPECIMEN / coolstore-lint; W4-292)."""
    if not myaml.is_file():
        return None
    text = myaml.read_text(encoding="utf-8", errors="replace")
    lm = re.search(r"legacyPackage:\s*([\w.]+)", text)
    tm = re.search(r"targetPackage:\s*([\w.]+)", text)
    if not lm or not tm:
        return None
    return lm.group(1), tm.group(1)


def _is_char_test(path: str) -> bool:
    name = Path(path).name
    return bool(
        re.search(r"Characterization.*Test\.java$|CharacterizationTest\.java$", name)
    ) or (
        path.startswith("src/test/")
        and "characterization" in name.lower()
        and name.endswith("Test.java")
    )


def _pins_legacy_only(text: str, legacy: str, target: str) -> bool:
    legacy_fs = bool(
        re.search(
            r"/projects/legacy\b|Files\.readString\s*\(|"
            + re.escape(legacy.replace(".", "/")),
            text,
        )
    )
    if not legacy_fs:
        return False
    # Converted pin: import/Class.forName under target — ignore `package …`
    # (char tests often live under targetPackage and would false-GREEN).
    body = re.sub(r"(?m)^\s*package\s+[\w.]+\s*;\s*", "", text)
    tgt = re.escape(target)
    uses_target = bool(
        re.search(rf"\bimport\s+{tgt}\b", body)
        or re.search(rf'Class\.forName\s*\(\s*"{tgt}\.', body)
        or re.search(rf"\b{tgt}\.[A-Z][A-Za-z0-9_]*\b", body)
    )
    return not uses_target


def main() -> int:
    myaml = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("migration.yaml")
    pkgs = _pkgs(myaml)
    if pkgs is None:
        # Fail closed without specimen package literals (O-NOSPECIMEN).
        print(
            "O-CHARPROTECT:cannot-infer-packages "
            "(set legacyPackage/targetPackage in migration.yaml)"
        )
        return 1
    legacy, target = pkgs
    paths = [ln.strip() for ln in sys.stdin if ln.strip().endswith(".java")]
    bad: list[str] = []
    for p in paths:
        if not _is_char_test(p):
            continue
        fp = Path(p)
        if not fp.is_file():
            continue
        text = fp.read_text(encoding="utf-8", errors="replace")
        if _pins_legacy_only(text, legacy, target):
            bad.append(p)
    if bad:
        print("O-CHARPROTECT:" + ",".join(bad[:8]))
        return 1
    print("char-protect:ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
