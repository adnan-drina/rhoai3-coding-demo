"""Native cooperative control for the outcome board (outcome-board/v2).

Hermes Kanban is the ONE task lifecycle authority: task identity and state,
run history, dependencies, claims, review and rework, dispatch and crash
recovery are the pinned runtime's own (tasks, task_runs, task_links, the
gateway dispatcher, request_review / request_changes / block / complete).
This module is the small migration-specific adapter the architect review of
2026-09-27 retains (tmp/native-hermes-review-20260927/NATIVE-SOLUTION-REVIEW.md):

  1. deterministic publication and read-back of the plan's nodes and bounded
     revisions through native operations (planner/native_publish.py);
  2. validation of a requested native action against the task's attached
     contract, its current native run, the baseline and candidate, scope,
     evidence and the semantic repair budget (the pre_tool_call hook,
     kernel/native_gate.py and advance.py through _outcome_bridge);
  3. domain verdicts and evidence recorded ON THE BOARD: native comments
     (``[native-control] {json}`` records), attachments (plan revisions, task
     contracts, held candidates, assessments) and native run metadata; a
     read-only progress projection.

There is no second store, no service, no reconciler and no intent table. A
record is keyed; a replayed step finds its key and does not repeat an effect.

Trust boundary (stated with every claim): native Kanban uses a cooperative
local-user model. The worker's own user can alter kanban.db, the attachments
and these records; nothing here is tamper-resistant against worker code
(the earlier protected-writer requirement F1 is amended for v2 runs by the
user's decision of 2026-09-27). Worker-produced build/test/parity receipts
are trusted subject to binding and consistency checks (measurement trust
``cooperative-receipts``). The migration acceptance criteria are unchanged.

Semantics that differ from outcome-board/v1 on purpose:

  M3   one native task per outcome; a rejected attempt or a reviewer's
       request_changes is another native RUN of the same task. The
       implementer hands an accepted outcome to review; the reviewer completes
       it (the domain gate below) or requests changes.
  M4   means "verification ACCEPTED". A measured REFUSE is kept as evidence
       on its run; the same M4 task gains the necessary repairs as
       prerequisites (repair -> M4) and waits (kanban_block kind=dependency);
       native promotion resumes it. Only an accepted, candidate-bound M4
       releases M5, whose stages depend on it natively.
  M5   PREFLIGHT -> DEPLOY -> VALIDATE are native tasks created at M2 under
       M4; a push is recovered by read-back of the remote, never repeated.
"""
from __future__ import annotations

import base64
import fcntl
import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

from planner.outcome_checks import (AMEND_LIMIT, AMEND_MAX_FILES, CAUSE_CLASSES, DELIVERY_OK_VERDICTS, HOLD_MAX_BYTES,
                                    MAX_ASSESSMENT_GENERATIONS, OWNER_DEFECT, VERDICT, Refusal, _covers, _git,
                                    _is_product, _read_json, _unit_kind, changed_product_paths, commit_product_tree,
                                    git_commits_after, load_worklist, norm_rel, open_obligations, owner_repair_id,
                                    owner_repair_revision, planned_cluster_id, refuse_revision, repair_evidence_gaps,
                                    requirement_measurement, stage_evidence_facts)
from planner.outcome_graph import CONTROL_M2, IMPL, brief_document, plan_digest

KEY_VERSION = "v2"
ROLE_PREFIX = {"repair": "outcome", "assess": "assess", "deliver": "deliver"}
PREFIX_ROLE = {v: k for k, v in ROLE_PREFIX.items()}
M2_KEY = "m2-plan"
RECORD = "[native-control]"
CONTRACT = "contract.json"
CONTRACT_SCHEMA = "rhoai3.native-contract/v1"
PLAN_SCHEMA = "rhoai3.native-plan/v1"
PLAN_NAME = re.compile(r"^plan\.r(\d+)\.json$")
REVIEWER = "reviewer"
PROTECTED_DIRS = ("verification/outcome-board/", ".hermes/", ".git/")
LOCK = Path("verification") / "native-board" / "publish.lock"
MAX_RETRIES = 2
WORKSPACE = "dir:/projects/modernized"


# ---------------------------------------------------------------------------
# identity
# ---------------------------------------------------------------------------

def native_key(run_id: str, node: dict[str, Any]) -> str:
    return "%s:%s:%s:%s" % (ROLE_PREFIX[node["role"]], KEY_VERSION, run_id, node["outcome_id"])


def parse_key(key: str | None) -> tuple[str, str, str] | None:
    """(role, run id, outcome id) of a v2 node key; None for anything else
    (M1/M2 control cards, serial-loop cards, outcome-board/v1 keys)."""
    parts = str(key or "").split(":", 3)
    if len(parts) != 4 or parts[1] != KEY_VERSION or parts[0] not in PREFIX_ROLE or not parts[2] or not parts[3]:
        return None
    return PREFIX_ROLE[parts[0]], parts[2], parts[3]


def canonical_bytes(doc: Any) -> bytes:
    return (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def contract_doc(plan: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    """The task's attached contract: the brief (membership, checks, lineage),
    its native identity, budget family and the paths an owner repair may
    reach. Descriptive and immutable once attached; ownership that a later
    revision moves is read from the latest plan revision, never from here."""
    doc = brief_document(plan, node)
    doc.update({
        "schema": CONTRACT_SCHEMA,
        "native_key": native_key(plan["run_id"], node),
        "stage": node.get("stage") or "",
        "budget": dict(node.get("budget") or {}),
        "repair_paths": list(node.get("repair_paths") or []),
        "repair_scenarios": list(node.get("repair_scenarios") or []),
        "control": "native-cooperative",
        "note": "Descriptive. Product edits are granted per issued cluster (native_gate.py issue), never by this file.",
    })
    return doc


def native_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """The initial revision as native control publishes it: the M5 stages are
    ASSIGNED at creation (their native parent, the accepted M4, holds them;
    there are no stage grants). Deterministic; the digest is recomputed."""
    out = dict(plan)
    out["nodes"] = [dict(n, assignee=IMPL) if n.get("role") == "deliver" else dict(n) for n in plan["nodes"]]
    out["control"] = "native-cooperative"
    out.pop("digest", None)
    out["digest"] = plan_digest(out)
    return out


def plan_attachment(plan: dict[str, Any], added: list[str]) -> dict[str, Any]:
    """The revision document attached to the board: the plan and the digest
    of the contract of every node this revision introduces."""
    nodes = {n["outcome_id"]: n for n in plan["nodes"]}
    return {"schema": PLAN_SCHEMA, "revision": int(plan["revision"]), "plan": plan,
            "contracts": {oid: sha256(canonical_bytes(contract_doc(plan, nodes[oid]))) for oid in sorted(added)}}


# ---------------------------------------------------------------------------
# the board as the adapter reads it
# ---------------------------------------------------------------------------

class Board:
    """Read side over one native board (KanbanNative or FakeNative), plus the
    keyed record writer. Everything here is derived from native state."""

    def __init__(self, native: Any, *, author: str | None = None):
        self.native = native
        self.author = author if author is not None else (os.environ.get("HERMES_PROFILE") or "").strip()

    # -- tasks -----------------------------------------------------------------
    def task(self, task_id: str) -> dict[str, Any] | None:
        return self.native.task(task_id) if task_id else None

    def node_of(self, task_id: str) -> tuple[str, str, str] | None:
        t = self.task(task_id)
        return parse_key(t.get("idempotency_key")) if t else None

    def is_m2(self, task_id: str) -> bool:
        t = self.task(task_id)
        return bool(t and t.get("idempotency_key") == M2_KEY)

    def m2_task(self) -> str:
        rows = [r for r in self.native.by_key(M2_KEY) if r["status"] != "archived"]
        return rows[0]["id"] if len(rows) == 1 else ""

    def run_tasks(self, run_id: str) -> dict[str, dict[str, Any]]:
        """outcome id -> native row, every v2 node of this run (archived included)."""
        out: dict[str, dict[str, Any]] = {}
        for prefix in ROLE_PREFIX.values():
            for r in self.native.tasks_with_key_prefix("%s:%s:%s:" % (prefix, KEY_VERSION, run_id)):
                parsed = parse_key(r["idempotency_key"])
                if parsed:
                    out.setdefault(parsed[2], r)
        return out

    def task_of(self, run_id: str, node: dict[str, Any]) -> str:
        live = [r for r in self.native.by_key(native_key(run_id, node)) if r["status"] != "archived"]
        return live[0]["id"] if len(live) == 1 else ""

    # -- attachments -------------------------------------------------------------
    def attachment(self, task_id: str, name: str) -> tuple[bytes, dict[str, Any]] | None:
        rows = [a for a in self.native.attachments(task_id) if a["filename"] == name]
        if not rows:
            return None
        if len(rows) > 1:
            raise Refusal("ATTACHMENT_AMBIGUOUS", "%s carries %d attachments named %s" % (task_id, len(rows), name))
        try:
            return Path(rows[0]["stored_path"]).read_bytes(), rows[0]
        except OSError as exc:
            raise Refusal("ATTACHMENT_UNREADABLE", "%s %s: %s" % (task_id, name, exc)) from exc

    def contract(self, task_id: str) -> dict[str, Any]:
        got = self.attachment(task_id, CONTRACT)
        if got is None:
            raise Refusal("CONTRACT_MISSING", "%s carries no %s" % (task_id, CONTRACT))
        try:
            doc = json.loads(got[0])
        except ValueError as exc:
            raise Refusal("CONTRACT_CORRUPT", "%s %s: %s" % (task_id, CONTRACT, exc)) from exc
        t = self.task(task_id) or {}
        if doc.get("schema") != CONTRACT_SCHEMA or doc.get("native_key") != t.get("idempotency_key"):
            raise Refusal("CONTRACT_FOREIGN", "%s's contract names %r" % (task_id, doc.get("native_key")))
        return doc

    # -- plan revisions ------------------------------------------------------------
    def revisions(self, run_id: str) -> dict[int, tuple[str, dict[str, Any]]]:
        """revision -> (task that carries it, document). Two different
        documents for one revision refuse PLAN_FORKED."""
        holders = [self.m2_task()] + [r["id"] for r in self.run_tasks(run_id).values()]
        out: dict[int, tuple[str, dict[str, Any]]] = {}
        for tid in [h for h in holders if h]:
            for a in self.native.attachments(tid):
                m = PLAN_NAME.match(str(a["filename"]))
                if not m:
                    continue
                try:
                    doc = json.loads(Path(a["stored_path"]).read_bytes())
                except (OSError, ValueError) as exc:
                    raise Refusal("PLAN_CORRUPT", "%s %s: %s" % (tid, a["filename"], exc)) from exc
                if not isinstance(doc, dict) or doc.get("schema") != PLAN_SCHEMA or not isinstance(doc.get("plan"), dict):
                    raise Refusal("PLAN_CORRUPT", "%s %s is not a native plan revision" % (tid, a["filename"]))
                if doc["plan"].get("run_id") != run_id:
                    continue
                n = int(m.group(1))
                if n in out and out[n][1]["plan"].get("digest") != doc["plan"].get("digest"):
                    raise Refusal("PLAN_FORKED", "revision %d exists twice with different digests (%s, %s)" % (n, out[n][0], tid))
                out.setdefault(n, (tid, doc))
        return out

    def plan(self, run_id: str) -> dict[str, Any]:
        revs = self.revisions(run_id)
        if not revs:
            raise Refusal("PLAN_MISSING", "no native plan revision is attached for run %s" % run_id)
        top = max(revs)
        if sorted(revs) != list(range(1, top + 1)):
            raise Refusal("PLAN_GAP", "revisions %s are not a contiguous chain" % sorted(revs))
        for n in range(2, top + 1):
            if int(revs[n][1]["plan"].get("parent_revision") or 0) != n - 1:
                raise Refusal("PLAN_GAP", "revision %d does not follow %d" % (n, n - 1))
        plan = revs[top][1]["plan"]
        if plan_digest(plan) != plan.get("digest"):
            raise Refusal("PLAN_DIGEST", "revision %d digest does not cover its content" % top)
        return plan

    def contract_digests(self, run_id: str) -> dict[str, str]:
        out: dict[str, str] = {}
        for _n, (_tid, doc) in sorted(self.revisions(run_id).items()):
            for oid, digest in (doc.get("contracts") or {}).items():
                out.setdefault(oid, digest)
        return out

    # -- records -------------------------------------------------------------------
    def records(self, task_id: str, kind: str | None = None) -> list[dict[str, Any]]:
        """The domain records on a task, oldest first; a key is recorded once
        (the first occurrence wins). Each carries its board-wide comment id."""
        seen: set[str] = set()
        out: list[dict[str, Any]] = []
        for c in self.native.comment_rows(task_id):
            body = str(c.get("body") or "")
            if not body.startswith(RECORD + " "):
                continue
            try:
                doc = json.loads(body[len(RECORD) + 1:])
            except ValueError:
                continue
            if not isinstance(doc, dict) or not doc.get("key") or doc["key"] in seen:
                continue
            seen.add(doc["key"])
            doc["_id"] = int(c["id"])
            if kind is None or doc.get("kind") == kind:
                out.append(doc)
        return out

    def record(self, task_id: str, kind: str, key: str, **doc: Any) -> dict[str, Any]:
        """Write one keyed record; an existing key is returned unchanged."""
        for r in self.records(task_id):
            if r["key"] == key:
                return r
        body = dict(doc, kind=kind, key=key, v=1)
        self.native.comment(task_id, "%s %s" % (RECORD, json.dumps(body, sort_keys=True, separators=(",", ":"))),
                            self.author)
        got = next((r for r in self.records(task_id) if r["key"] == key), None)
        if got is None:
            raise Refusal("RECORD_LOST", "the record %s on %s did not read back" % (key, task_id))
        return got


def board_for(root: Path, native: Any = None) -> Board:
    if native is None:
        from planner.outcome_native import KanbanNative, default_db_path
        db = default_db_path()
        native = KanbanNative(db, hermes=(os.environ.get("HERMES_BIN") or "hermes").split(),
                              env=dict(os.environ, HERMES_KANBAN_DB=db) if db else None)
    return Board(native)


# ---------------------------------------------------------------------------
# run identity and the plan node of a task
# ---------------------------------------------------------------------------

def _gate(root: Path) -> None:
    from planner.outcome_protocol import execution_gate, select_protocol
    sel = select_protocol(root)
    if not sel.native:
        raise Refusal("PROTOCOL_NOT_NATIVE", "this run selects %s" % sel.protocol)
    g = execution_gate(root, sel)
    if g:
        raise Refusal(g[0][0], g[0][1])


def _node(plan: dict[str, Any], oid: str) -> dict[str, Any] | None:
    return next((n for n in plan.get("nodes") or [] if n["outcome_id"] == oid), None)


def node_context(board: Board, task_id: str) -> tuple[str, str, str, dict[str, Any], dict[str, Any]]:
    """(role, run id, outcome id, latest plan, node) of a published task."""
    parsed = board.node_of(task_id)
    if parsed is None:
        raise Refusal("NOT_A_NODE", "%s is not an outcome-board/v2 node" % task_id)
    role, run_id, oid = parsed
    plan = board.plan(run_id)
    node = _node(plan, oid)
    if node is None or node.get("role") != role:
        raise Refusal("NODE_UNKNOWN", "%s (%s) is not in the current plan revision" % (task_id, oid))
    return role, run_id, oid, plan, node


def live_run(board: Board, task_id: str, run_id: int) -> dict[str, Any]:
    t = board.task(task_id)
    if t is None:
        raise Refusal("RUN_FOREIGN_TASK", "%s is not on the board" % task_id)
    if t.get("status") != "running" or int(t.get("current_run_id") or 0) != int(run_id) or not run_id:
        raise Refusal("RUN_STALE", "%s is %s with run %s; the caller holds run %s"
                      % (task_id, t.get("status"), t.get("current_run_id"), run_id))
    return t


def owned(plan: dict[str, Any], node: dict[str, Any]) -> set[str]:
    oid = node["outcome_id"]
    return set(node.get("obligations") or []) | {ob for ob, o in (plan.get("ownership") or {}).items() if o == oid}


def _product_tree(root: Path) -> str:
    from planner.canonical import product_tree_sha256
    return product_tree_sha256(root)


def _head(root: Path) -> str:
    p = _git(root, "rev-parse", "HEAD")
    return p.stdout.strip() if p.returncode == 0 else ""


# ---------------------------------------------------------------------------
# the semantic repair budget (native runs + domain records, per family)
# ---------------------------------------------------------------------------

def family_spent(board: Board, run_id: str, plan: dict[str, Any], key: str) -> int:
    """Rejected attempts plus reviewer change requests across every task of
    one budget family (an owner, its follow-ups and its owner repairs share
    one key). Quota waits, crashes, timeouts and dependency waits spend
    nothing: they are neither reject records nor changes_requested runs."""
    if not key:
        return 0
    tasks = board.run_tasks(run_id)
    spent = 0
    for n in plan.get("nodes") or []:
        if n.get("role") != "repair" or str((n.get("budget") or {}).get("key") or "") != key:
            continue
        row = tasks.get(n["outcome_id"])
        if not row:
            continue
        spent += len(board.records(row["id"], "reject"))
        spent += sum(1 for r in board.native.runs(row["id"]) if r.get("outcome") == "changes_requested")
    return spent


def budget_state(board: Board, run_id: str, plan: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    b = node.get("budget") or {}
    key, limit = str(b.get("key") or ""), int(b.get("limit") or 0)
    spent = family_spent(board, run_id, plan, key)
    return {"key": key, "limit": limit, "spent": spent, "exhausted": bool(limit) and spent >= limit}


# ---------------------------------------------------------------------------
# issue: the run-bound scope of THIS native run
# ---------------------------------------------------------------------------

def _allowed_paths(node: dict[str, Any], worklist: dict[str, Any] | None, own: set[str]) -> tuple[str, list[str]]:
    """The ONE open cluster this outcome may edit now, and its write set."""
    if node.get("role") != "repair" or worklist is None:
        return "", []
    for c in worklist.get("clusters") or []:
        if not isinstance(c, dict) or c.get("status") != "open":
            continue
        if own & set(c.get("items") or []) or c.get("id") in set(node.get("clusters") or []):
            return str(c["id"]), sorted(str(p) for p in c.get("write_set") or [])
    return "", []


def _open_pending(board: Board, task_id: str) -> dict[str, Any] | None:
    pend = None
    for r in board.records(task_id):
        if r["kind"] == "pending":
            pend = r
        elif r["kind"] in ("reject", "accept-commit", "accept-aborted") and pend is not None:
            pend = None
        elif r["kind"] == "restore" and pend is not None and r.get("closes_pending"):
            pend = None
    return pend


def _accept_records(board: Board, task_id: str) -> list[dict[str, Any]]:
    return [r for r in board.records(task_id) if r["kind"] in ("accept-commit", "accept-evaluated")]


def _rework_paths(root: Path, board: Board, task_id: str) -> list[str]:
    """After a reviewer's request_changes: the product paths this task's own
    accepted commits changed (git diff-tree), bounded."""
    paths: set[str] = set()
    for r in board.records(task_id, "accept-commit"):
        commit = str(r.get("commit") or "")
        got = changed_product_paths(root, commit + "^1", commit) if commit else None
        paths |= set(got or [])
    return sorted(paths)[:AMEND_MAX_FILES]


def _changes_requested_since_accept(board: Board, task_id: str) -> bool:
    runs = board.native.runs(task_id)
    last_change = max((int(r["id"]) for r in runs if r.get("outcome") == "changes_requested"), default=0)
    if not last_change:
        return False
    last_accept_run = max((int(r.get("run") or 0) for r in _accept_records(board, task_id)), default=0)
    return last_change > last_accept_run


def _owner_hold_pending(root: Path, board: Board, run_id: str, plan: dict[str, Any], task_id: str) -> str:
    """The owner repair a held candidate of this task still waits on ('' when
    none). Recovers an interrupted publication of that repair first."""
    for h in board.records(task_id, "owner-hold"):
        fid = str(h.get("repair") or "")
        node = _node(plan, fid)
        if node is None:
            # the hold was recorded, the revision not yet attached: finish it
            _publish_owner_repair(root, board, run_id, plan, h)
            plan = board.plan(run_id)
            node = _node(plan, fid)
        tid = board.task_of(run_id, node) if node else ""
        t = board.task(tid) if tid else None
        if not t or t.get("status") != "done":
            # finish an interrupted publication (task, contract, links); every step is looked up first
            from planner.native_publish import publish_revision
            publish_revision(root, board, plan, added=[fid], holder=task_id)
            return fid
    return ""


def repair_waiting(board: Board, run_id: str, plan: dict[str, Any], task_id: str) -> str:
    """The owner repair a held candidate of this task waits on and that is
    not done yet ('' when none). Read-only."""
    for h in board.records(task_id, "owner-hold"):
        node = _node(plan, str(h.get("repair") or ""))
        tid = board.task_of(run_id, node) if node else ""
        if not tid or (board.task(tid) or {}).get("status") != "done":
            return str(h.get("repair") or "")
    return ""


def issue(root: Path, board: Board, *, task_id: str, run_id: int, claim_lock: str = "") -> dict[str, Any]:
    """The scope of this native run: the one open cluster (or planned unit,
    owner repair unit, rework unit) of the task's outcome, the baseline it is
    measured against and the budget it spends from. Recorded as an ``issue``
    record on the task; loop tools read its projection (issued.json)."""
    root = Path(root)
    _gate(root)
    t = live_run(board, task_id, run_id)
    if claim_lock and t.get("claim_lock") and t["claim_lock"] != claim_lock:
        raise Refusal("RUN_STALE", "the claim lock does not match the native claim")
    role, run, oid, plan, node = node_context(board, task_id)
    if t.get("assignee") != IMPL:
        raise Refusal("ISSUE_UNASSIGNED", "%s is assigned %r; only the implementer's run is issued" % (task_id, t.get("assignee")))
    board.contract(task_id)                                     # the attached contract is this task's
    undone = [p for p in t.get("parents") or [] if (board.task(p) or {}).get("status") != "done"]
    if undone:
        raise Refusal("ISSUE_PARENT_UNDONE", "%s runs before its prerequisites %s are done" % (task_id, ", ".join(undone[:4])))
    tree, head = _product_tree(root), _head(root)
    if role == "deliver":
        m4 = m4_acceptance(root, board, run, plan)
        if not m4["accepted"]:
            raise Refusal("ISSUE_M4_NOT_ACCEPTED", "M5 runs only on an accepted verification: %s" % m4["why"])
        if m4["candidate"] != tree:
            raise Refusal("ISSUE_STALE_CANDIDATE", "M4 accepted candidate %s; the tree is now %s (candidate drift)"
                          % (m4["candidate"][:12], tree[:12]))
    budget = budget_state(board, run, plan, node) if role == "repair" else {"key": "", "limit": 0, "spent": 0, "exhausted": False}
    if role == "repair":
        waiting = _owner_hold_pending(root, board, run, plan, task_id)
        if waiting:
            raise Refusal("OWNER_REPAIR_PENDING", "%s waits on the repair %s of its owner; end this run with "
                                                  "kanban_block kind=dependency" % (oid, waiting))
        if budget["exhausted"]:
            raise Refusal("ISSUE_BUDGET_EXHAUSTED", "%s spent %d of %d (rejected attempts and change requests, cumulative "
                          "across runs); kanban_block kind=needs_input naming the outcome" % (budget["key"], budget["spent"], budget["limit"]))
        # a commit made by a worker that died before recording it is recovered from git history first
        recover_accept(root, board, task_id=task_id, skip_run=run_id)
    pending = _open_pending(board, task_id)
    committed = commit_product_tree(root, head) if head else ""
    if committed and tree != committed and not (pending and pending.get("candidate") == tree):
        raise Refusal("ISSUE_BASELINE_DRIFT", "the product tree differs from HEAD %s and is not the retained candidate of %s; "
                      "unexplained edits are not blessed" % (head[:12], oid))
    worklist, why = load_worklist(root)
    if role == "repair" and worklist is None:
        raise Refusal("ISSUE_" + why, "an outcome is issued against the measured work list")
    cluster, allowed, unit = "", [], None
    if role == "repair":
        own = owned(plan, node)
        cluster, allowed = _allowed_paths(node, worklist, own)
        if not cluster and node.get("repair_paths"):
            cluster = planned_cluster_id(oid)
            allowed = sorted(node["repair_paths"])[:AMEND_MAX_FILES]
            unit = {"refusal": "", "paths": allowed, "basis": "owner repair"}
        elif not cluster and (node.get("planned_units") or node.get("requirements")):
            from planner.outcome_graph import planned_unit_grant
            g = planned_unit_grant(node, plan.get("requirements") or [], exists=lambda rel: (root / rel).exists(),
                                   cluster_open=False)
            unit = dict(g)
            if not g.get("refusal"):
                cluster = planned_cluster_id(oid)
                allowed = sorted(g.get("paths") or [])
        if not cluster and _changes_requested_since_accept(board, task_id):
            paths = _rework_paths(root, board, task_id)
            if paths:
                cluster = "rework:%s:%d" % (oid, run_id)
                allowed = paths
                unit = {"refusal": "", "paths": paths, "basis": "reviewer requested changes"}
        if cluster:
            allowed = sorted(set(allowed) | amended_paths(board, task_id, cluster))
    seq = len([r for r in board.records(task_id, "issue") if int(r.get("run") or 0) == int(run_id)]) + 1
    rec = board.record(task_id, "issue", "issue:%d:%d" % (run_id, seq), run=int(run_id), seq=seq, outcome_id=oid,
                       role=role, cluster=cluster, allowed_paths=allowed, baseline_commit=head, baseline_tree=tree,
                       budget_key=budget["key"], revision=int(plan["revision"]))
    return {"issue_id": seq, "task_id": task_id, "run_id": int(run_id), "outcome_id": oid, "role": role,
            "cluster": cluster, "allowed_paths": allowed, "budget": budget, "retained_candidate": bool(pending),
            "planned_unit": (dict(unit, owed=unit.get("owed") or [], bounds=unit.get("bounds") or {},
                                  kind=_unit_kind(node)) if unit else None),
            "held_candidate": bool(board.records(task_id, "owner-hold")) and not board.records(task_id, "restore-held"),
            "run": run, "baseline_commit": head, "baseline_tree": tree, "claimed_control": False,
            "control": "native-cooperative", "record": rec["key"],
            "amendments": [{"path": a["path"], "reason": a["reason"], "locus": a["locus"], "evidence": a.get("evidence") or {}}
                           for a in board.records(task_id, "amend") if a.get("cluster") == cluster] if cluster else []}


def active_issue(board: Board, task_id: str, run_id: int) -> dict[str, Any]:
    """The latest issue of THIS native run, revalidated against the board."""
    live_run(board, task_id, run_id)
    rows = [r for r in board.records(task_id, "issue") if int(r.get("run") or 0) == int(run_id)]
    if not rows:
        raise Refusal("ISSUE_MISSING", "no issue for %s run %s; run python3 .hermes/kernel/native_gate.py --root . issue "
                                       "after the claim" % (task_id, run_id))
    return rows[-1]


def amended_paths(board: Board, task_id: str, cluster: str) -> set[str]:
    return {str(a["path"]) for a in board.records(task_id, "amend") if a.get("cluster") == cluster}


def amend(root: Path, board: Board, *, task_id: str, run_id: int, cluster: str, rel: str, row: dict[str, Any]) -> dict[str, Any]:
    """Scope amendment (amend-scope.py validated evidence and locus): the same
    bounds as before, then a keyed ``amend`` record and a fresh issue."""
    iss = active_issue(board, task_id, run_id)
    rel = norm_rel(rel)
    if str(iss.get("cluster") or "") != cluster:
        raise Refusal("AMEND_FOREIGN_CLUSTER", "the issue for this run is cluster %r, not %r" % (iss.get("cluster"), cluster))
    if rel in set(iss.get("allowed_paths") or []):
        return {"path": rel, "already": True, "allowed_paths": iss["allowed_paths"]}
    if not _is_product(rel) or rel == "pom.xml" or (rel.startswith("src/test/") and not rel.endswith((".properties", ".yaml", ".yml"))):
        raise Refusal("AMEND_PATH", "%s is not a path an amendment may reach" % rel)
    if len(str(row.get("reason") or "").strip()) < 12 or not str(row.get("locus") or "").strip():
        raise Refusal("AMEND_UNEVIDENCED", "an amendment carries a reason and the locus the validator established")
    changed = changed_product_paths(root, str(iss.get("baseline_commit") or ""), only=[rel])
    if changed is None or changed:
        raise Refusal("AMEND_ALREADY_EDITED", "%s has already been edited; an amendment authorizes a change before it happens" % rel)
    prior = [a for a in board.records(task_id, "amend") if a.get("cluster") == cluster]
    if len(prior) >= AMEND_LIMIT:
        raise Refusal("AMEND_LIMIT", "cluster %s already carries %d amendment(s) (limit %d)" % (cluster, len(prior), AMEND_LIMIT))
    allowed = sorted(set(iss.get("allowed_paths") or []) | {rel})
    if len(allowed) > AMEND_MAX_FILES:
        raise Refusal("AMEND_OVERSIZE", "%d files exceed the unit bound %d" % (len(allowed), AMEND_MAX_FILES))
    board.record(task_id, "amend", "amend:%s:%s" % (cluster, rel), cluster=cluster, path=rel, run=int(run_id),
                 reason=str(row.get("reason") or "")[:500], locus=str(row.get("locus") or "")[:500], evidence=row.get("evidence") or {})
    seq = int(iss.get("seq") or 1) + len(prior) + 1
    board.record(task_id, "issue", "issue:%d:%d:amend:%s" % (run_id, seq, sha256(rel.encode())[:12]),
                 **{k: v for k, v in iss.items() if k not in ("kind", "key", "v", "_id", "allowed_paths", "seq")},
                 seq=seq, allowed_paths=allowed)
    return {"path": rel, "already": False, "allowed_paths": allowed, "issue_id": seq, "amendments": len(prior) + 1}


# ---------------------------------------------------------------------------
# hook checks
# ---------------------------------------------------------------------------

def check_write(board: Board, *, task_id: str, run_id: int, rel_paths: list[str]) -> None:
    """A product write outside this run's issued scope refuses; harness state
    is never tool-written."""
    for rel in rel_paths:
        r = norm_rel(rel)
        if any(r == d.rstrip("/") or r.startswith(d) for d in PROTECTED_DIRS):
            raise Refusal("STORE_WRITE_REFUSED", "%s is harness state; only its own entry points write it" % r)
    product = [r for r in (norm_rel(x) for x in rel_paths) if _is_product(r)]
    if not product:
        return
    iss = active_issue(board, task_id, run_id)
    allowed = set(iss.get("allowed_paths") or [])
    for r in product:
        if r not in allowed:
            raise Refusal("WRITE_OUTSIDE_ISSUE", "%s is not in the issued scope %s (%s)"
                          % (r, iss.get("cluster") or "(none)", ", ".join(sorted(allowed)) or "no product edits"))


def outcome_acceptance(root: Path, board: Board, task_id: str, plan: dict[str, Any], node: dict[str, Any]) -> tuple[bool, str]:
    """Is this repair outcome accepted ON THE CURRENT TREE? The latest
    acceptance record says so, it was measured on exactly this product tree,
    and no obligation the outcome owns is open in the measured work list."""
    recs = _accept_records(board, task_id)
    if not recs or not recs[-1].get("outcome_accepted"):
        return False, "no accepted measurement is recorded for %s" % node["outcome_id"]
    tree = _product_tree(root)
    if recs[-1].get("tree") != tree:
        return False, "%s was accepted on tree %s; the tree is now %s" % (node["outcome_id"], str(recs[-1].get("tree"))[:12], tree[:12])
    wl, why = load_worklist(root)
    if wl is None:
        return False, "completion is judged against the measured work list (%s)" % why
    still = sorted(open_obligations(wl) & owned(plan, node))
    if still:
        return False, "%s still owns open %s" % (node["outcome_id"], ", ".join(still[:5]))
    return True, "accepted on %s" % tree[:12]


def m4_acceptance(root: Path, board: Board, run_id: str, plan: dict[str, Any]) -> dict[str, Any]:
    """The M4 the delivery stages are bound to: its task, its latest
    assessment, and whether that assessment is an accepted verdict."""
    bind = ""
    for n in plan.get("nodes") or []:
        if n.get("role") == "deliver" and n.get("stage") == "prepare":
            bind = str((n.get("binding") or {}).get("assessment") or "")
    node = _node(plan, bind) if bind else None
    tid = board.task_of(run_id, node) if node else ""
    rec = latest_assessment(board, tid) if tid else None
    verdict = str((rec or {}).get("verdict") or "")
    ok = verdict in DELIVERY_OK_VERDICTS
    return {"task": tid, "assessment": bind, "verdict": verdict, "candidate": str((rec or {}).get("candidate") or ""),
            "accepted": ok, "done": bool(tid and (board.task(tid) or {}).get("status") == "done"),
            "why": "" if ok else ("verdict %s" % (verdict or "unrecorded"))}


def m4_closure(root: Path, native: Any = None) -> dict[str, Any] | None:
    """The M4 closure an outcome-board/v2 run delivers from (m5_delivery):
    the M4 task done on an accepted verdict."""
    board = board_for(Path(root), native)
    run_id = run_id_of(Path(root), board)
    try:
        plan = board.plan(run_id)
    except Refusal:
        return None
    m4 = m4_acceptance(Path(root), board, run_id, plan)
    if not m4["done"] or not m4["accepted"]:
        return None
    return {"closed": True, "card": m4["task"], "verdict": m4["verdict"], "assessment": m4["assessment"]}


def run_id_of(root: Path, board: Board) -> str:
    """The run of this destination: the factory declaration's run id, else
    the key of the M2 plan revision."""
    decl = _read_json(Path(root) / "run-budget.json")
    rid = str((decl or {}).get("run_id") or "") if isinstance(decl, dict) else ""
    if rid:
        return rid
    m2 = board.m2_task()
    for a in board.native.attachments(m2) if m2 else []:
        if PLAN_NAME.match(str(a["filename"])):
            try:
                return str(json.loads(Path(a["stored_path"]).read_bytes())["plan"]["run_id"])
            except (OSError, ValueError, KeyError, TypeError):
                continue
    return ""


def check_terminator(root: Path, board: Board, *, task_id: str, run_id: int, kind: str, profile: str,
                     audit_green: Callable[[], bool]) -> dict[str, Any] | None:
    """The domain decision on a native terminator of a v2 task. None: this
    task is neither the M2 control card nor a v2 node (the serial rules
    apply). kind: complete | request_review | block."""
    root = Path(root)
    if board.is_m2(task_id):
        if kind == "block":
            return {"action": "allow", "code": "BLOCK_ALLOWED"}
        _gate(root)
        run = run_id_of(root, board)
        from planner.native_publish import readback
        try:
            plan = board.plan(run)
        except Refusal as exc:
            raise Refusal("M2_PUBLICATION_INCOMPLETE", "%s: %s" % (exc.code, exc.detail)) from exc
        gaps = readback(board, plan)
        if gaps:
            raise Refusal("M2_READBACK", "; ".join(gaps[:4]))
        if kind == "complete":
            if profile != REVIEWER:
                raise Refusal("M2_TERMINATOR", "M2 ends with kanban_request_review reviewer=reviewer; the reviewer completes it")
            if not audit_green():
                raise Refusal("M2_AUDIT_RED", "the paved-road M2 audit has not exited 0 in this run")
            return {"action": "allow", "code": "M2_RELEASE"}
        return {"action": "allow", "code": "M2_REVIEW_ALLOWED"}
    if board.node_of(task_id) is None:
        return None
    if kind == "block":
        # a legal result: dependency waits, exhausted budgets, external blockers
        return {"action": "allow", "code": "BLOCK_ALLOWED"}
    _gate(root)
    role, run, oid, plan, node = node_context(board, task_id)
    if kind == "complete" and profile != REVIEWER:
        raise Refusal("NATIVE_TERMINATOR", "%s ends its implementation run with kanban_request_review reviewer=reviewer; "
                                           "the reviewer completes it after the domain gate" % oid)
    if role == "repair":
        waiting = repair_waiting(board, run, plan, task_id)
        if waiting:
            raise Refusal("OWNER_REPAIR_PENDING", "%s holds a candidate for the repair %s: end this run with "
                                                  "kanban_block kind=dependency" % (oid, waiting))
        ok, why = outcome_acceptance(root, board, task_id, plan, node)
        if not ok:
            raise Refusal("OUTCOME_NOT_ACCEPTED", "%s: a rejected or unfinished attempt keeps the outcome open" % why)
        if kind == "complete" and not audit_green():
            raise Refusal("OUTCOME_AUDIT_RED", "the paved-road M3 audit has not exited 0 in this reviewer run")
        return {"action": "allow", "code": "OUTCOME_%s_ALLOWED" % ("COMPLETE" if kind == "complete" else "REVIEW")}
    if role == "assess":
        rec = latest_assessment(board, task_id)
        if rec is None:
            raise Refusal("ASSESS_UNRECORDED", "no assessment record on %s (native_gate.py assessment-record)" % task_id)
        if rec.get("verdict") not in DELIVERY_OK_VERDICTS:
            raise Refusal("ASSESS_NOT_ACCEPTED", "the latest assessment is %s: M4 means verification ACCEPTED. Run "
                          "native_gate.py m4-repair and end this run with kanban_block kind=dependency" % rec.get("verdict"))
        if rec.get("candidate") != _product_tree(root):
            raise Refusal("ASSESS_STALE", "the assessment measured another candidate")
        if kind == "complete" and not audit_green():
            raise Refusal("ASSESS_AUDIT_RED", "the paved-road M4 audit has not exited 0 in this reviewer run")
        return {"action": "allow", "code": "ASSESS_%s_ALLOWED" % ("COMPLETE" if kind == "complete" else "REVIEW")}
    # deliver
    m4 = m4_acceptance(root, board, run, plan)
    if not m4["accepted"] or m4["candidate"] != _product_tree(root):
        raise Refusal("DELIVER_STALE_CANDIDATE", "the delivery candidate is not the accepted M4 candidate (%s)" % (m4["why"] or "drift"))
    if kind == "request_review":
        active_issue(board, task_id, run_id)
        return {"action": "allow", "code": "DELIVER_REVIEW_ALLOWED"}
    if not audit_green():
        raise Refusal("DELIVER_AUDIT_RED", "the paved-road M5 audit has not exited 0 in this reviewer run")
    ok, facts, reasons = stage_evidence(root, board, run, plan, str(node.get("stage") or ""))
    if not ok:
        code = "STAGE_EVIDENCE_MISSING" if any(r.startswith("STAGE_EVIDENCE_MISSING") for r in reasons) else "STAGE_EVIDENCE_REFUSED"
        raise Refusal(code, "; ".join(reasons[:4]))
    return {"action": "allow", "code": "DELIVER_COMPLETE_ALLOWED"}


# ---------------------------------------------------------------------------
# attempts on the SAME outcome task
# ---------------------------------------------------------------------------

def _scope_gaps(root: Path, iss: dict[str, Any], commit: str = "") -> list[str]:
    changed = changed_product_paths(root, str(iss.get("baseline_commit") or ""), commit)
    if changed is None:
        return ["the changed paths since baseline %s could not be measured" % str(iss.get("baseline_commit") or "none")[:12]]
    allowed = set(iss.get("allowed_paths") or [])
    return ["%s is outside the issued scope" % c for c in changed if c not in allowed]


def record_verdict(root: Path, board: Board, *, task_id: str, run_id: int, verdict: str, candidate: str, attempt: str,
                   reason: str = "", retained: dict[str, Any] | None = None) -> dict[str, Any]:
    """REVERTED / VERIFICATION_PENDING / ACCEPTED (accept-begin) of the issued scope."""
    root = Path(root)
    iss = active_issue(board, task_id, run_id)
    role, run, oid, plan, node = node_context(board, task_id)
    key = "%s:%s" % (run_id, attempt)
    if verdict == "REVERTED":
        recovered = owner_recovery(root, board, iss, task_id=task_id, run_id=run_id, candidate=candidate, key=key)
        if recovered is not None:
            return recovered
        rec = board.record(task_id, "reject", "reject:%s" % key, run=int(run_id), cluster=iss.get("cluster") or "",
                           candidate=candidate, reason=reason[:300])
        b = budget_state(board, run, plan, node)
        return {"verdict": verdict, "outcome_id": oid, "spent": b["spent"], "limit": b["limit"], "exhausted": b["exhausted"],
                "card": "stays open (same outcome task)", "record": rec["key"]}
    if verdict == "VERIFICATION_PENDING":
        board.record(task_id, "pending", "pending:%s" % key, run=int(run_id), cluster=iss.get("cluster") or "",
                     candidate=candidate, baseline_commit=iss.get("baseline_commit"), baseline_tree=iss.get("baseline_tree"),
                     retained=retained or {}, reason=reason[:300])
        return {"verdict": verdict, "outcome_id": oid, "spent": budget_state(board, run, plan, node)["spent"]}
    if verdict == "ACCEPTED":
        gaps = _scope_gaps(root, iss)
        if gaps:
            raise Refusal("ACCEPT_OUT_OF_SCOPE", "; ".join(gaps[:4]))
        board.record(task_id, "accept-begin", "accept-begin:%s" % key, run=int(run_id), cluster=iss.get("cluster") or "",
                     candidate=candidate, baseline_commit=iss.get("baseline_commit"))
        return {"verdict": verdict, "outcome_id": oid, "next": "commit, then accept-commit"}
    raise Refusal("VERDICT_UNKNOWN", verdict)


def _measure(root: Path, plan: dict[str, Any], node: dict[str, Any], worklist: dict[str, Any], tree: str,
             measurement: dict[str, Any]) -> dict[str, Any]:
    from planner.requirement_checks import passed
    scenarios = [str(s) for s in measurement.get("scenarios") or []]
    open_now = open_obligations(worklist)
    m = {"tree": tree, "classes": sorted(set(measurement.get("classes") or [])), "scenarios": sorted(set(scenarios)),
         "open_owned": sorted(open_now & owned(plan, node)), "open_count": len(open_now),
         "classes_asserted_by": "worker-receipts"}
    checks = requirement_measurement(root, plan, node, worklist, scenarios, tree)
    if checks:
        m["checks"] = passed(checks)
    return m


def accept_commit(root: Path, board: Board, *, task_id: str, run_id: int, attempt: str, commit: str,
                  measurement: dict[str, Any]) -> dict[str, Any]:
    """Record the committed acceptance of the issued scope and decide whether
    the OUTCOME is accepted: every owned obligation absent from the rebuilt
    work list and the outcome's check class measured on this tree."""
    root = Path(root)
    iss = active_issue(board, task_id, run_id)
    role, run, oid, plan, node = node_context(board, task_id)
    key = "%s:%s" % (run_id, attempt)
    begin = [r for r in board.records(task_id, "accept-begin") if r["key"] == "accept-begin:%s" % key]
    if not begin:
        raise Refusal("ACCEPT_UNBEGUN", "no accept-begin for attempt %s" % attempt)
    tree = _product_tree(root)
    if tree != begin[-1]["candidate"]:
        raise Refusal("ACCEPT_TREE_DRIFT", "the committed tree is not the verified candidate")
    if _head(root) != commit:
        raise Refusal("ACCEPT_COMMIT_MISMATCH", "HEAD is not the named commit %s" % commit[:12])
    parent = _git(root, "rev-parse", "--verify", "-q", "%s^1" % commit).stdout.strip()
    if not iss.get("baseline_commit") or parent != iss["baseline_commit"]:
        raise Refusal("ACCEPT_BASELINE_ANCESTRY", "commit %s is not a child of the issued baseline %s"
                      % (commit[:12], str(iss.get("baseline_commit") or "none")[:12]))
    gaps = _scope_gaps(root, iss, commit)
    if gaps:
        raise Refusal("ACCEPT_OUT_OF_SCOPE", "; ".join(gaps[:4]))
    wl, why = load_worklist(root)
    if wl is None:
        raise Refusal("ACCEPT_" + why, "acceptance reads the rebuilt work list")
    m = _measure(root, plan, node, wl, tree, measurement)
    covered = _covers(node, m)
    evidence_gaps = repair_evidence_gaps(root, node, tree)
    done = not m["open_owned"] and covered and not evidence_gaps
    board.record(task_id, "accept-commit", "accept-commit:%s" % key, run=int(run_id), commit=commit, tree=tree,
                 cluster=iss.get("cluster") or "", outcome_accepted=done, measurement=m, repair_evidence_gaps=evidence_gaps)
    return {"outcome_id": oid, "outcome_accepted": done, "open_owned": m["open_owned"],
            "covered": covered, "repair_evidence_gaps": evidence_gaps}


def recover_accept(root: Path, board: Board, *, task_id: str, skip_run: int | None = None,
                   commits: Callable[[str], list[tuple[str, str, str]]] | None = None) -> list[dict[str, Any]]:
    """After a crash between accept-begin and accept-commit: the commit whose
    parent is the recorded baseline and whose product tree is the candidate is
    recorded (recovered); none aborts to a retained candidate. Never spends,
    never commits again."""
    commits = commits or git_commits_after(Path(root))
    closed = {r["key"].split(":", 1)[1] for r in board.records(task_id) if r["kind"] in ("accept-commit", "accept-aborted")}
    out = []
    for r in board.records(task_id, "accept-begin"):
        attempt_key = r["key"].split(":", 1)[1]
        if attempt_key in closed or (skip_run is not None and int(r.get("run") or 0) == int(skip_run)):
            continue
        hits = [s for s, parent, tree in commits(str(r.get("baseline_commit") or ""))
                if parent == r.get("baseline_commit") and tree == r.get("candidate")]
        if len(hits) > 1:
            raise Refusal("ACCEPT_RECOVERY_AMBIGUOUS", "%d commits carry candidate %s; the acceptance of attempt %s is not guessed"
                          % (len(hits), str(r.get("candidate"))[:12], attempt_key))
        if len(hits) == 1:
            board.record(task_id, "accept-commit", "accept-commit:%s" % attempt_key, run=int(r.get("run") or 0),
                         commit=hits[0], tree=r.get("candidate"), cluster=r.get("cluster") or "", recovered=True,
                         outcome_accepted=False)
            out.append({"attempt": attempt_key, "recovered_commit": hits[0]})
        else:
            board.record(task_id, "accept-aborted", "accept-aborted:%s" % attempt_key, run=int(r.get("run") or 0),
                         why="no commit carries the candidate")
            board.record(task_id, "pending", "pending:%s:aborted" % attempt_key, run=int(r.get("run") or 0),
                         candidate=r.get("candidate"), baseline_commit=r.get("baseline_commit"),
                         reason="acceptance interrupted before commit; candidate retained")
            out.append({"attempt": attempt_key, "aborted": True})
    return out


def evaluate_recovered(root: Path, board: Board, *, task_id: str, run_id: int, measurement: dict[str, Any]) -> dict[str, Any] | None:
    """Finish an acceptance that recovery recorded: the recovered commit is
    the current tree, re-measured, judged exactly as accept_commit judges.
    None when there is nothing to finish."""
    root = Path(root)
    active_issue(board, task_id, run_id)
    role, run, oid, plan, node = node_context(board, task_id)
    rows = _accept_records(board, task_id)
    if not rows or not rows[-1].get("recovered") or rows[-1].get("outcome_accepted"):
        return None
    last = rows[-1]
    tree = _product_tree(root)
    if tree != last.get("tree"):
        raise Refusal("ACCEPT_TREE_DRIFT", "the tree is not the recovered commit's tree")
    wl, why = load_worklist(root)
    if wl is None:
        raise Refusal("ACCEPT_" + why, "acceptance reads the rebuilt work list")
    m = _measure(root, plan, node, wl, tree, measurement)
    covered = _covers(node, m)
    done = not m["open_owned"] and covered and not repair_evidence_gaps(root, node, tree)
    board.record(task_id, "accept-evaluated", "accept-evaluated:%s" % last["key"].split(":", 1)[1], run=int(run_id),
                 commit=last.get("commit"), tree=tree, outcome_accepted=done, measurement=m)
    return {"outcome_id": oid, "outcome_accepted": done, "open_owned": m["open_owned"], "covered": covered,
            "commit": last.get("commit")}


def restore_pending(root: Path, board: Board, *, task_id: str, run_id: int, candidate_now: str) -> dict[str, Any]:
    iss = active_issue(board, task_id, run_id)
    pend = _open_pending(board, task_id)
    if pend is None:
        raise Refusal("RESTORE_NO_PENDING", "no retained candidate on %s" % task_id)
    if candidate_now != pend.get("candidate"):
        raise Refusal("RESTORE_DIGEST", "the restored tree is not the retained candidate")
    moved = str(iss.get("baseline_commit") or "") != str(pend.get("baseline_commit") or "")
    board.record(task_id, "restore", "restore:%s:%s" % (run_id, pend["key"]), run=int(run_id), candidate=candidate_now,
                 original_baseline=pend.get("baseline_commit"), current_baseline=iss.get("baseline_commit"),
                 baseline_moved=moved, closes_pending=False)
    return {"outcome_id": iss.get("outcome_id"), "baseline_moved": moved}


# ---------------------------------------------------------------------------
# automatic owner recovery on native tasks
# ---------------------------------------------------------------------------

def accepted_steps(root: Path, board: Board, run_id: str) -> list[dict[str, Any]]:
    """Every committed acceptance on the board, oldest first (board-wide
    comment order), with the paths each commit changed."""
    rows = []
    for oid, t in board.run_tasks(run_id).items():
        for r in board.records(t["id"], "accept-commit"):
            if r.get("commit"):
                rows.append((r["_id"], oid, t["id"], r))
    out = []
    for _id, oid, tid, r in sorted(rows):
        commit = str(r["commit"])
        out.append({"cluster": str(r.get("cluster") or oid), "card": tid, "commit": commit, "verdict": "accepted",
                    "outcome_id": oid, "changed": changed_product_paths(root, commit + "^1", commit) or []})
    return out


def _classify(root: Path, board: Board, run_id: str, plan: dict[str, Any], iss: dict[str, Any]) -> dict[str, Any] | None:
    try:
        from planner import runtime_cause as RC
    except ImportError:
        return None
    from planner.paths import LOOP_ACCEPTED, PARITY_DIR
    wl, _why = load_worklist(root)
    wl = wl or {"items": [], "clusters": []}
    row = next((c for c in wl.get("clusters") or [] if isinstance(c, dict) and c.get("id") == iss.get("cluster")), {})
    node = _node(plan, str(iss.get("outcome_id") or "")) or {}
    issued = {"cluster": iss.get("cluster") or "", "task_id": "", "items": list(row.get("items") or []), "gate_items": [],
              "scenarios": list(node.get("scenarios") or []), "entry_points": list(node.get("entry_points") or []),
              "write_set": list(iss.get("allowed_paths") or []), "amendments": []}
    changed = changed_product_paths(root, str(iss.get("baseline_commit") or "")) or []
    cur = {"failures": RC.failures_of(wl, issued, RC.scenario_records(root / PARITY_DIR)), "changed": changed}
    if not cur["failures"]:
        return None
    baseline = {"tree": str(iss.get("baseline_tree") or ""), "records": RC.scenario_records(root / LOOP_ACCEPTED / "parity")}
    try:
        out = RC.classify(root, issued, cur, accepted_steps(root, board, run_id), baseline)
    except Exception as exc:  # a classifier failure is no evidence of anything
        return {"class": "ambiguous", "owner": None, "evidence": [], "reason": "classifier failed: %s" % type(exc).__name__}
    if isinstance(out, dict):
        out = dict(out, failing_scenarios=sorted({str(f.get("scenario") or "") for f in cur["failures"]} - {""}),
                   baseline_tree=baseline["tree"])
    return out if isinstance(out, dict) else None


def _hold_files(root: Path, iss: dict[str, Any]) -> dict[str, str] | None:
    changed = changed_product_paths(root, str(iss.get("baseline_commit") or ""))
    if changed is None or not set(changed) <= set(iss.get("allowed_paths") or []):
        return None
    out: dict[str, str] = {}
    size = 0
    for rel in changed:
        p = root / rel
        data = p.read_bytes() if p.is_file() and not p.is_symlink() else b""
        size += len(data)
        out[rel] = base64.b64encode(data).decode("ascii") if p.exists() else ""
    return out if size <= HOLD_MAX_BYTES else None


def owner_recovery(root: Path, board: Board, iss: dict[str, Any], *, task_id: str, run_id: int, candidate: str,
                   key: str) -> dict[str, Any] | None:
    """None = the ordinary rejection applies. A validated owner defect: the
    candidate is HELD (a versioned attachment on this task, no attempt spent),
    ONE bounded repair of the owner is published as a native task, linked as a
    prerequisite of this task (and of the open M4), and this run ends with
    kanban_block kind=dependency. Native promotion resumes it."""
    role, run, oid, plan, node = node_context(board, task_id)
    res = _classify(root, board, run, plan, iss)
    if res is None:
        return None
    cls = str(res.get("class") or "")
    why = ""
    if cls not in CAUSE_CLASSES:
        why = "classifier answered %r" % cls
    elif cls != OWNER_DEFECT:
        why = "%s: %s" % (cls, str(res.get("reason") or "")[:200])
    owner_doc = res.get("owner") if isinstance(res.get("owner"), dict) else {}
    owner = str(owner_doc.get("outcome_id") or "")
    evidence = res.get("evidence") if isinstance(res.get("evidence"), list) else []
    onode = _node(plan, owner) if owner else None
    fid = owner_repair_id(owner, oid) if owner else ""
    if not why:
        otask = board.task_of(run, onode) if onode else ""
        base_rows = [e for e in evidence if isinstance(e, dict) and e.get("kind") == "baseline-record"]
        if not onode or owner == oid or onode.get("role") != "repair" or (board.task(otask) or {}).get("status") != "done":
            why = "owner %r is not another accepted (done) repair outcome" % owner
        elif not base_rows or not any(e.get("kind") == "baseline-failure" for e in evidence):
            why = "no evidence names the failure on the baseline"
        elif any(e.get("baseline_tree") != iss.get("baseline_tree") or e.get("bound_to") != iss.get("baseline_tree")
                 for e in base_rows):
            why = "the evidence names another baseline than the issued one"
        elif not res.get("failing_scenarios"):
            why = "no failing scenario to re-measure after the repair"
        elif budget_state(board, run, plan, onode)["exhausted"]:
            why = "the owner's budget %s is exhausted" % (onode.get("budget") or {}).get("key")
        elif _node(plan, fid) is not None or any(h.get("repair") == fid for h in board.records(task_id, "owner-hold")):
            why = "the one bounded repair of %s for %s was already scheduled" % (owner, oid)
    held = _hold_files(root, iss) if not why else None
    if not why and held is None:
        why = "the candidate cannot be held (outside the issue, unmeasurable or too large)"
    if why:
        if cls in CAUSE_CLASSES and cls != "candidate-regression":
            board.record(task_id, "cause-report", "cause:%s" % key, run=int(run_id), cls=cls, owner=owner, why=why[:300])
        return None
    # the held candidate: an attachment (the bytes), then the keyed record naming it
    name = "held.%s.json" % sha256(key.encode())[:12]
    data = canonical_bytes({"schema": "rhoai3.native-held/v1", "task": task_id, "run": int(run_id), "candidate": candidate,
                            "baseline_commit": iss.get("baseline_commit"), "files": held})
    if board.attachment(task_id, name) is None:
        with tempfile.TemporaryDirectory(prefix="native-held-") as td:
            p = Path(td) / name
            p.write_bytes(data)
            board.native.attach(task_id, str(p), name)
    owner_task = board.task_of(run, onode)
    last_issue = next((r for r in reversed(board.records(owner_task, "issue")) if r.get("allowed_paths")), None)
    repair_paths = sorted(set((last_issue or {}).get("allowed_paths") or []) | set(owner_doc.get("paths") or []))[:AMEND_MAX_FILES]
    hold = board.record(task_id, "owner-hold", "owner-hold:%s" % key, run=int(run_id), owner=owner, repair=fid,
                        candidate=candidate, attachment=name, sha256=sha256(data), baseline_commit=iss.get("baseline_commit"),
                        repair_paths=repair_paths, repair_scenarios=list(res.get("failing_scenarios") or []),
                        budget={"key": (onode.get("budget") or {}).get("key"), "limit": (onode.get("budget") or {}).get("limit")},
                        reason=str(res.get("reason") or "")[:300], evidence=evidence[:6])
    _publish_owner_repair(root, board, run, plan, hold)
    return {"verdict": "OWNER_RECOVERY", "outcome_id": oid, "owner": owner, "repair": fid, "spent": budget_state(board, run, plan, node)["spent"],
            "limit": int((node.get("budget") or {}).get("limit") or 0), "exhausted": False, "held_paths": sorted(held),
            "card": "stays open; revert the tree and end this run with kanban_block kind=dependency"}


def _publish_owner_repair(root: Path, board: Board, run_id: str, plan: dict[str, Any], hold: dict[str, Any]) -> None:
    """The revision adding the owner repair, attached to the dependent, then
    the repair task and its links (repair -> dependent, repair -> open M4).
    Every step is looked up before it is repeated."""
    from planner.native_publish import publish_revision
    dep_task = ""
    for oid, row in board.run_tasks(run_id).items():
        if any(h["key"] == hold["key"] for h in board.records(row["id"], "owner-hold")):
            dep_task = row["id"]
            dep = oid
            break
    if not dep_task:
        raise Refusal("OWNER_HOLD_LOST", "the owner-hold record %s is on no task of run %s" % (hold["key"], run_id))
    doc = {"owner": hold["owner"], "dependent": dep, "evidence": hold.get("evidence") or [], "reason": hold.get("reason") or "",
           "repair_paths": hold.get("repair_paths") or [], "repair_scenarios": hold.get("repair_scenarios") or [],
           "budget": hold.get("budget") or {}}
    tasks = board.run_tasks(run_id)
    open_assess = {n["outcome_id"] for n in plan["nodes"] if n.get("role") == "assess"
                   and (board.task(tasks.get(n["outcome_id"], {}).get("id", "")) or {}).get("status") != "done"}
    nxt = owner_repair_revision(plan, doc, open_assessments=open_assess)
    if isinstance(nxt, Refusal):
        raise nxt
    if nxt is None:                      # replay: the revision already carries it; finish its publication
        publish_revision(root, board, plan, added=[hold["repair"]], holder=dep_task)
        return
    publish_revision(root, board, nxt, added=[hold["repair"]], holder=dep_task)


def restore_held(root: Path, board: Board, *, task_id: str, run_id: int) -> dict[str, Any]:
    """The held candidate (after its owner's repair), for the caller to write
    back and re-verify on the repaired baseline: only paths the CURRENT issue
    allows. No acceptance is carried over."""
    iss = active_issue(board, task_id, run_id)
    holds = board.records(task_id, "owner-hold")
    if not holds:
        raise Refusal("RESTORE_NO_HOLD", "no held candidate on %s" % task_id)
    h = holds[-1]
    got = board.attachment(task_id, str(h.get("attachment") or ""))
    if got is None or sha256(got[0]) != h.get("sha256"):
        raise Refusal("RESTORE_HELD_CORRUPT", "the held candidate %s is missing or differs from its record" % h.get("attachment"))
    files = json.loads(got[0]).get("files") or {}
    outside = sorted(set(files) - set(iss.get("allowed_paths") or []))
    if outside:
        raise Refusal("RESTORE_OUTSIDE_ISSUE", "held paths %s are outside the current issue" % ", ".join(outside[:3]))
    board.record(task_id, "restore-held", "restore-held:%s" % h["key"], run=int(run_id), files=sorted(files))
    return {"outcome_id": iss.get("outcome_id"), "files": files, "owner": h.get("owner"),
            "baseline_then": h.get("baseline_commit"), "baseline_now": iss.get("baseline_commit")}


# ---------------------------------------------------------------------------
# M4: verification ACCEPTED, or repairs as prerequisites of the same task
# ---------------------------------------------------------------------------

def latest_assessment(board: Board, task_id: str) -> dict[str, Any] | None:
    rows = board.records(task_id, "assessment")
    return rows[-1] if rows else None


def record_assessment(root: Path, board: Board, *, task_id: str, run_id: int, verdict_doc: dict[str, Any]) -> dict[str, Any]:
    """The M4 measurement of this run: the verdict (bound to this task), the
    candidate tree and the open obligations the rebuilt work list names, as
    a versioned attachment plus a keyed record."""
    root = Path(root)
    iss = active_issue(board, task_id, run_id)
    role, run, oid, plan, node = node_context(board, task_id)
    if role != "assess":
        raise Refusal("ASSESS_FOREIGN", "%s is not an assessment" % oid)
    if str(verdict_doc.get("card_id") or "") != task_id:
        raise Refusal("ASSESS_UNBOUND", "the verdict names card %r, not %s" % (verdict_doc.get("card_id"), task_id))
    token = str(verdict_doc.get("verdict") or verdict_doc.get("token") or "").upper()
    if not token:
        raise Refusal("ASSESS_UNBOUND", "the verdict carries no token")
    wl, why = load_worklist(root)
    tree = _product_tree(root)
    obligations = []
    if wl is not None:
        clusters = {str(i): c for c in wl.get("clusters") or [] for i in c.get("items") or []}
        for it in wl.get("items") or []:
            if it.get("category") == "mandatory":
                c = clusters.get(str(it["id"])) or {}
                obligations.append({"id": it["id"], "kind": it.get("kind"), "entry_point": it.get("entry_point", ""),
                                    "scenario": it.get("scenario", ""), "cluster": c.get("id", ""), "status": c.get("status", ""),
                                    "write_set": list(c.get("write_set") or []), "gate": it.get("gate", ""),
                                    "key": (c.get("unit") or {}).get("unit_id") or c.get("retry_key") or c.get("id", ""),
                                    "path": it.get("path", "")})
    doc = {"schema": "rhoai3.native-assessment/v1", "task": task_id, "run": int(run_id), "verdict": token, "candidate": tree,
           "worklist": why or "present", "obligations": obligations,
           "failed_floors": list(verdict_doc.get("failed_floors") or []),
           "release_blockers": list(verdict_doc.get("release_blockers") or []),
           "qualifications": list(verdict_doc.get("qualifications") or []),
           "parity_scenarios": [str(s) for s in verdict_doc.get("parity_scenarios") or []],
           "classes_asserted_by": "worker-receipts"}
    data = canonical_bytes(doc)
    digest = sha256(data)
    name = "assessment.%d.%s.json" % (int(run_id), digest[:12])
    if board.attachment(task_id, name) is None:
        with tempfile.TemporaryDirectory(prefix="native-assess-") as td:
            p = Path(td) / name
            p.write_bytes(data)
            board.native.attach(task_id, str(p), name)
    rec = board.record(task_id, "assessment", "assessment:%d:%s" % (int(run_id), digest[:16]), run=int(run_id),
                       verdict=token, candidate=tree, attachment=name, sha256=digest, open_obligations=len(obligations),
                       worklist=why or "present")
    return {"verdict": token, "candidate": tree, "open_obligations": len(obligations), "record": rec["key"],
            "accepted": token in DELIVERY_OK_VERDICTS}


def _assessment_doc(board: Board, task_id: str, rec: dict[str, Any]) -> dict[str, Any]:
    got = board.attachment(task_id, str(rec.get("attachment") or ""))
    if got is None or sha256(got[0]) != rec.get("sha256"):
        raise Refusal("ASSESS_CORRUPT", "assessment %s is missing or differs from its record" % rec.get("attachment"))
    return json.loads(got[0])


def m4_repair(root: Path, board: Board, *, task_id: str, run_id: int) -> dict[str, Any]:
    """After a measured REFUSE on this M4 run: the repairs the verdict needs,
    published as native tasks and linked as prerequisites of THIS task
    (repair -> M4). The caller then ends the run with kanban_block
    kind=dependency; native promotion resumes M4 when they are done."""
    root = Path(root)
    active_issue(board, task_id, run_id)
    role, run, oid, plan, node = node_context(board, task_id)
    if role != "assess":
        raise Refusal("ASSESS_FOREIGN", "%s is not an assessment" % oid)
    rec = latest_assessment(board, task_id)
    if rec is None or int(rec.get("run") or 0) != int(run_id):
        raise Refusal("REFUSE_UNRECORDED", "record this run's assessment first (native_gate.py assessment-record)")
    if rec["verdict"] in DELIVERY_OK_VERDICTS:
        raise Refusal("REFUSE_NOT_REFUSED", "the assessment is %s: hand it to review" % rec["verdict"])
    tasks = board.run_tasks(run)
    ran = [n["outcome_id"] for n in plan["nodes"] if n.get("role") == "deliver"
           and (board.task(tasks.get(n["outcome_id"], {}).get("id", "")) or {}).get("status") in ("running", "review", "done")]
    if ran:
        raise Refusal("DELIVERY_CYCLE_UNSUPPORTED", "delivery stage %s already ran for a candidate; a second cycle is an explicit stop" % ran[0])
    if rec.get("worklist") != "present":
        raise Refusal("REFUSE_" + str(rec.get("worklist")), "the assessment has no measured work list")
    refused_runs = sorted({int(r.get("run") or 0) for r in board.records(task_id, "assessment")
                           if r.get("verdict") not in DELIVERY_OK_VERDICTS})
    gen = len(refused_runs)
    doc = _assessment_doc(board, task_id, rec)

    def status_of(o: str) -> str:
        row = tasks.get(o)
        return "done" if row and (board.task(row["id"]) or {}).get("status") == "done" else "open"

    def budget_of(o: str) -> dict[str, Any]:
        return dict((_node(plan, o) or {}).get("budget") or {})

    prior = [r for r in board.records(task_id, "m4-repair") if int(r.get("run") or 0) == int(run_id)]
    if prior:
        nxt_rev = int(prior[-1]["revision"])
        cur = board.plan(run)
        if int(cur["revision"]) < nxt_rev:
            raise Refusal("REFUSE_REVISION_LOST", "revision %d recorded for this run is not on the board" % nxt_rev)
        added = list(prior[-1].get("added") or [])
        from planner.native_publish import publish_revision
        publish_revision(root, board, cur, added=added, holder=task_id)
        return {"verdict": rec["verdict"], "revision": nxt_rev, "added": added, "replayed": True,
                "terminator": "kanban_block kind=dependency"}
    nxt = refuse_revision(plan, doc.get("obligations") or [], gen=gen, trigger=oid, verdict=rec["verdict"],
                          status_of=status_of, budget_of=budget_of, successor=False)
    if isinstance(nxt, Refusal):
        raise nxt
    added = list(nxt.get("additions") or [])
    # the targets that are existing open owners already are M4's prerequisites (every repair is)
    board.record(task_id, "m4-repair", "m4-repair:%d" % int(run_id), run=int(run_id), revision=int(nxt["revision"]),
                 added=added, verdict=rec["verdict"])
    from planner.native_publish import publish_revision
    publish_revision(root, board, nxt, added=added, holder=task_id)
    return {"verdict": rec["verdict"], "revision": int(nxt["revision"]), "added": added, "replayed": False,
            "unresolved": [u["id"] for u in nxt.get("unresolved") or []], "terminator": "kanban_block kind=dependency"}


# ---------------------------------------------------------------------------
# M5: stage evidence and the push effect, recovered by read-back
# ---------------------------------------------------------------------------

def _stage_task(board: Board, run_id: str, plan: dict[str, Any], stage: str) -> str:
    node = next((n for n in plan["nodes"] if n.get("role") == "deliver" and n.get("stage") == stage), None)
    return board.task_of(run_id, node) if node else ""


def stage_evidence(root: Path, board: Board, run_id: str, plan: dict[str, Any], stage: str) -> tuple[bool, dict[str, Any], list[str]]:
    m4 = m4_acceptance(root, board, run_id, plan)
    push_task = _stage_task(board, run_id, plan, "push")

    def landed(head: str) -> bool:
        return bool(head and push_task and any(r.get("state") == "landed" and r.get("head") == head
                                               for r in board.records(push_task, "push")))
    return stage_evidence_facts(root, stage, m4_task=m4["task"], push_landed=landed)


def push_probe(root: Path, remote: str, ref: str, want: str) -> str | None:
    """'landed' when the remote ref is exactly ``want``, 'failed' when it
    answers another value, None when the remote cannot be read (uncertain)."""
    p = subprocess.run(["git", "-C", str(root), "ls-remote", remote, ref], capture_output=True, text=True, timeout=60)
    if p.returncode != 0:
        return None
    got = (p.stdout.split() or [""])[0]
    return "landed" if got == want else "failed"


def push(root: Path, board: Board, *, task_id: str, run_id: int, remote: str = "origin", ref: str = "refs/heads/main",
         pusher: Callable[[list[str]], subprocess.CompletedProcess] | None = None) -> dict[str, Any]:
    """The M5 DEPLOY publication step: exactly the accepted candidate, once.
    The remote is read back FIRST: a push that already landed (a crashed
    earlier run) is recorded, never repeated."""
    root = Path(root)
    active_issue(board, task_id, run_id)
    role, run, oid, plan, node = node_context(board, task_id)
    if role != "deliver" or node.get("stage") != "push":
        raise Refusal("EFFECT_STAGE", "%s may not push; only the M5 DEPLOY stage may" % oid)
    ok, _facts, reasons = stage_evidence(root, board, run, plan, "prepare")
    head = _head(root)
    if not ok:
        raise Refusal("EFFECT_INELIGIBLE", "preflight evidence does not admit %s (%s)" % (head[:12], "; ".join(reasons[:2])))
    op = "%s:%s@%s" % (remote, ref, head)
    done = [r for r in board.records(task_id, "push") if r.get("op") == op and r.get("state") in ("landed", "failed")]
    if done:
        return {"op": op, "state": done[-1]["state"], "already": True}
    seen = push_probe(root, remote, ref, head)
    if seen == "landed":
        board.record(task_id, "push", "push:%s:landed" % op, run=int(run_id), op=op, head=head, state="landed", recovered=True)
        return {"op": op, "state": "landed", "already": True}
    board.record(task_id, "push", "push:%s:sent:%d" % (op, int(run_id)), run=int(run_id), op=op, head=head, state="sent")
    run_push = pusher or (lambda argv: subprocess.run(argv, capture_output=True, text=True, timeout=600))
    p = run_push(["git", "-C", str(root), "push", remote, "%s:%s" % (head, ref)])
    state = push_probe(root, remote, ref, head) or "uncertain"
    board.record(task_id, "push", "push:%s:%s" % (op, state if state != "uncertain" else "uncertain:%d" % int(run_id)),
                 run=int(run_id), op=op, head=head, state=state, rc=int(getattr(p, "returncode", -1)))
    return {"op": op, "state": state, "already": False}


# ---------------------------------------------------------------------------
# progress: a read-only projection of the board
# ---------------------------------------------------------------------------

def progress_account(root: Path, board: Board, run_id: str) -> dict[str, Any]:
    """active = baseline + additions = accepted + unfinished; accepted splits
    into proof_applicable (accepted on the current tree, or covered by an
    accepted M4 of the current tree) and awaiting_revalidation. Derived from
    native tasks and their records only; never read back as a decision."""
    plan = board.plan(run_id)
    tasks = board.run_tasks(run_id)
    tree = _product_tree(root)
    revs = board.revisions(run_id)
    base_ids = {n["outcome_id"] for n in revs[min(revs)][1]["plan"]["nodes"] if n.get("role") == "repair"} if revs else set()
    repair = [n for n in plan["nodes"] if n.get("role") == "repair"]
    now_ids = {n["outcome_id"] for n in repair}
    m4 = m4_acceptance(Path(root), board, run_id, plan)
    accepted, applicable = [], []
    for n in repair:
        row = tasks.get(n["outcome_id"])
        if not row or (board.task(row["id"]) or {}).get("status") != "done":
            continue
        accepted.append(n["outcome_id"])
        recs = _accept_records(board, row["id"])
        if (recs and recs[-1].get("tree") == tree) or (m4["accepted"] and m4["candidate"] == tree):
            applicable.append(n["outcome_id"])
    statuses = {oid: (board.task(r["id"]) or {}).get("status") for oid, r in tasks.items()}
    return {
        "control": "native-cooperative", "revision": int(plan["revision"]),
        "baseline": len(base_ids), "additions": len(now_ids - base_ids), "active": len(now_ids),
        "accepted_historically": len(accepted), "proof_applicable": len(applicable),
        "awaiting_revalidation": len(accepted) - len(applicable), "unfinished": len(now_ids) - len(accepted),
        "unresolved": [u["id"] for u in plan.get("unresolved") or []],
        "milestones": {n["outcome_id"]: statuses.get(n["outcome_id"], "unpublished") for n in plan["nodes"]
                       if n.get("role") in ("assess", "deliver")},
        "m4": {k: m4[k] for k in ("verdict", "accepted", "done")},
        "complete_claim_allowed": not plan.get("unresolved") and len(accepted) == len(now_ids) and len(applicable) == len(accepted),
        "claimed_control": False,
    }


# ---------------------------------------------------------------------------
# the one serialization point for publication (a lock file, not state)
# ---------------------------------------------------------------------------

@contextmanager
def publication_lock(root: Path, timeout: float = 120.0) -> Iterator[None]:
    """The pinned create_task checks idempotency outside its write
    transaction: concurrent creates can duplicate. Every native graph
    mutation of this adapter runs under this exclusive lock."""
    p = Path(root) / LOCK
    p.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(p), os.O_RDWR | os.O_CREAT, 0o644)
    deadline = time.monotonic() + timeout
    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() > deadline:
                    raise Refusal("PUBLICATION_BUSY", "another publisher holds %s" % LOCK)
                time.sleep(0.2)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


__all__ = ["Board", "board_for", "native_key", "parse_key", "contract_doc", "native_plan", "plan_attachment", "issue",
           "active_issue", "amend", "check_write", "check_terminator", "record_verdict", "accept_commit", "recover_accept",
           "evaluate_recovered", "restore_pending", "restore_held", "owner_recovery", "record_assessment", "m4_repair",
           "m4_acceptance", "m4_closure", "stage_evidence", "push", "progress_account", "publication_lock", "Refusal",
           "CONTROL_M2", "VERDICT"]
