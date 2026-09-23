"""Serial migration roadmap after M2 (derived view, not a fourth sealed plan).

The work list remains the only plan. This document exposes known work,
dependencies, acceptance checks, and unresolved questions, and shows
M4 VERIFY plus M5 PREFLIGHT / DEPLOY / VALIDATE as planned milestones.
Planned rows never claim a candidate, receipt, or card id. Exactly one
task may be executable: the admitted next card from ``next_card``.
Parallel M3 execution stays deferred.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from planner.canonical import digest, load_json, write_canonical
from planner.cards import CLOSE_ID, card_title, next_card
from planner.paths import (
    ADMISSION_RECEIPT,
    DECIDED_REPAIRS_RECEIPT,
    LOOP_ISSUED,
    LOOP_STEPS,
    SERIAL_ROADMAP,
    WORKLIST,
)
from planner.schema_lite import load_schema, validate
from planner.worklist import head_cluster

SCHEMA = "rhoai3.serial-roadmap/v1"
CLAIM_KEYS = (
    "card_id",
    "task_id",
    "candidate_sha",
    "candidate_sha256",
    "receipt_sha256",
    "git_sha",
    "mutations_xml_sha256",
    "pit_measurement",
    "close_card",
    "idempotency_key",
)
M5_MILESTONES = (
    ("PREFLIGHT", "M5 PREFLIGHT"),
    ("DEPLOY", "M5 DEPLOY"),
    ("VALIDATE", "M5 VALIDATE"),
)
M3_ACCEPTANCE = (
    "edit only this cluster write set",
    "run-verify then advance",
    "strict lexicographic measure decrease with no new mandatory obligation",
)
M4_ACCEPTANCE = (
    "paved-road-m4 in order",
    "compose-m4-verdict from measured exits",
    "kanban_request_review; never dest-dispatch M5",
)
M5_ACCEPTANCE = (
    "start-m5-delivery after closed M4 (eligibility-checked, dest-isolated)",
    "existing release contract plus pinned G-1 kill-ratio evidence",
)
SCHEMA_PATH = Path(__file__).resolve().parents[2] / "planning" / "schemas" / "serial-roadmap.schema.json"


def _optional_json(root: Path, rel: Path) -> dict[str, Any]:
    path = Path(root) / rel
    if not path.is_file():
        return {}
    try:
        doc = load_json(path)
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _m3_title(cluster: dict[str, Any], attempt: int) -> str:
    head = dict(cluster)
    head.setdefault("items", [])
    head.setdefault("write_set", [])
    try:
        return card_title(head, attempt)
    except (ValueError, KeyError, TypeError):
        return "M3 %s" % (cluster.get("id") or cluster.get("path") or "cluster")


def _strip_claims(row: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in row.items() if k not in CLAIM_KEYS}


def _open_clusters(worklist: dict[str, Any]) -> list[dict[str, Any]]:
    return [c for c in (worklist.get("clusters") or []) if isinstance(c, dict) and c.get("status") == "open"]


def _issued_task(root: Path, cluster_id: str) -> str:
    issued = _optional_json(root, LOOP_ISSUED)
    if str(issued.get("cluster") or issued.get("id") or "") != cluster_id:
        return ""
    task = str(issued.get("task_id") or "")
    return task if task.startswith("t_") else ""


def _reconciled(root: Path) -> list[dict[str, str]]:
    doc = _optional_json(root, DECIDED_REPAIRS_RECEIPT)
    out: list[dict[str, str]] = []
    for row in doc.get("rows") or []:
        if not isinstance(row, dict):
            continue
        status = str(row.get("status") or "")
        if status not in ("applied", "already-applied"):
            continue
        out.append({
            "id": str(row.get("id") or ""),
            "adr": str(row.get("adr") or ""),
            "status": status,
        })
    return out


def _unresolved(worklist: dict[str, Any], admission: dict[str, Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    status = str(admission.get("status") or "")
    if status and status != "ADMITTED":
        out.append({"class": "ADMISSION", "subject": status, "detail": "nothing mints until admission is ADMITTED"})
        for block in admission.get("blocks") or []:
            if isinstance(block, dict):
                out.append({
                    "class": str(block.get("class") or "BLOCK"),
                    "subject": str(block.get("subject") or ""),
                    "detail": str(block.get("detail") or ""),
                })
    for cid in worklist.get("deferred") or []:
        out.append({"class": "DEFERRED", "subject": str(cid), "detail": "human-owned cluster; loop stops when nothing else is left"})
    for cid in worklist.get("blocked_clusters") or []:
        out.append({"class": "BLOCKED", "subject": str(cid), "detail": "cluster cannot mint"})
    for row in worklist.get("unlocatable") or []:
        out.append({"class": "UNLOCATABLE", "subject": str(row), "detail": "obligation has no production write scope"})
    return out


def _planned_m5() -> list[dict[str, Any]]:
    rows = []
    depends = "closed M4 VERIFY"
    for stage, title in M5_MILESTONES:
        rows.append(_strip_claims({
            "class": "planned",
            "role": "M5",
            "stage": stage,
            "title": title,
            "admitted": False,
            "depends_on": [depends],
            "acceptance": list(M5_ACCEPTANCE),
        }))
        depends = title
    return rows


def compose_serial_roadmap(root: Path) -> dict[str, Any]:
    """Derive ``evidence/planning/serial-roadmap.json`` from M1/M2 evidence."""
    root = Path(root)
    worklist_path = root / WORKLIST
    admission_path = root / ADMISSION_RECEIPT
    if not worklist_path.is_file():
        raise FileNotFoundError(str(WORKLIST))
    if not admission_path.is_file():
        raise FileNotFoundError(str(ADMISSION_RECEIPT))
    worklist = load_json(worklist_path)
    admission = load_json(admission_path)
    if not isinstance(worklist, dict) or not isinstance(admission, dict):
        raise ValueError("work list and admission receipt must be objects")
    steps = _optional_json(root, LOOP_STEPS)
    admitted = str(admission.get("status") or "") == "ADMITTED"
    nxt = next_card(worklist, steps) if admitted else None
    executable: list[dict[str, Any]] = []
    if nxt is not None:
        row: dict[str, Any] = {
            "class": "executable",
            "role": "M4" if nxt.get("kind") == "close" else "M3",
            "kind": str(nxt.get("kind") or ""),
            "title": str(nxt.get("title") or ""),
            "admitted": True,
            "cluster_id": str(nxt.get("id") or ""),
            "item_count": len(nxt.get("items") or []),
            "acceptance": list(M4_ACCEPTANCE if nxt.get("kind") == "close" else M3_ACCEPTANCE),
        }
        task_id = _issued_task(root, str(nxt.get("id") or ""))
        if task_id:
            row["task_id"] = task_id
        executable.append(row)

    planned: list[dict[str, Any]] = []
    remaining = [c for c in _open_clusters(worklist) if c.get("id") and (nxt is None or c.get("id") != nxt.get("id"))]
    predecessor = str((nxt or {}).get("id") or "admission")
    for cluster in remaining:
        planned.append(_strip_claims({
            "class": "planned",
            "role": "M3",
            "kind": str(cluster.get("kind") or ""),
            "title": _m3_title(cluster, 1),
            "admitted": False,
            "cluster_id": str(cluster.get("id") or ""),
            "item_count": len(cluster.get("items") or []),
            "depends_on": [predecessor],
            "acceptance": list(M3_ACCEPTANCE),
        }))
        predecessor = str(cluster.get("id") or predecessor)
    if not (nxt and nxt.get("id") == CLOSE_ID):
        planned.append(_strip_claims({
            "class": "planned",
            "role": "M4",
            "stage": "VERIFY",
            "title": "M4 VERIFY",
            "admitted": False,
            "depends_on": ["empty work list", "runtime ready", "nothing deferred"],
            "acceptance": list(M4_ACCEPTANCE),
        }))
    planned.extend(_planned_m5())

    measure = worklist.get("measure") if isinstance(worklist.get("measure"), dict) else {}
    doc = {
        "schema": SCHEMA,
        "worklist_sha256": digest(worklist),
        "admission_digest": str(admission.get("receipt_digest") or digest({k: v for k, v in admission.items() if k != "receipt_digest"})),
        "admission_status": str(admission.get("status") or ""),
        "parallel_execution": "deferred",
        "note": (
            "The work list remains the only plan. This document exposes serial "
            "scope after M2. Planned milestones do not claim a candidate, receipt, or card id."
        ),
        "known_work": {
            "tuple": list(measure.get("tuple") or []),
            "known": bool(measure.get("known")),
            "mandatory_incidents": measure.get("mandatory_incidents"),
            "compile_errors": measure.get("compile_errors"),
            "failing_tests": measure.get("failing_tests"),
            "parity_mismatches": measure.get("parity_mismatches"),
            "open_clusters": len(_open_clusters(worklist)),
            "head": str((head_cluster(worklist) or {}).get("id") or worklist.get("head") or ""),
            "order_policy": str(worklist.get("order_policy") or "build → config → compile → incident → test → parity"),
        },
        "executable": executable,
        "planned": planned,
        "unresolved": _unresolved(worklist, admission),
        "reconciled": _reconciled(root),
    }
    errors = validate(doc, load_schema(SCHEMA_PATH))
    if errors:
        raise ValueError("serial-roadmap schema: " + "; ".join(errors[:8]))
    claimed = [k for row in planned for k in CLAIM_KEYS if k in row]
    if claimed:
        raise ValueError("planned milestones must not claim %s" % sorted(set(claimed)))
    if len(executable) > 1:
        raise ValueError("serial roadmap admits at most one executable task")
    write_canonical(root / SERIAL_ROADMAP, doc)
    return doc
