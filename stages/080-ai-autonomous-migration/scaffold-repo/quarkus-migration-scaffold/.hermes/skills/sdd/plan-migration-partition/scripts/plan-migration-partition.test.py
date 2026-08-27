#!/usr/bin/env python3
"""Operator 143201ZO: producer skill + heading coverage. Not dest."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
SYNC = HERE / "assert-partition-schema-sync.py"
HEADINGS = HERE / "assert-m2-story-headings.py"
GOLDEN = SKILL.parents[3]


def run(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args],
        text=True,
        capture_output=True,
    )


def main() -> int:
    skill_md = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    if "--skill plan-migration-partition" not in skill_md:
        print("FAIL: SKILL.md must pin --skill plan-migration-partition", file=sys.stderr)
        return 1
    if "speckit-specify" not in skill_md:
        print("FAIL: SKILL.md must name speckit-specify as a Hermes skill", file=sys.stderr)
        return 1
    if "speckit-plan" not in skill_md or "speckit-tasks" not in skill_md:
        print("FAIL: SKILL.md must name speckit-plan and speckit-tasks", file=sys.stderr)
        return 1
    if "files: {}" not in skill_md and "files:{}" not in skill_md:
        print(
            "FAIL: SKILL.md must name hermes.manifest files:{} "
            "(Architect 170540ZA)",
            file=sys.stderr,
        )
        return 1
    if "kanban_block" not in skill_md:
        print("FAIL: SKILL.md must name kanban_block when speckit cannot run", file=sys.stderr)
        return 1
    if "specify-from-project.sh" in skill_md and "workflow run speckit" in skill_md:
        print(
            "FAIL: SKILL.md must not prescribe specify-from-project.sh "
            "workflow run speckit as the M2 dispatch (hermes files:{})",
            file=sys.stderr,
        )
        return 1
    if "```bash\nspecify workflow run speckit\n```" in skill_md:
        print(
            "FAIL: SKILL.md must not prescribe the bare specify form as the run",
            file=sys.stderr,
        )
        return 1
    if "```bash\nspecify workflow run speckit -i spec=" in skill_md:
        print(
            "FAIL: SKILL.md must not PATH-lookup specify (dest-9 shadow)",
            file=sys.stderr,
        )
        return 1
    if "k4_convert.py" not in skill_md or "k4_mint.py" not in skill_md:
        print("FAIL: SKILL.md must name k4_convert.py and k4_mint.py", file=sys.stderr)
        return 1
    if "k4_*.py" not in skill_md and "reverse-engineer" not in skill_md:
        print("FAIL: SKILL.md must tell workers not to read k4_*.py", file=sys.stderr)
        return 1
    if "legacy_source" not in skill_md:
        print("FAIL: SKILL.md must name legacy_source for HTTP stories", file=sys.stderr)
        return 1
    if "dest_file" not in skill_md or "K4_DEST_FILE" not in skill_md:
        print("FAIL: SKILL.md must name dest_file / K4_DEST_FILE for HTTP stories", file=sys.stderr)
        return 1

    ready = GOLDEN / ".hermes" / "skills" / "sdd" / "check-spec-readiness" / "SKILL.md"
    ready_txt = ready.read_text(encoding="utf-8")
    if "plan-migration-partition" not in ready_txt:
        print(
            "FAIL: check-spec-readiness must name plan-migration-partition as producer",
            file=sys.stderr,
        )
        return 1

    agents = GOLDEN / "AGENTS.md"
    if "plan-migration-partition" not in agents.read_text(encoding="utf-8"):
        print("FAIL: AGENTS.md skill router must name plan-migration-partition", file=sys.stderr)
        return 1

    proc = run(SYNC)
    if proc.returncode != 0:
        print("FAIL: schema sync: %s%s" % (proc.stdout, proc.stderr), file=sys.stderr)
        return 1

    aligned = (
        GOLDEN
        / ".hermes"
        / "skills"
        / "sdd"
        / "check-spec-readiness"
        / "fixtures"
        / "partition-dest6-aligned"
    )
    covering = "\n".join(
        [
            "# Tasks",
            "## Phase 1: Setup (Shared Infrastructure)",
            "- [ ] T001 Author `pom.xml`",
            "## Phase 3: User Story 1 - Greeting (Priority: P1)",
            "- [ ] T012 [US1] Create GreetingResource",
            "",
        ]
    )
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        spec = root / ".specify" / "specs" / "001-migrate"
        spec.mkdir(parents=True)
        (spec / "tasks.md").write_text(covering, encoding="utf-8")
        (root / "evidence").mkdir()
        src = aligned / "evidence" / "partition.json"
        (root / "evidence" / "partition.json").write_text(
            src.read_text(encoding="utf-8"), encoding="utf-8"
        )
        proc = run(HEADINGS, str(root))
        if proc.returncode != 0:
            print(
                "FAIL: dest-6 aligned headings must PASS: %s%s"
                % (proc.stdout, proc.stderr),
                file=sys.stderr,
            )
            return 1

        (spec / "tasks.md").write_text(
            covering + "\n## Phase 4: User Story 2 - Extra\n- [ ] T020 [US2] extra\n",
            encoding="utf-8",
        )
        proc = run(HEADINGS, str(root))
        blob = proc.stdout + proc.stderr
        if proc.returncode != 1 or "STORY_HEADING_MISMATCH" not in blob:
            print("FAIL: extra User Story 2 must REFUSE: %s" % blob, file=sys.stderr)
            return 1

        (spec / "tasks.md").write_text(
            "# Tasks\n## Phase 3: User Story 1 - Greeting\n- [ ] T012 [US1] x\n",
            encoding="utf-8",
        )
        proc = run(HEADINGS, str(root))
        blob = proc.stdout + proc.stderr
        if proc.returncode != 1 or "setup" not in blob.lower():
            print("FAIL: missing Setup heading must REFUSE: %s" % blob, file=sys.stderr)
            return 1

    print("OK: plan-migration-partition producer + heading coverage")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
