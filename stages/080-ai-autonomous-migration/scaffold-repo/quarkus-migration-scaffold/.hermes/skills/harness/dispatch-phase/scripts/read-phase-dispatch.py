#!/usr/bin/env python3
"""Read one phase seed from phase-dispatch.yaml (no PyYAML, no eval).

LG7: dispatch-phase.sh / mint-m3-hermes.md must not eval parser output.
This script prints JSON on stdout. Missing max_runtime_seconds → exit 2
(fail-closed; Deputy E-20260815T100000Z).

Phase keys may include hyphens (the old regex [A-Za-z0-9_] excluded them).
Indent is still the two-space subset the file is authored with — reindent
fails closed rather than silently matching nothing.

Usage:
  python3 read-phase-dispatch.py --yaml .hermes/phase-dispatch.yaml --phase M3
  python3 read-phase-dispatch.py --help
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PHASE_KEY = re.compile(r"^  ([A-Za-z0-9_-]+):\s*$")
MAX_RT = re.compile(r"^    max_runtime_seconds:\s*(\d+)\s*$")
MAX_RETRIES = re.compile(r"^    max_retries:\s*(\d+)\s*$")
SKILL_ITEM = re.compile(r"^      -\s+(\S+)\s*$")
FILES_WRITABLE = re.compile(r"^    files_writable:\s*(.*)$")


def _list_items(lines: list[str], start: int) -> tuple[list[str], int]:
    items: list[str] = []
    i = start
    while i < len(lines):
        sm = SKILL_ITEM.match(lines[i])
        if not sm:
            break
        items.append(sm.group(1))
        i += 1
    return items, i


def parse_phase(text: str, phase: str) -> dict[str, object]:
    lines = text.splitlines()
    in_phases = False
    in_phase = False
    skills: list[str] = []
    files_writable: list[str] | None = None
    max_rt = ""
    max_retries = ""
    i = 0
    while i < len(lines):
        ln = lines[i]
        if re.match(r"^phases:\s*$", ln):
            in_phases = True
            i += 1
            continue
        if in_phases and re.match(r"^[A-Za-z]", ln) and not ln.startswith(" "):
            break
        m = PHASE_KEY.match(ln)
        if in_phases and m:
            in_phase = m.group(1) == phase
            i += 1
            continue
        if in_phase:
            if PHASE_KEY.match(ln):
                break
            mm = MAX_RT.match(ln)
            if mm:
                max_rt = mm.group(1)
            mr = MAX_RETRIES.match(ln)
            if mr:
                max_retries = mr.group(1)
            if re.match(r"^    skills:\s*$", ln):
                skills, i = _list_items(lines, i + 1)
                continue
            fw = FILES_WRITABLE.match(ln)
            if fw:
                rest = fw.group(1).strip()
                if rest in ("[]",):
                    files_writable = []
                    i += 1
                    continue
                if rest == "":
                    files_writable, i = _list_items(lines, i + 1)
                    continue
        i += 1
    if not max_rt:
        print(
            f"die missing max_runtime for phase={phase!r}",
            file=sys.stderr,
        )
        raise SystemExit(2)
    retries = int(max_retries) if max_retries else 2
    return {
        "phase": phase,
        "max_runtime_seconds": int(max_rt),
        "max_retries": retries,
        "skills": skills,
        "files_writable": files_writable,
        "title": f"{phase}: migration phase seed",
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Read one phase seed from phase-dispatch.yaml as JSON (LG7)."
    )
    p.add_argument("--yaml", required=True, help="path to phase-dispatch.yaml")
    p.add_argument("--phase", required=True, help="phase key (M1, M2, M3, …)")
    p.add_argument(
        "--print",
        dest="print_field",
        choices=(
            "max_runtime_seconds",
            "max_retries",
            "skills",
            "title",
            "phase",
            "files_writable_json",
        ),
        help="print one field instead of JSON (skills as newline-separated)",
    )
    args = p.parse_args(argv)
    path = Path(args.yaml)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"FAIL: cannot read {path}: {exc}", file=sys.stderr)
        return 1
    rec = parse_phase(text, args.phase)
    if args.print_field == "files_writable_json":
        json.dump(rec.get("files_writable"), sys.stdout, separators=(",", ":"))
        sys.stdout.write("\n")
        return 0
    if args.print_field:
        val = rec[args.print_field]
        if isinstance(val, list):
            sys.stdout.write("\n".join(str(x) for x in val))
            if val:
                sys.stdout.write("\n")
        else:
            sys.stdout.write(str(val) + "\n")
        return 0
    json.dump(rec, sys.stdout, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
