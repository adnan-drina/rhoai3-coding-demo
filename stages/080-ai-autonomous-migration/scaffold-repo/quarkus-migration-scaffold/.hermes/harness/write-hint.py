#!/usr/bin/env python3
"""K10 — write a distilled per-rule hint (story ADVANCE / Retro).

Usage:
  write-hint.py <rule-id> <hint text…>
Rejects specimen identifiers (same filter as hint-inject). Caps length.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

FORBIDDEN = re.compile(
    r"coolstore|com\.redhat\.coolstore|CartEndpoint|ShoppingCart",
    re.I,
)
MAX_HINT_CHARS = 400


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: write-hint.py <rule-id> <hint…>", file=sys.stderr)
        return 2
    rid = re.sub(r"[^A-Za-z0-9._-]+", "-", sys.argv[1].strip())
    text = " ".join(sys.argv[2:]).strip()
    text = re.sub(r"\s+", " ", text)
    if FORBIDDEN.search(text):
        print("REFUSED: hint contains specimen identifiers", file=sys.stderr)
        return 1
    if len(text) > MAX_HINT_CHARS:
        text = text[: MAX_HINT_CHARS - 1].rstrip() + "…"
    d = Path("migration/hints")
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{rid}.md").write_text(text + "\n", encoding="utf-8")
    print(f"wrote:migration/hints/{rid}.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
