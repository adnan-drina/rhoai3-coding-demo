#!/usr/bin/env python3
"""K7 — normalized failure signatures + delta for sfix honesty.

capture <out.txt> [log…]  — parse compile/test/sonar keys into a sorted set
diff <before.txt> <after.txt>  — print NEW:/GONE: lines (exit 0; exit 1 if NEW)

Keys (migration-general, from tool output only):
  compile:<file>:<symbol-or-msg>
  test:<ClassName.method>
  sonar:<rule>:<file>
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


def parse_text(text: str) -> set[str]:
    keys: set[str] = set()
    # Surefire / failsafe: ClassName.method: or Tests run failures
    for m in re.finditer(
        r"(?m)^(?:\[ERROR\]\s+)?([A-Za-z0-9_.]+)\.([A-Za-z0-9_]+)\s*(?:\(\)|:|\s+Time)",
        text,
    ):
        cls, meth = m.group(1), m.group(2)
        if meth.lower() in {"java", "xml", "txt"}:
            continue
        keys.add(f"test:{cls}.{meth}")
    for m in re.finditer(r"(?m)^<<< FAILURE! —\s*([A-Za-z0-9_.]+)\.([A-Za-z0-9_]+)", text):
        keys.add(f"test:{m.group(1)}.{m.group(2)}")
    # Compiler: /path/File.java:[line,col] error: …
    for m in re.finditer(
        r"(?m)([A-Za-z0-9_./-]+\.java):\[[0-9,]+\]\s*(?:error:\s*)?(.+)$",
        text,
    ):
        msg = re.sub(r"\s+", " ", m.group(2).strip())[:80]
        keys.add(f"compile:{Path(m.group(1)).name}:{msg}")
    for m in re.finditer(r"(?m)cannot find symbol\s*\n\s*symbol:\s*(\S+)", text):
        keys.add(f"compile:symbol:{m.group(1)}")
    # Sonar violations file: RULE file:line or similar
    for m in re.finditer(
        r"(?m)^(S\d+|java:[A-Za-z0-9_.]+)\s+(\S+\.java)",
        text,
    ):
        keys.add(f"sonar:{m.group(1)}:{Path(m.group(2)).name}")
    for m in re.finditer(
        r"(?m)([A-Za-z0-9_./-]+\.java):(\d+)\s+(S\d+|java:[A-Za-z0-9_.]+)",
        text,
    ):
        keys.add(f"sonar:{m.group(3)}:{Path(m.group(1)).name}")
    # SENSOR RED lines
    for m in re.finditer(r"SENSOR RED \((\w+)\):\s*(.+)$", text, re.M):
        kind = m.group(1)
        detail = re.sub(r"\s+", " ", m.group(2).strip())[:100]
        keys.add(f"sensor:{kind}:{detail}")
    return keys


def load_sig(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    return {
        ln.strip()
        for ln in path.read_text(encoding="utf-8", errors="replace").splitlines()
        if ln.strip() and not ln.startswith("#")
    }


def cmd_capture(out: Path, logs: list[Path]) -> int:
    keys: set[str] = set()
    for p in logs:
        if p.is_file():
            keys |= parse_text(p.read_text(encoding="utf-8", errors="replace"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "# failure-sig (K7)\n" + "\n".join(sorted(keys)) + ("\n" if keys else ""),
        encoding="utf-8",
    )
    print(f"captured:{len(keys)}:{out}")
    return 0


def cmd_diff(before: Path, after: Path) -> int:
    a, b = load_sig(before), load_sig(after)
    new, gone = sorted(b - a), sorted(a - b)
    print("# failure-delta (K7) — NEW = introduced since before-sig")
    for k in new:
        print(f"NEW:{k}")
    for k in gone:
        print(f"GONE:{k}")
    print(f"SUMMARY new={len(new)} gone={len(gone)} before={len(a)} after={len(b)}")
    return 1 if new else 0


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: failure-sig.py capture|diff …", file=sys.stderr)
        return 2
    cmd = sys.argv[1]
    if cmd == "capture":
        if len(sys.argv) < 3:
            return 2
        return cmd_capture(Path(sys.argv[2]), [Path(p) for p in sys.argv[3:]])
    if cmd == "diff":
        if len(sys.argv) < 4:
            return 2
        return cmd_diff(Path(sys.argv[2]), Path(sys.argv[3]))
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
