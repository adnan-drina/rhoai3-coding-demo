#!/usr/bin/env python3
"""O-M1SKIPPROV — provenance stamp for M1 ANALYZE / PROFILE skip gates.

Existence of M1 artifacts alone must not skip re-derivation after an abort
wipe that kept carry-over files. Skip only when a stamp matches the current
legacy HEAD plus digests of the claimed artifacts (and PROFILE rubric green
is checked by the caller).

Subcommands:
  write-analyze [--root DIR] [--legacy DIR]
  check-analyze [--root DIR] [--legacy DIR]
  write-profile [--root DIR] [--legacy DIR]
  check-profile [--root DIR] [--legacy DIR]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ANALYZE_STAMP = "migration/.m1-analyze.stamp.json"
PROFILE_STAMP = "migration/.m1-profile.stamp.json"
ANALYZE_FILES = (
    "migration/mta-findings.json",
    "migration/findings-inventory.md",
    "migration/dependency-order.md",
    "migration/recipe-log.md",
    # O-RULESETLOG: coverage file must match findings; missing → no skip.
    "migration/ruleset-coverage.md",
)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _legacy_head(legacy: Path) -> str:
    try:
        out = subprocess.check_output(
            ["git", "-C", str(legacy), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return out.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "missing"


def _staging_java_count(root: Path) -> int:
    staging = root / "migration" / "staging"
    if not staging.is_dir():
        return 0
    return sum(1 for _ in staging.rglob("*.java"))


def _analysis_targets(root: Path) -> list[str]:
    """O-RULESETLOG / O-OPENJDK21TARGET: target list changes invalidate skip."""
    import re

    yml = root / "migration.yaml"
    if not yml.is_file():
        return []
    text = yml.read_text(encoding="utf-8", errors="replace")
    # Prefer shared parser when available (same directory).
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from ruleset_coverage import parse_targets  # type: ignore

        return parse_targets(text)
    except Exception:
        pass
    m = re.search(r"^\s*targets:\s*\[(.*)\]\s*$", text, re.M)
    if not m:
        return []
    return [t.strip().strip("'\"") for t in m.group(1).split(",") if t.strip()]


def analyze_payload(root: Path, legacy: Path) -> dict:
    digests = {}
    for rel in ANALYZE_FILES:
        p = root / rel
        if not p.is_file():
            raise FileNotFoundError(rel)
        digests[rel] = _sha256(p)
    n = _staging_java_count(root)
    if n < 1:
        raise ValueError("migration/staging has no .java files")
    return {
        "kind": "m1-analyze",
        "legacy_head": _legacy_head(legacy),
        "digests": digests,
        "staging_java_count": n,
        # Changing analysis.targets must force re-ANALYZE (kantra re-run).
        "analysis_targets": _analysis_targets(root),
    }


def profile_payload(root: Path, legacy: Path) -> dict:
    rel = "migration/architecture-profile.md"
    p = root / rel
    if not p.is_file():
        raise FileNotFoundError(rel)
    return {
        "kind": "m1-profile",
        "legacy_head": _legacy_head(legacy),
        "digests": {rel: _sha256(p)},
    }


def write_stamp(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def check_stamp(path: Path, expected: dict) -> tuple[bool, str]:
    if not path.is_file():
        return False, f"missing stamp {path}"
    try:
        got = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return False, f"corrupt stamp: {e}"
    if got.get("kind") != expected.get("kind"):
        return False, "kind mismatch"
    if got.get("legacy_head") != expected.get("legacy_head"):
        return False, (
            f"legacy_head mismatch stamp={got.get('legacy_head')} "
            f"now={expected.get('legacy_head')}"
        )
    if got.get("digests") != expected.get("digests"):
        return False, "artifact digest mismatch"
    if expected.get("kind") == "m1-analyze":
        if got.get("staging_java_count") != expected.get("staging_java_count"):
            return False, "staging_java_count mismatch"
        if got.get("analysis_targets") != expected.get("analysis_targets"):
            return False, (
                f"analysis_targets mismatch stamp={got.get('analysis_targets')} "
                f"now={expected.get('analysis_targets')}"
            )
    return True, "ok"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=[
        "write-analyze", "check-analyze", "write-profile", "check-profile",
    ])
    ap.add_argument("--root", default=".")
    ap.add_argument("--legacy", default="/projects/legacy")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    legacy = Path(args.legacy).resolve()

    try:
        if args.cmd == "write-analyze":
            payload = analyze_payload(root, legacy)
            write_stamp(root / ANALYZE_STAMP, payload)
            print(f"WROTE {ANALYZE_STAMP} legacy={payload['legacy_head'][:12]}")
            return 0
        if args.cmd == "check-analyze":
            expected = analyze_payload(root, legacy)
            ok, msg = check_stamp(root / ANALYZE_STAMP, expected)
            print(("OK" if ok else "RED") + f" analyze-provenance: {msg}")
            return 0 if ok else 1
        if args.cmd == "write-profile":
            payload = profile_payload(root, legacy)
            write_stamp(root / PROFILE_STAMP, payload)
            print(f"WROTE {PROFILE_STAMP} legacy={payload['legacy_head'][:12]}")
            return 0
        if args.cmd == "check-profile":
            expected = profile_payload(root, legacy)
            ok, msg = check_stamp(root / PROFILE_STAMP, expected)
            print(("OK" if ok else "RED") + f" profile-provenance: {msg}")
            return 0 if ok else 1
    except (FileNotFoundError, ValueError) as e:
        print(f"RED missing-artifact: {e}")
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
