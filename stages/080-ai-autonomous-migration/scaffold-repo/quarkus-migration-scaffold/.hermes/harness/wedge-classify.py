#!/usr/bin/env python3
"""O-WORKERWEDGE-RCA — classify why a worker session was killed / failed.

V10 evidence (S04–S05): consecutive Qwen wedges were not one cause —
  READ_THRASH — many read/glob, zero mutate (O-WORKERREAD)
  JSON_STALE  — session JSON froze (O-WORKERWEDGE)
  TRUNCATION  — final text mid-sentence, empty .err (O-OCERR-SILENT)
  OTHER       — compile/tool errors, quota, unknown

Usage:
  wedge-classify.py </tmp/oc-T-NNN.err> [/tmp/oc-T-NNN.json]
Prints one class token on stdout.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


def classify(err: str, json_text: str = "") -> str:
    e = err.lower()
    if "o-workerread" in e or "read-thrash" in e:
        return "READ_THRASH"
    if "o-workerwedge" in e or "no session output" in e or "json size frozen" in e:
        return "JSON_STALE"
    if "o-ocerr" in e and "truncat" in e:
        return "TRUNCATION"
    if "truncat" in e:
        return "TRUNCATION"
    # Heuristic: final assistant text ends mid-thought, no ERROR patterns.
    if json_text and not re.search(r"ERROR|BUILD FAILURE|COMPILATION", json_text):
        texts = re.findall(r'"text"\s*:\s*"([^"]{20,})"', json_text)
        if texts:
            last = texts[-1].rstrip()
            if last.endswith(("…", "...", "First,", "Let me", "Now I")) or (
                not last.endswith((".", "!", "?", "`", '"')) and len(last) > 40
            ):
                if "edit" not in json_text.lower() and "write" not in json_text.lower():
                    return "TRUNCATION"
    if re.search(r"ERROR|BUILD FAILURE|COMPILATION ERROR", err):
        return "OTHER"
    if err.strip():
        return "OTHER"
    return "OTHER"


def main() -> int:
    if len(sys.argv) < 2:
        print("OTHER")
        return 0
    err_p = Path(sys.argv[1])
    err = err_p.read_text(encoding="utf-8", errors="replace") if err_p.is_file() else ""
    js = ""
    if len(sys.argv) >= 3:
        jp = Path(sys.argv[2])
        if jp.is_file():
            js = jp.read_text(encoding="utf-8", errors="replace")[:200_000]
    print(classify(err, js))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
