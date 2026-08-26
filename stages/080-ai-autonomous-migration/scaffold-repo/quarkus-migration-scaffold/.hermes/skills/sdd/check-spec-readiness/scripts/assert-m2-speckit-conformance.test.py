#!/usr/bin/env python3
"""Operator 123401ZO §4: dest-8 missing tasks.md must REFUSE. Not dest."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "assert-m2-speckit-conformance.py"
SKILL = HERE.parent
DEST8 = SKILL / "fixtures" / "m2-speckit-bypass-dest8"
ALIGNED = SKILL / "fixtures" / "partition-dest6-aligned"


def run(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(root)],
        text=True,
        capture_output=True,
    )


def main() -> int:
    proc = run(DEST8)
    blob = proc.stdout + proc.stderr
    if proc.returncode != 1:
        print("FAIL: dest-8 missing tasks.md must exit 1: %s" % blob, file=sys.stderr)
        return 1
    if "M2_SPECKIT_BYPASS" not in blob or "tasks.md" not in blob:
        print("FAIL: dest-8 must name M2_SPECKIT_BYPASS/tasks.md: %s" % blob, file=sys.stderr)
        return 1

    partition = json.loads(
        (ALIGNED / "evidence" / "partition.json").read_text(encoding="utf-8")
    )
    covering = "\n".join(
        [
            "# Tasks",
            "- [ ] `pom.xml`",
            "- [ ] `src/main/resources/application.properties`",
            "- [ ] `src/main/java/com/demo/Greeting.java`",
            "- [ ] `src/main/java/com/demo/GreetingResource.java`",
            "- [ ] `src/test/java/com/demo/GreetingResourceTest.java`",
            "",
        ]
    )
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        spec = root / ".specify" / "specs" / "001-migrate-rest-service"
        spec.mkdir(parents=True)
        (spec / "spec.md").write_text("# migrate rest service\n", encoding="utf-8")
        (spec / "tasks.md").write_text(covering, encoding="utf-8")
        (root / "evidence").mkdir()
        (root / "evidence" / "partition.json").write_text(
            json.dumps(partition) + "\n", encoding="utf-8"
        )
        proc = run(root)
        if proc.returncode != 0:
            print(
                "FAIL: covering tasks.md must exit 0: %s%s"
                % (proc.stdout, proc.stderr),
                file=sys.stderr,
            )
            return 1

        (spec / "tasks.md").write_text(
            covering + "- [ ] `src/main/java/com/demo/Missing.java`\n",
            encoding="utf-8",
        )
        proc = run(root)
        blob = proc.stdout + proc.stderr
        if proc.returncode != 1 or "K4_PLANNING_DEFECT" not in blob:
            print(
                "FAIL: extra tasks.md path must be K4_PLANNING_DEFECT: %s" % blob,
                file=sys.stderr,
            )
            return 1

    print("OK: assert-m2-speckit-conformance dest-8 refuse + covering pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
