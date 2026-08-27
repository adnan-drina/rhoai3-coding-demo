#!/usr/bin/env python3
"""Worker-facing skill scripts must be named in SKILL.md or reachable from one.

Architect 150114ZA: unreferenced-script is a defect only if not reachable
from a named entrypoint (rNN_*.py via run-composite.sh is not a defect).
Operator 145553ZO: internals matching import/stem of a named script are
not the 1 true positive.

Not dest-apply. Does not kanban.
"""
from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path

TEST_NAME = re.compile(
    r"(?:^test_|_test\.py$|\.test\.py$|\.selftest\.py$|-selftest\.py$|_selftest\.py$"
    r"|\.test\.sh$|-selftest\.sh$|_selftest\.sh$|\.selftest\.sh$)"
)
RULE_NAME = re.compile(r"^r\d+_")
SKILL_ROOT_DEFAULT = (
    Path(__file__).resolve().parents[1] / "skills"
)


def _is_worker_script(path: Path) -> bool:
    if path.suffix not in {".py", ".sh"}:
        return False
    return not TEST_NAME.search(path.name)


def _named_in_skill(skill_md: str, skill_dir: Path, path: Path) -> bool:
    rel = path.relative_to(skill_dir).as_posix()
    return path.name in skill_md or rel in skill_md


def _reachable_text(src: str, candidate: Path) -> bool:
    if candidate.name in src:
        return True
    stem = candidate.stem
    if ("import %s" % stem) in src or ("from %s " % stem) in src:
        return True
    if ("from %s import" % stem) in src:
        return True
    if ("from lib.%s" % stem) in src or ("lib.%s" % stem) in src:
        return True
    if ("/%s" % candidate.name) in src:
        return True
    return False


def unnamed_scripts(skills_root: Path) -> list[str]:
    out: list[str] = []
    for skill_md_path in sorted(skills_root.glob("*/*/SKILL.md")):
        skill_dir = skill_md_path.parent
        scripts_dir = skill_dir / "scripts"
        if not scripts_dir.is_dir():
            continue
        skill_md = skill_md_path.read_text(encoding="utf-8", errors="replace")
        files = [p for p in scripts_dir.rglob("*") if p.is_file() and _is_worker_script(p)]
        named = {p.name for p in files if _named_in_skill(skill_md, skill_dir, p)}
        reachable = set(named)
        changed = True
        while changed:
            changed = False
            for p in files:
                if p.name not in reachable:
                    continue
                src = p.read_text(encoding="utf-8", errors="replace")
                for q in files:
                    if q.name in reachable:
                        continue
                    if _reachable_text(src, q):
                        reachable.add(q.name)
                        changed = True
                    elif RULE_NAME.match(q.name) and p.name == "run-composite.sh":
                        reachable.add(q.name)
                        changed = True
        for p in files:
            if p.name not in reachable:
                out.append((skill_dir.relative_to(skills_root) / "scripts" / p.relative_to(scripts_dir)).as_posix())
    return out


def _fixture_unnamed_is_detected() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "migration" / "orphan-skill"
        scripts = root / "scripts"
        scripts.mkdir(parents=True)
        (root / "SKILL.md").write_text("# Orphan\n\nRun `scripts/named.py`.\n", encoding="utf-8")
        (scripts / "named.py").write_text("print(0)\n", encoding="utf-8")
        (scripts / "hidden.py").write_text("print(1)\n", encoding="utf-8")
        found = unnamed_scripts(Path(tmp))
        if "migration/orphan-skill/scripts/hidden.py" not in found:
            raise AssertionError("fixture must REFUSE hidden.py: %s" % found)
        if "migration/orphan-skill/scripts/named.py" in found:
            raise AssertionError("named.py must be reachable: %s" % found)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--skills-root", type=Path, default=SKILL_ROOT_DEFAULT)
    args = ap.parse_args(argv)
    try:
        _fixture_unnamed_is_detected()
    except AssertionError as exc:
        print("FAIL: %s" % exc, file=sys.stderr)
        return 1
    found = unnamed_scripts(args.skills_root)
    if found:
        print("FAIL: unreferenced worker scripts:", file=sys.stderr)
        for item in found:
            print("  %s" % item, file=sys.stderr)
        return 1
    print("OK: every worker-facing skill script is named or reachable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
