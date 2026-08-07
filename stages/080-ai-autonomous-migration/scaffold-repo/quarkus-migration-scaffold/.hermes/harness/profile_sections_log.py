#!/usr/bin/env python3
"""Emit architecture-profile.md §§1–7 for outer-loop (O-PROFSECTIONS).

Usage:
  profile_sections_log.py [--summary] <architecture-profile.md>

Default: full section dump (side-file / forensic).
--summary: compact per-section stats for outer-loop.log (O-PROFSECTIONNOISE —
does not reprint every §7 role bullet into the live progress log).

Exit 0 always (logging helper — rubric owns pass/fail).
"""
from __future__ import annotations

import argparse
import re
import sys

# Canonical titles for outer-loop narrative (match ANALYSIS.md / rubric).
SECTIONS = (
    (1, "Purpose & Domain", r"purpose\s*&?\s*domain"),
    (2, "Components & Relationships", r"components\s*&?\s*relationships"),
    (3, "Integration Surfaces", r"integration\s+surfaces"),
    (4, "Behavioral Contract Sources", r"behavioral\s+contract"),
    (5, "Modernization Surface", r"modernization\s+surface"),
    (6, "Domain Boundaries", r"domain\s+boundaries"),
    (7, "Class Roles & Target Contract", r"class\s+roles"),
)


def _section_body(text: str, needle: str) -> str:
    """Body of the heading matching needle, through next same-or-higher heading."""
    m = re.search(r"^(#{2,6})[ \t]+.*" + needle + r".*$", text, re.M | re.I)
    if not m:
        return ""
    level = len(m.group(1))
    rest = text[m.end() :]
    nxt = re.search(r"^#{1," + str(level) + r"}[ \t]", rest, re.M)
    return rest[: nxt.start()] if nxt else rest


def _summarize_body(num: int, title: str, body: str) -> str:
    # Demo-facing: always §N (Title) — bare §N is opaque to workshop viewers.
    label = f"§{num} ({title})"
    if not body.strip():
        return f"{label}: ABSENT/empty"
    words = len(re.findall(r"\S+", body))
    skel = len(re.findall(r"LLM fills", body, re.I))
    cited = bool(
        re.search(r"src/[\w./-]+\.java:\d+|migration/[\w./-]+|\.java:\d+", body)
    )
    if num == 7:
        h = len(re.findall(r"\bHARVEST\b", body))
        r = len(re.findall(r"\bREDESIGN\b", body))
        u = len(re.findall(r"\bUNDECIDED\b", body))
        pins = len(re.findall(r"Target contract\s*\(", body))
        return (
            f"{label}: {words} words · role lines≈"
            f"H={h} R={r} U={u} · hardpins={pins} · skel={skel}"
        )
    return (
        f"{label}: {words} words · skel={skel} · "
        f"cited={'yes' if cited else 'no'}"
    )


def emit_full(text: str) -> None:
    print("O-PROFSECTIONS: begin architecture-profile.md §§1–7")
    for num, title, needle in SECTIONS:
        body = _section_body(text, needle).strip()
        print(f"── {num}. {title} ──")
        if not body:
            print("(section absent or empty)")
            print("")
            continue
        for line in body.splitlines():
            print(line)
        print("")
    print("O-PROFSECTIONS: end")


def emit_summary(text: str) -> None:
    print("O-PROFSECTIONS: summary (full dump → /tmp/outer-m1-profile-sections.log)")
    for num, title, needle in SECTIONS:
        body = _section_body(text, needle)
        print(_summarize_body(num, title, body))
    print("O-PROFSECTIONS: end")


def main() -> int:
    ap = argparse.ArgumentParser(description="O-PROFSECTIONS profile dump/summary")
    ap.add_argument("profile", nargs="?", default="migration/architecture-profile.md")
    ap.add_argument(
        "--summary",
        action="store_true",
        help="compact stats for outer-loop.log (not full prose/§7 dump)",
    )
    args = ap.parse_args()
    try:
        text = open(args.profile, encoding="utf-8").read()
    except OSError as e:
        print(f"O-PROFSECTIONS: missing {args.profile} ({e})")
        return 0
    if args.summary:
        emit_summary(text)
    else:
        emit_full(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
