#!/usr/bin/env python3
"""M2 exit — speckit workflow actually ran (Operator 123401ZO §4).

A hand-written partition.json is a legal K4 input (Architect 123751ZA).
It is not a conformant M2 complete. dest-8 M2 bypassed ``specify workflow
run speckit``: ``spec.md`` existed, ``tasks.md`` did not, and
``k4_convert.py`` ran without ``--tasks`` so planning-defect checks sat
behind ``if tasks_text:``.

This gate must REFUSE dest-8 as it stands (missing ``tasks.md``). It
must also REFUSE a hand-authored ``tasks.md`` whose only provenance is a
worker-writable ``workflow-run.json`` (Architect ``170112ZA``: that
receipt is forgeable). Presence of ``tasks.md`` is not provenance.

Architect ``170540ZA``: hermes integration ``files: {}``. Provenance is
the official task log A-gate (``assert-card-performed.py``), not the
receipt.

This gate does not scrape write-sets from ``tasks.md`` (PATH_TOKEN
OBJECT). When ``tasks.md`` exists it invokes K4 with ``--tasks`` so
``K4_PLANNING_DEFECT`` can fire.

Exit 0: exactly one non-empty Spec Kit 0.16.1 ``tasks.md`` (via
``.specify/feature.json`` ``feature_directory``, else ``specs/*/tasks.md``),
no files under the copy tree, A-gate PASS on the official log, and
``k4_convert.py --partition … --tasks`` is clean.
Exit 1: missing/empty tasks.md, SPECIFY_SPECS_COPY_TREE, two Spec Kit
trees, A-gate REFUSE, missing partition, or planning defect.
Exit 2: usage.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

KERNEL = Path(__file__).resolve().parents[4] / "kernel"
if str(KERNEL) not in sys.path:
    sys.path.insert(0, str(KERNEL))

from k4_convert import convert_file, format_issues  # noqa: E402
from speckit_feature import find_tasks  # noqa: E402

PARTITION_CANDIDATES = (
    Path("evidence") / "partition.json",
    Path("evidence") / "briefs" / "partition.json",
)
PERFORMED = Path(__file__).resolve().parent / "assert-card-performed.py"


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def check_a_gate(log: Path | None, task_id: str | None) -> str:
    """Empty string = ok. Otherwise refuse reason."""
    argv = [sys.executable, str(PERFORMED)]
    if log is not None:
        argv.extend(["--log", str(log)])
    elif task_id:
        argv.append(task_id)
    else:
        return (
            "M2_SPECKIT_BYPASS: missing official-log A-gate "
            "(--log or HERMES_KANBAN_TASK; workflow-run.json is forgeable)"
        )
    proc = subprocess.run(argv, text=True, capture_output=True)
    blob = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        return "M2_SPECKIT_BYPASS: A-gate REFUSE: %s" % blob.strip()
    return ""


def find_partition(root: Path) -> Path | None:
    for rel in PARTITION_CANDIDATES:
        path = root / rel
        if path.is_file():
            return path
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root")
    ap.add_argument("--log", type=Path, help="official task log (A-gate)")
    ap.add_argument(
        "--task-id",
        default=os.environ.get("HERMES_KANBAN_TASK") or "",
        help="t_… (default HERMES_KANBAN_TASK)",
    )
    args = ap.parse_args(argv)
    root = Path(args.root)
    if not root.is_dir():
        print("FAIL: not a directory %s" % root, file=sys.stderr)
        return 2

    tasks, tasks_err = find_tasks(root)
    if tasks_err:
        return _fail(
            tasks_err
            + "; speckit-specify/plan/tasks did not produce the Spec Kit "
            "0.16.1 tasks.md; hand-written partition.json is not a "
            "conformant M2 complete; do not kanban_complete"
        )
    if not tasks:
        return _fail(
            "M2_SPECKIT_BYPASS: missing non-empty specs/*/tasks.md "
            "(speckit-specify/plan/tasks did not produce tasks.md; "
            "hand-written partition.json is not a conformant M2 complete; "
            "do not kanban_complete)"
        )
    if len(tasks) != 1:
        return _fail(
            "M2_SPECKIT_BYPASS: need exactly one non-empty tasks.md, found %s"
            % ",".join(str(p) for p in tasks)
        )
    tasks_path = tasks[0]
    a_err = check_a_gate(args.log, args.task_id or None)
    if a_err:
        return _fail(a_err)

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
