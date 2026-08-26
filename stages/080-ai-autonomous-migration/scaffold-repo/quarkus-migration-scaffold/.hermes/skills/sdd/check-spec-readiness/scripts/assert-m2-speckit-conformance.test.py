#!/usr/bin/env python3
"""dest-8 missing tasks.md REFUSE; hand-authored tasks.md REFUSE. Not dest."""
from __future__ import annotations

import hashlib
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


def write_receipt(root: Path, tasks: Path, producer: str = "specify-from-project.sh") -> None:
    digest = hashlib.sha256(tasks.read_bytes()).hexdigest()
    path = root / "evidence" / "receipts" / "speckit" / "workflow-run.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema": "rhoai3.speckit-workflow-run/v1",
                "cmd": ["specify", "workflow", "run", "speckit", "-i", "spec=x"],
                "rc": 0,
                "producer": producer,
                "tasks_rel": str(tasks.relative_to(root)),
                "tasks_digest_sha256": digest,
            }
        )
        + "\n",
        encoding="utf-8",
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
    for story in partition.get("stories") or []:
        if story.get("story_id") == "us1_greeting":
            story["dest_file"] = "src/main/java/com/demo/GreetingResource.java"
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
        tasks = spec / "tasks.md"
        tasks.write_text(covering, encoding="utf-8")
        (root / "evidence").mkdir()
        (root / "evidence" / "partition.json").write_text(
            json.dumps(partition) + "\n", encoding="utf-8"
        )
        proc = run(root)
        blob = proc.stdout + proc.stderr
        if proc.returncode != 1 or "presence is not provenance" not in blob:
            print(
                "FAIL: hand-authored tasks.md must REFUSE provenance: %s" % blob,
                file=sys.stderr,
            )
            return 1

        write_receipt(root, tasks, producer="compose-m4-verdict")
        proc = run(root)
        blob = proc.stdout + proc.stderr
        if proc.returncode != 1 or "producer" not in blob:
            print("FAIL: illegal producer must REFUSE: %s" % blob, file=sys.stderr)
            return 1

        write_receipt(root, tasks)
        proc = run(root)
        if proc.returncode != 0:
            print(
                "FAIL: covering tasks.md with helper receipt must exit 0: %s%s"
                % (proc.stdout, proc.stderr),
                file=sys.stderr,
            )
            return 1

        tasks.write_text(
            covering + "- [ ] `src/main/java/com/demo/Missing.java`\n",
            encoding="utf-8",
        )
        proc = run(root)
        blob = proc.stdout + proc.stderr
        if proc.returncode != 1:
            print("FAIL: edited tasks.md must REFUSE: %s" % blob, file=sys.stderr)
            return 1
        if "digest" not in blob and "K4_PLANNING_DEFECT" not in blob:
            print(
                "FAIL: edited tasks.md must name digest or planning defect: %s"
                % blob,
                file=sys.stderr,
            )
            return 1

    print("OK: assert-m2-speckit-conformance dest-8 + hand-author refuse")
    return 0


if __name__ == "__main__":
    sys.exit(main())
