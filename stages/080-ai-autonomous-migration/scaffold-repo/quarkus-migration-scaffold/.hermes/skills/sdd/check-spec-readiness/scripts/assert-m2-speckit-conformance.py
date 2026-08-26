#!/usr/bin/env python3
"""M2 exit — speckit workflow actually ran (Operator 123401ZO §4).

A hand-written partition.json is a legal K4 input (Architect 123751ZA).
It is not a conformant M2 complete. dest-8 M2 bypassed ``specify workflow
run speckit``: ``spec.md`` existed, ``tasks.md`` did not, and
``k4_convert.py`` ran without ``--tasks`` so planning-defect checks sat
behind ``if tasks_text:``.

This gate must REFUSE dest-8 as it stands (missing ``tasks.md``). It
must also REFUSE a hand-authored ``tasks.md`` with no successful
``specify workflow run speckit`` receipt (dest-9 M2: three red specify
runs, then LLM-authored tasks.md; Operator ``201929ZO``). Presence of
``tasks.md`` is not provenance.

This gate does not scrape write-sets from ``tasks.md`` (PATH_TOKEN
OBJECT). When ``tasks.md`` exists it invokes K4 with ``--tasks`` so
``K4_PLANNING_DEFECT`` can fire.

Exit 0: exactly one non-empty ``.specify/specs/*/tasks.md``, a matching
``evidence/receipts/speckit/workflow-run.json`` (producer
``specify-from-project.sh``, rc 0, digest of that tasks.md), and
``k4_convert.py --partition … --tasks`` is clean.
Exit 1: missing/empty tasks.md, missing/wrong receipt, missing partition,
or planning defect.
Exit 2: usage.
"""
from __future__ import annotations

import argparse
import hashlib
import json
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
RECEIPT_REL = Path("evidence") / "receipts" / "speckit" / "workflow-run.json"
LEGAL_PRODUCERS = frozenset({"specify-from-project.sh"})
RECEIPT_SCHEMA = "rhoai3.speckit-workflow-run/v1"


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


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def check_receipt(root: Path, tasks_path: Path) -> str:
    """Empty string = ok. Otherwise refuse reason."""
    path = root / RECEIPT_REL
    if not path.is_file():
        return (
            "M2_SPECKIT_BYPASS: missing %s "
            "(hand-authored tasks.md is dest-9 M2; presence is not provenance)"
            % RECEIPT_REL
        )
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return "M2_SPECKIT_BYPASS: unreadable speckit receipt: %s" % exc
    if not isinstance(doc, dict):
        return "M2_SPECKIT_BYPASS: speckit receipt is not an object"
    if str(doc.get("schema") or "") != RECEIPT_SCHEMA:
        return "M2_SPECKIT_BYPASS: speckit receipt schema %r" % doc.get("schema")
    producer = str(doc.get("producer") or "")
    if producer not in LEGAL_PRODUCERS:
        return (
            "M2_SPECKIT_BYPASS: speckit receipt producer %r is not %s"
            % (producer, ",".join(sorted(LEGAL_PRODUCERS)))
        )
    try:
        rc = int(doc.get("rc"))
    except (TypeError, ValueError):
        return "M2_SPECKIT_BYPASS: speckit receipt missing rc"
    if rc != 0:
        return "M2_SPECKIT_BYPASS: speckit receipt rc=%s (not a successful run)" % rc
    cmd = doc.get("cmd")
    cmd_s = " ".join(str(x) for x in cmd) if isinstance(cmd, list) else str(cmd or "")
    if "workflow" not in cmd_s or "run" not in cmd_s or "speckit" not in cmd_s:
        return "M2_SPECKIT_BYPASS: speckit receipt cmd is not workflow run speckit"
    want = sha256_file(tasks_path)
    got = str(doc.get("tasks_digest_sha256") or "")
    if got != want:
        return (
            "M2_SPECKIT_BYPASS: tasks.md digest %s != receipt %s "
            "(hand-edit after specify is dest-9)"
            % (want, got)
        )
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
    receipt_err = check_receipt(root, tasks_path)
    if receipt_err:
        return _fail(receipt_err)

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
