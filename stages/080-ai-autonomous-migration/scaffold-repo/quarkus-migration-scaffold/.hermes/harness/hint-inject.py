#!/usr/bin/env python3
"""K10 — load bounded solved-example hints for Findings rule ids.

Hints live at migration/hints/<rule-id>.md (within-run machine data).
No specimen identifiers. Caps match K2 token discipline.

Usage (library + CLI):
  hint-inject.py <rule-id> [<rule-id> ...]
  Prints a 'Solved-example hints:' block or nothing.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

MAX_HINTS = 3
MAX_HINT_CHARS = 400
# Forbid specimen / package hardcoding in hints (coolstore-lint companion).
FORBIDDEN = re.compile(
    r"coolstore|com\.redhat\.coolstore|CartEndpoint|ShoppingCart",
    re.I,
)


def hints_dir(root: Path | None = None) -> Path:
    root = root or Path(".")
    return root / "migration" / "hints"


def load_hint(rule_id: str, root: Path | None = None) -> str | None:
    # Sanitize path segment
    rid = re.sub(r"[^A-Za-z0-9._-]+", "-", rule_id.strip())
    if not rid:
        return None
    p = hints_dir(root) / f"{rid}.md"
    if not p.is_file():
        return None
    text = p.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return None
    if FORBIDDEN.search(text):
        return None  # reject specimen-tainted hints
    text = re.sub(r"\s+", " ", text)
    if len(text) > MAX_HINT_CHARS:
        text = text[: MAX_HINT_CHARS - 1].rstrip() + "…"
    return text


def format_hints(rule_ids: list[str], root: Path | None = None) -> str:
    lines: list[str] = []
    for rid in rule_ids:
        if len(lines) >= MAX_HINTS:
            break
        h = load_hint(rid, root)
        if h:
            lines.append(f"- {rid}: {h}")
    if not lines:
        return ""
    return "Solved-example hints (K10 — prior accepted patterns; apply shape, not copy):\n" + "\n".join(
        lines
    )


def main() -> int:
    if len(sys.argv) < 2:
        return 0
    root = Path(".")
    print(format_hints(sys.argv[1:], root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
