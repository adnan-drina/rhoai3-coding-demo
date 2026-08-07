#!/usr/bin/env python3
"""O-TREEFIXSTUB — refuse comment-only / REMOVED stubs under src/main.

Migration-general (any Spring Boot → Quarkus specimen):

  Tree-fix / tip-accept must NOT clear spring residue by rewriting owned
  Targets to comment-only stubs (`/* REMOVED: … */`) or by deleting type
  bodies while leaving a `.java` husk. That games residue greps and can
  leave sensors GREEN while the convert stack is dishonest.

  Rules:
    1. Every `src/main/java/**/*.java` (except package-info / module-info)
       must declare a class|interface|enum|record.
    2. Files whose only substance is a REMOVED / "prematurely harvested"
       comment are RED even if tiny.
    3. With `--sha`, also refuse commits that *delete* a `src/main/**/*.java`
       path claimed as Target/Owns in the current story tasks.md (owned
       Target nuke).

Usage:
  tree-fix-stub-check.py              # scan working tree
  tree-fix-stub-check.py --sha HEAD   # scan commit (+ parent deletes)

Exit 0 = clean; exit 1 = violation(s) on stdout (one per line).
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(".").resolve()
TYPE_DECL = re.compile(
    r"\b(?:public\s+|protected\s+|private\s+)?"
    r"(?:static\s+|final\s+|abstract\s+|sealed\s+|non-sealed\s+)*"
    r"(?:class|interface|enum|record)\b"
)
REMOVED_MARK = re.compile(
    r"(?i)\bREMOVED\b|prematurely\s+harvested|stub(?:bed)?\s+out|"
    r"intentionally\s+(?:left\s+)?empty|delete(?:d)?\s+pending\s+harvest"
)
SKIP_NAMES = {"package-info.java", "module-info.java"}
_JAVA_PATH = re.compile(r"src/(?:main|test)/java/[\w./-]+\.java")
_CLAIM_LINE = re.compile(
    r"(?i)(?:^\s*\*?\*?(?:Absorbs|Owns|Target\s*design|Target|Design)\*?\*?\s*:)"
)
_OOS_LINE = re.compile(r"(?i)^\s*\*?\*?(?:Out[- ]of[- ]scope|Deferred)\b")


def _show_names_status(sha: str) -> list[tuple[str, str]]:
    try:
        out = subprocess.check_output(
            ["git", "show", "--name-status", "--format=", sha], text=True
        )
    except subprocess.CalledProcessError:
        return []
    rows: list[tuple[str, str]] = []
    for ln in out.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        parts = ln.split("\t")
        if len(parts) < 2:
            continue
        status, path = parts[0], parts[-1]
        rows.append((status[:1], path))
    return rows


def _read_work(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _read_sha(sha: str, rel: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "show", f"{sha}:{rel}"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return ""


def _is_stub_text(text: str) -> str | None:
    """Return smell tag if text is a dishonest stub; else None."""
    if not text or not text.strip():
        return "empty-file"
    if REMOVED_MARK.search(text) and not TYPE_DECL.search(text):
        return "removed-comment-stub"
    if not TYPE_DECL.search(text):
        # Allow files that are only a package + imports + comments with no
        # type — still dishonest under src/main (except package-info).
        return "no-type-declaration"
    # REMOVED mark plus almost no code (type decl may be faked as comment)
    if REMOVED_MARK.search(text):
        # Strip comments/strings roughly; if no method/ctor body remains → stub
        stripped = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        stripped = re.sub(r"//.*?$", "", stripped, flags=re.M)
        if not re.search(r"\{[^{}]{8,}\}", stripped):
            if len(stripped.strip()) < 200:
                return "removed-husk"
    return None


def _claimed_main_targets() -> set[str]:
    """Target/Owns src/main .java paths from story tasks.md (if present)."""
    tasks = sorted(ROOT.glob("specs/*/tasks.md"))
    if not tasks:
        return set()
    path = tasks[0]
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    claimed: set[str] = set()
    for line in text.splitlines():
        if _OOS_LINE.search(line):
            continue
        if not (_CLAIM_LINE.search(line) or "→" in line or "->" in line):
            continue
        for m in _JAVA_PATH.finditer(line):
            rel = m.group(0).lstrip("./")
            if rel.startswith("src/main/"):
                claimed.add(rel)
    return claimed


def check(sha: str | None = None) -> list[str]:
    problems: list[str] = []
    if sha:
        for status, rel in _show_names_status(sha):
            if not rel.endswith(".java") or not rel.startswith("src/main/"):
                continue
            base = Path(rel).name
            if base in SKIP_NAMES:
                continue
            if status == "D":
                claimed = _claimed_main_targets()
                if rel in claimed:
                    problems.append(f"O-TREEFIXSTUB:deleted-owned-target:{rel}")
                continue
            if status not in ("A", "M", "R", "C"):
                continue
            text = _read_sha(sha, rel)
            smell = _is_stub_text(text)
            if smell:
                problems.append(f"O-TREEFIXSTUB:{smell}:{rel}")
        return problems

    root = ROOT / "src/main/java"
    if not root.is_dir():
        return problems
    for path in sorted(root.rglob("*.java")):
        if path.name in SKIP_NAMES:
            continue
        text = _read_work(path)
        smell = _is_stub_text(text)
        if smell:
            rel = str(path.relative_to(ROOT))
            problems.append(f"O-TREEFIXSTUB:{smell}:{rel}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sha", default=None)
    args = ap.parse_args()
    problems = check(args.sha)
    if problems:
        print("\n".join(problems[:24]))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
