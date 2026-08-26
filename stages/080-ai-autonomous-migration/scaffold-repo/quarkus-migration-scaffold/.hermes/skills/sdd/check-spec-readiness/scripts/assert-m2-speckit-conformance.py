#!/usr/bin/env python3
"""M2 exit — speckit workflow actually ran (Operator 123401ZO §4).

A hand-written partition.json is a legal K4 input (Architect 123751ZA).
It is not a conformant M2 complete. dest-8 M2 bypassed ``specify workflow
run speckit``: ``spec.md`` existed, ``tasks.md`` did not, and
``k4_convert.py`` ran without ``--tasks`` so planning-defect checks sat
behind ``if tasks_text:``.

This gate must REFUSE dest-8 as it stands (missing ``tasks.md``). It does
not scrape write-sets from ``tasks.md`` (PATH_TOKEN OBJECT). When
``tasks.md`` exists it invokes K4 with ``--tasks`` so
``K4_PLANNING_DEFECT`` can fire.

Exit 0: exactly one non-empty ``.specify/specs/*/tasks.md`` and
``k4_convert.py --partition … --tasks`` is clean.
Exit 1: missing/empty tasks.md, missing partition, or planning defect.
Exit 2: usage.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

KERNEL = Path(__file__).resolve().parents[4] / "kernel"
if str(KERNEL) not in sys.path:
    sys.path.insert(0, str(KERNEL))

from k4_convert import convert_file, format_issues  # noqa: E402

PARTITION_CANDIDATES = (
    Path("evidence") / "partition.json",
    Path("evidence") / "briefs" / "partition.json",
)


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def find_tasks(root: Path) -> list[Path]:
    specs = root / ".specify" / "specs"
    if not specs.is_dir():
        return []
    out: list[Path] = []
    for path in sorted(specs.glob("*/tasks.md")):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if text.strip():
            out.append(path)
    return out


def find_partition(root: Path) -> Path | None:
    for rel in PARTITION_CANDIDATES:
        path = root / rel
        if path.is_file():
            return path
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root")
    args = ap.parse_args(argv)
    root = Path(args.root)
    if not root.is_dir():
        print("FAIL: not a directory %s" % root, file=sys.stderr)
        return 2

    tasks = find_tasks(root)
    if not tasks:
        looked = root / ".specify" / "specs" / "*" / "tasks.md"
        return _fail(
            "M2_SPECKIT_BYPASS: missing non-empty %s "
            "(specify workflow run speckit did not produce tasks.md; "
            "hand-written partition.json is not a conformant M2 complete; "
            "do not kanban_complete)"
            % looked
        )
    if len(tasks) != 1:
        return _fail(
            "M2_SPECKIT_BYPASS: need exactly one non-empty tasks.md, found %s"
            % ",".join(str(p) for p in tasks)
        )
    tasks_path = tasks[0]

    partition = find_partition(root)
    if partition is None:
        looked = " ".join(str(root / rel) for rel in PARTITION_CANDIDATES)
        return _fail("M2_SPECKIT_BYPASS: missing partition.json (looked %s)" % looked)

    _result, issues = convert_file(partition, tasks_path=tasks_path)
    if issues:
        print(format_issues(issues), file=sys.stderr)
        return _fail(
            "M2_SPECKIT_BYPASS: k4_convert --tasks %s failed "
            "(planning defects are process REFUSE, not a skip)"
            % tasks_path
        )
    print(
        "OK: M2 speckit conformance (tasks=%s partition=%s k4 --tasks clean)"
        % (tasks_path.relative_to(root), partition.relative_to(root))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
