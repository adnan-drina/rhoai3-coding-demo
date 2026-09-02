#!/usr/bin/env python3
"""Architect 202952ZA: copy tree is refuse even when feature.json exists."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

KERNEL = Path(__file__).resolve().parent
sys.path.insert(0, str(KERNEL))
from speckit_feature import copy_tree_refuse, find_tasks  # noqa: E402


def _fail(msg: str) -> int:
    print("FAIL: %s" % msg, file=sys.stderr)
    return 1


def _feature_json(root: Path, rel: str) -> None:
    specify = root / ".specify"
    specify.mkdir(parents=True, exist_ok=True)
    (specify / "feature.json").write_text(
        json.dumps({"feature_directory": rel}) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        feat = root / "specs" / "001-migrate-rest-service"
        feat.mkdir(parents=True)
        _feature_json(root, "specs/001-migrate-rest-service")
        (feat / "tasks.md").write_text("# Tasks\n- [ ] `pom.xml`\n", encoding="utf-8")
        tasks, err = find_tasks(root)
        if err or len(tasks) != 1:
            return _fail("clean feature.json tree must resolve: %s %s" % (tasks, err))

        copy = root / ".specify" / "specs" / "001-migrate-rest-service"
        copy.mkdir(parents=True)
        (copy / "spec.md").write_text("# spec\n", encoding="utf-8")
        tasks, err = find_tasks(root)
        if not err or "SPECIFY_SPECS_COPY_TREE" not in err:
            return _fail(
                "spec.md in copy tree with feature.json must REFUSE: %s %s"
                % (tasks, err)
            )
        if copy_tree_refuse(root) != err:
            return _fail("copy_tree_refuse must be the find_tasks reason")

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        plan = root / "specs" / "001-migrate-rest-service"
        plan.mkdir(parents=True)
        _feature_json(root, "specs/001-migrate-rest-service")
        (plan / "plan.md").write_text("# plan\n", encoding="utf-8")
        copy = root / ".specify" / "specs" / "001-migrate-rest-service"
        copy.mkdir(parents=True)
        (copy / "spec.md").write_text("# spec\n", encoding="utf-8")
        tasks, err = find_tasks(root)
        if tasks or "SPECIFY_SPECS_COPY_TREE" not in err:
            return _fail(
                "dest-21 split (spec.md copy, plan.md under specs/) must REFUSE: %s %s"
                % (tasks, err)
            )

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "specs" / "001-a").mkdir(parents=True)
        (root / ".specify" / "specs" / "001-a").mkdir(parents=True)
        (root / "specs" / "001-a" / "tasks.md").write_text("# Tasks\n- [ ] `pom.xml`\n")
        (root / ".specify" / "specs" / "001-a" / "tasks.md").write_text(
            "# Tasks\n- [ ] `pom.xml`\n"
        )
        tasks, err = find_tasks(root)
        if tasks or "SPECIFY_SPECS_COPY_TREE" not in err:
            return _fail(
                "dual trees without feature.json must REFUSE copy tree: %s %s"
                % (tasks, err)
            )

    print("OK: speckit_feature copy-tree refuse")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
