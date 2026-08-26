#!/usr/bin/env python3
"""Operator 143706ZO: M4 producer + failed_floors schema. Not dest."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
GOLDEN = SKILL.parents[3]
SCHEMA = HERE / "assert-m4-verdict-schema.py"
SYNC = HERE / "assert-m4-verdict-schema-sync.py"
DEST8 = (
    GOLDEN
    / ".hermes"
    / "skills"
    / "gates"
    / "check-release-readiness"
    / "fixtures"
    / "complete-around"
    / "dest-8-m4-verdict.json"
)


def run(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args],
        text=True,
        capture_output=True,
    )


def main() -> int:
    skill_md = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    if "--skill compose-m4-verdict" not in skill_md:
        print("FAIL: SKILL.md must pin --skill compose-m4-verdict", file=sys.stderr)
        return 1
    if "failed_floors" not in skill_md:
        print("FAIL: SKILL.md must name failed_floors", file=sys.stderr)
        return 1
    if "evidence/receipts/gates/" not in skill_md:
        print("FAIL: SKILL.md must consume evidence/receipts/gates/", file=sys.stderr)
        return 1
    if "idle" not in skill_md.lower():
        print("FAIL: SKILL.md must fold failed-floor-as-idle", file=sys.stderr)
        return 1

    ready = (
        GOLDEN
        / ".hermes"
        / "skills"
        / "gates"
        / "check-release-readiness"
        / "SKILL.md"
    )
    ready_txt = ready.read_text(encoding="utf-8")
    if "compose-m4-verdict" not in ready_txt:
        print(
            "FAIL: check-release-readiness must name compose-m4-verdict as producer",
            file=sys.stderr,
        )
        return 1

    agents = GOLDEN / "AGENTS.md"
    if "compose-m4-verdict" not in agents.read_text(encoding="utf-8"):
        print("FAIL: AGENTS.md skill router must name compose-m4-verdict", file=sys.stderr)
        return 1

    proc = run(SYNC)
    if proc.returncode != 0:
        print("FAIL: schema sync: %s%s" % (proc.stdout, proc.stderr), file=sys.stderr)
        return 1

    if not DEST8.is_file():
        print("FAIL: missing dest-8 verdict fixture", file=sys.stderr)
        return 1
    proc = run(SCHEMA, str(DEST8))
    blob = proc.stdout + proc.stderr
    if proc.returncode != 1 or "failed_floors" not in blob:
        print("FAIL: dest-8 verdict must REFUSE missing failed_floors: %s" % blob, file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        honest = root / "honest.json"
        honest.write_text(
            json.dumps(
                {
                    "gate": "M4_VERDICT",
                    "phase": "M4",
                    "ran": True,
                    "verdict": "REFUSE",
                    "ship": False,
                    "failed_floors": ["check-product-tests"],
                    "floors": [
                        {
                            "name": "check-product-tests",
                            "rc": 1,
                            "idle": False,
                        }
                    ],
                    "reason": "AR-2.8 missing product-test families: boot",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        proc = run(SCHEMA, str(honest))
        if proc.returncode != 0:
            print(
                "FAIL: honest REFUSE + failed_floors must PASS: %s%s"
                % (proc.stdout, proc.stderr),
                file=sys.stderr,
            )
            return 1

        idle_fail = root / "idle-fail.json"
        idle_fail.write_text(
            json.dumps(
                {
                    "gate": "M4_VERDICT",
                    "phase": "M4",
                    "ran": True,
                    "verdict": "PROVISIONAL_ACCEPT",
                    "ship": False,
                    "failed_floors": [],
                    "floors": [
                        {
                            "name": "check-product-tests",
                            "rc": 1,
                            "idle": True,
                        }
                    ],
                    "reason": "AR-2.8 completion floor idle",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        proc = run(SCHEMA, str(idle_fail))
        blob = proc.stdout + proc.stderr
        if proc.returncode != 1 or "FAILED_FLOOR_AS_IDLE" not in blob:
            print("FAIL: idle-for-failed-floor must REFUSE: %s" % blob, file=sys.stderr)
            return 1

        accept_fail = root / "accept-fail.json"
        accept_fail.write_text(
            json.dumps(
                {
                    "gate": "M4_VERDICT",
                    "phase": "M4",
                    "ran": True,
                    "verdict": "PROVISIONAL_ACCEPT",
                    "ship": False,
                    "failed_floors": ["check-product-tests"],
                    "floors": [
                        {
                            "name": "check-product-tests",
                            "rc": 1,
                            "idle": False,
                        }
                    ],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        proc = run(SCHEMA, str(accept_fail))
        blob = proc.stdout + proc.stderr
        if proc.returncode != 1 or "ACCEPT_WITH_FAILED_FLOOR" not in blob:
            print("FAIL: ACCEPT + failed_floors must REFUSE: %s" % blob, file=sys.stderr)
            return 1

        genuine = root / "genuine-idle.json"
        genuine.write_text(
            json.dumps(
                {
                    "gate": "M4_VERDICT",
                    "phase": "M4",
                    "ran": True,
                    "verdict": "PROVISIONAL_ACCEPT",
                    "ship": False,
                    "failed_floors": [],
                    "floors": [
                        {
                            "name": "check-runnable-db-config",
                            "rc": 0,
                            "idle": True,
                        },
                        {
                            "name": "check-product-tests",
                            "rc": 0,
                            "idle": False,
                        },
                    ],
                    "reason": "AR-2.1 completion floor idle (no DB intent)",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        proc = run(SCHEMA, str(genuine))
        if proc.returncode != 0:
            print(
                "FAIL: genuine idle + rc 0 must PASS: %s%s"
                % (proc.stdout, proc.stderr),
                file=sys.stderr,
            )
            return 1

    print("OK: compose-m4-verdict producer + failed_floors schema")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
