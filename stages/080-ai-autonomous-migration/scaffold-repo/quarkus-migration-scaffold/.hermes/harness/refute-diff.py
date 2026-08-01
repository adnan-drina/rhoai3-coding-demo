#!/usr/bin/env python3
"""K12 — adversarial refute of a high-stakes commit (deterministic core).

Scans `git show <sha>` (or a diff file) for fabrication / honesty smells.
Bias: REFUTE on match. Migration-general patterns only (no specimen ids).

Usage:
  refute-diff.py HEAD
  refute-diff.py --diff /tmp/patch.diff
Exit 0 = PASS (no smells); exit 1 = REFUTED (prints findings).
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# (id, regex on added lines / full diff, note)
SMELLS: list[tuple[str, re.Pattern[str], str]] = [
    (
        "G-PLACE",
        re.compile(r"^\+.*(assertThat\s*\(\s*true\s*\)|assertTrue\s*\(\s*true\s*\))", re.I | re.M),
        "ceremonial true-assertion",
    ),
    (
        "FAIL-OPEN",
        re.compile(
            r"^\+.*catch\s*\([^)]+\)[\s\S]{0,200}^\+.*return\s+(Response\.ok|List\.of\(\)|Collections\.empty|new\s+\w+\()",
            re.M,
        ),
        "catch→ok/empty return (fail-open)",
    ),
    (
        "MAPPER-EXCEPTION",
        re.compile(r"^\+.*ExceptionMapper\s*<\s*Exception\s*>", re.M),
        "ExceptionMapper<Exception>",
    ),
    (
        "MOCK-FABRICATE",
        re.compile(r"^\+.*(getMockProducts|Fallback to mock|mockProducts\s*\()", re.M),
        "forbidden mock fabrication",
    ),
    (
        "STATUS-MAP",
        re.compile(
            r"^\+.*(Map\.of\s*\(\s*\"status\"|AcceptanceStatus|service_interfaces_ready|platform_ready)",
            re.M,
        ),
        "ceremonial status-map acceptance",
    ),
]

# Bare assertThat(x).isNotNull(); — ceremonial when it is the only substance.
# O-K12WEAKTEST / O-K12NEST: do NOT parse assertThat(...) args with [^)]+ —
# nested calls like getOwner() made strong-assert detection false-negative
# (Wave2 T-019 CircularGroupIntegrationTest). Instead: any non-isNotNull
# assertThat on an added line counts as substance.
_WEAK_ISNOTNULL = re.compile(
    r"^\+.*assertThat\s*\(.*\)\s*\.\s*isNotNull\s*\(\s*\)\s*;\s*$"
)
_ASSERTTHAT_LINE = re.compile(r"^\+.*\bassertThat\s*\(")


def load_diff(sha: str | None, diff_path: Path | None) -> str:
    if diff_path is not None:
        return diff_path.read_text(encoding="utf-8", errors="replace")
    r = subprocess.run(
        ["git", "show", "--format=", sha or "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return r.stdout or ""


def _weak_assert_smell(diff: str) -> bool:
    saw_weak_non_ann = False
    for line in diff.splitlines():
        if line.startswith("++") or not _ASSERTTHAT_LINE.search(line):
            continue
        if "import " in line:
            continue
        if _WEAK_ISNOTNULL.match(line):
            if "getAnnotation" in line or "Annotation" in line:
                continue
            saw_weak_non_ann = True
            continue
        # Any other assertThat (isSameAs/extracting/hasSize/…) is substance.
        return False
    return saw_weak_non_ann


def refute(diff: str) -> list[str]:
    hits: list[str] = []
    for sid, pat, note in SMELLS:
        if pat.search(diff):
            hits.append(f"REFUTED:{sid}:{note}")
    if _weak_assert_smell(diff):
        hits.append("REFUTED:WEAK-ASSERT:weak isNotNull-only assertion (suspect)")
    return hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("sha", nargs="?", default="HEAD")
    ap.add_argument("--diff", type=Path, default=None)
    args = ap.parse_args()
    diff = load_diff(None if args.diff else args.sha, args.diff)
    if not diff.strip():
        print("PASS: empty diff")
        return 0
    hits = refute(diff)
    if hits:
        print("\n".join(hits))
        return 1
    print("PASS: no K12 smells")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
