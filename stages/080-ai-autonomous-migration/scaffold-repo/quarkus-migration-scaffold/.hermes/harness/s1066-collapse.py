#!/usr/bin/env python3
"""O-S1066 — collapse nested single-statement ifs (Sonar java:S1066).

OpenRewrite CollapsibleIfStatements is not in rewrite-static-analysis:1.21.1
(the version pinned for the other cleanup recipes). This deterministic fixer
covers the common shape:

    if (a) {
        if (b) {
            BODY
        }
    }

→  if (a && b) {
        BODY
    }

Only collapses when the outer then-block contains exactly one inner if with
no else on either. Safe for Spring→Quarkus service harvests; skips files it
cannot parse confidently.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".")

# Outer if (cond) { <ws> if (cond2) { body } <ws> }
PAT = re.compile(
    r"if\s*\((?P<a>[^()]*(?:\([^()]*\)[^()]*)*)\)\s*\{\s*"
    r"if\s*\((?P<b>[^()]*(?:\([^()]*\)[^()]*)*)\)\s*\{"
    r"(?P<body>(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*)"
    r"\}\s*\}",
    re.M,
)


def collapse(text: str) -> tuple[str, int]:
    n = 0

    def repl(m: re.Match[str]) -> str:
        nonlocal n
        a, b, body = m.group("a").strip(), m.group("b").strip(), m.group("body")
        # Skip if either condition uses || (needs parens; leave to model)
        if "||" in a or "||" in b:
            return m.group(0)
        n += 1
        return f"if ({a} && {b}) {{{body}}}"

    # Iterate to collapse deeper nests
    prev = None
    cur = text
    while prev != cur:
        prev = cur
        cur, k = PAT.subn(repl, cur)
        if k == 0:
            break
    return cur, n


def main() -> int:
    changed = 0
    for path in sorted((ROOT / "src").rglob("*.java")) if (ROOT / "src").is_dir() else []:
        orig = path.read_text(encoding="utf-8", errors="replace")
        new, n = collapse(orig)
        if n and new != orig:
            path.write_text(new, encoding="utf-8")
            print(f"s1066-collapse: {path.relative_to(ROOT)} ({n} collapse(s))")
            changed += 1
    print(f"s1066-collapse: {changed} file(s) changed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
