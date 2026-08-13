#!/usr/bin/env python3
"""Fail-closed dangling .hermes / governance path references (Deputy E-174046Z).

Relocation residue pattern: artefact moves, satellites stay and teach the wrong
thing. This lint asserts in-scaffold path citations resolve on disk.

Allowlists run-state and seat-provisioned paths so golden stays green without
disabling the gate.

Usage:
  python3 check-dangling-hermes-refs.py --root .
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Path-like citations under .hermes/ or governance/ (post-split ready).
# Lookbehind includes '-' so record-run-evidence/... is not parsed as evidence/...
PATH_RX = re.compile(
    r"(?<![A-Za-z0-9_./$-])"
    r"((?:\.hermes|governance|evidence)/[A-Za-z0-9_./${}-]+\."
    r"(?:py|sh|md|yaml|yml|json|txt))"
)

SKIP_PARTS = frozenset({"__pycache__", ".git", "evidence/derived"})
SCAN_SUFFIXES = {".md", ".py", ".sh", ".yaml", ".yml", ".txt"}

# Legitimate absences: run-state, seat provision, or template noise.
ALLOW_EXACT = frozenset(
    {
        # Runtime analysis outputs (seat-generated)
        "evidence/entry-point-inventory.json",
        "evidence/findings-handoff.json",
        "evidence/mta-findings.json",
        "governance/contracts/g1-kill-ratio-pin.json",
        # Seat / Managed Scope provision (not golden-committed)
        ".hermes/home/SOUL.md",
        ".hermes/home/config.yaml",
        ".hermes/config.yaml",
        # Fallback lookup paths in loaders (primary file exists beside them)
        ".hermes/skills/validate-contracts/references/r-sk9-architect-keep.txt",
        ".hermes/r-sk9-architect-keep.txt",
        ".hermes/skills/validate-contracts/references/r-sk5-specimen-keep.txt",
    }
)
ALLOW_PREFIXES = (
    "evidence/runs/",
    "evidence/receipts/",
    "evidence/derived/",
    "evidence/acks/",
    "evidence/verdicts/",
    "evidence/bodies/",
    "evidence/briefs/",
    "evidence/mta-analyze-out/",
    "evidence/slices/",
    "evidence/preflight/",
    "evidence/fixtures/admission/out/",
    "evidence/examples/",
    "evidence/recovery/",
    "evidence/authority/",
    "evidence/tasks/",
    "evidence/kanban/",
    "evidence/provenance/",
    ".specify/",
)


def allowed(rel: str) -> bool:
    if rel in ALLOW_EXACT:
        return True
    if "${" in rel or "}" in rel or "<" in rel:
        return True
    return any(rel.startswith(p) for p in ALLOW_PREFIXES)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Exit: 0=pass, 1=dangling refs, 2=usage",
    )
    ap.add_argument("--root", default=".", help="scaffold root")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"FAIL: bad root {root}", file=sys.stderr)
        return 2

    missing: list[str] = []
    checked = 0
    for p in root.rglob("*"):
        if not p.is_file() or p.suffix not in SCAN_SUFFIXES:
            continue
        try:
            rel_p = str(p.relative_to(root)).replace("\\", "/")
        except ValueError:
            continue
        if any(part in SKIP_PARTS or part == "derived" for part in p.parts):
            continue
        if "evidence/derived" in rel_p:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in PATH_RX.finditer(text):
            target_rel = m.group(1)
            if allowed(target_rel):
                continue
            checked += 1
            if not (root / target_rel).exists():
                missing.append(f"{rel_p}: dangling {target_rel}")

    # de-dupe preserve order
    seen: set[str] = set()
    uniq: list[str] = []
    for e in missing:
        if e not in seen:
            seen.add(e)
            uniq.append(e)

    for e in uniq:
        print(e, file=sys.stderr)
    print(f"DANGLING_HERMES_REFS_CHECKED={checked} VIOLATIONS={len(uniq)}")
    return 1 if uniq else 0


if __name__ == "__main__":
    raise SystemExit(main())
