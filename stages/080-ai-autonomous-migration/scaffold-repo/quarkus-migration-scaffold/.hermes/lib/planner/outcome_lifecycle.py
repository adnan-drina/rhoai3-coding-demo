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
    # plan semantics v1 (decisions.loop.plan_semantics, sealed by the receipt
    # just verified): the source-derived requirements enter revision 1; absent
    # keeps the revision exactly as before
    from planner.decisions import plan_semantics
    oracles = _oracles(root)
    extra: dict[str, Any] = {}
    if plan_semantics(load_decisions(root)) == "v1":
        from planner import source_requirements
        extra["requirements"] = source_requirements.for_root(root, oracles=oracles)["requirements"]
    return derive_initial_graph(
        run_id=run_id or "local", worklist=worklist, entry_points=inv["entry_points"], oracles=oracles,
        references=_references(root), max_attempts=max_attempts(load_decisions(root)),
        provenance={"snapshot_kind": "admission", "scope_note": "admission-time work list and M1 inventories of this run",
                    "receipt_sha256": receipt.get("receipt_digest"), "worklist_sha256": sha256_file(root / WORKLIST),
                    "entry_point_inventory_sha256": sha256_file(root / EP_INVENTORY)}, **extra)


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


def quiescent(pid: int | None, pgid: int | None, ctx: Ctx | None = None) -> bool:
    """The previous writer and every process in its group are gone. Elapsed
    time alone is never quiescence. Under the service the answer comes from
    the caller's process snapshot (ctx.alive): the authority shares no process
    namespace with the worker."""
    if ctx is not None and ctx.alive is not None:
        return not ctx.alive(pid, pgid)
    return not _pid_alive(pid) and not _pgid_alive(pgid)


def _git(root: Path, *args: str, binary: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=not binary)


def _tree_blobs(root: Path, commit: str) -> dict[str, tuple[str, str]] | None:
    """{rel: (mode, blob id)} of a committed tree's product paths (ls-tree: object
    data only; no working tree, no filter)."""
    from planner.paths import is_product_path
    ls = _git(root, "ls-tree", "-r", "-z", "--full-tree", commit, binary=True)
    if ls.returncode != 0:
        return None
    out: dict[str, tuple[str, str]] = {}
    for rec in ls.stdout.split(b"\0"):
        if not rec:
            continue
        meta, _, name = rec.partition(b"\t")
        mode, kind, oid = meta.split()
        rel = name.decode("utf-8", "surrogateescape")
        if kind == b"blob" and is_product_path(rel):
            out[rel] = (mode.decode(), oid.decode())
    return out


def _blob_id(data: bytes, algo: str) -> str:
    import hashlib
    h = hashlib.new(algo)
    h.update(b"blob %d\0" % len(data))
    h.update(data)
    return h.hexdigest()


def changed_product_paths(root: Path, base: str, commit: str = "", only: list[str] | None = None) -> list[str] | None:
    """Product paths that differ between the baseline commit and ``commit``, or
    the working tree (untracked, not ignored, included) when ``commit`` is
    empty. The working tree is compared IN PYTHON against the baseline's raw
    blob ids: git never reads a worktree file here, so no repository-configured
    clean filter, fsmonitor or diff driver can run (in the authority's
    principal). None when git cannot answer: unknown is never 'nothing changed'."""
    from planner.paths import is_product_path
    if not base:
        return None
    if commit:
        p = _git(root, "diff-tree", "-r", "--no-renames", "--name-only", "-z", base, commit)
        if p.returncode != 0:
            return None
        return sorted({n for n in p.stdout.split("\0") if n and is_product_path(n)})
    fmt = _git(root, "rev-parse", "--show-object-format").stdout.strip() or "sha1"
    blobs = _tree_blobs(root, base)
    ign = _git(root, "ls-files", "--others", "--ignored", "--exclude-standard", "--directory", "-z")
    if blobs is None or ign.returncode != 0 or fmt not in ("sha1", "sha256"):
        return None
    ignored = [n for n in ign.stdout.split("\0") if n]
    root = Path(root)
    changed: set[str] = set()
    seen: set[str] = set()
    names = list(only) if only is not None else None
    if names is None:
        names = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d != ".git"]
            for fn in filenames:
                names.append(os.path.relpath(os.path.join(dirpath, fn), root).replace(os.sep, "/"))
    for rel in names:
        if not is_product_path(rel) or any(rel == i.rstrip("/") or (i.endswith("/") and rel.startswith(i)) for i in ignored):
            continue
        p = root / rel
        if p.is_symlink():
            data, mode = os.readlink(p).encode("utf-8", "surrogateescape"), "120000"
        elif p.is_file():
            data, mode = p.read_bytes(), "100755" if os.access(p, os.X_OK) else "100644"
        else:
            continue
        seen.add(rel)
        want = blobs.get(rel)
        if want is None or want[1] != _blob_id(data, fmt) or (want[0] == "120000") != (mode == "120000"):
            changed.add(rel)
    for rel in blobs:
        if (only is None or rel in only) and rel not in seen:
            changed.add(rel)          # deleted since the baseline
    return sorted(changed)


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
            "run": store.meta("run_id"),
            "amendments": [{"path": a["path"], "reason": a["reason"], "locus": a["locus"], "evidence": a.get("evidence") or {}}
                           for a in amends]}


def _issue_seal(iid: int, task_id: str, run_id: int, rev: int, cluster: str, allowed: list[str], gen: int,
                head: str, tree: str) -> dict[str, Any]:
    return {"issue_id": int(iid), "task_id": task_id, "run_id": int(run_id), "rev": int(rev), "cluster": cluster,
            "allowed_paths": sorted(allowed), "generation": int(gen), "baseline_commit": head, "baseline_tree": tree}


AMEND_LIMIT = 4
AMEND_MAX_FILES = 20


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
    rec = record_measurement(ctx, tree=tree, classes=list(measurement.get("classes") or []),
                             scenarios=list(measurement.get("scenarios") or []), open_ids=open_now, source="accept:%s" % key,
                             asserted_by=_asserted_by(ctx))
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
    rec = record_measurement(ctx, tree=tree, classes=list(measurement.get("classes") or []),
                             scenarios=list(measurement.get("scenarios") or []), open_ids=open_now,
                             source="recovered:%s" % last["attempt_key"], asserted_by=_asserted_by(ctx))
    owned = _owned(ctx.store, oid)
    node = _node(_plan(ctx.store), oid) or {}
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


def git_commits_after(root: Path) -> Callable[[str], list[tuple[str, str, str]]]:
    """commits(baseline) -> [(sha, first parent, product tree digest)] for every
    commit between the baseline and HEAD. The digest is the product-tree identity
    of the committed tree (the same algorithm as the working tree's)."""
    def commits(baseline: str) -> list[tuple[str, str, str]]:
        if not baseline:
            return []
        p = subprocess.run(["git", "-C", str(root), "rev-list", "--parents", "%s..HEAD" % baseline],
                           capture_output=True, text=True)
        if p.returncode != 0:
            return []
        out = []
        for line in p.stdout.splitlines():
            parts = line.split()
            if len(parts) < 2 or parts[1] != baseline:
                continue
            digest = commit_product_tree(root, parts[0])
            if digest:
                out.append((parts[0], parts[1], digest))
        return out
    return commits


def commit_product_tree(root: Path, commit: str) -> str:
    """The product-tree digest (canonical.product_tree_sha256's algorithm) of a
    COMMITTED tree, from raw blobs: ls-tree and cat-file only, so no checkout,
    archive conversion or repository-configured filter runs. '' when git
    cannot answer."""
    import hashlib
    tree = _tree_blobs(root, commit)
    if tree is None:
        return ""
    entries = [(rel, oid) for rel, (_mode, oid) in tree.items()]
    h = hashlib.sha256()
    if entries:
        batch = subprocess.run(["git", "-C", str(root), "cat-file", "--batch"], input=b"".join(e[1].encode() + b"\n" for e in sorted(entries)),
                               capture_output=True)
        if batch.returncode != 0:
            return ""
        data, pos = batch.stdout, 0
        blobs = {}
        for rel, oid in sorted(entries):
            eol = data.index(b"\n", pos)
            size = int(data[pos:eol].split()[2])
            blobs[rel] = data[eol + 1:eol + 1 + size]
            pos = eol + 1 + size + 1
        # the working-tree digest walks sorted Paths: component-wise order, not string order
        for rel in sorted(blobs, key=lambda r: tuple(r.split("/"))):
            h.update(rel.encode("utf-8", "surrogateescape"))
            h.update(b"\0")
            h.update(blobs[rel])
            h.update(b"\0")
    return h.hexdigest()


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
                       source: str, asserted_by: str = "") -> dict[str, Any]:
    doc = {"tree": tree, "classes": sorted(set(classes)), "scenarios": sorted(set(scenarios)),
           "open": sorted(set(open_ids)), "source": source}
    if asserted_by:
        doc["classes_asserted_by"] = asserted_by
    with ctx.store.txn() as c:
        ctx.store.append(c, "_measure", "measurement", doc, attempt_key="%s:%s" % (source, tree))
    return doc


def _covers(node: dict[str, Any], m: dict[str, Any]) -> bool:
    cls = node.get("class")
    have = set(m.get("classes") or [])
    # plan semantics v1: an outcome owning source requirements is covered only
    # by a measurement that records each of their named checks; an empty live
    # work list or a vanished diagnostic never discharges them
    req = set(((node.get("acceptance") or {}).get("requirement_checks")) or [])
    if req and not req <= set(m.get("checks") or []):
        return False
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


DELIVERY_RECEIPTS = {
    "prepare": (Path("verification/delivery/candidate.json"), Path("verification/delivery/eligibility.json")),
    "push": (Path("verification/delivery/pipeline.json"), Path("verification/delivery/deployment.json")),
    "accept": (Path("verification/delivery/live.json"), Path("evidence/verdicts/m5-verdict.json")),
}


def _git_head(root: Path) -> str:
    p = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True)
    return p.stdout.strip() if p.returncode == 0 else ""


def _stage_assessment_task(store: Store) -> str:
    plan = store.current_revision() or {}
    node = next((n for n in plan.get("nodes") or [] if n["outcome_id"] == "deliver:prepare:c1"), {})
    bind = (node.get("binding") or {}).get("assessment") or ""
    row = store.conn.execute("SELECT task_id FROM publication WHERE outcome_id=?", (bind,)).fetchone() if bind else None
    return row[0] if row and row[0] else ""


def stage_evidence(root: Path, store: Store, stage: str) -> tuple[bool, dict[str, Any], list[str]]:
    """The deciding facts of one M5 stage, DERIVED from the stage producers' own
    receipts (prepare-release-candidate, observe-app-push/assert-deployed-app,
    live-acceptance/compose-m5-verdict) and the push effect record, all bound to
    the current Git candidate. (ok, facts, reasons). Missing, failed or
    contradictory evidence is never success."""
    root = Path(root)
    head = _git_head(root)
    reasons: list[str] = []
    docs: dict[str, dict[str, Any]] = {}
    digests: dict[str, str] = {}
    for rel in DELIVERY_RECEIPTS.get(stage, ()):
        doc = _read_json(root / rel)
        if not isinstance(doc, dict):
            reasons.append("STAGE_EVIDENCE_MISSING:%s" % rel)
            continue
        docs[rel.name] = doc
        digests[str(rel)] = sha(canonical(doc))
    if stage not in DELIVERY_RECEIPTS:
        reasons.append("STAGE_UNKNOWN:%s" % stage)
    if reasons:
        return False, {"stage": stage, "candidate_sha": head}, reasons

    def bound(label: str, doc: dict[str, Any]) -> None:
        if str(doc.get("candidate_sha") or "") != head or not head:
            reasons.append("CANDIDATE_MISMATCH:%s names %s, HEAD is %s" % (label, str(doc.get("candidate_sha") or "none")[:12], head[:12]))

    facts: dict[str, Any] = {"stage": stage, "candidate_sha": head, "receipts": digests}
    if stage == "prepare":
        cand, elig = docs["candidate.json"], docs["eligibility.json"]
        bound("candidate.json", cand)
        bound("eligibility.json", elig)
        if cand.get("ok") is not True or cand.get("pipeline_eligible") is not True:
            reasons.append("PREFLIGHT_FAILED:%s" % (cand.get("reason") or "candidate not pipeline-eligible"))
        if elig.get("pipeline_eligible") is not True:
            reasons.append("PREFLIGHT_FAILED:eligibility not pipeline-eligible")
        want = _stage_assessment_task(store)
        if not want or str(cand.get("m4_card") or "") != want:
            reasons.append("ASSESSMENT_MISMATCH:candidate binds M4 %r, the stage binds %r" % (cand.get("m4_card"), want))
        facts.update(pipeline_eligible=cand.get("pipeline_eligible") is True, release_eligible=bool(cand.get("release_eligible")),
                     m4_card=str(cand.get("m4_card") or ""), outstanding=len(cand.get("outstanding") or []))
    elif stage == "push":
        pipe, dep = docs["pipeline.json"], docs["deployment.json"]
        bound("pipeline.json", pipe)
        bound("deployment.json", dep)
        if pipe.get("ok") is not True or pipe.get("succeeded") is not True or not pipe.get("image_digest"):
            reasons.append("DEPLOY_FAILED:pipeline %s" % (pipe.get("reason") or "not a succeeded run with an image digest"))
        if dep.get("ok") is not True or dep.get("image_digest") != pipe.get("image_digest"):
            reasons.append("DEPLOY_FAILED:deployment %s" % (",".join(dep.get("issues") or []) or "image differs from the pipeline's"))
        if not str(dep.get("route_url") or "").startswith("https://"):
            reasons.append("DEPLOY_FAILED:route is not https")
        landed = store.conn.execute("SELECT effect_id FROM effects WHERE kind='push' AND candidate=? AND state='landed'",
                                    (head,)).fetchone()
        if not landed:
            reasons.append("PUSH_NOT_LANDED:no recorded, landed push effect for %s" % head[:12])
        facts.update(image_digest=str(pipe.get("image_digest") or ""), route_url=str(dep.get("route_url") or ""),
                     https=str(dep.get("route_url") or "").startswith("https://"), pipeline_run=str(pipe.get("pipeline_run") or ""))
    else:
        live, verdict = docs["live.json"], docs["m5-verdict.json"]
        bound("live.json", live)
        bound("m5-verdict.json", verdict)
        if live.get("ok") is not True:
            reasons.append("VALIDATE_FAILED:live %s" % ",".join(live.get("issues") or []))
        token = str(verdict.get("verdict") or "")
        if token not in ("ACCEPT", "INCONCLUSIVE") or verdict.get("failed_stage"):
            reasons.append("VALIDATE_FAILED:M5 verdict %s %s" % (token or "missing", verdict.get("failed_stage") or ""))
        facts.update(verdict=token, ship=bool(token == "ACCEPT" and verdict.get("ship") is True),
                     deployment_status=str(verdict.get("deployment_status") or ""))
    return not reasons, facts, reasons


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
