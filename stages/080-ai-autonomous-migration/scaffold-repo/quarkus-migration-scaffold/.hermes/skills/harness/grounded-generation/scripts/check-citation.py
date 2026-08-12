#!/usr/bin/env python3
"""AD-H §17 — commit/packet citation lint + refuse invent-without-locus (cheap).

Looks under migration/tasks/*.json and migration/kanban/*.json for IMPLEMENT /
implementer packets. Non-trivial packets must cite task id, brief/story id, and
legacy locus (path:lines or staging/harvest path). Trivial exemption: trivial=true.

Optional --commit-msg FILE lints a commit message the same way.

Idle (exit 0) when no IMPLEMENT packets and no --commit-msg.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Task id: T-1, TASK-001, M3-T12, etc.
TASK_ID_RE = re.compile(r"\b(?:T|TASK|M[0-9]+-T)[-_]?\d+\b", re.I)
# Brief / story: B-1, STORY-12, brief B-1, story_id: …
BRIEF_ID_RE = re.compile(
    r"\b(?:B|BRIEF|STORY|S)[-_]?\d+\b|"
    r"\b(?:brief|story)[_ -]?(?:id)?\s*[:=]\s*\S+",
    re.I,
)
# Legacy locus: path with optional :start-end or :line, or staging/harvest/
LOCUS_PATH_RE = re.compile(
    r"(?:"
    r"(?:legacy|projects/legacy|/projects/legacy|staging|harvest|legacy-at-3)"
    r"[^\s,;)]*"
    r"(?::\d+(?:-\d+)?)?"
    r"|"
    r"[A-Za-z0-9_./-]+\.(?:java|xml|yml|yaml|properties|sql|kt)"
    r":\d+(?:-\d+)?"
    r")",
    re.I,
)


def load_items(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else [data]


def is_implement(obj: dict) -> bool:
    phase = str(obj.get("phase") or obj.get("m_phase") or "").upper()
    role = str(obj.get("role") or obj.get("actor") or "").lower().replace("_", "-")
    kind = str(obj.get("kind") or obj.get("task_kind") or "").lower()
    if phase in {"M3", "IMPLEMENT"}:
        return True
    if role in {"implement", "implementer", "worker", "opencode"}:
        return True
    if kind in {"implement", "harvest", "redesign"}:
        return True
    return False


def is_trivial(obj: dict) -> bool:
    for key in ("trivial", "is_trivial", "isTrivial", "formatting_only"):
        v = obj.get(key)
        if v in (True, "true", "yes", 1):
            return True
    return False


def task_id_of(obj: dict) -> str:
    for key in ("id", "task_id", "taskId", "kanban_id", "kanbanId"):
        v = obj.get(key)
        if v not in (None, ""):
            return str(v).strip()
    return ""


def brief_id_of(obj: dict) -> str:
    for key in (
        "brief_id",
        "briefId",
        "story_id",
        "storyId",
        "unit_id",
        "unitId",
        "identity_ref",
        "identityRef",
        "spec_path",
        "specPath",
    ):
        v = obj.get(key)
        if v not in (None, ""):
            return str(v).strip()
    return ""


def locus_of(obj: dict) -> str:
    for key in (
        "legacy_locus",
        "legacyLocus",
        "locus",
        "legacy_ref",
        "legacyRef",
        "harvest_path",
        "harvestPath",
        "staging_path",
        "stagingPath",
        "legacy_path",
        "legacyPath",
    ):
        v = obj.get(key)
        if v not in (None, ""):
            if isinstance(v, list):
                return " ".join(str(x) for x in v)
            return str(v).strip()
    # Nested citation block
    cite = obj.get("citation") or obj.get("cites") or {}
    if isinstance(cite, dict):
        for key in ("legacy_locus", "legacyLocus", "locus", "legacy"):
            v = cite.get(key)
            if v not in (None, ""):
                return str(v).strip()
    return ""


def claims_done_or_writes(obj: dict) -> bool:
    status = str(obj.get("status") or obj.get("state") or "").lower()
    if status in {"done", "complete", "completed", "closed", "merged"}:
        return True
    for key in ("writes", "files_touched", "files_written", "filesWritten"):
        v = obj.get(key)
        if isinstance(v, list) and v:
            return True
    return False


def invent_without_locus(obj: dict) -> bool:
    """True when packet invents behaviour with no locus / evidence anchor."""
    if locus_of(obj):
        return False
    if obj.get("invention") in (True, "true", "yes", 1):
        return True
    # REDESIGN without targetContract/AC and without locus → invent
    kind = str(obj.get("kind") or obj.get("task_kind") or "").lower()
    if kind == "redesign":
        tc = obj.get("targetContract") or obj.get("target_contract")
        acs = obj.get("ac_ids") or obj.get("acIds") or []
        if not tc and not acs:
            return True
    # Done/writes without locus on non-trivial → invent-without-locus
    if claims_done_or_writes(obj) and not is_trivial(obj):
        return True
    return False


def check_commit_msg(text: str, *, trivial: bool = False) -> list[str]:
    errs: list[str] = []
    if not TASK_ID_RE.search(text):
        errs.append("commit message missing task id (AD-H §7.5 / §17)")
    if trivial:
        return errs
    if not BRIEF_ID_RE.search(text):
        errs.append("commit message missing brief/story id (AD-H §17)")
    if not LOCUS_PATH_RE.search(text):
        errs.append("commit message missing legacy locus (AD-H §17)")
    # Explicit invent markers without locus already covered by locus check
    if re.search(r"(?i)\binvent(?:ion|ed|ing)?\b", text) and not LOCUS_PATH_RE.search(text):
        errs.append("commit claims invention without legacy locus")
    return errs


def main() -> int:
    ap = argparse.ArgumentParser(description="AD-H §17 citation / invent-without-locus lint")
    ap.add_argument("root", nargs="?", default=".", help="scaffold / workspace root")
    ap.add_argument("--commit-msg", metavar="FILE", help="lint a commit message file")
    ap.add_argument(
        "--trivial",
        action="store_true",
        help="treat --commit-msg as trivial (task id only)",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()
    bad = 0
    checked = 0

    def fail(msg: str) -> None:
        nonlocal bad
        print(f"FAIL: {msg}", file=sys.stderr)
        bad = 1

    if args.commit_msg:
        checked += 1
        msg_path = Path(args.commit_msg)
        try:
            text = msg_path.read_text(encoding="utf-8")
        except Exception as e:
            fail(f"commit-msg: {e}")
            return 1
        for err in check_commit_msg(text, trivial=args.trivial):
            fail(err)
        if bad == 0:
            print("OK: commit message citation passed")
        # continue to also check packets when present

    files: list[Path] = []
    for d in (root / "migration/tasks", root / "migration/kanban"):
        if d.is_dir():
            files.extend(sorted(d.glob("*.json")))

    impl_checked = 0
    for path in files:
        rel = str(path.relative_to(root))
        try:
            items = load_items(path)
        except Exception as e:
            fail(f"{rel}: {e}")
            continue
        for i, obj in enumerate(items):
            if not isinstance(obj, dict) or not is_implement(obj):
                continue
            impl_checked += 1
            checked += 1
            label = rel if len(items) == 1 else f"{rel}[{i}]"
            if not task_id_of(obj):
                fail(f"{label}: IMPLEMENT packet missing task id")

            if invent_without_locus(obj):
                fail(f"{label}: invent-without-locus refused (AD-H §17)")
                continue

            if is_trivial(obj):
                continue

            if not brief_id_of(obj):
                fail(f"{label}: non-trivial IMPLEMENT missing brief/story id")
            locus = locus_of(obj)
            if not locus:
                fail(f"{label}: non-trivial IMPLEMENT missing legacy_locus")
            elif not LOCUS_PATH_RE.search(locus) and "/" not in locus and ":" not in locus:
                fail(f"{label}: legacy_locus not a path/line or staging/harvest ref: {locus!r}")

    if checked == 0:
        print("OK: no IMPLEMENT packets / commit-msg — citation lint idle")
        return 0
    if bad:
        print(f"Grounded-generation citation FAILED ({checked} artifact(s)).", file=sys.stderr)
        return 1
    if impl_checked:
        print(f"OK: grounded-generation citation passed ({impl_checked} IMPLEMENT packet(s)).")
    elif args.commit_msg:
        pass  # already printed
    else:
        print("OK: grounded-generation citation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
