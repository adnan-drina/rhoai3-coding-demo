#!/usr/bin/env python3
"""Completion consumer — reject N/A self-amend of binding Done criteria.

Operator E-20260811T120200Z / Architect E-20260811T115550Z:
  kanban_complete with any binding criterion self-declared N/A (or equivalent
  self-amend) ⇒ REJECT → needs_input. Workers may satisfy or BLOCK; never amend.

Exit: 0 = OK; 1 = REJECT (needs_input); 2 = usage/harness error.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# Patterns that rewrite binding Done criteria to N/A / not-applicable
NA_SELF_AMEND = re.compile(
    r"(?is)"
    r"("
    r"\bN/?A\b.{0,80}(done|criterion|criteria|spec\s*kit|speckit)"
    r"|(done|criterion|criteria).{0,80}\bN/?A\b"
    r"|doesn'?t apply"
    r"|not applicable"
    r"|self[- ]?certif"
    r"|rewrote.{0,40}(done|criterion)"
    r"|amended.{0,40}(done|criterion|obligation)"
    r")"
)


def collect_text(task_id: str | None, text: str | None, path: Path | None) -> str:
    chunks: list[str] = []
    if text:
        chunks.append(text)
    if path and path.is_file():
        chunks.append(path.read_text(encoding="utf-8", errors="replace"))
    if task_id:
        env = {
            **dict(**{k: v for k, v in __import__("os").environ.items()}),
        }
        try:
            show = subprocess.run(
                ["hermes", "kanban", "show", task_id],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )
            chunks.append(show.stdout or "")
            chunks.append(show.stderr or "")
        except FileNotFoundError:
            print("COMPLETION_NA: hermes not on PATH", file=sys.stderr)
            raise SystemExit(2)
        try:
            log = subprocess.run(
                ["hermes", "kanban", "log", task_id],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )
            # Tail — full logs are huge
            out = log.stdout or ""
            chunks.append(out[-200_000:])
        except FileNotFoundError:
            pass
    return "\n".join(chunks)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--task-id", default="")
    ap.add_argument("--text", default="")
    ap.add_argument("--file", type=Path, default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if not args.task_id and not args.text and not args.file:
        print("usage: check-completion-na-reject.py --task-id t_… | --text … | --file …", file=sys.stderr)
        return 2
    blob = collect_text(args.task_id or None, args.text or None, args.file)
    hits = list(NA_SELF_AMEND.finditer(blob))
    # Require proximity to completion / Done language to reduce false positives
    scored = []
    for m in hits:
        window = blob[max(0, m.start() - 120) : m.end() + 120]
        if re.search(r"(?i)done|complete|criterion|spec\s*kit|speckit|obligation", window):
            scored.append(window.replace("\n", " ")[:200])
    payload = {
        "schema": "rhoai3.completion-na-reject/v1",
        "task_id": args.task_id or None,
        "reject": bool(scored),
        "hits": scored[:8],
        "law": "E-20260811T120200Z / E-20260811T115550Z",
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    if scored:
        print(
            "REJECT: binding Done criterion self-declared N/A / self-amended — "
            "needs_input (never amend obligations)",
            file=sys.stderr,
        )
        for h in scored[:5]:
            print(f"  hit: {h}", file=sys.stderr)
        return 1
    print("OK: completion consumer — no N/A self-amend detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
