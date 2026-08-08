#!/usr/bin/env python3
"""AD-S §S.6 cheap checks — identity presence, refuse worker re-plan, plan_revision.

Idle (exit 0) when no plan/task artifacts exist.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def load_json(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else [data]


def is_implement(obj: dict) -> bool:
    phase = str(obj.get("phase") or obj.get("m_phase") or "").upper()
    role = str(obj.get("role") or obj.get("actor") or "").lower()
    kind = str(obj.get("kind") or obj.get("task_kind") or "").lower()
    if phase in {"M3", "M4", "IMPLEMENT", "VERIFY"}:
        return True
    if role in {"implement", "implementer", "worker", "opencode"}:
        return True
    if kind in {"implement", "harvest", "redesign"}:
        return True
    return False


def truthy_replan(obj: dict) -> bool:
    for key in ("replan", "re_plan", "may_replan", "mayReplan", "worker_replan"):
        if key in obj and obj[key] not in (False, None, "", 0, "false", "no"):
            return True
    return False


def has_identity(obj: dict) -> bool:
    for key in (
        "brief_id",
        "briefId",
        "story_id",
        "storyId",
        "unit_id",
        "unitId",
        "identity_ref",
        "identityRef",
    ):
        if obj.get(key) not in (None, ""):
            return True
    return False


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    bad = 0
    checked = 0

    def fail(msg: str) -> None:
        nonlocal bad
        print(f"FAIL: {msg}", file=sys.stderr)
        bad = 1

    task_dirs = [root / "migration/tasks", root / "migration/kanban"]
    plan_dirs = [root / "migration/plans"]
    plan_files: list[Path] = []
    for d in plan_dirs:
        if d.is_dir():
            plan_files.extend(sorted(d.glob("*.json")))
    for p in (root / "specs").rglob("plan.md") if (root / "specs").is_dir() else []:
        plan_files.append(p)
    for p in (root / ".specify/specs").rglob("plan.md") if (root / ".specify/specs").is_dir() else []:
        plan_files.append(p)

    task_files: list[Path] = []
    for d in task_dirs:
        if d.is_dir():
            task_files.extend(sorted(d.glob("*.json")))

    briefs_exist = any(
        (root / p).is_dir() and any((root / p).rglob("*.md"))
        for p in ("migration/briefs", "migration/specs", "specs", ".specify/specs")
    )

    for path in task_files:
        checked += 1
        rel = str(path.relative_to(root))
        try:
            items = load_json(path)
        except Exception as e:
            fail(f"{rel}: unreadable JSON ({e})")
            continue
        for i, obj in enumerate(items):
            if not isinstance(obj, dict):
                fail(f"{rel}[{i}]: not an object")
                continue
            label = f"{rel}" if len(items) == 1 else f"{rel}[{i}]"
            if briefs_exist and not has_identity(obj):
                fail(
                    f"{label}: missing brief/story/unit identity ref (AD-S §S.6.1) "
                    "— set brief_id|story_id|unit_id"
                )
            if is_implement(obj) and truthy_replan(obj):
                fail(
                    f"{label}: IMPLEMENT worker must not re-plan (AD-S §S.6.3) "
                    "— clear replan flags; block + escalate"
                )
            supersedes = obj.get("supersedes") or obj.get("superseded_by") or obj.get("supersededBy")
            if supersedes and not (
                obj.get("plan_revision") or obj.get("planRevision")
            ):
                fail(
                    f"{label}: supersession requires plan_revision (AD-S §S.6.3)"
                )

    for path in plan_files:
        checked += 1
        rel = str(path.relative_to(root))
        if path.suffix == ".json":
            try:
                items = load_json(path)
            except Exception as e:
                fail(f"{rel}: unreadable JSON ({e})")
                continue
            for i, obj in enumerate(items):
                if not isinstance(obj, dict):
                    continue
                label = f"{rel}" if len(items) == 1 else f"{rel}[{i}]"
                status = str(obj.get("status") or "").lower()
                if status in {"superseded", "archived", "replaced"} or obj.get("superseded_by"):
                    if not (obj.get("plan_revision") or obj.get("planRevision")):
                        fail(f"{label}: superseded plan missing plan_revision")
        else:
            text = path.read_text(encoding="utf-8", errors="replace")
            if re.search(r"(?im)^status:\s*(superseded|archived|replaced)\b", text) or re.search(
                r"(?im)^superseded_by:\s*\S+", text
            ):
                if not re.search(r"(?im)^plan_revision:\s*\S+", text):
                    fail(f"{rel}: superseded plan.md missing plan_revision")

    if checked == 0:
        print("OK: no plan/task artifacts yet — §S.6 ordering lint idle")
        return 0
    if bad:
        print(f"SDD ordering FAILED ({checked} artifact(s) checked).", file=sys.stderr)
        return 1
    print(f"OK: SDD ordering (§S.6) passed ({checked} artifact(s) checked).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
