"""Serial migration roadmap after M2 (derived view, not a fourth sealed plan).

The work list remains the only plan. This document exposes known work,
dependencies, acceptance checks, and unresolved questions, and shows
M4 VERIFY plus M5 PREFLIGHT / DEPLOY / VALIDATE as planned milestones.
Planned rows never claim a candidate, receipt, or card id. Exactly one
task may be executable: the admitted next card from ``next_card``.
Parallel M3 execution stays deferred.
"""
from __future__ import annotations

import copy
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


_OUTCOME_ACCOUNTS_SCHEMA = "rhoai3.outcome-accounts-preview/v1"
_SNAPSHOT_KINDS = ("late-remainder", "synthetic")


def _oa_nonempty(value: object, label: str) -> str:
    if not isinstance(value, str) or value == "" or value != value.strip():
        raise ValueError("%s must be a nonempty string" % label)
    return value


def _oa_text(value: object, label: str) -> str:
    """Accept a string, including empty scenario text. Do not invent a value."""
    if not isinstance(value, str) or value != value.strip():
        raise ValueError("%s must be a string" % label)
    return value


def _oa_declaring_type(entry_point: object, item_id: str) -> str:
    def _bad() -> ValueError:
        return ValueError(
            "item %s entry point %r is not ep:<declaring type>#<member>:http" % (item_id, entry_point)
        )

    prefix = "ep:"
    suffix = ":http"
    if not isinstance(entry_point, str) or not entry_point.startswith(prefix) or not entry_point.endswith(suffix):
        raise _bad()
    body = entry_point[len(prefix):-len(suffix)]
    split = body.find("#")
    if split <= 0 or split >= len(body) - 1:
        raise _bad()
    declaring = body[:split]
    member = body[split + 1:]
    if not declaring or not member or declaring != declaring.strip() or member != member.strip():
        raise _bad()
    return declaring


def _oa_json(value: object, label: str) -> None:
    if value is None or isinstance(value, str):
        return
    if isinstance(value, bool):
        return
    if isinstance(value, int):
        return
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError("%s is not JSON-compatible" % label)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _oa_json(item, "%s[%d]" % (label, index))
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("%s has a non-string key" % label)
            _oa_json(item, "%s.%s" % (label, key))
        return
    raise ValueError("%s is not JSON-compatible" % label)


def _oa_provenance(provenance: dict) -> None:
    kind = provenance.get("snapshot_kind")
    if kind not in _SNAPSHOT_KINDS:
        raise ValueError("provenance.snapshot_kind must be late-remainder or synthetic")
    note = provenance.get("scope_note")
    if not isinstance(note, str) or note.strip() == "":
        raise ValueError("provenance.scope_note must be a nonempty string")
    if kind == "synthetic":
        construction = provenance.get("construction")
        if not isinstance(construction, str) or construction.strip() == "":
            raise ValueError("synthetic provenance requires a nonempty construction explanation")
        if provenance.get("observed_migration_event") is not False:
            raise ValueError("synthetic provenance requires observed_migration_event false")


def _oa_unresolved(rows: list) -> None:
    seen: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError("unresolved[%d] must be an object" % index)
        label = "unresolved[%d]" % index
        row_id = _oa_nonempty(row.get("id"), "%s id" % label)
        if row_id in seen:
            raise ValueError("duplicate unresolved id %s" % row_id)
        seen.add(row_id)
        reason = row.get("reason")
        if not isinstance(reason, str) or reason.strip() == "":
            raise ValueError("unresolved %s needs a nonempty reason" % row_id)


def _oa_items(items: list) -> dict[str, dict[str, str]]:
    by_id: dict[str, dict[str, str]] = {}
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError("worklist.items[%d] must be an object" % index)
        label = "worklist.items[%d]" % index
        if "id" not in item:
            raise ValueError("%s is missing id" % label)
        item_id = _oa_nonempty(item.get("id"), "%s id" % label)
        label = "item %s" % item_id
        if item_id in by_id:
            raise ValueError("duplicate item id %s" % item_id)
        for key in ("entry_point", "path", "kind", "category", "scenario", "security_mode"):
            if key not in item:
                raise ValueError("%s is missing %s" % (label, key))
        declaring = _oa_declaring_type(item.get("entry_point"), item_id)
        path = _oa_nonempty(item.get("path"), "%s path" % label)
        kind = _oa_nonempty(item.get("kind"), "%s kind" % label)
        if kind != "parity":
            raise ValueError("item %s kind %r is not supported mandatory HTTP parity" % (item_id, kind))
        category = _oa_nonempty(item.get("category"), "%s category" % label)
        if category != "mandatory":
            raise ValueError("item %s category %r is not mandatory" % (item_id, category))
        _oa_text(item.get("scenario"), "%s scenario" % label)
        _oa_nonempty(item.get("security_mode"), "%s security_mode" % label)
        by_id[item_id] = {"id": item_id, "path": path, "declaring_type": declaring}
    return by_id


def _oa_clusters(clusters: list, items_by_id: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    validated: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_members: dict[str, str] = {}
    for index, cluster in enumerate(clusters):
        if not isinstance(cluster, dict):
            raise ValueError("worklist.clusters[%d] must be an object" % index)
        label = "worklist.clusters[%d]" % index
        if "id" not in cluster:
            raise ValueError("%s is missing id" % label)
        cluster_id = _oa_nonempty(cluster.get("id"), "%s id" % label)
        if cluster_id in seen_ids:
            raise ValueError("duplicate cluster id %s" % cluster_id)
        seen_ids.add(cluster_id)
        kind = cluster.get("kind")
        if kind != "parity":
            raise ValueError("cluster %s kind %r is not supported HTTP parity" % (cluster_id, kind))
        status = cluster.get("status")
        if status != "open":
            raise ValueError("cluster %s status %r is not open" % (cluster_id, status))
        if "path" not in cluster:
            raise ValueError("cluster %s is missing path" % cluster_id)
        path = _oa_nonempty(cluster.get("path"), "cluster %s path" % cluster_id)
        write_set = cluster.get("write_set")
        if not isinstance(write_set, list):
            raise ValueError("cluster %s write_set must be a list" % cluster_id)
        copied_writes: list[str] = []
        for write_index, write_path in enumerate(write_set):
            copied_writes.append(_oa_nonempty(
                write_path, "cluster %s write_set[%d]" % (cluster_id, write_index),
            ))
        members = cluster.get("items")
        if not isinstance(members, list):
            raise ValueError("cluster %s items must be a list" % cluster_id)
        if not members:
            raise ValueError("cluster %s has no member obligations" % cluster_id)
        copied_members: list[str] = []
        seen_here: set[str] = set()
        for member in members:
            member_id = _oa_nonempty(member, "cluster %s member" % cluster_id)
            if member_id in seen_here:
                raise ValueError("duplicate membership of %s in cluster %s" % (member_id, cluster_id))
            seen_here.add(member_id)
            if member_id not in items_by_id:
                raise ValueError("cluster %s references unknown obligation %s" % (cluster_id, member_id))
            if member_id in seen_members:
                raise ValueError(
                    "duplicate membership of %s in cluster %s and cluster %s"
                    % (member_id, seen_members[member_id], cluster_id)
                )
            seen_members[member_id] = cluster_id
            copied_members.append(member_id)
        validated.append({
            "id": cluster_id,
            "path": path,
            "items": copied_members,
            "write_set": copied_writes,
        })
    for item_id in items_by_id:
        if item_id not in seen_members:
            raise ValueError("orphan obligation %s is not referenced by any cluster" % item_id)
    return validated


def _oa_group(items_by_id: dict[str, dict[str, str]], clusters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, list[str]]] = {}
    for cluster in clusters:
        types = sorted({items_by_id[item_id]["declaring_type"] for item_id in cluster["items"]})
        if len(types) != 1:
            raise ValueError(
                "cluster %s spans declaring types %s; refusing to divide it" % (cluster["id"], ", ".join(types))
            )
        outcome_id = "http-type:" + types[0]
        bucket = grouped.setdefault(outcome_id, {"obligation_ids": [], "cluster_ids": [], "paths": []})
        bucket["cluster_ids"].append(cluster["id"])
        for item_id in cluster["items"]:
            bucket["obligation_ids"].append(item_id)
            bucket["paths"].append(items_by_id[item_id]["path"])
        bucket["paths"].append(cluster["path"])
        bucket["paths"].extend(cluster["write_set"])
    outcomes: list[dict[str, Any]] = []
    for outcome_id in sorted(grouped):
        bucket = grouped[outcome_id]
        outcomes.append({
            "outcome_id": outcome_id,
            "obligation_ids": sorted(set(bucket["obligation_ids"])),
            "cluster_ids": sorted(set(bucket["cluster_ids"])),
            # Descriptive plan scope for this outcome. Not an edit grant.
            "plan_paths": sorted(set(bucket["paths"])),
            "parents": ["control:m2"],
            "assignee": "implementer",
        })
    return outcomes


def _oa_lineage(rows: list, outcomes: list[dict[str, Any]]) -> None:
    clusters_of = {row["outcome_id"]: set(row["cluster_ids"]) for row in outcomes}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError("lineage[%d] must be an object" % index)
        label = "lineage[%d]" % index
        for key in ("outcome_id", "cluster_id", "card_ids", "counts_as_addition"):
            if key not in row:
                raise ValueError("%s is missing %s" % (label, key))
        outcome_id = _oa_nonempty(row.get("outcome_id"), "%s outcome_id" % label)
        cluster_id = _oa_nonempty(row.get("cluster_id"), "%s cluster_id" % label)
        if outcome_id not in clusters_of:
            raise ValueError("lineage outcome %s is not a derived outcome" % outcome_id)
        if cluster_id not in clusters_of[outcome_id]:
            raise ValueError("lineage cluster %s is not a cluster of %s" % (cluster_id, outcome_id))
        card_ids = row.get("card_ids")
        if not isinstance(card_ids, list) or not card_ids:
            raise ValueError("lineage %s card_ids must list historical card ids" % outcome_id)
        for card_index, card_id in enumerate(card_ids):
            _oa_nonempty(card_id, "lineage %s card_ids[%d]" % (outcome_id, card_index))
        if row.get("counts_as_addition") is not False:
            raise ValueError(
                "lineage counts_as_addition must be false; this snapshot does not record an addition or an acceptance"
            )


def _oa_milestones(outcome_ids: list[str]) -> list[dict[str, Any]]:
    return [
        {"milestone_id": "assess:m4", "parents": list(outcome_ids), "assignee": "implementer"},
        {"milestone_id": "deliver:prepare", "parents": ["assess:m4"], "assignee": None},
        {"milestone_id": "deliver:push", "parents": ["deliver:prepare"], "assignee": None},
        {"milestone_id": "deliver:accept", "parents": ["deliver:push"], "assignee": None},
    ]


def _oa_counts(outcome_count: int) -> dict[str, int]:
    return {
        "baseline_behavior_outcomes": outcome_count,
        "measured_additions": 0,
        "accepted_current_outcomes": 0,
        "remaining_behavior_outcomes": outcome_count,
    }


def derive_outcome_accounts(
    worklist: dict,
    unresolved: list[dict],
    *,
    provenance: dict,
    lineage: list[dict],
) -> dict:
    """Project one supplied HTTP-parity remainder into an offline outcome account.

    Planning preview only: no board, mint, publication, or execution. The
    function reads its arguments and does not grant edits. Counts are the
    first snapshot of the obligations supplied here. Additions and accepted
    outcomes stay zero because this call has no prior plan and no acceptance
    ledger. Zero outcomes means nothing was supplied, not that a migration
    is complete.
    """
    if not isinstance(worklist, dict):
        raise ValueError("worklist must be an object")
    if "items" not in worklist or not isinstance(worklist.get("items"), list):
        raise ValueError("worklist.items must be a list")
    if "clusters" not in worklist or not isinstance(worklist.get("clusters"), list):
        raise ValueError("worklist.clusters must be a list")
    if not isinstance(unresolved, list):
        raise ValueError("unresolved must be a list")
    if not isinstance(lineage, list):
        raise ValueError("lineage must be a list")
    if not isinstance(provenance, dict):
        raise ValueError("provenance must be an object")
    worklist = copy.deepcopy(worklist)
    unresolved = copy.deepcopy(unresolved)
    provenance = copy.deepcopy(provenance)
    lineage = copy.deepcopy(lineage)
    _oa_provenance(provenance)
    _oa_unresolved(unresolved)
    items_by_id = _oa_items(worklist["items"])
    clusters = _oa_clusters(worklist["clusters"], items_by_id)
    outcomes = _oa_group(items_by_id, clusters)
    _oa_lineage(lineage, outcomes)
    _oa_json(unresolved, "unresolved")
    _oa_json(lineage, "lineage")
    _oa_json(provenance, "provenance")
    return {
        "schema": _OUTCOME_ACCOUNTS_SCHEMA,
        "planning_only": True,
        "coverage_scope": "provided-obligations-only",
        "outcomes": outcomes,
        "counts": _oa_counts(len(outcomes)),
        "unresolved": unresolved,
        "milestones": _oa_milestones([row["outcome_id"] for row in outcomes]),
        "lineage": lineage,
        "provenance": provenance,
    }
