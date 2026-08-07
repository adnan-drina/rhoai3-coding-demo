#!/usr/bin/env python3
"""O-CHARSEEDFIRST — seed missing Shape=create characterization *Test.java Targets.

Why
---
Qwen/OpenCode on S02-TC-UserRepositoryChar burned READ_THRASH (10r/3g/0m)
exploring `/projects/legacy` and siblings before creating the Target. Packet
already says O-CHARFIRSTMUT / O-CREATEFIRSTMUT; prose alone does not stop
explore-first. Seeding a minimal compilable shell makes the Target *exist*
so the first productive tool can be an edit/write of a real path.

O-CHARSEEDSURFACE (W4-768): refuse-char char_surface requires a real
``.member(`` call form against the unit's public surface. fail()-only shells
still FIRE after tip — seed must include at least one invocation token.

Migration-general: any characterization / src/test/**/*Test.java create task.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple

ROOT = Path(sys.argv[3] if len(sys.argv) > 3 else ".")
TASKS = Path(sys.argv[1]) if len(sys.argv) > 1 else None
TID = sys.argv[2] if len(sys.argv) > 2 else ""
HARNESS = Path(__file__).resolve().parent


def _task_body(tasks: Path, tid: str) -> str:
    try:
        sys.path.insert(0, str(HARNESS))
        from task_contract import task_heading_parts  # type: ignore

        _title, body = task_heading_parts(
            tasks.read_text(encoding="utf-8", errors="replace"), tid
        )
        return body or ""
    except Exception:
        return ""


def _owned_paths(tasks: Path, tid: str) -> list[str]:
    helper = HARNESS / "task-stage-paths.py"
    if not helper.is_file() or not tasks.is_file():
        return []
    try:
        out = subprocess.check_output(
            [sys.executable, str(helper), str(tasks), tid],
            text=True,
            stderr=subprocess.DEVNULL,
            cwd=str(ROOT),
        )
    except (subprocess.CalledProcessError, OSError):
        return []
    return [ln.strip() for ln in out.splitlines() if ln.strip()]


def _is_char_create(body: str, tid: str) -> bool:
    if re.search(r"(?i)-TC-|characteri[sz]", tid):
        return True
    if re.search(r"(?i)characteri[sz]", body):
        return True
    if re.search(r"(?im)^\*?\*?Shape\*?\*?\s*:\s*create\b", body) and re.search(
        r"src/test/.*Test\.java", body
    ):
        return True
    return False


def _pkg_and_class(rel: str) -> Tuple[Optional[str], Optional[str]]:
    rel = rel.replace("\\", "/")
    m = re.match(r"src/test/java/(.+)/([^/]+)Test\.java$", rel)
    if not m:
        return None, None
    return m.group(1).replace("/", "."), m.group(2) + "Test"


def _first_surface_member(unit_simple: str) -> str:
    """Best-effort first public method name from migration/staging (else save)."""
    stag = ROOT / "migration" / "staging"
    if stag.is_dir():
        hits = list(stag.rglob(f"{unit_simple}.java"))
        for hp in hits[:3]:
            try:
                text = hp.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            # skip comments roughly
            for m in re.finditer(
                r"(?m)^\s*(?:public\s+)?(?:[\w.<>,\[\]\s]+)\s+(\w+)\s*\(",
                text,
            ):
                name = m.group(1)
                if name in {unit_simple, "if", "for", "while", "switch", "return"}:
                    continue
                if name[0].islower():
                    return name
    return "save"


def _stub(pkg: str, cls: str) -> str:
    unit = cls[:-4] if cls.endswith("Test") else cls
    member = _first_surface_member(unit)
    # Local surface interface keeps the seed compilable before the real unit
    # is harvested, while still emitting `.member(` for char_surface refuse-char.
    return (
        f"package {pkg};\n\n"
        "import org.junit.jupiter.api.Test;\n\n"
        "/**\n"
        " * O-CHARSEEDFIRST / O-CHARSEEDSURFACE harness shell — worker replaces\n"
        " * with real characterization pins against the harvested unit.\n"
        " */\n"
        f"class {cls} {{\n"
        "    @FunctionalInterface\n"
        "    interface _CharSurfacePin {\n"
        f"        void {member}(Object arg);\n"
        "    }\n\n"
        "    @Test\n"
        "    void pendingCharacterizationMustExerciseUnitUnderTest() {\n"
        f"        _CharSurfacePin unit = arg -> {{ /* pin {unit}.{member} */ }};\n"
        f"        unit.{member}(null);\n"
        "        org.junit.jupiter.api.Assertions.fail(\n"
        '            "O-CHARSEEDFIRST: replace seed with real characterization");\n'
        "    }\n"
        "}\n"
    )


def main() -> int:
    if not TASKS or not TID:
        print(
            "usage: ensure-char-seed.py <tasks.md> <T-id> [root]",
            file=sys.stderr,
        )
        return 2
    body = _task_body(TASKS, TID)
    if not _is_char_create(body, TID):
        print(f"skip:{TID}:not-char-create")
        return 0
    paths = [
        p
        for p in _owned_paths(TASKS, TID)
        if p.endswith("Test.java") and "/test/" in p.replace("\\", "/")
    ]
    if not paths:
        print(f"skip:{TID}:no-test-target")
        return 0
    wrote = 0
    for rel in paths:
        dest = ROOT / rel
        if dest.is_file() and dest.stat().st_size > 0:
            print(f"exists:{rel}")
            continue
        pkg, cls = _pkg_and_class(rel)
        if not pkg or not cls:
            print(f"skip:{rel}:bad-path")
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(_stub(pkg, cls), encoding="utf-8")
        print(f"seeded:{rel}")
        wrote += 1
    print(f"charseed:{TID}:wrote={wrote}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
