#!/usr/bin/env python3
"""AD-H §16 — cheap refuse of cross-role writes when task JSON declares them.

Looks under migration/tasks/*.json and migration/kanban/*.json.
Optional fields: role, writes / files_touched / files_written (list of paths).
Idle (exit 0) when no task packets exist.

Usage:
  python3 check-role-writes.py                 # scan the current directory
  python3 check-role-writes.py /path/to/repo   # explicit workspace root
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

EXIT_CODES = """\
Exit codes:
  0  pass — declared writes stay inside each role's authority; also printed
     when no task packets exist, or none declare both role and writes
  1  BLOCK — at least one FAIL: line on stderr (unparseable packet, write to a
     globally banned path, role-denied prefix, or implementer write outside
     files_in_scope)
  2  usage error (bad/unknown arguments; emitted by argparse)
"""

BANNED_FOR_ALL_PREFIXES = (
    "projects/legacy",
    "/projects/legacy",
    ".hermes/skills/",
    ".hermes/SOUL.md",
    "SOUL.md",
)

# role -> path prefixes that role must NOT write
ROLE_DENY_PREFIXES: dict[str, tuple[str, ...]] = {
    "evidence-analyst": ("src/", "src/main/", "src/test/"),
    "planner": ("src/", "src/main/", "src/test/", ".specify/"),
    "spec-author": ("src/main/", "src/test/"),
    "implementer": (".hermes/skills/", "migration/acks/", ".hermes/SOUL.md"),
    "reviewer": ("src/", "src/main/", "src/test/", "migration/briefs/", ".specify/"),
    "validator": ("src/main/",),  # verdicts OK under migration/
}


def load_items(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else [data]


def writes_of(obj: dict) -> list[str]:
    for key in ("writes", "files_touched", "files_written", "filesWritten"):
        v = obj.get(key)
        if isinstance(v, list):
            return [str(x) for x in v]
    return []


def role_of(obj: dict) -> str:
    return str(obj.get("role") or obj.get("actor") or "").strip().lower().replace("_", "-")


def in_scope(path: str, scope: list[str]) -> bool:
    if not scope:
        return False
    norm = path.lstrip("./")
    for s in scope:
        s = str(s).lstrip("./")
        if norm == s or norm.startswith(s.rstrip("/") + "/") or s.startswith(norm):
            return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EXIT_CODES,
    )
    ap.add_argument(
        "root",
        nargs="?",
        default=".",
        help="workspace root to scan (default: current directory)",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()
    files: list[Path] = []
    for d in (root / "migration/tasks", root / "migration/kanban"):
        if d.is_dir():
            files.extend(sorted(d.glob("*.json")))
    if not files:
        print("OK: no task packets — role-write lint idle")
        return 0

    bad = 0
    checked = 0
    for path in files:
        rel = str(path.relative_to(root))
        try:
            items = load_items(path)
        except Exception as e:
            print(f"FAIL: {rel}: {e}", file=sys.stderr)
            bad = 1
            continue
        for i, obj in enumerate(items):
            if not isinstance(obj, dict):
                continue
            role = role_of(obj)
            writes = writes_of(obj)
            if not role or not writes:
                continue
            checked += 1
            label = rel if len(items) == 1 else f"{rel}[{i}]"
            scope = obj.get("files_in_scope") or obj.get("filesInScope") or []
            if not isinstance(scope, list):
                scope = []

            for w in writes:
                wn = w.lstrip("./")
                for ban in BANNED_FOR_ALL_PREFIXES:
                    if wn == ban or wn.startswith(ban):
                        print(f"FAIL: {label}: role={role} must not write {w}", file=sys.stderr)
                        bad = 1
                for ban in ROLE_DENY_PREFIXES.get(role, ()):
                    if wn == ban.rstrip("/") or wn.startswith(ban):
                        print(
                            f"FAIL: {label}: role={role} denied write to {w} (AD-H §16)",
                            file=sys.stderr,
                        )
                        bad = 1
                if role == "implementer" and scope and not in_scope(w, [str(s) for s in scope]):
                    print(
                        f"FAIL: {label}: implementer write {w} outside files_in_scope",
                        file=sys.stderr,
                    )
                    bad = 1

    if checked == 0:
        print("OK: task packets present but none declare role+writes — role-write lint idle")
        return 0
    if bad:
        print(f"Role-write checks FAILED ({checked} packet(s) with writes).", file=sys.stderr)
        return 1
    print(f"OK: role-write checks passed ({checked} packet(s)).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
