"""Deterministic publication of the outcome plan as native Hermes tasks (outcome-board/v2).

The ONE writer of the native graph for a native-control run, run as a CLI by
the worker that owns the triggering task (kernel/native_gate.py): the M2 card
publishes the initial plan; a dependent task publishes its owner repair; the
M4 task publishes the repairs its REFUSE needs. Nothing else creates or links
(the K2 hook refuses kanban_create / kanban_link and direct CLI graph edits).

Order, every step looked up before it is repeated:

  1. the plan revision document ``plan.r<N>.json`` is attached to the task that
     triggered it (M2 for revision 1): the plan and the digest of each contract
     it introduces. A different document under the same revision refuses.
  2. each new node in dependency order: one native task under its stable key
     ``<outcome|assess|deliver>:v2:<run>:<outcome id>``, parents given at
     creation; then its ``contract.json`` attachment.
  3. links from a new node to already published dependents (repair -> the
     waiting dependent, repair -> the open M4), never the reverse.
  4. read-back of the whole graph against the latest revision.

The pinned ``create_task`` checks the idempotency key outside its write
transaction, so concurrent creates can duplicate: every mutation here runs
under native_control.publication_lock, and a read-back that finds two live
tasks under one key stops (PUBLICATION_DUPLICATE). An existing key is reused
only when its fields match the expectation (a key match alone is not enough);
an archived identity is never re-created.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from planner.native_control import (CONTRACT, IMPL, MAX_RETRIES, REVIEWER, WORKSPACE, Board, Refusal, canonical_bytes,
                                    contract_doc, native_key, native_plan, plan_attachment, publication_lock, sha256)
from planner.outcome_graph import CONTROL_M2, topo_order

READBACK_ASSIGNEES = (IMPL, REVIEWER)


def workspace_for(root: Path, execution: str) -> str:
    """A real run always works in /projects/modernized; only a disposable
    qualification fixture works in its own root."""
    if execution == "qualification":
        return "dir:" + str(Path(root).resolve())
    return WORKSPACE


def _attach_bytes(board: Board, task_id: str, name: str, data: bytes) -> None:
    with tempfile.TemporaryDirectory(prefix="native-publish-") as td:
        p = Path(td) / name
        p.write_bytes(data)
        board.native.attach(task_id, str(p), name)


def _attach_plan(board: Board, holder: str, plan: dict[str, Any], added: list[str]) -> None:
    name = "plan.r%d.json" % int(plan["revision"])
    revs = board.revisions(plan["run_id"])
    have = revs.get(int(plan["revision"]))
    if have is not None:
        if have[1]["plan"].get("digest") != plan.get("digest"):
            raise Refusal("PUBLICATION_REPLAN", "revision %d is attached to %s with another digest; identity is frozen at "
                          "publication" % (int(plan["revision"]), have[0]))
        return
    top = max(revs) if revs else 0
    if int(plan["revision"]) != top + 1:
        raise Refusal("PUBLICATION_REVISION_ORDER", "revision %d does not follow the board's revision %d" % (int(plan["revision"]), top))
    _attach_bytes(board, holder, name, canonical_bytes(plan_attachment(plan, added)))


def _expected(node: dict[str, Any], parents: list[str]) -> dict[str, Any]:
    return {"title": node["title"], "body": node["description"], "assignee": node.get("assignee"),
            "parents": sorted(parents), "skills": list(node.get("skills") or [])}


def _find_or_create(board: Board, run_id: str, node: dict[str, Any], parents: list[str], workspace: str) -> str:
    key = native_key(run_id, node)
    rows = board.native.by_key(key)
    live = [r for r in rows if r["status"] != "archived"]
    if len(live) > 1:
        raise Refusal("PUBLICATION_DUPLICATE", "%s has %d live tasks %s" % (key, len(live), [r["id"] for r in live]))
    if not live and rows:
        raise Refusal("PUBLICATION_ARCHIVED", "%s exists only archived (%s); an archived identity is never re-created" % (key, rows[0]["id"]))
    exp = _expected(node, parents)
    if live:
        t = board.task(live[0]["id"]) or {}
        diffs = [f for f in ("title", "body") if t.get(f) != exp[f]]
        if list(t.get("skills") or []) != exp["skills"]:
            diffs.append("skills")
        if not set(exp["parents"]) <= set(t.get("parents") or []):
            diffs.append("parents")
        if diffs:
            raise Refusal("PUBLICATION_MISMATCH", "%s exists as %s with different %s; a key match alone is not a reuse"
                          % (key, live[0]["id"], ", ".join(diffs)))
        return live[0]["id"]
    return board.native.create(title=exp["title"], body=exp["body"], assignee=exp["assignee"], parents=exp["parents"],
                               key=key, skills=exp["skills"], workspace=workspace, max_retries=MAX_RETRIES)


def _attach_contract(board: Board, task_id: str, plan: dict[str, Any], node: dict[str, Any], want: str) -> None:
    data = canonical_bytes(contract_doc(plan, node))
    if sha256(data) != want:
        raise Refusal("CONTRACT_DIGEST", "the contract of %s does not match its revision's digest" % node["outcome_id"])
    got = board.attachment(task_id, CONTRACT)
    if got is not None:
        if sha256(got[0]) != want:
            raise Refusal("CONTRACT_MISMATCH", "%s carries another %s" % (task_id, CONTRACT))
        return
    _attach_bytes(board, task_id, CONTRACT, data)


def _resolve(board: Board, plan: dict[str, Any], m2: str) -> dict[str, str]:
    out = {CONTROL_M2: m2}
    for n in plan["nodes"]:
        tid = board.task_of(plan["run_id"], n)
        if tid:
            out[n["outcome_id"]] = tid
    return out


def _publish_nodes(board: Board, plan: dict[str, Any], added: list[str], *, workspace: str) -> list[dict[str, str]]:
    m2 = board.m2_task()
    resolve = _resolve(board, plan, m2)
    digests = board.contract_digests(plan["run_id"])
    wanted = set(added)
    created = []
    for node in topo_order(plan["nodes"]):
        oid = node["outcome_id"]
        if oid not in wanted:
            continue
        parents = []
        for p in node.get("parents") or []:
            if p not in resolve:
                raise Refusal("PUBLICATION_PARENT", "%s parent %s has no native task yet" % (oid, p))
            parents.append(resolve[p])
        tid = _find_or_create(board, plan["run_id"], node, parents, workspace)
        resolve[oid] = tid
        _attach_contract(board, tid, plan, node, digests[oid])
        created.append({"outcome_id": oid, "task_id": tid})
    # links from a new node to dependents that already exist (repair -> dependent, repair -> M4)
    for node in plan["nodes"]:
        child = resolve.get(node["outcome_id"])
        if not child or node["outcome_id"] in wanted:
            continue
        have = set((board.task(child) or {}).get("parents") or [])
        for p in node.get("parents") or []:
            if p in wanted and resolve.get(p) and resolve[p] not in have:
                board.native.link(resolve[p], child)
    return created


def readback(board: Board, plan: dict[str, Any]) -> list[str]:
    """Every difference between the latest plan revision and the live board. [] = equal."""
    gaps: list[str] = []
    m2 = board.m2_task()
    if not m2:
        return ["the M2 control task (key m2-plan) is not unique and live"]
    resolve = {CONTROL_M2: m2}
    run_id = plan["run_id"]
    try:
        digests = board.contract_digests(run_id)
    except Refusal as exc:
        return ["%s: %s" % (exc.code, exc.detail)]
    for node in plan["nodes"]:
        rows = board.native.by_key(native_key(run_id, node))
        live = [r for r in rows if r["status"] != "archived"]
        if len(live) == 1:
            resolve[node["outcome_id"]] = live[0]["id"]
    for node in plan["nodes"]:
        oid = node["outcome_id"]
        key = native_key(run_id, node)
        rows = board.native.by_key(key)
        live = [r for r in rows if r["status"] != "archived"]
        if len(live) != 1:
            gaps.append("%s: %d live tasks carry %s" % (oid, len(live), key) if live or not rows
                        else "%s: %s is archived" % (oid, key))
            continue
        t = board.task(live[0]["id"]) or {}
        for f, want in (("title", node["title"]), ("body", node["description"])):
            if t.get(f) != want:
                gaps.append("%s: %s differs" % (oid, f))
        if list(t.get("skills") or []) != list(node.get("skills") or []):
            gaps.append("%s: skills %s" % (oid, t.get("skills")))
        if (t.get("assignee") or None) not in READBACK_ASSIGNEES:
            gaps.append("%s: assignee %r" % (oid, t.get("assignee")))
        want_parents = sorted(resolve.get(p, "?:" + p) for p in node.get("parents") or [])
        have = sorted(t.get("parents") or [])
        if have != want_parents:
            gaps.append("%s: parents %s != %s" % (oid, have, want_parents))
        if oid not in digests:
            gaps.append("%s: no revision names its contract" % oid)
            continue
        try:
            got = board.attachment(live[0]["id"], CONTRACT)
        except Refusal as exc:
            gaps.append("%s: %s" % (oid, exc.detail))
            continue
        if got is None:
            gaps.append("%s: contract attachment missing" % oid)
        elif sha256(got[0]) != digests[oid]:
            gaps.append("%s: contract attachment bytes differ" % oid)
    return gaps


def publish_initial(root: Path, board: Board, *, m2: str, plan_file: str = "") -> dict[str, Any]:
    """Revision 1 under the OPEN M2 card: derive (or, in qualification mode
    only, read) the plan, attach it, publish every node, read back. M2 cannot
    complete until the read-back is empty (native_control.check_terminator)."""
    from planner.outcome_protocol import describe, execution_gate, select_protocol
    root = Path(root)
    sel = select_protocol(root)
    if not sel.native:
        raise Refusal("PROTOCOL_NOT_NATIVE", "this run selects %s" % sel.protocol)
    gate = execution_gate(root, sel)
    if gate:
        raise Refusal(gate[0][0], describe(gate).splitlines()[0])
    t = board.task(m2)
    if t is None or t.get("idempotency_key") != "m2-plan":
        raise Refusal("PUBLICATION_CALLER", "publication runs from the open M2 card (HERMES_KANBAN_TASK=%r is not it)" % m2)
    if t.get("status") in ("done", "archived"):
        raise Refusal("PUBLICATION_M2_CLOSED", "M2 %s is %s; publication happens under the open M2" % (m2, t.get("status")))
    if plan_file:
        if sel.execution != "qualification":
            raise Refusal("PLAN_FILE_REFUSED", "--plan-file is honoured in qualification mode only")
        plan = json.loads(Path(plan_file).read_text(encoding="utf-8"))
    else:
        from planner.outcome_checks import initial_plan_from_root
        plan = initial_plan_from_root(root)
    plan = native_plan(plan)
    workspace = workspace_for(root, sel.execution)
    added = [n["outcome_id"] for n in plan["nodes"]]
    with publication_lock(root):
        _attach_plan(board, m2, plan, added)
        created = _publish_nodes(board, plan, added, workspace=workspace)
        gaps = readback(board, board.plan(plan["run_id"]))
    return {"nodes": len(plan["nodes"]), "revision": int(plan["revision"]), "run_id": plan["run_id"],
            "created": created, "gaps": gaps}


def publish_revision(root: Path, board: Board, plan: dict[str, Any], *, added: list[str], holder: str) -> dict[str, Any]:
    """A bounded revision (owner repair, REFUSE repairs): attached to the task
    that triggered it, its new nodes published, their links to existing
    dependents made. Replaying it publishes nothing twice."""
    from planner.outcome_protocol import select_protocol
    root = Path(root)
    execution = select_protocol(root).execution
    with publication_lock(root):
        _attach_plan(board, holder, plan, added)
        created = _publish_nodes(board, plan, added, workspace=workspace_for(root, execution))
        gaps = readback(board, board.plan(plan["run_id"]))
    if gaps:
        raise Refusal("PUBLICATION_READBACK", "; ".join(gaps[:4]))
    return {"revision": int(plan["revision"]), "created": created}
