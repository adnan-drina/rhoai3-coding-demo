#!/usr/bin/env python3
"""K4 graph publication for the outcome board (OUTCOME-BOARD-CONTRACT.md T1–T4, T9).

Reached from k4_mint.py when the run's protocol is outcome-board/v1: the
initial graph from the open M2 card (worker identity RETAINED: the M2 task is
HERMES_KANBAN_TASK and is recorded as the control card, never scrubbed), and
later revisions from the named continuation (outcome_reconcile.py).

Every node is created successively, in dependency order, under the open M2
dependency path: M3 outcomes and the M4 assessment are assigned ``implementer``
at creation (the open M2 parent holds them); the M5 stages are created WITHOUT
an assignee and stay held until stage admission. Each native id is recorded
durably the moment it exists. Briefs are attachments whose bytes this module
hashes itself (the pinned CLI returns no digest).

The whole graph is not one transaction. A repeated idempotency key recovers the
existing live id and never updates it (not an upsert); archived rows are
excluded from native key lookup, so an archived mapped identity STOPS
(PUBLICATION_ARCHIVED) rather than being re-created, and two live rows with one
key stop (PUBLICATION_DUPLICATE). A field that differs from the expectation is
not repaired by another create: it stops (PUBLICATION_MISMATCH).

The publication generation is COMPLETE only when a read-back of the whole
graph matches. Missing or partial publication prevents M2 completion
(check_m2_release, called by the pre_tool_call hook).
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

_KERNEL = Path(__file__).resolve().parent
_LIB = _KERNEL.parent / "lib"
for _p in (_KERNEL, _LIB):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from planner.outcome_graph import CONTROL_M2, brief_document, topo_order  # noqa: E402
from planner.outcome_protocol import STORE_DIR  # noqa: E402
from planner.outcome_store import Store, StoreError, canonical, fault, sha  # noqa: E402

KEY_VERSION = "v1"
MAX_RETRIES = 2
WORKSPACE = "dir:/projects/modernized"
BRIEFS = STORE_DIR / "briefs"


class PublishError(RuntimeError):
    def __init__(self, code: str, detail: str):
        super().__init__("%s: %s" % (code, detail))
        self.code = code
        self.detail = detail


def native_key(run_id: str, node: dict[str, Any]) -> str:
    role = node.get("role")
    oid = node["outcome_id"]
    if role == "assess":
        return "assess:%s:%s:%s" % (KEY_VERSION, run_id, oid)
    if role == "deliver":
        return "deliver:%s:%s:%s" % (KEY_VERSION, run_id, oid)
    return "outcome:%s:%s:%s" % (KEY_VERSION, run_id, oid)


def expected_fields(node: dict[str, Any], parents: list[str], workspace: str = WORKSPACE) -> dict[str, Any]:
    return {"title": node["title"], "body": node["description"], "assignee": node.get("assignee"),
            "parents": sorted(parents), "skills": list(node.get("skills") or []), "workspace": workspace}


def workspace_for(root: Path, execution: str) -> str:
    """The workspace every outcome card runs in: the destination tree. A real run
    is always /projects/modernized (scratch workspaces are OBJECT); only a
    disposable qualification fixture runs in its own root."""
    if execution == "qualification":
        return "dir:" + str(Path(root).resolve())
    return WORKSPACE


def _safe(oid: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in oid)


def _brief_path(root: Path, oid: str, rev: int) -> tuple[Path, str]:
    name = "%s.r%d.json" % (_safe(oid), rev)
    return Path(root) / BRIEFS / name, name


def init_store(root: Path, *, run_id: str, m2_task: str, native_db: str, protocol: str,
               workspace: str = WORKSPACE) -> Store:
    store = Store(root, create=True)
    with store.txn() as c:
        cur_run = store.meta("run_id")
        if cur_run and cur_run != run_id:
            raise PublishError("PUBLICATION_FOREIGN", "store belongs to run %s" % cur_run)
        cur_m2 = store.meta("m2_task")
        if cur_m2 and cur_m2 != m2_task:
            raise PublishError("PUBLICATION_FOREIGN", "store names M2 %s, caller is %s" % (cur_m2, m2_task))
        cur_db = store.meta("native_db")
        if cur_db and cur_db != native_db:
            raise PublishError("NATIVE_REDIRECTED", "store names board %s, caller resolves %s" % (cur_db, native_db))
        for k, v in (("schema", "rhoai3.outcome-authority/v1"), ("run_id", run_id), ("m2_task", m2_task),
                     ("native_db", native_db), ("protocol", protocol), ("workspace", workspace)):
            if not store.meta(k):
                store.set_meta(c, k, v)
        if not store.meta("publication_state"):
            store.set_meta(c, "publication_state", "incomplete")
    return store


def persist_plan(store: Store, plan: dict[str, Any]) -> int:
    """The initial revision, persisted BEFORE any card exists (T1). A retry
    with the same digest reuses it; a different plan after publication began
    refuses (identity is frozen at publication)."""
    cur = store.current_revision()
    if cur is not None:
        if cur.get("digest") == plan.get("digest"):
            return int(cur["revision"])
        if store.conn.execute("SELECT COUNT(*) FROM publication").fetchone()[0]:
            raise PublishError("PUBLICATION_REPLAN", "revision %s is being published; a different initial plan "
                               "cannot replace it (identity is frozen at publication)" % cur["revision"])
        raise PublishError("PUBLICATION_REPLAN", "an unpublished revision exists with another digest; resolve it explicitly")
    rev = store.commit_revision(plan, kind=plan.get("kind", "initial"), parent=None)
    sync_ownership(store, plan)
    return rev


def sync_ownership(store: Store, plan: dict[str, Any]) -> None:
    """The revision's obligation ownership and dispositions, recorded at its
    revision number (conservation is read from here; the latest revision wins)."""
    with store.txn() as c:
        for ob, oid in sorted((plan.get("ownership") or {}).items()):
            c.execute("INSERT OR REPLACE INTO ownership(obligation_id, rev, outcome_id, disposition, reason) VALUES(?,?,?,?,?)",
                      (ob, plan["revision"], oid, "owned", ""))
        for d in plan.get("dispositions") or []:
            c.execute("INSERT OR REPLACE INTO ownership(obligation_id, rev, outcome_id, disposition, reason) VALUES(?,?,?,?,?)",
                      (d["obligation_id"], plan["revision"], None, d["disposition"], str(d.get("reason") or "")))


def _freeze(store: Store, plan: dict[str, Any], node: dict[str, Any], key: str) -> None:
    budget = node.get("budget") or {}
    with store.txn() as c:
        row = c.execute("SELECT native_key FROM outcomes WHERE outcome_id=?", (node["outcome_id"],)).fetchone()
        if row:
            if row[0] != key:
                raise PublishError("IDENTITY_CHANGED", "%s is frozen under %s" % (node["outcome_id"], row[0]))
            return
        c.execute("INSERT INTO outcomes(outcome_id, role, native_key, first_rev, budget_key, budget_limit, natural_key, aliases, lineage) "
                  "VALUES(?,?,?,?,?,?,?,?,?)",
                  (node["outcome_id"], node["role"], key, plan["revision"],
                   str(budget.get("key") or "rk:outcome:%s:%s" % (plan["run_id"], node["outcome_id"])),
                   int(budget.get("limit") or 0), node.get("natural_key") or "",
                   json.dumps(node.get("aliases") or []), json.dumps(node.get("lineage") or [])))


def _pub(store: Store, oid: str) -> dict[str, Any] | None:
    row = store.conn.execute("SELECT * FROM publication WHERE outcome_id=?", (oid,)).fetchone()
    return dict(row) if row else None


def publish_node(root: Path, store: Store, native: Any, plan: dict[str, Any], node: dict[str, Any], *,
                 resolve: dict[str, str], hold: bool = False) -> str:
    """Create (or recover) one node and its brief; returns its native id."""
    run_id = plan["run_id"]
    key = native_key(run_id, node)
    _freeze(store, plan, node, key)
    parents = []
    for p in node.get("parents") or []:
        tid = resolve.get(p)
        if not tid:
            raise PublishError("PUBLICATION_PARENT", "%s parent %s has no native id yet" % (node["outcome_id"], p))
        parents.append(tid)
    assignee = None if hold else node.get("assignee")
    workspace = store.meta("workspace") or WORKSPACE
    exp = expected_fields(dict(node, assignee=assignee), parents, workspace)
    exp["final_assignee"] = node.get("assignee")
    pub = _pub(store, node["outcome_id"])
    if pub is None:
        with store.txn() as c:
            c.execute("INSERT INTO publication(outcome_id, native_key, expected, rev, state) VALUES(?,?,?,?,?)",
                      (node["outcome_id"], key, canonical(exp), plan["revision"], "creating"))
        pub = _pub(store, node["outcome_id"])
    elif pub["native_key"] != key:
        raise PublishError("IDENTITY_CHANGED", "%s published under %s" % (node["outcome_id"], pub["native_key"]))
    tid = pub.get("task_id") or ""
    if tid:
        t = native.task(tid)
        if t is None or t.get("status") == "archived":
            raise PublishError("PUBLICATION_ARCHIVED", "%s (%s) is %s" % (node["outcome_id"], tid, "archived" if t else "gone"))
    else:
        rows = native.by_key(key)
        live = [r for r in rows if r["status"] != "archived"]
        if len(live) > 1:
            raise PublishError("PUBLICATION_DUPLICATE", "%s has %d live cards %s" % (key, len(live), [r["id"] for r in live]))
        if not live and rows:
            raise PublishError("PUBLICATION_ARCHIVED", "%s exists only archived (%s); an archived identity is never re-created"
                               % (key, rows[0]["id"]))
        if live:
            tid = live[0]["id"]
        else:
            tid = native.create(title=exp["title"], body=exp["body"], assignee=assignee, parents=parents, key=key,
                                skills=exp["skills"], workspace=workspace, max_retries=MAX_RETRIES)
            fault("after-create")
        with store.txn() as c:
            c.execute("UPDATE publication SET task_id=?, state='created' WHERE outcome_id=?", (tid, node["outcome_id"]))
    _attach_brief(root, store, native, plan, node, tid)
    with store.txn() as c:
        c.execute("UPDATE publication SET state='published' WHERE outcome_id=? AND state!='released'", (node["outcome_id"],))
    return tid


def _attach_brief(root: Path, store: Store, native: Any, plan: dict[str, Any], node: dict[str, Any], tid: str) -> None:
    doc = brief_document(plan, node)
    path, name = _brief_path(root, node["outcome_id"], plan["revision"])
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    digest = sha(text)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_file() or sha(path.read_text(encoding="utf-8")) != digest:
        path.write_text(text, encoding="utf-8")
    pub = _pub(store, node["outcome_id"])
    from planner.outcome_native import sha256_file
    if pub.get("attachment_id") and pub.get("attachment_name") == name:
        rows = [a for a in native.attachments(tid) if int(a["id"]) == int(pub["attachment_id"])]
        if not rows or sha256_file(rows[0]["stored_path"]) != pub["attachment_sha256"]:
            raise PublishError("PUBLICATION_ATTACHMENT_MISMATCH", "%s attachment %s bytes differ from the record"
                               % (tid, pub["attachment_id"]))
        return
    stem = os.path.splitext(name)[0]
    same = [a for a in native.attachments(tid)
            if str(a["filename"]).startswith(stem) and sha256_file(a["stored_path"]) == digest]
    if len(same) > 1:
        raise PublishError("PUBLICATION_ATTACHMENT_AMBIGUOUS", "%s carries %d copies of %s" % (tid, len(same), name))
    if same:
        att = int(same[0]["id"])
    else:
        att = native.attach(tid, str(path), name)
        fault("after-attach")
    with store.txn() as c:
        c.execute("UPDATE publication SET attachment_id=?, attachment_sha256=?, attachment_name=? WHERE outcome_id=?",
                  (att, digest, name, node["outcome_id"]))


def publish_plan(root: Path, store: Store, native: Any, plan: dict[str, Any], *, m2_task: str,
                 nodes: list[dict[str, Any]] | None = None, hold: bool = False) -> dict[str, Any]:
    resolve = {CONTROL_M2: m2_task}
    for r in store.conn.execute("SELECT outcome_id, task_id FROM publication WHERE task_id IS NOT NULL"):
        resolve[r["outcome_id"]] = r["task_id"]
    created = []
    for node in topo_order(nodes if nodes is not None else plan["nodes"]):
        tid = publish_node(root, store, native, plan, node, resolve=resolve, hold=hold)
        resolve[node["outcome_id"]] = tid
        created.append({"outcome_id": node["outcome_id"], "task_id": tid})
    return {"created": created, "by_outcome": resolve}


def readback(store: Store, native: Any, plan: dict[str, Any] | None = None, *, m2_task: str = "") -> list[str]:
    """Every mismatch between the recorded graph and the live board. [] = equal."""
    plan = plan or store.current_revision()
    if plan is None:
        return ["no published revision"]
    m2_task = m2_task or store.meta("m2_task")
    gaps: list[str] = []
    resolve = {CONTROL_M2: m2_task}
    pubs = {r["outcome_id"]: dict(r) for r in store.conn.execute("SELECT * FROM publication")}
    for oid, p in pubs.items():
        if p.get("task_id"):
            resolve[oid] = p["task_id"]
    for node in plan["nodes"]:
        oid = node["outcome_id"]
        p = pubs.get(oid)
        if not p or not p.get("task_id"):
            gaps.append("%s: not published" % oid)
            continue
        if p["state"] not in ("published", "released"):
            gaps.append("%s: publication state %s" % (oid, p["state"]))
        t = native.task(p["task_id"])
        if t is None:
            gaps.append("%s: %s is gone" % (oid, p["task_id"]))
            continue
        if t.get("status") == "archived":
            gaps.append("%s: %s is archived" % (oid, p["task_id"]))
        if t.get("idempotency_key") != p["native_key"]:
            gaps.append("%s: key %r != %r" % (oid, t.get("idempotency_key"), p["native_key"]))
        exp = json.loads(p["expected"])
        for f in ("title", "body"):
            if t.get(f) != exp[f]:
                gaps.append("%s: %s differs" % (oid, f))
        if (t.get("assignee") or None) not in {exp["assignee"], exp.get("final_assignee")}:
            gaps.append("%s: assignee %r" % (oid, t.get("assignee")))
        if node.get("role") == "deliver" and t.get("assignee") and not _granted(store, oid):
            gaps.append("%s: assigned without a stage grant" % oid)
        want_parents = sorted(resolve.get(x, "?") for x in node.get("parents") or [])
        have = sorted(t.get("parents") or [])
        # a held delivery stage may gain the successor assessment as a parent (linked by the
        # continuation); every other node's prerequisites are exactly the published ones
        if (node.get("role") == "deliver" and not set(want_parents) <= set(have)) or \
                (node.get("role") != "deliver" and have != want_parents):
            gaps.append("%s: parents %s != %s" % (oid, have, want_parents))
        if list(t.get("skills") or []) != exp["skills"]:
            gaps.append("%s: skills %s" % (oid, t.get("skills")))
        live = [r for r in native.by_key(p["native_key"]) if r["status"] != "archived"]
        if len(live) != 1:
            gaps.append("%s: %d live cards carry %s" % (oid, len(live), p["native_key"]))
        from planner.outcome_native import sha256_file
        atts = [a for a in native.attachments(p["task_id"]) if p.get("attachment_id") and int(a["id"]) == int(p["attachment_id"])]
        if not atts:
            gaps.append("%s: brief attachment missing" % oid)
        elif sha256_file(atts[0]["stored_path"]) != p.get("attachment_sha256"):
            gaps.append("%s: brief attachment bytes differ" % oid)
    return gaps


def _granted(store: Store, oid: str) -> bool:
    row = store.conn.execute("SELECT state FROM grants WHERE outcome_id=?", (oid,)).fetchone()
    return bool(row and row[0] in ("granted", "executed", "done"))


def complete_generation(store: Store, native: Any) -> list[str]:
    gaps = readback(store, native)
    if not gaps:
        with store.txn() as c:
            if store.meta("publication_state") == "incomplete":
                store.set_meta(c, "publication_state", "complete")
                store.set_meta(c, "publication_completed_at", time.time())
    return gaps


def main(argv: list[str] | None = None) -> int:
    """k4_graph.py --root PATH (publish|readback) -- normally reached through k4_mint.py."""
    import argparse
    from planner.outcome_protocol import OUTCOME, describe, execution_gate, select_protocol
    from planner.outcome_native import KanbanNative, default_db_path
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("action", choices=("publish", "readback", "preview"))
    ap.add_argument("--hermes", default=os.environ.get("HERMES_BIN", "hermes"))
    ap.add_argument("--plan-file", default="", help="qualification mode only: publish this derived plan revision")
    ns = ap.parse_args(argv)
    root = Path(ns.root).resolve()
    sel = select_protocol(root)
    if ns.action == "preview":
        # read-only: the plan revision K4 would publish, with no native operation
        from planner.outcome_lifecycle import initial_plan_from_root
        try:
            plan = initial_plan_from_root(root)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(json.dumps({"preview": True, "gate": [list(g) for g in execution_gate(root, sel)],
                          "nodes": [{k: n.get(k) for k in ("outcome_id", "title", "parents", "assignee")} for n in plan["nodes"]],
                          "counts": plan["counts"], "unresolved": [u["id"] for u in plan["unresolved"]]}, indent=2))
        return 0
    gate = execution_gate(root, sel)
    if gate:
        print(describe(gate), file=sys.stderr)
        print("K4 graph REFUSED before any native operation.", file=sys.stderr)
        return 1
    if ns.action == "readback":
        # read-only, from the board recorded at publication; any caller
        try:
            store = Store(root)
            gaps = readback(store, KanbanNative(store.meta("native_db"), hermes=ns.hermes.split()))
        except (StoreError, RuntimeError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(json.dumps({"gaps": gaps, "publication_state": store.meta("publication_state")}, indent=2))
        return 0 if not gaps else 1
    m2 = (os.environ.get("HERMES_KANBAN_TASK") or "").strip()
    if not m2.startswith("t_"):
        print("K4_GRAPH_CALLER: publication runs from the open M2 card (HERMES_KANBAN_TASK unset); "
              "the worker identity is retained, never scrubbed", file=sys.stderr)
        return 1
    native = KanbanNative(default_db_path(), hermes=ns.hermes.split())
    try:
        t = native.task(m2)
        if t is None or t.get("status") in ("done", "archived"):
            raise PublishError("PUBLICATION_M2_CLOSED", "M2 %s is %s; publication happens under the open M2" % (m2, (t or {}).get("status", "absent")))
        if ns.plan_file:
            # the runtime qualification publishes a plan derived from a fixture; a real run
            # (factory declaration, run control) can never be in qualification mode
            if sel.execution != "qualification":
                raise PublishError("PLAN_FILE_REFUSED", "--plan-file is honoured in qualification mode only")
            plan = json.loads(Path(ns.plan_file).read_text(encoding="utf-8"))
        else:
            from planner.outcome_lifecycle import initial_plan_from_root
            plan = initial_plan_from_root(root)
        store = init_store(root, run_id=plan["run_id"], m2_task=m2, native_db=native.db_path, protocol=OUTCOME,
                           workspace=workspace_for(root, sel.execution))
        persist_plan(store, plan)
        publish_plan(root, store, native, plan, m2_task=m2)
        gaps = complete_generation(store, native)
    except (PublishError, StoreError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        print("K4 graph publication STOPPED (resume with the same command; nothing is duplicated).", file=sys.stderr)
        return 1
    if gaps:
        print("K4 graph read-back mismatch:\n  " + "\n  ".join(gaps), file=sys.stderr)
        return 1
    print("OK: K4 graph published (%d nodes, revision %s, generation complete)" % (len(plan["nodes"]), plan["revision"]))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
