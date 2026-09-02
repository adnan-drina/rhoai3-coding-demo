#!/usr/bin/env python3
"""Stamp evidence/receipts/speckit/workflow-run.json after a successful specify.

Operator ``201929ZO`` / Lead:m2-conformance-gate-is-presence-not-provenance:
hand-authored tasks.md is dest-9 M2. Presence is not provenance. Only the
HOME=project helper may author this receipt.

Exit 0 always (stamping must not mask specify rc). No stamp when rc!=0,
argv is not workflow run speckit, or tasks.md is missing/empty.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

KERNEL = Path(__file__).resolve().parents[4] / "kernel"
if str(KERNEL) not in sys.path:
    sys.path.insert(0, str(KERNEL))

from speckit_feature import find_tasks  # noqa: E402

SCHEMA = "rhoai3.speckit-workflow-run/v1"
PRODUCER = "specify-from-project.sh"
RECEIPT_REL = Path("evidence") / "receipts" / "speckit" / "workflow-run.json"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def stamp(root: Path, rc: int, argv: list[str]) -> None:
    if rc != 0:
        return
    if "workflow" not in argv or "run" not in argv or "speckit" not in argv:
        return
    tasks, tasks_err = find_tasks(root)
    if tasks_err or len(tasks) != 1:
        return
    tasks_path = tasks[0]
    receipt = {
        "schema": SCHEMA,
        "cmd": ["specify", *argv],
        "rc": rc,
        "producer": PRODUCER,
        "tasks_rel": str(tasks_path.relative_to(root)),
        "tasks_digest_sha256": sha256_file(tasks_path),
    }
    out = root / RECEIPT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    if len(sys.argv) < 3:
        return 0
    root = Path(sys.argv[1])
    try:
        rc = int(sys.argv[2])
    except ValueError:
        return 0
    stamp(root, rc, sys.argv[3:])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
