"""Outcome-board execution lifecycle: the authority's transition methods.

Every function here validates a transition REQUEST against the records and
the native board and then writes, in one short transaction, only what it
recomputed itself. None of them accepts a worker-supplied PASS, scope or budget
(architect F1: a protected writer validates, it never merely signs).

Each public transition is registered with ``@transition``. Called with an
in-process ``Ctx`` it runs here, against the in-tree store (qualification
fixtures: cooperative). Called with a ``RemoteCtx`` (enabled execution) it is
sent as a REQUEST to the protected authority service
(planner/outcome_authority.py), which runs the same function in its own
principal, against its own store, and replaces every value it can measure
itself (candidate tree, worker process, git state) before deciding. See
OUTCOME-BOARD-CONTRACT.md sections 3 and 8a.

Transitions (contract section 4): issue (T5), record_verdict (T6a-c),
check_complete (T4, T7, T8 and the M5 stage terminator), record_assessment
(the M4 measurement), plan_after_refuse (T9), grant_stage (T10),
admit_effect / record_effect / recover_effect (T11), progress_account (F3).
"""
from __future__ import annotations

import functools
import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from planner.outcome_graph import (ASSESS_PREFIX, CONTROL_M2, DELIVER_STAGES, IMPL, REPAIR_SKILL, ASSESS_SKILL,
                                   declaring_type, derive_initial_graph, plan_digest, render_description)
from planner.outcome_native import MARKER
from planner.outcome_protocol import STORE_DIR, execution_gate
from planner.outcome_store import Store, StoreError, canonical, sha
from planner.outcome_checks import (  # noqa: F401  the pure predicates, shared with native_control (v2)
    Refusal, WORKLIST, EP_INVENTORY, STRUCTURE, VERDICT, DELIVERY_OK_VERDICTS, EXEMPT_DIRS, AMEND_LIMIT,
    AMEND_MAX_FILES, DELIVERY_RECEIPTS, OWNER_DEFECT, CAUSE_CLASSES, HOLD_MAX_BYTES, _read_json, _oracles,
    _references, initial_plan_from_root, load_worklist, open_obligations, _git, _tree_blobs, _blob_id,
    changed_product_paths, norm_rel, _is_product, planned_cluster_id, _unit_kind, requirement_measurement, _covers,
    repair_evidence_gaps, git_commits_after, commit_product_tree, stage_admission, _git_head, owner_repair_id,
    MAX_ASSESSMENT_GENERATIONS, refuse_revision, owner_repair_revision, stage_evidence_facts)

ACCOUNT = STORE_DIR / "account.json"
PROTECTED_DIRS = (str(STORE_DIR) + "/", ".hermes/", ".git/")


@dataclass
class Ctx:
    root: Path
    store: Store
    native: Any
    tree: Callable[[Path], str] | None = None
    head: Callable[[Path], str] | None = None
    # liveness of a worker process as the CALLER's container sees it
    # ((pid, pgid) -> alive). The authority service has no view of the worker's
    # processes; it answers from the snapshot the request carried.
    alive: Callable[[int | None, int | None], bool] | None = None
    # the in-process authority writes the derived observer views (account.json)
    # into the tree; the service never writes the other principal's tree
    observer_writes: bool = True
    remote: Any = None

    def product_tree(self) -> str:
        if self.tree:
            return self.tree(self.root)
        from planner.canonical import product_tree_sha256
        return product_tree_sha256(self.root)

    def git_head(self) -> str:
        if self.head:
            return self.head(self.root)
        p = subprocess.run(["git", "-C", str(self.root), "rev-parse", "HEAD"], capture_output=True, text=True)
        return p.stdout.strip() if p.returncode == 0 else ""


class RemoteCtx:
    """The caller side of the protected authority: every ``@transition`` called
    with it becomes a request on the service socket. ``native`` is the local,
    read-only view of the board (lifecycle data, cooperative by design); the
    decision records live only in the service."""

    def __init__(self, root: Path, endpoint: str, native: Any = None):
        self.root = Path(root)
        self.endpoint = endpoint
        self.native = native
        self.remote = self

    def call(self, op: str, kwargs: dict[str, Any]) -> Any:
        from planner.outcome_authority import AuthorityError, call
        try:
            return call(self.endpoint, "transition", {"name": op, "kwargs": kwargs})
        except AuthorityError as exc:
            raise Refusal(exc.code, exc.detail) from exc

    def product_tree(self) -> str:
        from planner.canonical import product_tree_sha256
        return product_tree_sha256(self.root)   # informational: the service measures its own


TRANSITIONS: dict[str, Callable[..., Any]] = {}


def transition(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Register a public authority transition (ctx, **kwargs). With a RemoteCtx
    the call is a request to the service; the service calls ``TRANSITIONS``."""
    TRANSITIONS[fn.__name__] = fn

    @functools.wraps(fn)
    def wrapper(ctx: Any, *args: Any, **kwargs: Any) -> Any:
        if getattr(ctx, "remote", None) is not None:
            if args:
                raise TypeError("%s takes keyword arguments only through the authority" % fn.__name__)
            return ctx.remote.call(fn.__name__, kwargs)
        return fn(ctx, *args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# initial plan from the destination's admission-time evidence (T1)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# lookups
# ---------------------------------------------------------------------------

def _outcome(store: Store, oid: str) -> dict[str, Any] | None:
    row = store.conn.execute("SELECT * FROM outcomes WHERE outcome_id=?", (oid,)).fetchone()
    return dict(row) if row else None


def _pub_by_task(store: Store, task_id: str) -> dict[str, Any] | None:
    row = store.conn.execute("SELECT * FROM publication WHERE task_id=?", (task_id,)).fetchone()
    return dict(row) if row else None


def _node(plan: dict[str, Any], oid: str) -> dict[str, Any] | None:
    return next((n for n in plan.get("nodes") or [] if n["outcome_id"] == oid), None)


def _plan(store: Store) -> dict[str, Any]:
    plan = store.current_revision()
    if plan is None:
        raise Refusal("PLAN_MISSING", "no published revision")
    if plan_digest(plan) != plan.get("digest"):
        raise Refusal("STORE_TAMPERED", "revision %s digest does not cover its content" % plan.get("revision"))
    return plan


def _integrity(ctx: Ctx) -> None:
    try:
        ctx.store.verify_chain()
    except StoreError as exc:
        raise Refusal(exc.code, exc.detail) from exc
    recorded = ctx.store.meta("native_db")
    if recorded and os.path.realpath(ctx.native.db_path) != os.path.realpath(recorded):
        raise Refusal("NATIVE_REDIRECTED", "checks read %s; the board was published on %s" % (ctx.native.db_path, recorded))


def _gate(ctx: Ctx) -> None:
    g = execution_gate(ctx.root)
    if g:
        raise Refusal(g[0][0], g[0][1])


def _native_rejections(ctx: Ctx, task_id: str) -> int:
    return sum(1 for c in ctx.native.comments(task_id) if str(c).startswith(MARKER + " rejected"))


def _pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _pgid_alive(pgid: int | None) -> bool:
    if not pgid:
        return False
    try:
        os.killpg(int(pgid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def quiescent(pid: int | None, pgid: int | None, ctx: Ctx | None = None) -> bool:
    """The previous writer and every process in its group are gone. Elapsed
    time alone is never quiescence. Under the service the answer comes from
    the caller's process snapshot (ctx.alive): the authority shares no process
    namespace with the worker."""
    if ctx is not None and ctx.alive is not None:
        return not ctx.alive(pid, pgid)
    return not _pid_alive(pid) and not _pgid_alive(pgid)


def _scope_gaps(ctx: Ctx, iss: dict[str, Any], commit: str = "") -> list[str]:
    """The authority's own scope measurement: every product path the attempt
    changed since the issued baseline is in the issue's allowed paths
    (amendments included). Measured from git, never from a worker list."""
    changed = changed_product_paths(ctx.root, str(iss.get("baseline_commit") or ""), commit)
    if changed is None:
        return ["the changed paths since baseline %s could not be measured" % str(iss.get("baseline_commit") or "none")[:12]]
    allowed = set(iss.get("allowed_paths") or [])
    return ["%s is outside the issued scope" % c for c in changed if c not in allowed]


# ---------------------------------------------------------------------------
# T5: claim -> run-bound execution issue
# ---------------------------------------------------------------------------

def _allowed_paths(root: Path, node: dict[str, Any], worklist: dict[str, Any] | None,
                   owned: set[str] | None = None) -> tuple[str, list[str]]:
    """The ONE cluster this outcome may edit now, and its write set. Never the
    union of the outcome's plan paths. Ownership is the recorded ownership
    (latest revision), so obligations a revision assigned later count."""
    if node.get("role") != "repair" or worklist is None:
        return "", []
    owned = set(node.get("obligations") or []) | set(owned or ())
    for c in worklist.get("clusters") or []:
        if not isinstance(c, dict) or c.get("status") != "open":
            continue
        if owned & set(c.get("items") or []) or c.get("id") in set(node.get("clusters") or []):
            return str(c["id"]), sorted(str(p) for p in c.get("write_set") or [])
    return "", []


@transition
def issue(ctx: Ctx, *, task_id: str, run_id: int, claim_lock: str, pid: int, pgid: int) -> dict[str, Any]:
    _gate(ctx)
    _integrity(ctx)
    store = ctx.store
    if store.meta("publication_state") not in ("released",):
        m2 = ctx.native.task(store.meta("m2_task"))
        if not (m2 and m2.get("status") == "done" and store.meta("publication_state") == "complete"):
            raise Refusal("ISSUE_BEFORE_RELEASE", "the published graph is %s and M2 is %s"
                          % (store.meta("publication_state") or "absent", (m2 or {}).get("status")))
    t = ctx.native.task(task_id)
    if t is None:
        raise Refusal("ISSUE_FOREIGN_TASK", "%s is not on the recorded board" % task_id)
    if t.get("status") != "running" or t.get("current_run_id") != run_id:
        raise Refusal("ISSUE_STALE_RUN", "%s is %s with run %s; the caller holds run %s"
                      % (task_id, t.get("status"), t.get("current_run_id"), run_id))
    if not claim_lock or t.get("claim_lock") != claim_lock:
        raise Refusal("ISSUE_STALE_RUN", "the claim lock does not match the native claim")
    pub = _pub_by_task(store, task_id)
    if pub is None:
        raise Refusal("ISSUE_FOREIGN_TASK", "%s is not a published outcome" % task_id)
    oid = pub["outcome_id"]
    if t.get("idempotency_key") != pub["native_key"]:
        raise Refusal("ISSUE_FOREIGN_TASK", "%s carries key %r, not %r" % (task_id, t.get("idempotency_key"), pub["native_key"]))
    plan = _plan(store)
    node = _node(plan, oid)
    orow = _outcome(store, oid)
    if node is None or orow is None:
        raise Refusal("ISSUE_FOREIGN_TASK", "%s is not in the current revision" % oid)
    if t.get("assignee") != IMPL:
        raise Refusal("ISSUE_UNASSIGNED", "%s is assigned %r" % (task_id, t.get("assignee")))
    if node["role"] == "deliver":
        g = store.conn.execute("SELECT * FROM grants WHERE outcome_id=?", (oid,)).fetchone()
        if not g or g["state"] not in ("granted", "executed"):
            raise Refusal("ISSUE_UNGRANTED", "%s has no stage grant; a manual claim grants nothing" % oid)
        if g["candidate"] != ctx.product_tree():
            raise Refusal("ISSUE_STALE_CANDIDATE", "%s was granted for another candidate" % oid)
    if orow["status"] in ("accepted", "assessed", "done"):
        raise Refusal("ISSUE_ALREADY_DONE", "%s is %s" % (oid, orow["status"]))
    parents = []
    for p in node.get("parents") or []:
        if p == CONTROL_M2:
            continue
        ppub = store.conn.execute("SELECT task_id FROM publication WHERE outcome_id=?", (p,)).fetchone()
        pt = ctx.native.task(ppub[0]) if ppub and ppub[0] else None
        if pt is None or pt.get("status") == "archived":
            raise Refusal("ISSUE_PARENT_ARCHIVED", "parent %s is %s; an archived parent is not a prerequisite" % (p, "archived" if pt else "gone"))
        parents.append((p, pt))
    for p, pt in parents:
        prow = _outcome(store, p)
        if pt.get("status") != "done" or prow is None or prow["status"] not in ("accepted", "assessed", "done"):
            raise Refusal("ISSUE_PARENT_UNACCEPTED", "parent %s is %s natively and %s in the domain record"
                          % (p, pt.get("status"), (prow or {}).get("status")))
    waiting = _awaiting_owner_repair(store, oid)
    if waiting:
        raise Refusal("OWNER_REPAIR_PENDING", "%s waits on the repair %s of its owner; end this run with "
                                              "kanban_block kind=dependency" % (oid, waiting))
    spent = store.spent(orow["budget_key"])
    if _native_rejections(ctx, task_id) > sum(1 for r in store.ledger(oid) if r["kind"] == "reject"):
        raise Refusal("STORE_ROLLBACK", "the board records more rejected attempts on %s than the ledger: an older store "
                      "was restored" % task_id)
    if orow["budget_limit"] and spent >= orow["budget_limit"]:
        raise Refusal("ISSUE_BUDGET_EXHAUSTED", "%s spent %d of %d" % (orow["budget_key"], spent, orow["budget_limit"]))
    # an acceptance begun and committed by a worker that died before recording it is
    # recovered here, from Git history, before anything is judged (review R5)
    w0 = store.conn.execute("SELECT * FROM writer WHERE slot='product-tree'").fetchone()
    if not w0 or (w0["task_id"] == task_id and w0["run_id"] == run_id) or quiescent(w0["pid"], w0["pgid"], ctx):
        # never while the previous writer may still be committing; never this run's own
        recover_accept(ctx, oid=oid, commits=git_commits_after(ctx.root), skip_run=run_id)
    head, tree = ctx.git_head(), ctx.product_tree()
    base_commit = store.meta("accepted_commit") or store.meta("baseline_commit")
    base_tree = store.meta("accepted_tree") or store.meta("baseline_tree")
    pending = _open_pending(store, oid)
    if base_commit and head != base_commit:
        raise Refusal("ISSUE_BASELINE_DRIFT", "HEAD %s is not the accepted baseline %s" % (head[:12], base_commit[:12]))
    if base_tree and tree != base_tree and not (pending and pending["doc"].get("candidate") == tree):
        raise Refusal("ISSUE_BASELINE_DRIFT", "the product tree is neither the accepted baseline nor the retained "
                      "candidate of %s; unexplained edits are not blessed" % oid)
    worklist, why = load_worklist(ctx.root)
    if node["role"] == "repair" and worklist is None:
        raise Refusal("ISSUE_" + why, "an outcome is issued against the measured work list")
    cluster, allowed = _allowed_paths(ctx.root, node, worklist, _owned(store, oid))
    if cluster:
        # amendments granted earlier to this cluster survive a restart (never renewed, never lost)
        allowed = sorted(set(allowed) | set(amended_paths(store, oid, cluster)))
    unit_grant: dict[str, Any] = {}
    if node["role"] == "repair" and not cluster and node.get("repair_paths"):
        # an owner repair (automatic owner recovery): the owner's recorded write set and the
        # throwing file the classifier named, bounded; a synthetic unit id so the loop tools
        # (brief, run-verify, advance) have a card to act on
        cluster = planned_cluster_id(oid)
        allowed = sorted(node["repair_paths"])[:AMEND_MAX_FILES]
        unit_grant = {"refusal": "", "paths": allowed, "basis": "owner repair"}
    elif node["role"] == "repair" and not cluster and (node.get("planned_units") or node.get("requirements")):
        # no OPEN finding cluster grants this outcome anything: its planned work
        # (outcome_graph.planned_unit_grant, the frozen plan's own bounds) -- granted
        # only without a refusal, under the same writer generation, budget, parent
        # and baseline checks as a cluster, and amendable like one
        from planner.outcome_graph import planned_unit_grant
        unit_grant = planned_unit_grant(node, plan.get("requirements") or [],
                                        exists=lambda rel: (ctx.root / rel).exists(), cluster_open=False)
        if not unit_grant.get("refusal"):
            cluster = planned_cluster_id(oid)
            allowed = sorted(set(unit_grant.get("paths") or []) | set(amended_paths(store, oid, cluster)))
    with store.txn() as c:
        prior = c.execute("SELECT issue_id, run_id FROM issues WHERE task_id=? AND state='active'", (task_id,)).fetchall()
        for r in prior:
            if r["run_id"] != run_id:
                c.execute("UPDATE issues SET state='superseded' WHERE issue_id=?", (r["issue_id"],))
        w = c.execute("SELECT * FROM writer WHERE slot='product-tree'").fetchone()
        gen = int(store.meta("generation", "0") or 0)
        if w and not (w["task_id"] == task_id and w["run_id"] == run_id):
            if not quiescent(w["pid"], w["pgid"], ctx):
                raise Refusal("WRITER_BUSY", "the shared tree is owned by %s run %s (pid %s still alive)" % (w["task_id"], w["run_id"], w["pid"]))
        if not w or not (w["task_id"] == task_id and w["run_id"] == run_id):
            gen += 1
            c.execute("INSERT OR REPLACE INTO writer(slot, task_id, run_id, pid, pgid, generation, granted_at) VALUES('product-tree',?,?,?,?,?,?)",
                      (task_id, run_id, pid, pgid, gen, time.time()))
            store.set_meta(c, "generation", gen)
        else:
            gen = int(w["generation"])
        head_hash = store.meta("ledger_head")
        c.execute("INSERT INTO issues(task_id, run_id, claim_digest, outcome_id, rev, baseline_commit, baseline_tree, cluster, "
                  "allowed_paths, pins, budget_key, generation, ledger_head, state, created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (task_id, run_id, sha(claim_lock), oid, plan["revision"], head, tree, cluster, json.dumps(allowed),
                   json.dumps({"skills": node.get("skills") or []}), orow["budget_key"], gen, head_hash, "active", time.time()))
        iid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        store.append(c, oid, "issue", _issue_seal(iid, task_id, run_id, plan["revision"], cluster, allowed, gen, head, tree),
                     attempt_key="issue:%d" % iid)
    amends = [r["doc"] for r in store.ledger(oid) if r["kind"] == "amend" and r["doc"].get("cluster") == cluster] if cluster else []
    return {"issue_id": iid, "task_id": task_id, "run_id": run_id, "outcome_id": oid, "role": node["role"],
            "cluster": cluster, "allowed_paths": allowed, "budget": {"key": orow["budget_key"], "spent": spent,
                                                                      "limit": orow["budget_limit"]},
            "retained_candidate": bool(pending), "generation": gen, "claimed_control": False,
            "planned_unit": ({"refusal": unit_grant.get("refusal") or "", "owed": unit_grant.get("owed") or [],
                              "bounds": unit_grant.get("bounds") or {}, "basis": unit_grant.get("basis") or "",
                              "kind": _unit_kind(node)} if unit_grant else None),
            "run": store.meta("run_id"), "baseline_commit": head, "baseline_tree": tree,
            "amendments": [{"path": a["path"], "reason": a["reason"], "locus": a["locus"], "evidence": a.get("evidence") or {}}
                           for a in amends]}


def _awaiting_owner_repair(store: Store, oid: str) -> str:
    """The owner repair this outcome's held candidate waits on, until that
    repair is accepted; '' otherwise."""
    for r in store.ledger(oid):
        if r["kind"] != "owner-hold":
            continue
        fid = owner_repair_id(str(r["doc"].get("owner") or ""), oid)
        row = _outcome(store, fid)
        if not row or row["status"] not in ("accepted", "done"):
            return fid
    return ""


def _issue_seal(iid: int, task_id: str, run_id: int, rev: int, cluster: str, allowed: list[str], gen: int,
                head: str, tree: str) -> dict[str, Any]:
    return {"issue_id": int(iid), "task_id": task_id, "run_id": int(run_id), "rev": int(rev), "cluster": cluster,
            "allowed_paths": sorted(allowed), "generation": int(gen), "baseline_commit": head, "baseline_tree": tree}


def amended_paths(store: Store, oid: str, cluster: str) -> list[str]:
    return sorted({str(r["doc"]["path"]) for r in store.ledger(oid)
                   if r["kind"] == "amend" and r["doc"].get("cluster") == cluster})


@transition
def amend_issue(ctx: Ctx, *, task_id: str, run_id: int, cluster: str, rel: str, row: dict[str, Any]) -> dict[str, Any]:
    """The authority's scope-amendment transition (review R6). amend-scope.py has
    validated the evidence and the locus; this transition re-checks the bounds
    it owns (the run-bound issue and its cluster, product path, never a test
    source or the build file, not yet edited, the amendment count and the unit
    file bound) and only then widens the GOVERNING permission: a new issue for
    the same run, outcome, baseline, generation and budget, sealed in the ledger.
    The projection (issued.json) is written after it, never instead of it."""
    iss = active_issue(ctx, task_id, run_id)
    rel = norm_rel(rel)
    if str(iss.get("cluster") or "") != cluster:
        raise Refusal("AMEND_FOREIGN_CLUSTER", "the issue for this run is cluster %r, not %r" % (iss.get("cluster"), cluster))
    if rel in set(iss["allowed_paths"]):
        return {"path": rel, "already": True, "allowed_paths": iss["allowed_paths"]}
    if not _is_product(rel) or rel == "pom.xml" or (rel.startswith("src/test/") and not rel.endswith((".properties", ".yaml", ".yml"))):
        raise Refusal("AMEND_PATH", "%s is not a path an amendment may reach" % rel)
    if len(str(row.get("reason") or "").strip()) < 12 or not str(row.get("locus") or "").strip():
        raise Refusal("AMEND_UNEVIDENCED", "an amendment carries a reason and the locus the validator established")
    changed = changed_product_paths(ctx.root, str(iss.get("baseline_commit") or ""), only=[rel])
    if changed is None or changed:
        raise Refusal("AMEND_ALREADY_EDITED", "%s has already been edited; an amendment authorizes a change before it happens" % rel)
    oid = iss["outcome_id"]
    prior = [r for r in ctx.store.ledger(oid) if r["kind"] == "amend" and r["doc"].get("cluster") == cluster]
    if len(prior) >= AMEND_LIMIT:
        raise Refusal("AMEND_LIMIT", "cluster %s already carries %d amendment(s) (limit %d)" % (cluster, len(prior), AMEND_LIMIT))
    allowed = sorted(set(iss["allowed_paths"]) | {rel})
    if len(allowed) > AMEND_MAX_FILES:
        raise Refusal("AMEND_OVERSIZE", "%d files exceed the unit bound %d" % (len(allowed), AMEND_MAX_FILES))
    with ctx.store.txn() as c:
        c.execute("UPDATE issues SET state='superseded' WHERE issue_id=?", (iss["issue_id"],))
        c.execute("INSERT INTO issues(task_id, run_id, claim_digest, outcome_id, rev, baseline_commit, baseline_tree, cluster, "
                  "allowed_paths, pins, budget_key, generation, ledger_head, state, created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (task_id, run_id, iss["claim_digest"], oid, iss["rev"], iss["baseline_commit"], iss["baseline_tree"], cluster,
                   json.dumps(allowed), iss["pins"], iss["budget_key"], iss["generation"], ctx.store.meta("ledger_head"),
                   "active", time.time()))
        iid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        ctx.store.append(c, oid, "amend", {"cluster": cluster, "path": rel, "reason": str(row.get("reason") or "")[:500],
                                           "locus": str(row.get("locus") or "")[:500], "evidence": row.get("evidence") or {},
                                           "run_id": run_id, "issue_id": int(iid)},
                         attempt_key="amend:%s:%s" % (cluster, rel))
        ctx.store.append(c, oid, "issue", _issue_seal(iid, task_id, run_id, iss["rev"], cluster, allowed, iss["generation"],
                                                     iss["baseline_commit"] or "", iss["baseline_tree"] or ""),
                         attempt_key="issue:%d" % iid)
    return {"path": rel, "already": False, "allowed_paths": allowed, "issue_id": int(iid), "amendments": len(prior) + 1}


def _open_pending(store: Store, oid: str) -> dict[str, Any] | None:
    rows = store.ledger(oid)
    pend = None
    for r in rows:
        if r["kind"] == "pending":
            pend = r
        elif r["kind"] in ("restore", "reject", "accept-commit", "accept-aborted") and pend is not None:
            if r["kind"] != "restore" or r["doc"].get("closes_pending"):
                pend = None
    return pend


def active_issue(ctx: Ctx, task_id: str, run_id: int) -> dict[str, Any]:
    """The issue this run may act under, revalidated against the native run,
    the current revision and the writer generation."""
    _gate(ctx)
    _integrity(ctx)
    row = ctx.store.conn.execute("SELECT * FROM issues WHERE task_id=? AND state='active' ORDER BY issue_id DESC LIMIT 1",
                                 (task_id,)).fetchone()
    if row is None:
        raise Refusal("ISSUE_MISSING", "no execution issue for %s; run outcome_gate.py issue after the claim" % task_id)
    row = dict(row)
    seal = next((r for r in ctx.store.ledger(row["outcome_id"]) if r["kind"] == "issue"
                 and r["attempt_key"] == "issue:%d" % row["issue_id"]), None)
    want = _issue_seal(row["issue_id"], row["task_id"], row["run_id"], row["rev"], row["cluster"] or "",
                       json.loads(row["allowed_paths"]), row["generation"], row["baseline_commit"] or "", row["baseline_tree"] or "")
    if seal is None or seal["doc"] != want:
        raise Refusal("STORE_TAMPERED", "issue %s does not match its sealed ledger row" % row["issue_id"])
    if row["run_id"] != run_id:
        raise Refusal("ISSUE_STALE_RUN", "issue is for run %s; this run is %s" % (row["run_id"], run_id))
    t = ctx.native.task(task_id)
    if t is None or t.get("current_run_id") != run_id or t.get("status") != "running":
        raise Refusal("ISSUE_STALE_RUN", "native %s is %s with run %s" % (task_id, (t or {}).get("status"), (t or {}).get("current_run_id")))
    if t.get("claim_lock") and sha(t["claim_lock"]) != row["claim_digest"]:
        raise Refusal("ISSUE_STALE_RUN", "the native claim changed since the issue")
    cur = int(ctx.store.meta("revision", "0") or 0)
    if row["rev"] != cur:
        raise Refusal("ISSUE_STALE_REVISION", "issued under revision %s; current is %s" % (row["rev"], cur))
    w = ctx.store.conn.execute("SELECT * FROM writer WHERE slot='product-tree'").fetchone()
    if not w or w["task_id"] != task_id or w["run_id"] != run_id or int(w["generation"]) != int(row["generation"]):
        raise Refusal("WRITER_FENCED", "writer generation moved on; this run no longer owns the shared tree")
    row["allowed_paths"] = json.loads(row["allowed_paths"])
    return row


# ---------------------------------------------------------------------------
# hook checks
# ---------------------------------------------------------------------------


@transition
def check_write(ctx: Ctx, *, task_id: str, run_id: int, rel_paths: list[str]) -> None:
    """Refuse a product write outside the issued cluster, and every direct write
    to the authority store. Body text and environment never widen this."""
    for rel in rel_paths:
        r = norm_rel(rel)
        if any(r == d.rstrip("/") or r.startswith(d) for d in PROTECTED_DIRS):
            raise Refusal("STORE_WRITE_REFUSED", "%s is authority or harness state; only the authority's own entry points write it" % r)
    product = [r for r in (norm_rel(x) for x in rel_paths) if _is_product(r)]
    if not product:
        return
    iss = active_issue(ctx, task_id, run_id)
    allowed = set(iss["allowed_paths"])
    for r in product:
        if r not in allowed:
            raise Refusal("WRITE_OUTSIDE_ISSUE", "%s is not in the issued cluster %s (%s)"
                          % (r, iss["cluster"] or "(none)", ", ".join(sorted(allowed)) or "no product edits"))


@transition
def check_complete(ctx: Ctx, *, task_id: str, run_id: int, profile: str, audit_green: bool) -> dict[str, Any]:
    """Allow a native completion only when the domain record says so; record
    the continuation intent BEFORE allowing it (F2)."""
    _gate(ctx)
    _integrity(ctx)
    store = ctx.store
    if task_id == store.meta("m2_task"):
        if not audit_green:
            raise Refusal("M2_AUDIT_RED", "the paved-road M2 audit has not exited 0 in this log")
        return _m2_release(ctx)
    pub = _pub_by_task(store, task_id)
    if pub is None:
        raise Refusal("COMPLETE_FOREIGN_TASK", "%s is not a published outcome" % task_id)
    plan = _plan(store)
    node = _node(plan, pub["outcome_id"])
    orow = _outcome(store, pub["outcome_id"])
    if node is None or orow is None:
        raise Refusal("COMPLETE_FOREIGN_TASK", "%s is not in the current revision" % pub["outcome_id"])
    if node["role"] == "repair":
        waiting = _awaiting_owner_repair(store, node["outcome_id"])
        if waiting and orow["status"] != "accepted":
            raise Refusal("OWNER_REPAIR_PENDING", "%s waits on the repair %s of its owner: end this run with "
                                                  "kanban_block kind=dependency (not kanban_complete)" % (node["outcome_id"], waiting))
        if orow["status"] != "accepted":
            raise Refusal("OUTCOME_NOT_ACCEPTED", "%s is %s: a rejected or pending attempt keeps the outcome open"
                          % (node["outcome_id"], orow["status"]))
        if orow["accepted_tree"] != ctx.product_tree():
            raise Refusal("OUTCOME_STALE_ACCEPTANCE", "%s was accepted on another tree" % node["outcome_id"])
        wl, why = load_worklist(ctx.root)
        if wl is None:
            raise Refusal("COMPLETE_" + why, "completion is judged against the measured work list")
        still = sorted(open_obligations(wl) & _owned(store, node["outcome_id"]))
        if still:
            raise Refusal("OUTCOME_OBLIGATION_OPEN", "%s still owns open %s" % (node["outcome_id"], ", ".join(still[:5])))
        return _intent(store, "m3-accepted:%s" % node["outcome_id"], "m3-accepted", task_id,
                       {"outcome_id": node["outcome_id"], "tree": orow["accepted_tree"]})
    if node["role"] == "assess":
        if profile != "reviewer":
            raise Refusal("ASSESS_TERMINATOR", "the assessment ends with kanban_request_review; the reviewer completes it")
        if not audit_green:
            raise Refusal("ASSESS_AUDIT_RED", "the paved-road M4 audit has not exited 0 in this log")
        rec = _assessment(store, node["outcome_id"])
        if rec is None:
            raise Refusal("ASSESS_UNRECORDED", "no bound assessment record for %s (outcome_gate.py assessment-record)" % node["outcome_id"])
        if rec["doc"]["candidate"] != ctx.product_tree():
            raise Refusal("ASSESS_STALE", "the assessment measured another candidate")
        return _intent(store, "m4-assessed:%s" % node["outcome_id"], "m4-assessed", task_id,
                       {"outcome_id": node["outcome_id"], "assessment_seq": rec["seq"], "verdict": rec["doc"]["verdict"],
                        "candidate": rec["doc"]["candidate"]}, set_status=(node["outcome_id"], "assessed"))
    if node["role"] == "deliver":
        # M5's own procedure: the implementer ends with kanban_request_review, the reviewer
        # completes after the stage audit is green; the deciding facts are the stage's
        # domain receipts, bound to this candidate, never a worker's assertion (review R1/R3)
        g = store.conn.execute("SELECT * FROM grants WHERE outcome_id=?", (node["outcome_id"],)).fetchone()
        if not g or g["state"] not in ("granted", "executed"):
            raise Refusal("DELIVER_UNGRANTED", "%s was never admitted" % node["outcome_id"])
        if profile != "reviewer":
            raise Refusal("DELIVER_TERMINATOR", "a delivery stage ends with kanban_request_review reviewer=reviewer; "
                                                "the reviewer completes it after the stage audit")
        if not audit_green:
            raise Refusal("DELIVER_AUDIT_RED", "the paved-road M5 audit has not exited 0 in this log")
        doc = _record_stage_evidence(ctx, node, run_id)
        return _intent(store, "m5-stage-done:%s" % node["outcome_id"], "m5-stage-done", task_id,
                       {"outcome_id": node["outcome_id"], "stage": node.get("stage"), "result": doc},
                       set_status=(node["outcome_id"], "done"))
    raise Refusal("COMPLETE_FOREIGN_TASK", "role %s" % node["role"])


@transition
def check_review(ctx: Ctx, *, task_id: str, run_id: int) -> dict[str, Any]:
    """Who may hand a card to review: M2 only after a green publication
    read-back; an assessment's implementer; a granted delivery stage under its
    own issue. A repair outcome has no review lane: it completes on its
    recorded acceptance."""
    _gate(ctx)
    _integrity(ctx)
    store = ctx.store
    if task_id == store.meta("m2_task"):
        from k4_graph import readback
        gaps = readback(store, ctx.native)
        if store.meta("publication_state") not in ("complete", "released") or gaps:
            raise Refusal("M2_PUBLICATION_INCOMPLETE", "; ".join(gaps[:3]) or store.meta("publication_state") or "unpublished")
        return {"code": "M2_REVIEW_ALLOWED"}
    pub = _pub_by_task(store, task_id)
    if pub and pub["outcome_id"].startswith("assess:"):
        return {"code": "ASSESS_REVIEW_ALLOWED"}
    if pub and pub["outcome_id"].startswith("deliver:"):
        # paved-road-m5: the implementer hands every stage to the reviewer, who completes it
        # after the stage audit on the stage's own receipts (check_complete)
        active_issue(ctx, task_id, run_id)
        return {"code": "DELIVER_REVIEW_ALLOWED"}
    raise Refusal("OUTCOME_NO_REVIEW_LANE", "an outcome card completes on its recorded acceptance; "
                                            "kanban_block if it cannot be accepted")


@transition
def status(ctx: Ctx) -> dict[str, Any]:
    """What an observer (hook fast path, launch check) may know without a task."""
    return {"published": bool(ctx.store.meta("publication_state")), "publication_state": ctx.store.meta("publication_state"),
            "revision": int(ctx.store.meta("revision", "0") or 0), "run_id": ctx.store.meta("run_id")}


def _owned(store: Store, oid: str) -> set[str]:
    rows = store.conn.execute("SELECT obligation_id, outcome_id, rev FROM ownership ORDER BY rev").fetchall()
    cur: dict[str, str] = {}
    for r in rows:
        cur[r["obligation_id"]] = r["outcome_id"]
    return {ob for ob, o in cur.items() if o == oid}


def _intent(store: Store, intent_id: str, kind: str, task_id: str, doc: dict[str, Any],
            set_status: tuple[str, str] | None = None) -> dict[str, Any]:
    with store.txn() as c:
        row = c.execute("SELECT state FROM intents WHERE intent_id=?", (intent_id,)).fetchone()
        if not row:
            c.execute("INSERT INTO intents(intent_id, kind, source_task, doc, state, created_at) VALUES(?,?,?,?,?,?)",
                      (intent_id, kind, task_id, canonical(doc), "pending", time.time()))
        if set_status:
            c.execute("UPDATE outcomes SET status=? WHERE outcome_id=? AND status NOT IN ('accepted','done')", (set_status[1], set_status[0]))
    return {"allow": True, "intent": intent_id}


def _m2_release(ctx: Ctx) -> dict[str, Any]:
    from k4_graph import readback  # kernel module; the hook adds the kernel dir to sys.path
    store = ctx.store
    if store.meta("publication_state") not in ("complete", "released"):
        raise Refusal("M2_PUBLICATION_INCOMPLETE", "the outcome graph is %s; M2 cannot release partial work"
                      % (store.meta("publication_state") or "unpublished"))
    gaps = readback(store, ctx.native)
    if gaps:
        raise Refusal("M2_READBACK", "; ".join(gaps[:4]))
    with store.txn() as c:
        store.set_meta(c, "release_in_progress", "1")
        if not c.execute("SELECT 1 FROM intents WHERE intent_id='m2-release'").fetchone():
            c.execute("INSERT INTO intents(intent_id, kind, source_task, doc, state, created_at) VALUES(?,?,?,?,?,?)",
                      ("m2-release", "m2-release", store.meta("m2_task"), canonical({"revision": store.meta("revision")}),
                       "pending", time.time()))
        if not store.meta("baseline_commit"):
            store.set_meta(c, "baseline_commit", ctx.git_head())
            store.set_meta(c, "baseline_tree", ctx.product_tree())
    return {"allow": True, "intent": "m2-release"}


# ---------------------------------------------------------------------------
# T6: attempts on the SAME outcome
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Automatic owner recovery (user decision 2026-09-26): a runtime failure the
# pure classifier proves pre-existing on the baseline and owned by an ACCEPTED
# outcome is repaired on that owner, once, before the dependent is judged.
# ---------------------------------------------------------------------------


def cause_inputs(ctx: Ctx, iss: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    """(issued, cur, steps, baseline) for planner.runtime_cause.classify, built
    by the AUTHORITY:

      issued    its own issue (cluster, allowed paths) and the issued cluster's
                items from the measured work list
      cur       the failures the measured work list reports for those items,
                each with the server error of its LIVE scenario record, and the
                paths the candidate changed since the issued baseline -- the
                latter measured here from git and the tree
      steps     every committed acceptance in its own ledger, with the paths
                that commit changed (git diff-tree commit^1..commit)
      baseline  the issue's baseline tree digest (its own) and the ACCEPTED
                parity snapshot's scenario records

    The scenario records and the work list are worker-produced parity/runtime
    receipts: the classification is only as authentic as they are (the
    declared measurement trust, cooperative-receipts; contract 8b). Parsing is
    runtime_cause's (failures_of, scenario_records), trust is not."""
    from planner import runtime_cause as RC
    from planner.paths import LOOP_ACCEPTED, PARITY_DIR
    wl, _why = load_worklist(ctx.root)
    wl = wl or {"items": [], "clusters": []}
    row = next((c for c in wl.get("clusters") or [] if isinstance(c, dict) and c.get("id") == iss.get("cluster")), {})
    node = _node(_plan(ctx.store), iss["outcome_id"]) or {}
    issued = {"cluster": iss.get("cluster") or "", "task_id": iss.get("task_id") or "", "items": list(row.get("items") or []),
              "gate_items": [], "scenarios": list(node.get("scenarios") or []), "entry_points": list(node.get("entry_points") or []),
              "write_set": list(iss.get("allowed_paths") or []), "amendments": []}
    changed = changed_product_paths(ctx.root, str(iss.get("baseline_commit") or "")) or []
    cur = {"failures": RC.failures_of(wl, issued, RC.scenario_records(ctx.root / PARITY_DIR)), "changed": changed}
    steps = []
    for r in ctx.store.ledger():
        if r["kind"] != "accept-commit" or not r["doc"].get("commit"):
            continue
        commit = str(r["doc"]["commit"])
        pub = ctx.store.conn.execute("SELECT task_id FROM publication WHERE outcome_id=?", (r["outcome_id"],)).fetchone()
        steps.append({"cluster": str(r["doc"].get("cluster") or r["outcome_id"]), "card": pub[0] if pub else "",
                      "commit": commit, "verdict": "accepted", "outcome_id": r["outcome_id"],
                      "changed": changed_product_paths(ctx.root, commit + "^1", commit) or []})
    baseline = {"tree": str(iss.get("baseline_tree") or ""),
                "records": RC.scenario_records(ctx.root / LOOP_ACCEPTED / "parity")}
    return issued, cur, steps, baseline


def _classify(ctx: Ctx, iss: dict[str, Any]) -> dict[str, Any] | None:
    """planner.runtime_cause.classify on the authority's inputs. None when the
    classifier is absent or the candidate reports no runtime failure (the
    ordinary rejection applies)."""
    try:
        from planner import runtime_cause
    except ImportError:
        return None
    issued, cur, steps, baseline = cause_inputs(ctx, iss)
    if not cur["failures"]:
        return None
    try:
        out = runtime_cause.classify(ctx.root, issued, cur, steps, baseline)
    except Exception as exc:  # a classifier failure is no evidence of anything
        return {"class": "ambiguous", "owner": None, "evidence": [], "reason": "classifier failed: %s" % type(exc).__name__}
    if isinstance(out, dict):
        out = dict(out, failing_scenarios=sorted({str(f.get("scenario") or "") for f in cur["failures"]} - {""}),
                   baseline_tree=baseline["tree"])
    return out if isinstance(out, dict) else None


def _hold_candidate(ctx: Ctx, iss: dict[str, Any]) -> dict[str, str] | None:
    """The dependent's candidate, captured by the authority from the tree: the
    changed product paths since the issued baseline, all inside the issue's
    allowed paths, base64 content ('' = deleted). None when it cannot be held."""
    import base64
    changed = changed_product_paths(ctx.root, str(iss.get("baseline_commit") or ""))
    if changed is None or not set(changed) <= set(iss.get("allowed_paths") or []):
        return None
    out: dict[str, str] = {}
    size = 0
    for rel in changed:
        p = ctx.root / rel
        data = p.read_bytes() if p.is_file() and not p.is_symlink() else b""
        size += len(data)
        out[rel] = base64.b64encode(data).decode("ascii") if p.exists() else ""
    return out if size <= HOLD_MAX_BYTES else None


def _owner_recovery(ctx: Ctx, iss: dict[str, Any], orow: dict[str, Any], *, task_id: str, run_id: int, candidate: str,
                    key: str, reason: str) -> dict[str, Any] | None:
    """None = the ordinary rejection applies (candidate regression, ambiguous,
    no classifier, or a claim the authority cannot validate). A validated
    owner defect: the candidate is HELD (captured, no attempt spent), and ONE
    bounded repair of the owner is scheduled as a durable intent the
    reconciler publishes (sharing the owner's budget key)."""
    store = ctx.store
    oid = iss["outcome_id"]
    res = _classify(ctx, iss)
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
    if not why:
        orow_owner = _outcome(store, owner) if owner else None
        base_rows = [e for e in evidence if isinstance(e, dict) and e.get("kind") == "baseline-record"]
        if not orow_owner or owner == oid or orow_owner["role"] != "repair" or orow_owner["status"] not in ("accepted", "done"):
            why = "owner %r is not another accepted repair outcome" % owner
        elif not base_rows or not any(e.get("kind") == "baseline-failure" for e in evidence):
            why = "no evidence names the failure on the baseline"
        elif any(e.get("baseline_tree") != iss.get("baseline_tree") or e.get("bound_to") != iss.get("baseline_tree")
                 for e in base_rows):
            why = "the evidence names another baseline than the issued one"
        elif not res.get("failing_scenarios"):
            why = "no failing scenario to re-measure after the repair"
        elif orow_owner["budget_limit"] and store.spent(orow_owner["budget_key"]) >= orow_owner["budget_limit"]:
            why = "the owner's budget %s is exhausted" % orow_owner["budget_key"]
        elif store.conn.execute("SELECT 1 FROM intents WHERE intent_id=?", ("owner-repair:%s:%s" % (owner, oid),)).fetchone():
            why = "the one bounded repair of %s for %s was already scheduled" % (owner, oid)
    held = _hold_candidate(ctx, iss) if not why else None
    if not why and held is None:
        why = "the candidate cannot be held (outside the issue, unmeasurable or too large)"
    if why:
        if cls in CAUSE_CLASSES and cls != "candidate-regression":
            try:  # visible report; no blame transfer, no scope grant
                ctx.native.comment(task_id, "%s runtime cause not transferred (%s)" % (MARKER, why[:300]))
            except Exception:
                pass
            with store.txn() as c:
                store.append(c, oid, "cause-report", {"class": cls, "owner": owner, "why": why[:500], "run_id": run_id},
                             attempt_key="%s:cause" % key)
        return None
    owner_row = _outcome(store, owner)
    last = store.conn.execute("SELECT allowed_paths FROM issues WHERE outcome_id=? ORDER BY issue_id DESC LIMIT 1",
                              (owner,)).fetchone()
    repair_paths = sorted(set(json.loads(last[0]) if last else []) | set(owner_doc.get("paths") or []))[:AMEND_MAX_FILES]
    doc = {"owner": owner, "dependent": oid, "dependent_task": task_id, "evidence": evidence,
           "reason": str(res.get("reason") or "")[:500], "repair_paths": repair_paths,
           "repair_scenarios": list(res.get("failing_scenarios") or []), "owner_step": owner_doc,
           "budget": {"key": owner_row["budget_key"], "limit": owner_row["budget_limit"]}}
    with store.txn() as c:
        store.append(c, oid, "owner-hold", {"owner": owner, "candidate": candidate, "files": held,
                                            "baseline_commit": iss.get("baseline_commit"), "run_id": run_id},
                     attempt_key="%s:hold" % key)
        c.execute("INSERT OR IGNORE INTO intents(intent_id, kind, source_task, doc, state, created_at) VALUES(?,?,?,?,?,?)",
                  ("owner-repair:%s:%s" % (owner, oid), "owner-repair", task_id, canonical(doc), "pending", time.time()))
    try:
        ctx.native.comment(task_id, "%s runtime failure proven on the baseline and owned by %s: candidate held, one repair "
                                    "of %s scheduled; this card waits on it (no attempt spent)" % (MARKER, owner, owner))
    except Exception:
        pass
    return {"verdict": "OWNER_RECOVERY", "outcome_id": oid, "owner": owner, "spent": store.spent(orow["budget_key"]),
            "limit": orow["budget_limit"], "exhausted": False, "held_paths": sorted(held),
            "card": "stays open; revert the tree and end this run with kanban_block kind=dependency"}


@transition
def restore_held(ctx: Ctx, *, task_id: str, run_id: int) -> dict[str, Any]:
    """The held candidate of this outcome (after its owner's repair), for the
    caller to write back and re-verify on the repaired baseline. Only paths
    the CURRENT issue allows; the candidate is judged afresh (no acceptance
    carried over)."""
    iss = active_issue(ctx, task_id, run_id)
    rows = [r for r in ctx.store.ledger(iss["outcome_id"]) if r["kind"] == "owner-hold"]
    if not rows:
        raise Refusal("RESTORE_NO_HOLD", "no held candidate on %s" % iss["outcome_id"])
    files = rows[-1]["doc"].get("files") or {}
    outside = sorted(set(files) - set(iss["allowed_paths"]))
    if outside:
        raise Refusal("RESTORE_OUTSIDE_ISSUE", "held paths %s are outside the current issue" % ", ".join(outside[:3]))
    return {"outcome_id": iss["outcome_id"], "files": files, "owner": rows[-1]["doc"].get("owner"),
            "baseline_then": rows[-1]["doc"].get("baseline_commit"), "baseline_now": iss.get("baseline_commit")}


@transition
def record_verdict(ctx: Ctx, *, task_id: str, run_id: int, verdict: str, candidate: str, attempt: str,
                   reason: str = "", retained: dict[str, Any] | None = None) -> dict[str, Any]:
    """REVERTED / VERIFICATION_PENDING / ACCEPTED for the issued cluster. The
    outcome stays the same card whatever the verdict; only its ledger moves."""
    iss = active_issue(ctx, task_id, run_id)
    oid = iss["outcome_id"]
    orow = _outcome(ctx.store, oid)
    key = "%s:%s" % (run_id, attempt)
    if verdict == "REVERTED":
        recovered = _owner_recovery(ctx, iss, orow, task_id=task_id, run_id=run_id, candidate=candidate, key=key,
                                    reason=reason)
        if recovered is not None:
            return recovered
        with ctx.store.txn() as c:
            seq, new = ctx.store.append(c, oid, "reject", {"cluster": iss["cluster"], "candidate": candidate,
                                                           "run_id": run_id, "reason": reason[:500]},
                                        budget_key=orow["budget_key"], attempt_key=key)
        spent = ctx.store.spent(orow["budget_key"])
        if new:
            try:
                ctx.native.comment(task_id, "%s rejected attempt %d of %d on %s: %s" % (
                    MARKER, spent, orow["budget_limit"], iss["cluster"] or oid, reason[:200]))
            except Exception:
                pass  # the ledger is the record; the comment is the visible copy
        exhausted = bool(orow["budget_limit"]) and spent >= orow["budget_limit"]
        if exhausted:
            with ctx.store.txn() as c:
                c.execute("UPDATE outcomes SET status='exhausted' WHERE outcome_id=?", (oid,))
        return {"verdict": verdict, "outcome_id": oid, "spent": spent, "limit": orow["budget_limit"],
                "exhausted": exhausted, "card": "stays open (same outcome)"}
    if verdict == "VERIFICATION_PENDING":
        with ctx.store.txn() as c:
            ctx.store.append(c, oid, "pending", {"cluster": iss["cluster"], "candidate": candidate,
                                                 "baseline_commit": iss["baseline_commit"], "baseline_tree": iss["baseline_tree"],
                                                 "retained": retained or {}, "run_id": run_id, "reason": reason[:500]},
                             attempt_key=key)
        return {"verdict": verdict, "outcome_id": oid, "spent": ctx.store.spent(orow["budget_key"])}
    if verdict == "ACCEPTED":
        out_of_scope = _scope_gaps(ctx, iss)
        if out_of_scope:
            raise Refusal("ACCEPT_OUT_OF_SCOPE", "; ".join(out_of_scope[:4]))
        with ctx.store.txn() as c:
            ctx.store.append(c, oid, "accept-begin", {"cluster": iss["cluster"], "candidate": candidate,
                                                      "baseline_commit": iss["baseline_commit"], "run_id": run_id},
                             attempt_key=key)
        return {"verdict": verdict, "outcome_id": oid, "next": "commit, then outcome_gate.py accept-commit"}
    raise Refusal("VERDICT_UNKNOWN", verdict)


@transition
def accept_commit(ctx: Ctx, *, task_id: str, run_id: int, attempt: str, commit: str,
                  measurement: dict[str, Any]) -> dict[str, Any]:
    """Record the committed acceptance of the issued cluster and decide whether
    the OUTCOME is now accepted: every owned obligation absent from the rebuilt
    work list and the outcome's check class measured on this tree."""
    iss = active_issue(ctx, task_id, run_id)
    oid = iss["outcome_id"]
    key = "%s:%s" % (run_id, attempt)
    begin = [r for r in ctx.store.ledger(oid) if r["kind"] == "accept-begin" and r["attempt_key"] == key]
    if not begin:
        raise Refusal("ACCEPT_UNBEGUN", "no accept-begin for attempt %s" % attempt)
    tree = ctx.product_tree()
    if tree != begin[-1]["doc"]["candidate"]:
        raise Refusal("ACCEPT_TREE_DRIFT", "the committed tree is not the verified candidate")
    # the commit IS the working tree's HEAD, sits directly on the issued baseline,
    # and changes nothing outside the issued scope: measured here, from git
    if ctx.git_head() != commit:
        raise Refusal("ACCEPT_COMMIT_MISMATCH", "HEAD is not the named commit %s" % commit[:12])
    parent = _git(ctx.root, "rev-parse", "--verify", "-q", "%s^1" % commit).stdout.strip()
    if not iss.get("baseline_commit") or parent != iss["baseline_commit"]:
        raise Refusal("ACCEPT_BASELINE_ANCESTRY", "commit %s is not a child of the issued baseline %s"
                      % (commit[:12], str(iss.get("baseline_commit") or "none")[:12]))
    out_of_scope = _scope_gaps(ctx, iss, commit)
    if out_of_scope:
        raise Refusal("ACCEPT_OUT_OF_SCOPE", "; ".join(out_of_scope[:4]))
    wl, why = load_worklist(ctx.root)
    if wl is None:
        raise Refusal("ACCEPT_" + why, "acceptance reads the rebuilt work list")
    open_now = sorted(open_obligations(wl))
    plan = _plan(ctx.store)
    node = _node(plan, oid) or {}
    rec = record_measurement(ctx, tree=tree, classes=list(measurement.get("classes") or []),
                             scenarios=list(measurement.get("scenarios") or []), open_ids=open_now, source="accept:%s" % key,
                             checks=requirement_measurement(ctx.root, plan, node, wl, list(measurement.get("scenarios") or []), tree),
                             asserted_by=_asserted_by(ctx))
    owned = _owned(ctx.store, oid)
    covered = _covers(node, rec)
    evidence_gaps = repair_evidence_gaps(ctx.root, node, tree)
    done = not (owned & set(open_now)) and covered and not evidence_gaps
    with ctx.store.txn() as c:
        ctx.store.append(c, oid, "accept-commit", {"commit": commit, "tree": tree, "cluster": iss["cluster"],
                                                   "outcome_accepted": done, "repair_evidence_gaps": evidence_gaps},
                         attempt_key=key)
        ctx.store.set_meta(c, "accepted_commit", commit)
        ctx.store.set_meta(c, "accepted_tree", tree)
        if done:
            c.execute("UPDATE outcomes SET status='accepted', accepted_tree=?, accepted_commit=?, accepted_rev=? WHERE outcome_id=?",
                      (tree, commit, int(ctx.store.meta("revision", "0")), oid))
    return {"outcome_id": oid, "outcome_accepted": done, "open_owned": sorted(owned & set(open_now)),
            "covered": covered, "repair_evidence_gaps": evidence_gaps}


@transition
def evaluate_recovered(ctx: Ctx, *, task_id: str, run_id: int, measurement: dict[str, Any]) -> dict[str, Any] | None:
    """Finish an acceptance that recovery recorded (review R5): the recovered
    commit is the current tree, the worker re-measured it, and the OUTCOME is
    judged exactly as accept_commit judges it. None when there is nothing to
    finish. Spends nothing and never re-commits."""
    iss = active_issue(ctx, task_id, run_id)
    oid = iss["outcome_id"]
    rows = [r for r in ctx.store.ledger(oid) if r["kind"] == "accept-commit"]
    if not rows or not rows[-1]["doc"].get("recovered") or rows[-1]["doc"].get("outcome_accepted"):
        return None
    last = rows[-1]
    tree = ctx.product_tree()
    if tree != last["doc"]["tree"]:
        raise Refusal("ACCEPT_TREE_DRIFT", "the tree is not the recovered commit's tree")
    wl, why = load_worklist(ctx.root)
    if wl is None:
        raise Refusal("ACCEPT_" + why, "acceptance reads the rebuilt work list")
    open_now = sorted(open_obligations(wl))
    plan = _plan(ctx.store)
    node = _node(plan, oid) or {}
    rec = record_measurement(ctx, tree=tree, classes=list(measurement.get("classes") or []),
                             scenarios=list(measurement.get("scenarios") or []), open_ids=open_now,
                             source="recovered:%s" % last["attempt_key"],
                             checks=requirement_measurement(ctx.root, plan, node, wl, list(measurement.get("scenarios") or []), tree),
                             asserted_by=_asserted_by(ctx))
    owned = _owned(ctx.store, oid)
    covered = _covers(node, rec)
    done = not (owned & set(open_now)) and covered
    with ctx.store.txn() as c:
        ctx.store.append(c, oid, "accept-evaluated", {"commit": last["doc"]["commit"], "tree": tree, "outcome_accepted": done,
                                                      "run_id": run_id}, attempt_key="%s:evaluated" % last["attempt_key"])
        if done:
            c.execute("UPDATE outcomes SET status='accepted', accepted_tree=?, accepted_commit=?, accepted_rev=? WHERE outcome_id=?",
                      (tree, last["doc"]["commit"], int(ctx.store.meta("revision", "0")), oid))
    return {"outcome_id": oid, "outcome_accepted": done, "open_owned": sorted(owned & set(open_now)), "covered": covered,
            "commit": last["doc"]["commit"]}


def recover_accept(ctx: Ctx, *, oid: str, commits: Callable[[str], list[tuple[str, str, str]]],
                   skip_run: int | None = None) -> list[dict[str, Any]]:
    """After a crash between accept-begin and accept-commit: find the commit
    whose parent is the recorded baseline and whose product tree is the
    candidate (commits(baseline) -> [(sha, parent, tree)]); record it, or
    abort the acceptance (the candidate stays pending). Never spends again."""
    out = []
    rows = ctx.store.ledger(oid)
    closed = {r["attempt_key"] for r in rows if r["kind"] in ("accept-commit", "accept-aborted")}
    for r in rows:
        if r["kind"] != "accept-begin" or r["attempt_key"] in closed:
            continue
        if skip_run is not None and r["doc"].get("run_id") == skip_run:
            continue
        hits = [s for s, parent, tree in commits(r["doc"]["baseline_commit"])
                if parent == r["doc"]["baseline_commit"] and tree == r["doc"]["candidate"]]
        if len(hits) > 1:
            raise Refusal("ACCEPT_RECOVERY_AMBIGUOUS", "%d commits on %s carry candidate %s; the acceptance of attempt %s "
                          "is not guessed" % (len(hits), r["doc"]["baseline_commit"][:12], r["doc"]["candidate"][:12], r["attempt_key"]))
        with ctx.store.txn() as c:
            if len(hits) == 1:
                ctx.store.append(c, oid, "accept-commit", {"commit": hits[0], "tree": r["doc"]["candidate"],
                                                           "cluster": r["doc"]["cluster"], "recovered": True,
                                                           "outcome_accepted": False}, attempt_key=r["attempt_key"])
                ctx.store.set_meta(c, "accepted_commit", hits[0])
                ctx.store.set_meta(c, "accepted_tree", r["doc"]["candidate"])
                out.append({"attempt": r["attempt_key"], "recovered_commit": hits[0]})
            else:
                ctx.store.append(c, oid, "accept-aborted", {"why": "%d matching commits" % len(hits)}, attempt_key=r["attempt_key"])
                ctx.store.append(c, oid, "pending", {"candidate": r["doc"]["candidate"], "baseline_commit": r["doc"]["baseline_commit"],
                                                     "reason": "acceptance interrupted before commit; candidate retained"},
                                 attempt_key=r["attempt_key"] + ":aborted")
                out.append({"attempt": r["attempt_key"], "aborted": True})
    return out


@transition
def restore_pending(ctx: Ctx, *, task_id: str, run_id: int, candidate_now: str) -> dict[str, Any]:
    """A new run adopts a retained candidate only when its digest is the one
    recorded and the accepted baseline did not move underneath it."""
    iss = active_issue(ctx, task_id, run_id)
    pend = _open_pending(ctx.store, iss["outcome_id"])
    if pend is None:
        raise Refusal("RESTORE_NO_PENDING", "no retained candidate on %s" % iss["outcome_id"])
    if candidate_now != pend["doc"]["candidate"]:
        raise Refusal("RESTORE_DIGEST", "the restored tree is not the retained candidate")
    moved = (ctx.store.meta("accepted_commit") or ctx.store.meta("baseline_commit")) != pend["doc"]["baseline_commit"]
    with ctx.store.txn() as c:
        ctx.store.append(c, iss["outcome_id"], "restore", {"candidate": candidate_now, "original_baseline": pend["doc"]["baseline_commit"],
                                                           "current_baseline": ctx.store.meta("accepted_commit") or ctx.store.meta("baseline_commit"),
                                                           "baseline_moved": moved, "run_id": run_id, "closes_pending": False},
                         attempt_key="%s:restore:%s" % (run_id, pend["seq"]))
    return {"outcome_id": iss["outcome_id"], "baseline_moved": moved, "spent": ctx.store.spent(_outcome(ctx.store, iss["outcome_id"])["budget_key"])}


# ---------------------------------------------------------------------------
# F3: measurements and proof applicability
# ---------------------------------------------------------------------------

def _asserted_by(ctx: Ctx) -> str:
    """Who stands behind a measurement's check classes. The authority measures
    tree identity, scope and ancestry itself; the build, test and parity
    classes are the worker's receipts (cooperative: OUTCOME-BOARD-CONTRACT 8a,
    the open measurement-trust decision). Recorded, never hidden."""
    return "worker-receipts"


def record_measurement(ctx: Ctx, *, tree: str, classes: list[str], scenarios: list[str], open_ids: list[str],
                       source: str, checks: dict[str, dict[str, str]] | None = None,
                       asserted_by: str = "") -> dict[str, Any]:
    doc = {"tree": tree, "classes": sorted(set(classes)), "scenarios": sorted(set(scenarios)),
           "open": sorted(set(open_ids)), "source": source}
    if asserted_by:
        doc["classes_asserted_by"] = asserted_by
    if checks:
        # plan semantics v1: the requirement checks RECOMPUTED on this tree
        # (planner.requirement_checks), never supplied by the caller; only the
        # passing ones cover (_covers), the rest stay recorded as evidence
        from planner.requirement_checks import passed
        doc["checks"] = passed(checks)
        doc["check_status"] = {k: dict(v) for k, v in sorted(checks.items())}
    with ctx.store.txn() as c:
        ctx.store.append(c, "_measure", "measurement", doc, attempt_key="%s:%s" % (source, tree))
    return doc


def proof_applicable(store: Store, node: dict[str, Any], orow: dict[str, Any], tree: str) -> bool:
    if orow.get("status") != "accepted":
        return False
    if orow.get("accepted_tree") == tree:
        return True
    owned = _owned(store, node["outcome_id"])
    for r in reversed(store.ledger("_measure")):
        m = r["doc"]
        if m["tree"] == tree and _covers(node, m) and not (owned & set(m["open"])):
            return True
    return False


def progress_account(store: Store, tree: str) -> dict[str, Any]:
    """active = baseline + additions - replaced/removed = accepted + unfinished;
    accepted = proof applicable + awaiting revalidation. Satisfied obligations,
    unresolved responsibilities and milestones are reported beside it."""
    plan = store.current_revision() or {"nodes": [], "unresolved": [], "dispositions": [], "counts": {}}
    repair = [n for n in plan["nodes"] if n.get("role") == "repair"]
    first = store.conn.execute("SELECT doc FROM revisions WHERE rev=1").fetchone()
    base_nodes = [n for n in json.loads(first[0])["nodes"] if n.get("role") == "repair"] if first else []
    base_ids = {n["outcome_id"] for n in base_nodes}
    now_ids = {n["outcome_id"] for n in repair}
    replaced = {n["outcome_id"] for n in repair if n.get("replaced_by")}
    active = now_ids - replaced
    accepted = [n for n in repair if n["outcome_id"] in active and (_outcome(store, n["outcome_id"]) or {}).get("status") == "accepted"]
    applicable = [n for n in accepted if proof_applicable(store, n, _outcome(store, n["outcome_id"]), tree)]
    acc = {
        "baseline": len(base_ids),
        "additions": len(now_ids - base_ids),
        "replaced_or_removed": len((base_ids - now_ids) | (replaced & base_ids)),
        "active": len(active),
        "accepted_historically": len(accepted),
        "proof_applicable": len(applicable),
        "awaiting_revalidation": len(accepted) - len(applicable),
        "unfinished": len(active) - len(accepted),
        "satisfied_obligations": sum(1 for d in plan.get("dispositions") or [] if d.get("disposition") == "satisfied"),
        "unresolved": [u["id"] for u in plan.get("unresolved") or []],
        "milestones": {n["outcome_id"]: (_outcome(store, n["outcome_id"]) or {}).get("status", "planned")
                       for n in plan["nodes"] if n.get("role") in ("assess", "deliver")},
        "complete_claim_allowed": not plan.get("unresolved") and len(accepted) == len(active) and len(applicable) == len(accepted),
    }
    assert acc["baseline"] + acc["additions"] - acc["replaced_or_removed"] == acc["active"], acc
    assert acc["accepted_historically"] + acc["unfinished"] == acc["active"], acc
    return acc


# ---------------------------------------------------------------------------
# M4: the assessment record (measured by the worker, completed by the reviewer)
# ---------------------------------------------------------------------------

def _assessment(store: Store, oid: str) -> dict[str, Any] | None:
    rows = [r for r in store.ledger(oid) if r["kind"] == "assessment"]
    return rows[-1] if rows else None


@transition
def record_assessment(ctx: Ctx, *, task_id: str, run_id: int, verdict_doc: dict[str, Any]) -> dict[str, Any]:
    iss = active_issue(ctx, task_id, run_id)
    if iss["outcome_id"].split(":g")[0] != ASSESS_PREFIX:
        raise Refusal("ASSESS_FOREIGN", "%s is not an assessment" % iss["outcome_id"])
    if str(verdict_doc.get("card_id") or "") != task_id:
        raise Refusal("ASSESS_UNBOUND", "the verdict names card %r, not %s" % (verdict_doc.get("card_id"), task_id))
    token = str(verdict_doc.get("verdict") or verdict_doc.get("token") or "").upper()
    if not token:
        raise Refusal("ASSESS_UNBOUND", "the verdict carries no token")
    wl, why = load_worklist(ctx.root)
    tree = ctx.product_tree()
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
    measured = [str(s) for s in verdict_doc.get("parity_scenarios") or []]
    doc = {"verdict": token, "candidate": tree, "worklist": why or "present", "obligations": obligations,
           "failed_floors": list(verdict_doc.get("failed_floors") or []),
           "release_blockers": list(verdict_doc.get("release_blockers") or []),
           "qualifications": list(verdict_doc.get("qualifications") or []), "run_id": run_id}
    with ctx.store.txn() as c:
        seq, _ = ctx.store.append(c, iss["outcome_id"], "assessment", doc, attempt_key="%s:%s" % (run_id, sha(canonical(doc))[:16]))
    if wl is not None:
        # plan semantics v1: the requirement checks of every owner node, recomputed on
        # this tree (a revalidation of historically accepted requirement owners)
        checks: dict[str, dict[str, str]] = {}
        plan = _plan(ctx.store)
        for n in plan.get("nodes") or []:
            if n.get("role") == "repair":
                got = requirement_measurement(ctx.root, plan, n, wl, measured, tree)
                if got:
                    checks.update(got)
        # the classes the verification of THIS tree executed (planner.measurement), not a stamp of all five
        from planner.measurement import classes as _proven, execution as _execution
        from planner.paths import VERIFY_RUN as _VR
        try:
            _run = json.loads((Path(ctx.root) / _VR).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _run = {}
        record_measurement(ctx, tree=tree, classes=_proven(_execution(wl, _run, tree, ctx.root)), scenarios=measured,
                           open_ids=[o["id"] for o in obligations], source="assessment:%s" % iss["outcome_id"],
                           checks=checks or None, asserted_by=_asserted_by(ctx))
    return {"assessment_seq": seq, "verdict": token, "open_obligations": len(obligations)}


# ---------------------------------------------------------------------------
# T9: REFUSE -> bounded repairs -> successor assessment
# ---------------------------------------------------------------------------

def plan_after_refuse(store: Store, plan: dict[str, Any], intent: dict[str, Any]) -> dict[str, Any] | Refusal:
    """The next revision, or a typed stop. Never reopens or overwrites the
    completed assessment; never renews a budget. The revision itself is
    outcome_checks.refuse_revision (shared with native control); here: the
    recorded assessment, the delivery-cycle stop and a successor assessment."""
    rec = next((r for r in store.ledger(intent["outcome_id"]) if r["seq"] == intent["assessment_seq"]), None)
    if rec is None:
        return Refusal("REFUSE_UNRECORDED", "assessment row %s is gone" % intent["assessment_seq"])
    gen = int(intent["outcome_id"].rsplit(":g", 1)[1])
    if gen >= MAX_ASSESSMENT_GENERATIONS:
        return Refusal("ASSESSMENT_BOUND", "generation %d reached the bound %d; escalate" % (gen, MAX_ASSESSMENT_GENERATIONS))
    executed = store.conn.execute("SELECT outcome_id FROM grants WHERE state IN ('granted','executed','done')").fetchall()
    if executed:
        return Refusal("DELIVERY_CYCLE_UNSUPPORTED", "delivery stage %s already ran for a candidate; a second cycle is an explicit stop" % executed[0][0])
    if rec["doc"]["worklist"] != "present":
        return Refusal("REFUSE_" + rec["doc"]["worklist"], "the assessment has no measured work list")

    def status_of(oid: str) -> str:
        return str((_outcome(store, oid) or {}).get("status") or "")

    def budget_of(oid: str) -> dict[str, Any]:
        o = _outcome(store, oid) or {}
        return {"key": o.get("budget_key"), "limit": o.get("budget_limit")}

    return refuse_revision(plan, rec["doc"]["obligations"], gen=gen, trigger=intent["outcome_id"], verdict=intent["verdict"],
                           status_of=status_of, budget_of=budget_of, successor=True)


def plan_owner_repair(store: Store, plan: dict[str, Any], doc: dict[str, Any]) -> dict[str, Any] | Refusal | None:
    """outcome_checks.owner_repair_revision, with the open assessments read
    from the store (an assessment not yet assessed/done gains the repair)."""
    open_assessments = {n["outcome_id"] for n in plan["nodes"] if n.get("role") == "assess"
                        and (_outcome(store, n["outcome_id"]) or {}).get("status") not in ("assessed", "done")}
    return owner_repair_revision(plan, doc, open_assessments=open_assessments)


def plan_split(store: Store, plan: dict[str, Any], oid: str, groups: dict[str, list[str]], *, evidence: str) -> dict[str, Any]:
    """Split an open, unissued outcome into successors that partition its
    obligations EXACTLY and share its budget key (one remaining allowance).
    The original stays in the plan as replaced (lineage), never deleted.
    Publishing a split natively is an explicit stop in this release
    (SPLIT_NATIVE_UNSUPPORTED); this is the revision and budget contract."""
    if not evidence.strip():
        raise Refusal("SPLIT_UNEVIDENCED", "a split needs recorded evidence")
    node = _node(plan, oid)
    orow = _outcome(store, oid)
    if node is None or orow is None or node.get("role") != "repair" or orow["status"] != "open":
        raise Refusal("SPLIT_REFUSED", "%s is not an open repair outcome" % oid)
    if store.conn.execute("SELECT 1 FROM issues WHERE outcome_id=? AND state='active'", (oid,)).fetchone():
        raise Refusal("SPLIT_REFUSED", "%s has an active execution issue" % oid)
    parts = [ob for obs in groups.values() for ob in obs]
    if sorted(parts) != sorted(node["obligations"]) or len(parts) != len(set(parts)):
        raise Refusal("SPLIT_NOT_CONSERVING", "successors must partition %s's obligations exactly" % oid)
    nodes = []
    succ_ids = []
    for n in plan["nodes"]:
        if n["outcome_id"] == oid:
            nodes.append(dict(n, replaced_by=["%s/split:%s" % (oid, k) for k in sorted(groups)]))
        else:
            nodes.append(n)
    for name in sorted(groups):
        sid = "%s/split:%s" % (oid, name)
        succ_ids.append(sid)
        s = dict(node, outcome_id=sid, obligations=sorted(groups[name]), natural_key="",
                 lineage=[{"split_from": oid, "evidence": evidence}],
                 budget={"key": orow["budget_key"], "limit": orow["budget_limit"]})
        s["title"] = "%s (part %s)" % (node["title"], name)
        s["description"] = render_description(s)
        nodes.append(s)
    ownership = dict(plan.get("ownership") or {})
    for sid, name in zip(succ_ids, sorted(groups)):
        for ob in groups[name]:
            ownership[ob] = sid
    counts = dict(plan.get("counts") or {})
    counts["additions"] = int(counts.get("additions") or 0) + len(succ_ids)
    counts["replaced_or_removed"] = int(counts.get("replaced_or_removed") or 0) + 1
    doc = dict(plan, revision=int(plan["revision"]) + 1, parent_revision=int(plan["revision"]), kind="split",
               nodes=nodes, ownership=ownership, counts=counts)
    doc.pop("digest", None)
    doc["digest"] = plan_digest(doc)
    return doc


# ---------------------------------------------------------------------------
# F5: M5 stage predicates (separate from assess_eligibility)
# ---------------------------------------------------------------------------


def delivery_facts(ctx: Ctx, stage_oid: str) -> dict[str, Any]:
    store = ctx.store
    plan = _plan(store)
    node = _node(plan, stage_oid) or {}
    bind = (node.get("binding") or {}).get("assessment") or ""
    rec = _assessment(store, bind) if bind else None
    arow = _outcome(store, bind) if bind else None
    wl, why = load_worklist(ctx.root)
    tree = ctx.product_tree()
    open_repairs = [n["outcome_id"] for n in plan["nodes"] if n.get("role") == "repair"
                    and (_outcome(store, n["outcome_id"]) or {}).get("status") not in ("accepted", "done")]
    facts: dict[str, Any] = {
        "candidate": tree,
        "assessment": {"bound": bool(rec and arow and arow["status"] in ("assessed", "done")),
                       "verdict": (rec or {}).get("doc", {}).get("verdict"), "candidate": (rec or {}).get("doc", {}).get("candidate")},
        "worklist": {"state": "present" if wl is not None else why.replace("WORKLIST_", "").lower(),
                     "open_mandatory": len(open_obligations(wl)) if wl is not None else None},
        "open_repairs": open_repairs,
        # a delivery-blocking unresolved row stands while any of its obligations is still measured open
        # (or it names none); a ship-blocking one (an unverified entry point) is a deferred release
        # qualification: it never prevents the measurement that resolves it
        "unresolved_ownership": [u["id"] for u in plan.get("unresolved") or [] if u.get("blocks", "delivery") == "delivery"
                                 and (not u.get("obligations") or wl is None or set(u["obligations"]) & open_obligations(wl))],
        "qualifications": list(((rec or {}).get("doc") or {}).get("qualifications") or []) + [
            {"id": u["id"], "class": "deferred", "satisfied": False, "before": "ship"}
            for u in plan.get("unresolved") or [] if u.get("blocks") == "ship"],
    }
    # an earlier stage counts only as its RECORDED, derived result that its receipts still
    # support for the current candidate (re-derived here; a worker's flag is never read)
    for prev, key in (("prepare", "preflight"), ("push", "deploy")):
        res = [r for r in store.ledger("deliver:%s:c1" % prev) if r["kind"] == "stage-result"]
        ok, doc, _reasons = stage_evidence(ctx.root, store, prev)
        if res and ok and res[-1]["doc"].get("candidate_sha") == doc.get("candidate_sha"):
            facts[key] = dict(doc, accepted=True, result=True, candidate=tree)
    facts["plan_coherent"] = True
    facts["build_authorized"] = bool((facts.get("preflight") or {}).get("pipeline_eligible"))
    facts["live_inputs"] = bool((facts.get("deploy") or {}).get("https"))
    return facts


def _stage_assessment_task(store: Store) -> str:
    plan = store.current_revision() or {}
    node = next((n for n in plan.get("nodes") or [] if n["outcome_id"] == "deliver:prepare:c1"), {})
    bind = (node.get("binding") or {}).get("assessment") or ""
    row = store.conn.execute("SELECT task_id FROM publication WHERE outcome_id=?", (bind,)).fetchone() if bind else None
    return row[0] if row and row[0] else ""


def stage_evidence(root: Path, store: Store, stage: str) -> tuple[bool, dict[str, Any], list[str]]:
    """outcome_checks.stage_evidence_facts with the bound assessment's task and
    the landed push effects read from the store."""
    def landed(head: str) -> bool:
        return bool(head and store.conn.execute("SELECT effect_id FROM effects WHERE kind='push' AND candidate=? AND state='landed'",
                                                (head,)).fetchone())
    return stage_evidence_facts(root, stage, m4_task=_stage_assessment_task(store), push_landed=landed)


def _record_stage_evidence(ctx: Ctx, node: dict[str, Any], run_id: int) -> dict[str, Any]:
    ok, doc, reasons = stage_evidence(ctx.root, ctx.store, str(node.get("stage") or ""))
    if not ok:
        code = "STAGE_EVIDENCE_MISSING" if any(r.startswith("STAGE_EVIDENCE_MISSING") for r in reasons) else "STAGE_EVIDENCE_REFUSED"
        raise Refusal(code, "; ".join(reasons[:4]))
    with ctx.store.txn() as c:
        ctx.store.append(c, node["outcome_id"], "stage-result", doc, attempt_key="%s:%s" % (run_id, sha(canonical(doc))[:16]))
        c.execute("UPDATE grants SET state='executed' WHERE outcome_id=?", (node["outcome_id"],))
    return doc


@transition
def record_stage_result(ctx: Ctx, *, task_id: str, run_id: int, result: dict[str, Any] | None = None) -> dict[str, Any]:
    """Record the stage's derived evidence (the reviewer's completion does the same).
    A caller-supplied result is refused: the deciding facts are the receipts."""
    if result is not None:
        raise Refusal("STAGE_RESULT_ASSERTED", "stage results are derived from the stage's receipts; a supplied result "
                                               "(%s) is never recorded" % ", ".join(sorted(result))[:120])
    iss = active_issue(ctx, task_id, run_id)
    if not iss["outcome_id"].startswith("deliver:"):
        raise Refusal("DELIVER_FOREIGN", "%s is not a delivery stage" % iss["outcome_id"])
    node = _node(_plan(ctx.store), iss["outcome_id"]) or {}
    return _record_stage_evidence(ctx, node, run_id)


def m4_closure(root: Path) -> dict[str, Any] | None:
    """The M4 closure an outcome-board run delivers from: the assessment the M5
    stages are bound to, completed (assessed) with its recorded verdict. Read
    from the authority, never from the serial loop's steps.json."""
    from planner.outcome_protocol import authority_endpoint, select_protocol
    from planner.outcome_store import service_binding
    if service_binding() is None:
        ep = authority_endpoint(select_protocol(Path(root)))
        if ep:
            return m4_closure_view(RemoteCtx(Path(root), ep))
    try:
        store = Store(Path(root))
    except StoreError:
        return None
    try:
        return _m4_closure(store)
    finally:
        store.close()


def _m4_closure(store: Store) -> dict[str, Any] | None:
    plan = store.current_revision() or {}
    node = next((n for n in plan.get("nodes") or [] if n["outcome_id"] == "deliver:prepare:c1"), {})
    bind = (node.get("binding") or {}).get("assessment") or ""
    orow = _outcome(store, bind) if bind else None
    rec = _assessment(store, bind) if bind else None
    if not orow or orow["status"] not in ("assessed", "done") or not rec:
        return None
    return {"closed": True, "card": _stage_assessment_task(store), "verdict": rec["doc"]["verdict"],
            "assessment": bind}


# ---------------------------------------------------------------------------
# F4: external effects under the one serialization mechanism
# ---------------------------------------------------------------------------

def admit_effect(store: Store, *, kind: str, candidate: str, operation_id: str, expected_rev: int,
                 predicate: Callable[[], list[str]] | None = None, doc: dict[str, Any] | None = None) -> str:
    """Admission in ONE transaction: the revision the caller checked is still
    current, no other effect is unresolved, and the predicate holds. Then the
    effect is recorded BEFORE it starts. A revision that commits later refuses
    while this effect is unresolved (Store.commit_revision)."""
    eid = "%s:%s" % (kind, operation_id)
    with store.txn() as c:
        row = c.execute("SELECT state FROM effects WHERE effect_id=?", (eid,)).fetchone()
        if row:
            raise Refusal("EFFECT_EXISTS", "%s is already %s; recover it by identity, never repeat it" % (eid, row[0]))
        cur = int(store.meta("revision", "0") or 0)
        if cur != expected_rev:
            raise Refusal("EFFECT_STALE_REVISION", "checked revision %d; current is %d" % (expected_rev, cur))
        other = store.unresolved_effects(c)
        if other:
            raise Refusal("EFFECT_IN_FLIGHT", "%s is %s" % (other[0]["effect_id"], other[0]["state"]))
        reasons = predicate() if predicate else []
        if reasons:
            raise Refusal("EFFECT_PREDICATE", "; ".join(reasons))
        gen = int(store.meta("generation", "0") or 0)
        now = time.time()
        c.execute("INSERT INTO effects(effect_id, kind, candidate, operation_id, rev, generation, state, doc, admitted_at, updated_at) "
                  "VALUES(?,?,?,?,?,?,?,?,?,?)", (eid, kind, candidate, operation_id, cur, gen, "admitted",
                                                   canonical(doc or {}), now, now))
    return eid


EFFECT_STAGE = {"push": "push", "deploy": "push"}


@transition
def admit_delivery_effect(ctx: Ctx, *, task_id: str, run_id: int, kind: str, operation_id: str) -> str:
    """Only the GRANTED M5 stage that owns the effect may admit it, for the
    current Git candidate that its preflight evidence admitted, under the one
    serialization lock (review R2). Everything else is refused before a row
    is written."""
    iss = active_issue(ctx, task_id, run_id)
    stage = EFFECT_STAGE.get(kind)
    oid = iss["outcome_id"]
    if not stage or not oid.startswith("deliver:%s:" % stage):
        raise Refusal("EFFECT_STAGE", "%s may not admit a %s effect; only the granted M5 %s stage may"
                      % (oid, kind, {"push": "DEPLOY"}.get(stage or "", "?")))
    head = _git_head(ctx.root)

    def predicate() -> list[str]:
        out = []
        g = ctx.store.conn.execute("SELECT state FROM grants WHERE outcome_id=?", (oid,)).fetchone()
        if not g or g[0] not in ("granted", "executed"):
            out.append("EFFECT_UNGRANTED:%s" % oid)
        ok, pre, reasons = stage_evidence(ctx.root, ctx.store, "prepare")
        rec = [r for r in ctx.store.ledger("deliver:prepare:c1") if r["kind"] == "stage-result"]
        if not ok or not rec or rec[-1]["doc"].get("candidate_sha") != head:
            out.append("EFFECT_INELIGIBLE:preflight evidence does not admit %s (%s)" % (head[:12], "; ".join(reasons[:2]) or "no recorded preflight"))
        return out

    return admit_effect(ctx.store, kind=kind, candidate=head, operation_id=operation_id,
                        expected_rev=int(ctx.store.meta("revision", "0") or 0), predicate=predicate,
                        doc={"worker_pid": int((ctx.native.task(task_id) or {}).get("worker_pid") or 0),
                             "task_id": task_id, "run_id": run_id, "stage": oid})


@transition
def admit_effect_checked(ctx: Ctx, *, task_id: str, run_id: int, kind: str, operation_id: str, revision: int) -> str:
    """outcome_gate.py effect-admit: the revision the caller checked must still
    be current, then the ordinary delivery-effect admission."""
    if int(ctx.store.meta("revision", "0") or 0) != int(revision):
        raise Refusal("EFFECT_STALE_REVISION", "checked revision %d is not current" % int(revision))
    return admit_delivery_effect(ctx, task_id=task_id, run_id=run_id, kind=kind, operation_id=operation_id)


@transition
def record_delivery_effect(ctx: Ctx, *, task_id: str, run_id: int, effect_id: str, state: str,
                           detail: dict[str, Any] | None = None) -> dict[str, Any]:
    """The effect's owner reports progress on its OWN admitted effect. The
    state machine (record_effect) refuses a regression; the result of a push
    is the caller's report of an external system (cooperative, recorded as
    such), never an admission."""
    active_issue(ctx, task_id, run_id)
    row = ctx.store.conn.execute("SELECT doc FROM effects WHERE effect_id=?", (effect_id,)).fetchone()
    if not row:
        raise Refusal("EFFECT_UNKNOWN", effect_id)
    doc = json.loads(row[0] or "{}")
    if doc.get("task_id") and doc.get("task_id") != task_id:
        raise Refusal("EFFECT_FOREIGN", "%s was admitted for %s, not %s" % (effect_id, doc.get("task_id"), task_id))
    record_effect(ctx.store, effect_id, state, dict(doc, reported=dict(detail or {}, by="effect-owner")))
    return {"effect_id": effect_id, "state": state}


@transition
def push_admit(ctx: Ctx, *, task_id: str, run_id: int, remote: str, ref: str) -> dict[str, Any]:
    """The admission half of push_candidate, for a caller that performs the push
    itself (the service holds no push credential): an already recorded push is
    reported and never admitted twice."""
    head = _git_head(ctx.root)
    op = "%s:%s@%s" % (remote, ref, head)
    eid = "push:%s" % op
    row = ctx.store.conn.execute("SELECT state FROM effects WHERE effect_id=?", (eid,)).fetchone()
    if row:
        return {"effect_id": eid, "operation_id": op, "head": head, "state": row[0], "already": True}
    admit_delivery_effect(ctx, task_id=task_id, run_id=run_id, kind="push", operation_id=op)
    return {"effect_id": eid, "operation_id": op, "head": head, "state": "admitted", "already": False}


@transition
def m4_closure_view(ctx: Ctx) -> dict[str, Any] | None:
    return _m4_closure(ctx.store)


def push_candidate(ctx: Ctx, *, task_id: str, run_id: int, remote: str, ref: str) -> dict[str, Any]:
    """The M5 DEPLOY publication step under the outcome protocol: admit the push
    effect (recorded BEFORE it starts), push exactly HEAD to <remote> <ref>,
    record sent, then establish the result by identity. A push already recorded
    for this candidate is never repeated: it is reported (landed) or probed."""
    head = _git_head(ctx.root)
    op = "%s:%s@%s" % (remote, ref, head)
    eid = "push:%s" % op
    row = ctx.store.conn.execute("SELECT state FROM effects WHERE effect_id=?", (eid,)).fetchone()
    if row:
        if row[0] in ("landed", "failed"):
            return {"effect_id": eid, "state": row[0], "already": True}
        state = push_probe(ctx.root)(dict(kind="push", operation_id=op)) or "uncertain"
        record_effect(ctx.store, eid, state, {"recovered": True})
        return {"effect_id": eid, "state": state, "already": True}
    admit_delivery_effect(ctx, task_id=task_id, run_id=run_id, kind="push", operation_id=op)
    p = subprocess.run(["git", "-C", str(ctx.root), "push", remote, "%s:%s" % (head, ref)], capture_output=True, text=True, timeout=600)
    record_effect(ctx.store, eid, "sent", {"rc": p.returncode, "stderr": (p.stderr or "")[-400:]})
    from planner.outcome_store import fault
    fault("after-push-sent")
    state = push_probe(ctx.root)(dict(kind="push", operation_id=op)) or "uncertain"
    record_effect(ctx.store, eid, state, {"rc": p.returncode})
    return {"effect_id": eid, "state": state, "already": False}


def recover_dead_effects(store: Store, root: Path, native: Any = None,
                         alive: Callable[[int | None, int | None], bool] | None = None) -> list[dict[str, Any]]:
    """The dispatcher's recovery: an unresolved effect whose admitting worker run
    is over (its native run is no longer current, or its worker process is gone)
    is established by identity and never re-sent. A live run keeps its own
    effect; it re-probes it through the same `push` step."""
    out = []
    probe = push_probe(root)
    for e in store.unresolved_effects():
        doc = json.loads(e.get("doc") or "{}")
        t = native.task(str(doc.get("task_id") or "")) if native is not None and doc.get("task_id") else None
        run_live = bool(t and t.get("current_run_id") == doc.get("run_id") and t.get("status") == "running")
        pid_alive = alive(doc.get("worker_pid"), None) if alive is not None else _pid_alive(doc.get("worker_pid"))
        if e["state"] in ("admitted", "sent") and run_live and pid_alive:
            continue
        seen = probe(e)
        state = seen if seen in ("landed", "failed") else "uncertain"
        if state != e["state"]:
            record_effect(store, e["effect_id"], state, dict(doc, recovered=True, probe=seen))
        out.append({"effect_id": e["effect_id"], "state": state})
    return out


def push_probe(root: Path) -> Callable[[dict[str, Any]], str | None]:
    """Recovery by identity for a push effect: operation id <remote>:<ref>@<sha>.
    The remote ref equal to the sha -> landed; the remote answering with
    another value -> failed (the dead process can no longer land it); an
    unreachable remote -> None (uncertain, never repeated automatically)."""
    def probe(e: dict[str, Any]) -> str | None:
        if e.get("kind") != "push":
            return None
        op = str(e.get("operation_id") or "")
        try:
            remote_ref, want = op.rsplit("@", 1)
            remote, ref = remote_ref.split(":", 1)
        except ValueError:
            return None
        p = subprocess.run(["git", "-C", str(root), "ls-remote", remote, ref], capture_output=True, text=True, timeout=60)
        if p.returncode != 0:
            return None
        got = (p.stdout.split() or [""])[0]
        return "landed" if got == want else "failed"
    return probe


def record_effect(store: Store, effect_id: str, state: str, detail: dict[str, Any] | None = None) -> None:
    order = {"admitted": 0, "sent": 1, "landed": 2, "failed": 2, "uncertain": 1}
    with store.txn() as c:
        row = c.execute("SELECT state FROM effects WHERE effect_id=?", (effect_id,)).fetchone()
        if not row:
            raise Refusal("EFFECT_UNKNOWN", effect_id)
        if order.get(state, -1) < order.get(row[0], 0) and not (row[0] == "uncertain" and state in ("landed", "failed")):
            raise Refusal("EFFECT_REGRESSION", "%s is %s; cannot become %s" % (effect_id, row[0], state))
        c.execute("UPDATE effects SET state=?, doc=?, updated_at=? WHERE effect_id=?",
                  (state, canonical(detail or {}), time.time(), effect_id))


def recover_effects(store: Store, probe: Callable[[dict[str, Any]], str | None]) -> list[dict[str, Any]]:
    """For every unresolved effect ask the world by its recorded identity:
    probe(effect) -> 'landed' | 'failed' | None (unknown). Unknown stays
    visibly 'uncertain'. Nothing is repeated here."""
    out = []
    for e in store.unresolved_effects():
        seen = probe(e)
        state = seen if seen in ("landed", "failed") else "uncertain"
        record_effect(store, e["effect_id"], state, {"recovered": True, "probe": seen})
        out.append({"effect_id": e["effect_id"], "state": state})
    return out


@transition
def write_account(ctx: Ctx) -> dict[str, Any]:
    acc = progress_account(ctx.store, ctx.product_tree())
    if not ctx.observer_writes:
        return acc
    path = ctx.root / ACCOUNT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(acc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return acc
