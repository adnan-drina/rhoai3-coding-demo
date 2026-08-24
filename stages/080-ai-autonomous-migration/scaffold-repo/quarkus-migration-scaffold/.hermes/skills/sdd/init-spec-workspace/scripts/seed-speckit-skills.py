#!/usr/bin/env python3
"""Copy speckit-* skills from specify-init output into the project skills tree.

Architect ``125450Z`` / Operator ``125618Z``: implementer must see
``speckit-specify`` on ``skills list`` after ``init-spec-workspace``.
Do **not** add user-root ``external_dirs``. ``speckit-implement`` is never copied.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

WANT = ("speckit-specify", "speckit-plan", "speckit-tasks", "speckit-analyze")
FORBID = frozenset({"speckit-implement"})


def _search_roots(human_home: str) -> list[Path]:
    roots: list[Path] = []
    for raw in (
        os.environ.get("HOME", ""),
        human_home,
        "/home/user",
    ):
        if not raw:
            continue
        p = Path(raw) / ".hermes" / "skills"
        if p not in roots:
            roots.append(p)
    return roots


def _discover(bases: list[Path]) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for base in bases:
        if not base.is_dir():
            continue
        for skill_md in base.rglob("SKILL.md"):
            parent = skill_md.parent
            name = parent.name
            if name in FORBID:
                continue
            if name in WANT and name not in found:
                found[name] = parent
    return found


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: seed-speckit-skills.py <workspace-root> [human-home]", file=sys.stderr)
        return 2
    root = Path(sys.argv[1]).resolve()
    human_home = sys.argv[2] if len(sys.argv) > 2 else "/home/user"
    dest = root / ".hermes" / "skills" / "sdd"
    dest.mkdir(parents=True, exist_ok=True)
    found = _discover(_search_roots(human_home))
    if "speckit-specify" not in found:
        print(
            "FAIL: speckit-specify SKILL.md not found under "
            + ", ".join(str(p) for p in _search_roots(human_home))
            + " — specify init --integration hermes did not install it",
            file=sys.stderr,
        )
        return 1
    for name in WANT:
        src = found.get(name)
        if src is None:
            print(f"WARN: {name} not found after specify init — skip", file=sys.stderr)
            continue
        target = dest / name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(src, target, dirs_exist_ok=False)
        print(f"seeded {name} → {target}", file=sys.stderr)
    specify = dest / "speckit-specify" / "SKILL.md"
    if not specify.is_file():
        print(f"FAIL: missing {specify} after copy", file=sys.stderr)
        return 1
    print(f"OK: speckit-specify seeded at {specify}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
