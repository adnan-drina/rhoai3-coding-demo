"""Outcome-board execution lifecycle: the authority's transition methods.

Every function here validates a transition REQUEST against the records and
the native board and then writes, in one short transaction, only what it
recomputed itself. None of them accepts a worker-supplied PASS, scope or budget
(architect F1: a protected writer validates, it never merely signs). The
store is cooperative in the current architecture (outcome_protocol.
authority_protected); see OUTCOME-BOARD-CONTRACT.md section 3.

Transitions (contract section 4): issue (T5), record_verdict (T6a-c),
check_complete (T4, T7, T8 and the M5 stage terminator), record_assessment
(the M4 measurement), plan_after_refuse (T9), grant_stage (T10),
admit_effect / record_effect / recover_effect (T11), progress_account (F3).
"""
from __future__ import annotations

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

WORKLIST = Path("evidence") / "planning" / "worklist.json"
EP_INVENTORY = Path("evidence") / "entry-point-inventory.json"
STRUCTURE = Path("evidence") / "structure" / "structure.json"
VERDICT = Path("evidence") / "verdicts" / "m4-verdict.json"
ACCOUNT = STORE_DIR / "account.json"
MAX_ASSESSMENT_GENERATIONS = 4
DELIVERY_OK_VERDICTS = ("ACCEPT", "PROVISIONAL_ACCEPT")
EXEMPT_DIRS = ("evidence/", "verification/", ".derived/", "target/")
PROTECTED_DIRS = (str(STORE_DIR) + "/", ".hermes/", ".git/")


class Refusal(RuntimeError):
    def __init__(self, code: str, detail: str):
        super().__init__("%s: %s" % (code, detail))
        self.code = code
        self.detail = detail


@dataclass
class Ctx:
    root: Path
    store: Store
    native: Any
    tree: Callable[[Path], str] | None = None
    head: Callable[[Path], str] | None = None

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


def _read_json(path: Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


# ---------------------------------------------------------------------------
# initial plan from the destination's admission-time evidence (T1)
# ---------------------------------------------------------------------------

def _oracles(root: Path) -> dict[str, list[str]] | None:
    from planner.worklist import _iter_corpus_docs
    out: dict[str, list[str]] = {}
    seen = False
    for doc in _iter_corpus_docs(root):
        seen = True
        for sc in doc.get("scenarios") or []:
            if isinstance(sc, dict) and sc.get("id") and sc.get("entry_point"):
                out.setdefault(str(sc["entry_point"]), []).append(str(sc["id"]))
    return out if seen else None


def _references(root: Path) -> dict[str, list[str]]:
    doc = _read_json(Path(root) / STRUCTURE)
    if not isinstance(doc, dict):
        return {}
    path_of = {str(t.get("fqn")): str(t.get("path") or "") for t in doc.get("types") or [] if isinstance(t, dict)}
    out: dict[str, set[str]] = {}
    for t in doc.get("types") or []:
        if not isinstance(t, dict) or not t.get("path"):
            continue
        for ref in list(t.get("type_refs") or []) + list(t.get("supertypes") or []):
            q = path_of.get(str(ref))
            if q and q != t["path"]:
                out.setdefault(str(t["path"]), set()).add(q)
    return {k: sorted(v) for k, v in out.items()}


def initial_plan_from_root(root: Path) -> dict[str, Any]:
    """Revision 1 from the ADMITTED work list and the M1 inventories. Missing
    admission evidence refuses (PlanError ADMISSION_EVIDENCE_INCOMPLETE)."""
    from planner.admission import verify_receipt
    from planner.decisions import load_decisions, max_attempts
    from planner.outcome_graph import PlanError
    root = Path(root)
    receipt, gaps = verify_receipt(root, require_admitted=True)
    if gaps or receipt is None:
        raise PlanError("ADMISSION_NOT_ADMITTED", "; ".join(gaps or ["no admission receipt"]))
    worklist = _read_json(root / WORKLIST)
    inv = _read_json(root / EP_INVENTORY)
    if not isinstance(inv, dict) or not isinstance(inv.get("entry_points"), list):
        raise PlanError("ADMISSION_EVIDENCE_INCOMPLETE", "%s is missing or malformed" % EP_INVENTORY)
    decl = _read_json(root / "run-budget.json") or {}
    run_id = str(decl.get("run_id") or "") if isinstance(decl, dict) else ""
    if not run_id:
        mig = root / "migration.yaml"
        from planner.yamlite import load_yaml
        doc = load_yaml(mig) if mig.is_file() else {}
        run_id = str(((doc or {}).get("resources") or {}).get("run") or "")
    from planner.canonical import sha256_file
    return derive_initial_graph(
        run_id=run_id or "local", worklist=worklist, entry_points=inv["entry_points"], oracles=_oracles(root),
        references=_references(root), max_attempts=max_attempts(load_decisions(root)),
        provenance={"snapshot_kind": "admission", "scope_note": "admission-time work list and M1 inventories of this run",
                    "receipt_sha256": receipt.get("receipt_digest"), "worklist_sha256": sha256_file(root / WORKLIST),
                    "entry_point_inventory_sha256": sha256_file(root / EP_INVENTORY)})


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


def load_worklist(root: Path) -> tuple[dict[str, Any] | None, str]:
    """(work list, '') or (None, why). Missing or corrupt is never empty."""
    p = Path(root) / WORKLIST
    if not p.is_file():
        return None, "WORKLIST_MISSING"
    doc = _read_json(p)
    if not isinstance(doc, dict) or not isinstance(doc.get("items"), list) or not isinstance(doc.get("clusters"), list):
        return None, "WORKLIST_CORRUPT"
    if not isinstance(doc.get("measure"), dict) or doc["measure"].get("known") is not True:
        return None, "WORKLIST_UNKNOWN"
    return doc, ""


def open_obligations(worklist: dict[str, Any]) -> set[str]:
    return {str(i["id"]) for i in worklist.get("items") or []
            if isinstance(i, dict) and i.get("category") == "mandatory" and i.get("id")}


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


def quiescent(pid: int | None, pgid: int | None) -> bool:
    """The previous writer and every process in its group are gone. Elapsed
    time alone is never quiescence."""
    return not _pid_alive(pid) and not _pgid_alive(pgid)


# ---------------------------------------------------------------------------
# T5: claim -> run-bound execution issue
# ---------------------------------------------------------------------------

def _allowed_paths(root: Path, node: dict[str, Any], worklist: dict[str, Any] | None) -> tuple[str, list[str]]:
    """The ONE cluster this outcome may edit now, and its write set. Never the
    union of the outcome's plan paths."""
    if node.get("role") != "repair" or worklist is None:
        return "", []
    owned = set(node.get("obligations") or [])
    for c in worklist.get("clusters") or []:
        if not isinstance(c, dict) or c.get("status") != "open":
            continue
        if owned & set(c.get("items") or []) or c.get("id") in set(node.get("clusters") or []):
            return str(c["id"]), sorted(str(p) for p in c.get("write_set") or [])
    return "", []


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
    spent = store.spent(orow["budget_key"])
    if _native_rejections(ctx, task_id) > sum(1 for r in store.ledger(oid) if r["kind"] == "reject"):
        raise Refusal("STORE_ROLLBACK", "the board records more rejected attempts on %s than the ledger: an older store "
                      "was restored" % task_id)
    if orow["budget_limit"] and spent >= orow["budget_limit"]:
        raise Refusal("ISSUE_BUDGET_EXHAUSTED", "%s spent %d of %d" % (orow["budget_key"], spent, orow["budget_limit"]))
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
    cluster, allowed = _allowed_paths(ctx.root, node, worklist)
    with store.txn() as c:
        prior = c.execute("SELECT issue_id, run_id FROM issues WHERE task_id=? AND state='active'", (task_id,)).fetchall()
        for r in prior:
            if r["run_id"] != run_id:
                c.execute("UPDATE issues SET state='superseded' WHERE issue_id=?", (r["issue_id"],))
        w = c.execute("SELECT * FROM writer WHERE slot='product-tree'").fetchone()
        gen = int(store.meta("generation", "0") or 0)
        if w and not (w["task_id"] == task_id and w["run_id"] == run_id):
            if not quiescent(w["pid"], w["pgid"]):
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
    return {"issue_id": iid, "task_id": task_id, "run_id": run_id, "outcome_id": oid, "role": node["role"],
            "cluster": cluster, "allowed_paths": allowed, "budget": {"key": orow["budget_key"], "spent": spent,
                                                                      "limit": orow["budget_limit"]},
            "retained_candidate": bool(pending), "generation": gen, "claimed_control": False}


def _issue_seal(iid: int, task_id: str, run_id: int, rev: int, cluster: str, allowed: list[str], gen: int,
                head: str, tree: str) -> dict[str, Any]:
    return {"issue_id": int(iid), "task_id": task_id, "run_id": int(run_id), "rev": int(rev), "cluster": cluster,
            "allowed_paths": sorted(allowed), "generation": int(gen), "baseline_commit": head, "baseline_tree": tree}


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

def norm_rel(rel: str) -> str:
    """Destination-relative POSIX path: backslashes folded, leading './'
    segments removed (never a leading '.' of a name such as .hermes)."""
    r = str(rel or "").replace("\\", "/")
    while r.startswith("./"):
        r = r[2:]
    return r.lstrip("/")


def _is_product(rel: str) -> bool:
    from planner.paths import is_product_path
    return is_product_path(rel)


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
        g = store.conn.execute("SELECT * FROM grants WHERE outcome_id=?", (node["outcome_id"],)).fetchone()
        if not g or g["state"] not in ("granted", "executed"):
            raise Refusal("DELIVER_UNGRANTED", "%s was never admitted" % node["outcome_id"])
        res = [r for r in store.ledger(node["outcome_id"]) if r["kind"] == "stage-result"]
        if not res:
            raise Refusal("DELIVER_NO_RESULT", "no recorded stage result for %s" % node["outcome_id"])
        return _intent(store, "m5-stage-done:%s" % node["outcome_id"], "m5-stage-done", task_id,
                       {"outcome_id": node["outcome_id"], "stage": node.get("stage"), "result": res[-1]["doc"]},
                       set_status=(node["outcome_id"], "done"))
    raise Refusal("COMPLETE_FOREIGN_TASK", "role %s" % node["role"])


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

def record_verdict(ctx: Ctx, *, task_id: str, run_id: int, verdict: str, candidate: str, attempt: str,
                   reason: str = "", retained: dict[str, Any] | None = None) -> dict[str, Any]:
    """REVERTED / VERIFICATION_PENDING / ACCEPTED for the issued cluster. The
    outcome stays the same card whatever the verdict; only its ledger moves."""
    iss = active_issue(ctx, task_id, run_id)
    oid = iss["outcome_id"]
    orow = _outcome(ctx.store, oid)
    key = "%s:%s" % (run_id, attempt)
    if verdict == "REVERTED":
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
        with ctx.store.txn() as c:
            ctx.store.append(c, oid, "accept-begin", {"cluster": iss["cluster"], "candidate": candidate,
                                                      "baseline_commit": iss["baseline_commit"], "run_id": run_id},
                             attempt_key=key)
        return {"verdict": verdict, "outcome_id": oid, "next": "commit, then outcome_gate.py accept-commit"}
    raise Refusal("VERDICT_UNKNOWN", verdict)


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
    wl, why = load_worklist(ctx.root)
    if wl is None:
        raise Refusal("ACCEPT_" + why, "acceptance reads the rebuilt work list")
    open_now = sorted(open_obligations(wl))
    rec = record_measurement(ctx, tree=tree, classes=list(measurement.get("classes") or []),
                             scenarios=list(measurement.get("scenarios") or []), open_ids=open_now, source="accept:%s" % key)
    owned = _owned(ctx.store, oid)
    node = _node(_plan(ctx.store), oid) or {}
    covered = _covers(node, rec)
    done = not (owned & set(open_now)) and covered
    with ctx.store.txn() as c:
        ctx.store.append(c, oid, "accept-commit", {"commit": commit, "tree": tree, "cluster": iss["cluster"],
                                                   "outcome_accepted": done}, attempt_key=key)
        ctx.store.set_meta(c, "accepted_commit", commit)
        ctx.store.set_meta(c, "accepted_tree", tree)
        if done:
            c.execute("UPDATE outcomes SET status='accepted', accepted_tree=?, accepted_commit=?, accepted_rev=? WHERE outcome_id=?",
                      (tree, commit, int(ctx.store.meta("revision", "0")), oid))
    return {"outcome_id": oid, "outcome_accepted": done, "open_owned": sorted(owned & set(open_now)),
            "covered": covered}


def recover_accept(ctx: Ctx, *, oid: str, commits: Callable[[str], list[tuple[str, str, str]]]) -> list[dict[str, Any]]:
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
        hits = [s for s, parent, tree in commits(r["doc"]["baseline_commit"])
                if parent == r["doc"]["baseline_commit"] and tree == r["doc"]["candidate"]]
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

def record_measurement(ctx: Ctx, *, tree: str, classes: list[str], scenarios: list[str], open_ids: list[str],
                       source: str) -> dict[str, Any]:
    doc = {"tree": tree, "classes": sorted(set(classes)), "scenarios": sorted(set(scenarios)),
           "open": sorted(set(open_ids)), "source": source}
    with ctx.store.txn() as c:
        ctx.store.append(c, "_measure", "measurement", doc, attempt_key="%s:%s" % (source, tree))
    return doc


def _covers(node: dict[str, Any], m: dict[str, Any]) -> bool:
    cls = node.get("class")
    have = set(m.get("classes") or [])
    if cls in ("build", "config"):
        return "build" in have
    if cls == "source":
        return {"compile", "tests"} <= have
    if cls == "runtime":
        return "runtime" in have
    if cls == "behavior":
        return "parity" in have and set(node.get("scenarios") or []) <= set(m.get("scenarios") or [])
    return False


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
        record_measurement(ctx, tree=tree, classes=["build", "compile", "tests", "runtime", "parity"], scenarios=measured,
                           open_ids=[o["id"] for o in obligations], source="assessment:%s" % iss["outcome_id"])
    return {"assessment_seq": seq, "verdict": token, "open_obligations": len(obligations)}


# ---------------------------------------------------------------------------
# T9: REFUSE -> bounded repairs -> successor assessment
# ---------------------------------------------------------------------------

def plan_after_refuse(store: Store, plan: dict[str, Any], intent: dict[str, Any]) -> dict[str, Any] | Refusal:
    """The next revision, or a typed stop. Never reopens or overwrites the
    completed assessment; never renews a budget."""
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
    run_id = plan["run_id"]
    nodes = [dict(n) for n in plan["nodes"]]
    by_id = {n["outcome_id"]: n for n in nodes}
    ownership = dict(plan.get("ownership") or {})
    unresolved = list(plan.get("unresolved") or [])
    touched: dict[str, dict[str, Any]] = {}
    additions: list[str] = []
    for ob in rec["doc"]["obligations"]:
        if ob.get("status") == "blocked" or not ob.get("write_set"):
            uid = "unresolved:decision:%s" % ob["id"]
            if not any(u["id"] == uid for u in unresolved):
                unresolved.append({"id": uid, "kind": "decision", "blocks": "delivery", "reason": "no card can discharge %s" % ob["id"], "obligations": [ob["id"]]})
            continue
        owner = ownership.get(ob["id"])
        if owner is None:
            typ, kind = declaring_type(ob.get("entry_point") or "")
            natural = "%s:%s" % (kind, typ) if typ else str(ob.get("key") or "")
            owner = next((n["outcome_id"] for n in nodes if n.get("role") == "repair" and n.get("natural_key") == natural), None)
        orow = _outcome(store, owner) if owner else None
        if owner and orow and orow["status"] not in ("accepted", "done"):
            target = owner
        elif owner and orow:
            target = "followup:%s:g%d" % (owner, gen + 1)
            if target not in by_id:
                parent = by_id[owner]
                by_id[target] = {"outcome_id": target, "role": "repair", "class": parent.get("class"), "subject": parent.get("subject"),
                                 "natural_key": "", "obligations": [], "clusters": [], "plan_paths": [], "entry_points": [],
                                 "scenarios": [], "parents": [], "assignee": IMPL, "skills": [REPAIR_SKILL],
                                 "lineage": [{"follows": owner, "reason": "assessment %s found new work after acceptance" % intent["outcome_id"]}],
                                 "budget": {"key": orow["budget_key"], "limit": orow["budget_limit"]}}
                additions.append(target)
        else:
            typ, kind = declaring_type(ob.get("entry_point") or "")
            cls = "behavior" if typ else ("runtime" if ob.get("gate") in ("package", "startup", "boot") else "source")
            target = ("behavior:%s:%s" % (kind, typ)) if typ else "%s:%s" % (cls, ob.get("key") or ob["id"])
            if target in by_id and _outcome(store, target) and _outcome(store, target)["status"] in ("accepted", "done"):
                target = "followup:%s:g%d" % (target, gen + 1)
            if target not in by_id:
                by_id[target] = {"outcome_id": target, "role": "repair", "class": cls, "subject": typ or str(ob.get("path") or ob["id"]),
                                 "natural_key": "%s:%s" % (kind, typ) if typ else str(ob.get("key") or ""),
                                 "obligations": [], "clusters": [], "plan_paths": [], "entry_points": [], "scenarios": [],
                                 "parents": [], "assignee": IMPL, "skills": [REPAIR_SKILL],
                                 "lineage": [{"discovered_by": intent["outcome_id"]}],
                                 "budget": {"key": "rk:outcome:%s:%s" % (run_id, target), "limit": 3}}
                additions.append(target)
        n = by_id[target]
        n["obligations"] = sorted(set(n["obligations"]) | {ob["id"]})
        if ob.get("cluster"):
            n["clusters"] = sorted(set(n["clusters"]) | {ob["cluster"]})
        n["plan_paths"] = sorted(set(n["plan_paths"]) | set(ob.get("write_set") or []))
        if ob.get("entry_point"):
            n["entry_points"] = sorted(set(n["entry_points"]) | {ob["entry_point"]})
        if ob.get("scenario"):
            n["scenarios"] = sorted(set(n["scenarios"]) | {ob["scenario"]})
        ownership[ob["id"]] = target
        touched[target] = n
    if not touched:
        return Refusal("REFUSE_NOTHING_REPAIRABLE", "the REFUSE names no obligation a card can discharge; %d unresolved decision(s)"
                       % sum(1 for u in unresolved if u["kind"] == "decision"))
    succ = "%s:g%d" % (ASSESS_PREFIX, gen + 1)
    open_repairs = sorted(oid for oid, n in by_id.items() if n.get("role") == "repair"
                          and ((_outcome(store, oid) or {}).get("status") not in ("accepted", "done") or oid in additions))
    for oid in additions:
        # a published card's description is never rewritten (the pinned CLI has
        # no body edit); only new outcomes get their text here
        n = by_id[oid]
        n["title"] = "Follow-up: %s" % n["subject"] if oid.startswith("followup:") else {
            "behavior": "Behavior: %s", "runtime": "Application %s", "source": "Source compatibility: %s"}.get(
            n.get("class"), "Outcome: %s") % n["subject"]
        n["description"] = render_description(n)
        n["acceptance"] = {"checks": {"behavior": ["worklist-absent", "parity:scenarios"],
                                      "runtime": ["worklist-absent", "gate:runtime"]}.get(
            n.get("class"), ["worklist-absent", "measure:compile", "measure:tests"])}
    by_id[succ] = {"outcome_id": succ, "role": "assess", "class": "assess", "generation": gen + 1, "subject": "M4 ASSESS",
                   "title": "M4 ASSESS (reassessment %d)" % (gen + 1), "parents": sorted(set(open_repairs) | {intent["outcome_id"]}),
                   "assignee": IMPL, "skills": [ASSESS_SKILL], "obligations": [], "clusters": [], "plan_paths": [],
                   "lineage": [{"succeeds": intent["outcome_id"], "verdict": intent["verdict"]}]}
    by_id[succ]["description"] = render_description(by_id[succ])
    for stage in DELIVER_STAGES:
        did = "deliver:%s:c1" % stage
        if did in by_id:
            d = dict(by_id[did])
            d["binding"] = {"assessment": succ}
            if stage == DELIVER_STAGES[0]:
                d["parents"] = sorted(set(d.get("parents") or []) | {succ})
            by_id[did] = d
    new_nodes = [by_id[k] for k in sorted(by_id)]
    counts = dict(plan.get("counts") or {})
    counts["additions"] = int(counts.get("additions") or 0) + len(additions)
    doc = {
        "schema": plan["schema"], "run_id": run_id, "revision": int(plan["revision"]) + 1,
        "parent_revision": int(plan["revision"]), "kind": "refuse-repair", "provenance": plan.get("provenance"),
        "trigger": {"intent": "m4-assessed:%s" % intent["outcome_id"], "verdict": intent["verdict"]},
        "nodes": new_nodes, "ownership": ownership, "dispositions": list(plan.get("dispositions") or []),
        "unresolved": sorted(unresolved, key=lambda u: u["id"]), "counts": counts,
        "additions": sorted(additions), "claimed_control": False,
    }
    doc["digest"] = plan_digest(doc)
    return doc


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

def stage_admission(stage: str, facts: dict[str, Any]) -> dict[str, Any]:
    """Admit one M5 stage from facts known at that point, and only those.

    A later stage's own output is never required before it can start. A
    deferred release qualification may remain recorded; a delivery-blocking one
    refuses. deploy_for_validation is never ship."""
    reasons: list[str] = []
    a = facts.get("assessment") or {}
    wl = facts.get("worklist") or {}
    cand = facts.get("candidate") or ""
    if stage == "prepare":
        if not a.get("bound"):
            reasons.append("ASSESSMENT_UNBOUND")
        if str(a.get("verdict") or "").upper() not in DELIVERY_OK_VERDICTS:
            reasons.append("ASSESSMENT_%s" % (str(a.get("verdict") or "MISSING").upper()))
        if a.get("candidate") != cand:
            reasons.append("CANDIDATE_STALE")
        if wl.get("state") != "present":
            reasons.append("WORKLIST_%s" % str(wl.get("state") or "MISSING").upper())
        elif int(wl.get("open_mandatory") or 0):
            reasons.append("OPEN_MANDATORY_OBLIGATIONS")
        if facts.get("open_repairs"):
            reasons.append("OPEN_MANDATORY_REPAIR")
        if facts.get("unresolved_ownership"):
            reasons.append("UNRESOLVED_OWNERSHIP")
    elif stage == "push":
        pf = facts.get("preflight") or {}
        if not pf.get("accepted") or pf.get("candidate") != cand:
            reasons.append("PREFLIGHT_NOT_ACCEPTED_FOR_CANDIDATE")
        if not facts.get("plan_coherent", False):
            reasons.append("PLAN_INCOHERENT")
        if not facts.get("build_authorized", False):
            reasons.append("BUILD_NOT_AUTHORIZED")
    elif stage == "accept":
        dep = facts.get("deploy") or {}
        if not dep.get("result") or dep.get("candidate") != cand or not dep.get("image_digest"):
            reasons.append("DEPLOYMENT_UNBOUND")
        if not facts.get("live_inputs", False):
            reasons.append("LIVE_INPUTS_MISSING")
    else:
        reasons.append("STAGE_UNKNOWN")
    for q in facts.get("qualifications") or []:
        if q.get("class") == "blocking" and not q.get("satisfied") and q.get("before", "prepare") == stage:
            reasons.append("QUALIFICATION_%s" % str(q.get("id")).upper())
    deferred = [q["id"] for q in facts.get("qualifications") or [] if q.get("class") == "deferred" and not q.get("satisfied")]
    ship = stage == "accept" and not reasons and bool(facts.get("shipping_evidence_complete"))
    return {"stage": stage, "admit": not reasons, "reasons": reasons, "deferred_qualifications": deferred,
            "permissions": {"deploy_for_validation": stage == "push" and not reasons, "ship": ship}}


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
    for prev in ("prepare", "push"):
        res = [r for r in store.ledger("deliver:%s:c1" % prev) if r["kind"] == "stage-result"]
        if res:
            facts["preflight" if prev == "prepare" else "deploy"] = res[-1]["doc"]
    facts["plan_coherent"] = True
    facts["build_authorized"] = bool((facts.get("preflight") or {}).get("build_authorized"))
    facts["live_inputs"] = bool((facts.get("deploy") or {}).get("live_inputs"))
    return facts


def record_stage_result(ctx: Ctx, *, task_id: str, run_id: int, result: dict[str, Any]) -> dict[str, Any]:
    iss = active_issue(ctx, task_id, run_id)
    if not iss["outcome_id"].startswith("deliver:"):
        raise Refusal("DELIVER_FOREIGN", "%s is not a delivery stage" % iss["outcome_id"])
    doc = dict(result, candidate=ctx.product_tree())
    with ctx.store.txn() as c:
        ctx.store.append(c, iss["outcome_id"], "stage-result", doc, attempt_key="%s:%s" % (run_id, sha(canonical(doc))[:16]))
        c.execute("UPDATE grants SET state='executed' WHERE outcome_id=?", (iss["outcome_id"],))
    return doc


# ---------------------------------------------------------------------------
# F4: external effects under the one serialization mechanism
# ---------------------------------------------------------------------------

def admit_effect(store: Store, *, kind: str, candidate: str, operation_id: str, expected_rev: int,
                 predicate: Callable[[], list[str]] | None = None) -> str:
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
                  "VALUES(?,?,?,?,?,?,?,?,?,?)", (eid, kind, candidate, operation_id, cur, gen, "admitted", "{}", now, now))
    return eid


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


def write_account(ctx: Ctx) -> dict[str, Any]:
    acc = progress_account(ctx.store, ctx.product_tree())
    path = ctx.root / ACCOUNT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(acc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return acc
