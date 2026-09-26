#!/usr/bin/env python3
"""Outcome-board continuation reconciler (architect F2; contract T4, T8–T10).

Named integration: a shell hook on the pinned runtime's ``on_kanban_dispatch_tick``
observer, which the gateway-embedded dispatcher fires once per tick after
releasing its lock. It also runs on ``kanban_task_completed`` in the worker, as
an accelerator only. It is not a scheduler, a daemon or a polling agent. It runs
when the dispatcher ticks, including after a gateway restart and while a gateway
survives a dead worker.

Each pending intent was written BEFORE the completion it follows (the
pre_tool_call hook records it, then allows the native complete). An intent acts
only once its source task is natively done, and every step is recorded as it
finishes. Each native operation is keyed, and before it runs, the reconciler
reads whether it already happened. A crash anywhere re-runs the lookup and never
the effect: no duplicate card, grant, budget or effect.

Does nothing (exit 0, no output) unless the root runs the outcome protocol with
execution not disabled and a store exists. Under enabled execution the tick is
a REQUEST to the protected authority service, which runs this same function in
its own principal against its own store (outcome_authority.py); the hook
process only forwards it and writes the observer view the service returns.
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

from k4_graph import complete_generation, publish_plan, readback, sync_ownership  # noqa: E402
from planner.outcome_graph import DELIVER_STAGES  # noqa: E402
from planner.outcome_lifecycle import (DELIVERY_OK_VERDICTS, Ctx, Refusal, delivery_facts, plan_after_refuse,  # noqa: E402
                                       stage_admission, write_account)
from planner.outcome_protocol import authority_endpoint, execution_gate, select_protocol  # noqa: E402
from planner.outcome_store import Store, StoreError, canonical, fault, store_path  # noqa: E402

IMPL = "implementer"


def _steps(store: Store, intent_id: str) -> dict[str, Any]:
    row = store.conn.execute("SELECT steps FROM intents WHERE intent_id=?", (intent_id,)).fetchone()
    return json.loads(row[0]) if row else {}


def _step(store: Store, intent_id: str, name: str, value: Any) -> None:
    with store.txn() as c:
        row = c.execute("SELECT steps FROM intents WHERE intent_id=?", (intent_id,)).fetchone()
        steps = json.loads(row[0]) if row else {}
        steps[name] = value
        c.execute("UPDATE intents SET steps=? WHERE intent_id=?", (canonical(steps), intent_id))


def _finish(store: Store, intent_id: str, state: str, result: dict[str, Any]) -> None:
    with store.txn() as c:
        c.execute("UPDATE intents SET state=?, done_at=?, result=? WHERE intent_id=?",
                  (state, time.time(), canonical(result), intent_id))


def _task_of(store: Store, oid: str) -> str:
    row = store.conn.execute("SELECT task_id FROM publication WHERE outcome_id=?", (oid,)).fetchone()
    return row[0] if row and row[0] else ""


def grant_stage(ctx: Ctx, stage_oid: str) -> dict[str, Any]:
    """Assign one pre-created, never-executed M5 stage after its predicate holds."""
    store = ctx.store
    tid = _task_of(store, stage_oid)
    if not tid:
        return {"granted": False, "reasons": ["STAGE_UNPUBLISHED"]}
    row = store.conn.execute("SELECT state FROM grants WHERE outcome_id=?", (stage_oid,)).fetchone()
    if row and row[0] in ("granted", "executed", "done"):
        return {"granted": True, "recovered": True}
    if not row:
        stage = stage_oid.split(":")[1]
        facts = delivery_facts(ctx, stage_oid)
        verdict = stage_admission(stage, facts)
        if not verdict["admit"]:
            return {"granted": False, "reasons": verdict["reasons"], "facts": facts}
        plan = store.current_revision() or {}
        node = next((n for n in plan.get("nodes") or [] if n["outcome_id"] == stage_oid), {})
        with store.txn() as c:
            c.execute("INSERT OR IGNORE INTO grants(outcome_id, stage, cycle, candidate, assessment, state, doc, granted_at) "
                      "VALUES(?,?,?,?,?,?,?,?)", (stage_oid, stage, 1, facts["candidate"],
                                                 (node.get("binding") or {}).get("assessment", ""), "granting",
                                                 canonical(verdict), time.time()))
    t = ctx.native.task(tid)
    if t is None or t.get("status") == "archived":
        return {"granted": False, "reasons": ["STAGE_ARCHIVED"]}
    if t.get("assignee") != IMPL:
        ctx.native.assign(tid, IMPL)
        fault("reconcile-after-assign")
    with store.txn() as c:
        c.execute("UPDATE grants SET state='granted' WHERE outcome_id=? AND state='granting'", (stage_oid,))
    return {"granted": True}


def _m2_release(ctx: Ctx, intent: dict[str, Any]) -> str:
    store = ctx.store
    m2 = ctx.native.task(store.meta("m2_task"))
    if not m2 or m2.get("status") != "done":
        return "pending"
    with store.txn() as c:
        store.set_meta(c, "publication_state", "released")
        store.set_meta(c, "release_in_progress", "0")
        c.execute("UPDATE publication SET state='released' WHERE state='published'")
    _finish(store, intent["intent_id"], "done", {"released": True})
    return "done"


def _m4_assessed(ctx: Ctx, intent: dict[str, Any]) -> str:
    store = ctx.store
    doc = json.loads(intent["doc"])
    src = ctx.native.task(intent["source_task"] or "")
    if not src or src.get("status") != "done":
        return "pending"
    iid = intent["intent_id"]
    steps = _steps(store, iid)
    if str(doc.get("verdict") or "").upper() in DELIVERY_OK_VERDICTS:
        g = grant_stage(ctx, "deliver:%s:c1" % DELIVER_STAGES[0])
        if g.get("granted"):
            _finish(store, iid, "done", {"granted": "deliver:prepare:c1"})
            return "done"
        _finish(store, iid, "stopped", {"reasons": g.get("reasons")})
        return "stopped"
    # REFUSE: bounded repairs, then a successor assessment
    if "revision" not in steps:
        plan = store.current_revision()
        nxt = plan_after_refuse(store, plan, doc)
        if isinstance(nxt, Refusal):
            _finish(store, iid, "stopped", {"code": nxt.code, "detail": nxt.detail})
            return "stopped"
        try:
            rev = store.commit_revision(nxt, kind="refuse-repair", parent=int(plan["revision"]))
        except StoreError as exc:
            if exc.code in ("REVISION_BLOCKED_BY_EFFECT", "REVISION_BLOCKED_BY_RELEASE"):
                return "pending"
            raise
        sync_ownership(store, nxt)
        _step(store, iid, "revision", rev)
        fault("reconcile-after-revision")
    plan = store.current_revision()
    if "nodes" not in _steps(store, iid):
        # the continuation's node set, persisted BEFORE any native operation: every node this
        # revision adds. A crash anywhere replays exactly this set (review R4).
        prev = store.conn.execute("SELECT doc FROM revisions WHERE rev=?", (int(plan["revision"]) - 1,)).fetchone()
        before = {n["outcome_id"] for n in json.loads(prev[0])["nodes"]} if prev else set()
        _step(store, iid, "nodes", sorted(n["outcome_id"] for n in plan["nodes"] if n["outcome_id"] not in before))
    wanted = set(_steps(store, iid).get("nodes") or [])
    nodes = [n for n in plan["nodes"] if n["outcome_id"] in wanted]
    # replay EVERY node of the set through complete publication (a node that already has a
    # task id may still lack its recorded brief); held: nothing is assigned yet
    publish_plan(ctx.root, store, ctx.native, plan, m2_task=store.meta("m2_task"), nodes=nodes, hold=True)
    fault("reconcile-after-publish")
    succ = next(n["outcome_id"] for n in nodes if n.get("role") == "assess")
    prep = _task_of(store, "deliver:%s:c1" % DELIVER_STAGES[0])
    succ_tid = _task_of(store, succ)
    t = ctx.native.task(prep)
    if prep and succ_tid and succ_tid not in (t or {}).get("parents", []):
        ctx.native.link(succ_tid, prep)
    gaps = readback(store, ctx.native, plan)
    if gaps:
        _step(store, iid, "readback", gaps[:8])
        return "pending"
    # only a complete revised graph that reads back releases work (T9 order)
    for oid in sorted(wanted):
        node = next(n for n in nodes if n["outcome_id"] == oid)
        tid = _task_of(store, oid)
        t = ctx.native.task(tid)
        if node.get("assignee") and t and t.get("assignee") != node["assignee"]:
            ctx.native.assign(tid, node["assignee"])
            fault("reconcile-after-assign")
    gaps = readback(store, ctx.native, plan)
    if gaps:
        _step(store, iid, "readback", gaps[:8])
        return "pending"
    _finish(store, iid, "done", {"revision": plan["revision"], "successor": succ, "published": sorted(wanted)})
    return "done"


def _m5_stage_done(ctx: Ctx, intent: dict[str, Any]) -> str:
    store = ctx.store
    doc = json.loads(intent["doc"])
    src = ctx.native.task(intent["source_task"] or "")
    if not src or src.get("status") != "done":
        return "pending"
    stage = doc.get("stage")
    with store.txn() as c:
        c.execute("UPDATE grants SET state='done' WHERE outcome_id=?", (doc["outcome_id"],))
    idx = DELIVER_STAGES.index(stage) if stage in DELIVER_STAGES else -1
    if idx < 0 or idx + 1 >= len(DELIVER_STAGES):
        _finish(store, intent["intent_id"], "done", {"delivery": "complete", "ship": bool((doc.get("result") or {}).get("ship"))})
        return "done"
    nxt = "deliver:%s:c1" % DELIVER_STAGES[idx + 1]
    g = grant_stage(ctx, nxt)
    if g.get("granted"):
        _finish(store, intent["intent_id"], "done", {"granted": nxt})
        return "done"
    _finish(store, intent["intent_id"], "stopped", {"reasons": g.get("reasons")})
    return "stopped"


def _m3_accepted(ctx: Ctx, intent: dict[str, Any]) -> str:
    src = ctx.native.task(intent["source_task"] or "")
    if not src or src.get("status") != "done":
        return "pending"
    _finish(ctx.store, intent["intent_id"], "done", {})
    return "done"

HANDLERS = {"m2-release": _m2_release, "m4-assessed": _m4_assessed, "m5-stage-done": _m5_stage_done,
            "m3-accepted": _m3_accepted}


def tick(root: Path, native: Any | None = None, *, alive: Any = None,
         observer_writes: bool = True) -> list[dict[str, Any]]:
    root = Path(root)
    if not store_path(root).exists() or execution_gate(root):
        return []
    store = Store(root)
    if native is None:
        from planner.outcome_native import KanbanNative
        db = store.meta("native_db")
        env = dict(os.environ, HERMES_KANBAN_DB=db)
        native = KanbanNative(db, hermes=(os.environ.get("HERMES_BIN") or "hermes").split(), env=env)
    ctx = Ctx(root, store, native, alive=alive, observer_writes=observer_writes)
    out = []
    if store.meta("publication_state") == "incomplete":
        complete_generation(store, native)
    from planner.outcome_lifecycle import recover_dead_effects
    for row in recover_dead_effects(store, root, native, alive=alive):
        out.append({"effect": row["effect_id"], "state": row["state"]})
    for row in store.conn.execute("SELECT * FROM intents WHERE state='pending' ORDER BY created_at, intent_id").fetchall():
        intent = dict(row)
        handler = HANDLERS.get(intent["kind"])
        if handler is None:
            continue
        try:
            state = handler(ctx, intent)
        except (Refusal, StoreError) as exc:
            _step(store, intent["intent_id"], "last_error", "%s" % exc)
            state = "pending"
        out.append({"intent": intent["intent_id"], "state": state})
    try:
        write_account(ctx)
    except Exception:
        pass
    return out


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    root = Path(os.environ.get("MODERNIZED_ROOT") or _KERNEL.parents[1])
    if "--root" in args:
        root = Path(args[args.index("--root") + 1])
    if not sys.stdin.isatty():
        try:
            sys.stdin.read()  # the hook payload; the reconciler reads state, not the event
        except OSError:
            pass
    try:
        endpoint = authority_endpoint(select_protocol(root))
        if endpoint:
            # the protected authority reconciles; this observer only asks it to
            from planner.outcome_authority import call
            out = call(endpoint, "tick", {}) or []
        else:
            out = tick(root)
    except Exception as exc:  # an observer never breaks dispatch; the intent stays pending
        print(json.dumps({"reconcile_error": str(exc)}), file=sys.stderr)
        return 0
    if out:
        print(json.dumps({"reconciled": out}), file=sys.stderr)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
