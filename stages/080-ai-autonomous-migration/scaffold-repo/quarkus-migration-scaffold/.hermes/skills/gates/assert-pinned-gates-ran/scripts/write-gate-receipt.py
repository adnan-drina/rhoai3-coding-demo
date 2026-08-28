#!/usr/bin/env python3
"""Atomic gate-run receipt. M4 write_file of this path is fenced (F4).

Runners (this script, or a gate's own process) write
``evidence/receipts/gates/<gate>.json``. compose-m4-verdict consumes;
it does not author. Presence of ``ran: true`` under ``evidence/verdicts/``
is not a run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

RECEIPT_DIR = Path("evidence") / "receipts" / "gates"
REQUIRED = ("cmd", "argv", "rc", "input_digest", "producer")
COMPOSER = "compose-m4-verdict"


def input_digest(argv: list[str], extra: str = "") -> str:
    blob = json.dumps({"argv": argv, "extra": extra}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def receipt_gaps(doc: Any) -> list[str]:
    if not isinstance(doc, dict):
        return ["receipt is not an object"]
    gaps: list[str] = []
    for key in REQUIRED:
        if key not in doc:
            gaps.append("missing " + key)
    argv = doc.get("argv")
    if not isinstance(argv, list) or not argv:
        gaps.append("argv must be a non-empty list")
    elif any(not isinstance(x, str) or not str(x).strip() for x in argv):
        gaps.append("argv entries must be non-empty strings")
    rc = doc.get("rc")
    if isinstance(rc, bool) or not isinstance(rc, int):
        gaps.append("rc must be an int")
    producer = str(doc.get("producer") or "").strip()
    if not producer:
        gaps.append("producer missing")
    elif COMPOSER in producer:
        gaps.append("producer is the verdict composer")
    digest = str(doc.get("input_digest") or "").strip()
    if digest and len(digest) != 64:
        gaps.append("input_digest must be 64 hex chars")
    if not str(doc.get("task_id") or "").strip() and not str(doc.get("run_id") or "").strip():
        gaps.append("task_id or run_id required")
    cmd = str(doc.get("cmd") or "").strip()
    if not cmd:
        gaps.append("cmd missing")
    return gaps


def is_runner_receipt(doc: Any) -> bool:
    return not receipt_gaps(doc)


def write_receipt(
    root: Path,
    gate: str,
    *,
    argv: list[str],
    rc: int,
    producer: str,
    task_id: str = "",
    run_id: str = "",
) -> Path:
    gate = gate.strip()
    if not gate:
        raise ValueError("gate name required")
    argv_s = [str(a) for a in argv if str(a).strip()]
    cmd = " ".join(argv_s)
    doc: dict[str, Any] = {
        "gate": gate,
        "cmd": cmd,
        "argv": argv_s,
        "rc": int(rc),
        "input_digest": input_digest(argv_s),
        "producer": producer.strip(),
    }
    if task_id.strip():
        doc["task_id"] = task_id.strip()
    if run_id.strip():
        doc["run_id"] = run_id.strip()
    if not task_id.strip() and not run_id.strip():
        doc["run_id"] = "local"
    gaps = receipt_gaps(doc)
    if gaps:
        raise ValueError("invalid receipt: " + "; ".join(gaps))
    path = root / RECEIPT_DIR / (gate + ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path


def emit_script_receipt(
    root: Path,
    gate: str,
    rc: int,
    script_file: str,
    argv: list[str] | None = None,
) -> Path:
    """Runner receipt for a gate script that took ``--write-receipt``."""
    argv_s = [str(a) for a in (argv if argv is not None else sys.argv)]
    return write_receipt(
        Path(root),
        gate,
        argv=argv_s,
        rc=int(rc),
        producer=Path(script_file).name,
        task_id=os.environ.get("HERMES_KANBAN_TASK", ""),
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--gate", required=True)
    ap.add_argument("--rc", type=int, required=True)
    ap.add_argument("--producer", required=True)
    ap.add_argument("--task-id", default="")
    ap.add_argument("--run-id", default="")
    ap.add_argument("argv", nargs=argparse.REMAINDER)
    args = ap.parse_args(argv)
    rest = list(args.argv)
    if rest and rest[0] == "--":
        rest = rest[1:]
    if not rest:
        print("FAIL: pass the ran argv after --", file=sys.stderr)
        return 2
    try:
        path = write_receipt(
            args.root.resolve(),
            args.gate,
            argv=rest,
            rc=args.rc,
            producer=args.producer,
            task_id=args.task_id,
            run_id=args.run_id,
        )
    except ValueError as exc:
        print("FAIL: " + str(exc), file=sys.stderr)
        return 1
    print("OK: gate receipt " + str(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
