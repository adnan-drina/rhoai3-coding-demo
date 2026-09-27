"""Exact-runtime qualification of native cooperative control (outcome-board/v2).

The pinned Hermes runtime (tree 8a3bb406, as installed in the ws-080 image)
owns every lifecycle transition here: the real ``hermes kanban`` CLI creates,
attaches, links and comments (driven by the golden's native_gate.py, run with
the worker's ``python3``), and the real ``hermes_cli.kanban_db`` functions
stand in for the dispatcher and the worker tools: claim, claim_review_task,
request_review, request_changes, block_task kind=dependency, complete_task
with the worker's expected_run_id, and crash detection. The real K2 hook
(kernel/pre_tool_call.sh) decides terminators and writes. No model, no
dispatcher loop, no cluster: the worker's reasoning is replaced by scripted
edits; the lifecycle and the domain gates are the real code.

Run inside the image (no pytest there; plain asserts, a JSON receipt):

  podman run --rm --platform linux/amd64 --entrypoint /bin/bash \\
    -v <scaffold>:/scaffold:ro -v <this dir>:/t:ro localhost/rhoai3-ws-080:<tag> \\
    -c 'RHOAI3_SCAFFOLD=/scaffold /opt/hermes-venv/bin/python3.11 /t/test_native_control.py'
"""
from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.dont_write_bytecode = True
SCAFFOLD = Path(os.environ.get("RHOAI3_SCAFFOLD", "")).resolve()
GOLDEN = SCAFFOLD / ".hermes"
if not (GOLDEN / "lib" / "planner" / "native_control.py").is_file():
    raise SystemExit("RHOAI3_SCAFFOLD must name the quarkus-migration-scaffold directory (got %r)" % str(SCAFFOLD))
WORKER_PY = os.environ.get("RHOAI3_WORKER_PYTHON", "python3")
TMP = Path(tempfile.mkdtemp(prefix="native-rt-"))
HOME = TMP / "home"
HOME.mkdir()
DB = HOME / "kanban.db"
for k in [k for k in os.environ if k.startswith("HERMES_")]:
    del os.environ[k]
os.environ.update(HERMES_HOME=str(HOME), HERMES_KANBAN_HOME=str(HOME), HERMES_KANBAN_DB=str(DB))
sys.path.insert(0, str(GOLDEN / "lib"))
from hermes_cli import kanban_db as kb  # noqa: E402  the pinned kernel
from planner import native_control as NC  # noqa: E402  read-side inspection only
from planner.outcome_graph import derive_initial_graph, topo_order  # noqa: E402
from planner.outcome_native import KanbanNative  # noqa: E402

SHOP = json.loads((GOLDEN / "lib" / "planner" / "fixtures" / "outcome-initial-shop.json").read_text())
RUN = "rt1"
RESULTS: list[dict] = []


def check(case: str, ok: bool, **facts) -> None:
    RESULTS.append({"case": case, "passed": bool(ok), **facts})
    print(("PASS " if ok else "FAIL ") + case + (" " + json.dumps(facts, sort_keys=True, default=str) if facts else ""), flush=True)
    assert ok, (case, facts)


def git(root, *a):
    return subprocess.run(["git", "-C", str(root), *a], capture_output=True, text=True, check=True).stdout.strip()


def conn():
    return kb.connect(DB)


def make_dest() -> Path:
    dest = TMP / "modernized"
    (dest / ".hermes").mkdir(parents=True)
    for name in ("lib", "kernel", "planning", "skills"):
        os.symlink(GOLDEN / name, dest / ".hermes" / name)
    (dest / "run-defaults.json").write_text(json.dumps({"schema": "rhoai3.run-defaults/v1", "budget": {},
                                                       "configuration": {"board_protocol": "outcome-board/v2"}}))
    (dest / ".hermes" / "pins.json").write_text(json.dumps({"pins": {"planner": {"outcome_board": {"execution": "qualification"}}}}))
    shutil.copy(SCAFFOLD / "decisions.yaml", dest / "decisions.yaml")
    for c in SHOP["worklist"]["clusters"]:
        for p in c["write_set"]:
            f = dest / p
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("// %s v0\n" % p)
    (dest / "evidence" / "planning").mkdir(parents=True)
    (dest / "evidence" / "planning" / "worklist.json").write_text(json.dumps(SHOP["worklist"]))
    (dest / ".gitignore").write_text("verification/\nevidence/\n")
    git(dest, "init", "-q")
    git(dest, "config", "user.email", "q@q")
    git(dest, "config", "user.name", "q")
    git(dest, "add", "-A")
    git(dest, "commit", "-qm", "baseline")
    plan = derive_initial_graph(run_id=RUN, worklist=SHOP["worklist"], entry_points=SHOP["entry_points"],
                                oracles=SHOP["oracles"], references=SHOP["references"], provenance=SHOP["provenance"])
    (TMP / "plan.json").write_text(json.dumps(plan))
    return dest


DEST = make_dest()
WL = copy.deepcopy(SHOP["worklist"])


def save_wl():
    (DEST / "evidence" / "planning" / "worklist.json").write_text(json.dumps(WL))


def drop(ids):
    ids = set(ids)
    WL["items"] = [i for i in WL["items"] if i["id"] not in ids]
    for c in WL["clusters"]:
        c["items"] = [i for i in c["items"] if i not in ids]
    WL["clusters"] = [c for c in WL["clusters"] if c["items"]]
    save_wl()


def env_for(task="", run=0, lock="", profile="implementer", **extra):
    e = dict(os.environ, HERMES_BIN="hermes", HERMES_PROFILE=profile, K2_ALLOW_ROOT=str(DEST),
             HERMES_WRITE_SAFE_ROOT=str(DEST), PYTHONDONTWRITEBYTECODE="1")
    if task:
        e["HERMES_KANBAN_TASK"] = task
    if run:
        e["HERMES_KANBAN_RUN_ID"] = str(run)
    if lock:
        e["HERMES_KANBAN_CLAIM_LOCK"] = lock
    e.update({k: str(v) for k, v in extra.items()})
    return e


def gate(cmd, *args, task="", run=0, lock="", env=None):
    p = subprocess.run([WORKER_PY, str(GOLDEN / "kernel" / "native_gate.py"), "--root", str(DEST), cmd, *args],
                       capture_output=True, text=True, env=env or env_for(task, run, lock), cwd=str(DEST))
    try:
        out = json.loads(p.stdout[p.stdout.find("{"):]) if "{" in p.stdout else {}
    except ValueError:
        out = {"raw": p.stdout}
    return p.returncode, out, p.stderr


def hook(tool, inp, *, task, run, profile="implementer", **extra):
    payload = {"hook_event_name": "pre_tool_call", "tool_name": tool, "tool_input": inp, "cwd": str(DEST)}
    p = subprocess.run(["bash", str(GOLDEN / "kernel" / "pre_tool_call.sh")], input=json.dumps(payload),
                       capture_output=True, text=True, env=env_for(task, run, profile=profile, **extra), cwd=str(DEST))
    try:
        out = json.loads(p.stdout or "{}")
    except ValueError:
        return {"raw": p.stdout, "stderr": p.stderr[-400:]}
    if os.environ.get("RHOAI3_DEBUG_HOOK"):
        print("HOOK %s -> %s | %s" % (tool, out, p.stderr[-600:]), flush=True)
    return out


def status(tid):
    c = conn()
    try:
        return kb.get_task(c, tid).status
    finally:
        c.close()


def board():
    return NC.Board(KanbanNative(str(DB)))


def tid_of(oid):
    b = board()
    return b.task_of(RUN, NC._node(b.plan(RUN), oid))


def claim(tid):
    c = conn()
    try:
        t = kb.claim_task(c, tid)
        assert t is not None, "claim of %s failed (%s)" % (tid, kb.get_task(c, tid).status)
        return t.current_run_id, t.claim_lock
    finally:
        c.close()


def review(tid, run, *, summary="candidate for review"):
    c = conn()
    try:
        assert kb.request_review(c, tid, reviewer="reviewer", summary=summary, expected_run_id=run)
        t = kb.claim_review_task(c, tid)
        assert t is not None
        return t.current_run_id
    finally:
        c.close()


def complete(tid, run):
    c = conn()
    try:
        return kb.complete_task(c, tid, summary="accepted", expected_run_id=run)
    finally:
        c.close()


def edit(rel, text):
    (DEST / rel).write_text(text)


def owned(oid):
    b = board()
    plan = b.plan(RUN)
    return NC.owned(plan, NC._node(plan, oid))


def accept(oid, *, text=None, attempt="1", drop_owned=True, classes="build,compile,tests", scenarios=""):
    """One implementation run to an accepted outcome, through native_gate as the worker runs it."""
    tid = tid_of(oid)
    run, lock = claim(tid)
    rc, iss, err = gate("issue", task=tid, run=run, lock=lock)
    assert rc == 0, (oid, iss, err)
    if iss["allowed_paths"]:
        edit(iss["allowed_paths"][0], text or "// %s accepted (%s)\n" % (oid, attempt))
    rc, out, err = gate("verdict", "--verdict", "ACCEPTED", "--attempt", attempt, task=tid, run=run)
    assert rc == 0, (oid, out, err)
    git(DEST, "add", "-A")
    git(DEST, "commit", "-qm", "accept %s" % oid, "--allow-empty")
    if drop_owned:
        drop(owned(oid))
    rc, out, err = gate("accept-commit", "--attempt", attempt, "--commit", git(DEST, "rev-parse", "HEAD"),
                        "--classes", classes, "--scenarios", scenarios, task=tid, run=run)
    assert rc == 0 and out["outcome_accepted"], (oid, out, err)
    return tid, run


def accept_and_complete(oid, **kw):
    tid, run = accept(oid, **kw)
    assert hook("kanban_request_review", {"reviewer": "reviewer", "summary": "x"}, task=tid, run=run) == {}
    rrun = review(tid, run)
    assert hook("kanban_complete", {"summary": "ok"}, task=tid, run=rrun, profile="reviewer", K2_PAVED_ROAD_AUDIT_EXIT="0") == {}
    assert complete(tid, rrun)
    return tid


def main() -> int:
    subprocess.run(["hermes", "kanban", "init"], env=env_for(), capture_output=True, check=False)
    out = subprocess.run(["hermes", "kanban", "create", "M2 PLAN", "--idempotency-key", "m2-plan", "--assignee", "implementer",
                          "--skill", "paved-road-m2", "--json"], env=env_for(), capture_output=True, text=True, check=True).stdout
    m2 = json.loads(out[out.find("{"):out.rfind("}") + 1])["id"]
    m2_run, m2_lock = claim(m2)

    # -- 1. publication under the open M2, resumable, no early dispatch ------------------
    rc, early, _ = gate("readback", task=m2, run=m2_run)
    d = hook("kanban_request_review", {"reviewer": "reviewer", "summary": "plan"}, task=m2, run=m2_run)
    check("m2_refused_before_publication", "M2_PUBLICATION_INCOMPLETE" in d.get("message", ""), message=d.get("message", "")[:120])
    # an interrupted publication: the real CLI fails on the 4th create (a wrapper stands in for a crash)
    wrap = TMP / "hermes-crash"
    wrap.write_text("#!/bin/bash\nn=$(cat %s/creates 2>/dev/null || echo 0)\nif [ \"$2\" = create ]; then n=$((n+1)); echo $n > %s/creates; "
                    "if [ $n -eq 4 ]; then echo crash >&2; exit 1; fi; fi\nexec hermes \"$@\"\n" % (TMP, TMP))
    wrap.chmod(0o755)
    rc, out, err = gate("publish", "--plan-file", str(TMP / "plan.json"), task=m2, run=m2_run,
                        env=env_for(m2, m2_run, m2_lock, HERMES_BIN=str(wrap)))
    tasks_after_crash = [t for t in kb.list_tasks(conn()) if NC.parse_key(t.idempotency_key)]
    check("interrupted_publication_holds_everything", rc != 0 and all(t.status == "todo" for t in tasks_after_crash),
          created_before_crash=len(tasks_after_crash))
    rc, out, err = gate("publish", "--plan-file", str(TMP / "plan.json"), task=m2, run=m2_run)
    plan = board().plan(RUN)
    keys = [t.idempotency_key for t in kb.list_tasks(conn()) if NC.parse_key(t.idempotency_key)]
    check("publication_resumes_without_duplicates", rc == 0 and out["gaps"] == [] and len(keys) == len(set(keys)) == len(plan["nodes"]),
          nodes=len(plan["nodes"]), rc=rc)
    rc, again, _ = gate("publish", "--plan-file", str(TMP / "plan.json"), task=m2, run=m2_run)
    check("publication_replay_is_a_no_op", rc == 0 and len([t for t in kb.list_tasks(conn()) if NC.parse_key(t.idempotency_key)]) == len(plan["nodes"]))
    b = board()
    check("contracts_attached_and_read_back", all(b.contract(tid_of(n["outcome_id"]))["outcome_id"] == n["outcome_id"] for n in plan["nodes"])
          and gate("readback")[0] == 0)
    check("m3_waits_on_open_m2", all(status(tid_of(n["outcome_id"])) == "todo" for n in plan["nodes"]))

    # -- 2. M2 release through the real review lifecycle and the K2 gate ------------------
    d = hook("kanban_request_review", {"reviewer": "reviewer", "summary": "plan"}, task=m2, run=m2_run)
    check("m2_review_allowed_on_green_readback", d == {}, got=d)
    rrun = review(m2, m2_run)
    d = hook("kanban_complete", {"summary": "released"}, task=m2, run=rrun, profile="reviewer", K2_PAVED_ROAD_AUDIT_EXIT="0")
    check("m2_complete_allowed_for_reviewer", d == {}, got=d)
    assert complete(m2, rrun)
    check("native_release_of_m3_roots", status(tid_of("build:rk:pom")) == "ready" and status(tid_of("source:rk:item")) == "todo")

    # -- 3. same-task rework: failed candidate -> changes requested -> accepted -------------
    pom = tid_of("build:rk:pom")
    run, lock = claim(pom)
    rc, iss, _ = gate("issue", task=pom, run=run, lock=lock)
    check("issue_scopes_the_cluster", rc == 0 and iss["allowed_paths"] == ["pom.xml"] and (DEST / "verification/loop/issued.json").is_file())
    d = hook("write_file", {"path": str(DEST / "src/main/java/com/acme/shop/web/ItemController.java"), "content": "x"}, task=pom, run=run)
    # refused by the loop card's write set (the issued.json projection) or the native issue record: both are this run's scope
    check("write_outside_issue_refused", d.get("action") == "block" and ("outside this card write set" in d.get("message", "")
                                                                         or "WRITE_OUTSIDE_ISSUE" in d.get("message", "")))
    check("write_inside_issue_allowed", hook("write_file", {"path": str(DEST / "pom.xml"), "content": "x"}, task=pom, run=run) == {})
    edit("pom.xml", "<project>red</project>\n")
    rc, rej, _ = gate("verdict", "--verdict", "REVERTED", "--attempt", "1", "--reason", "compile red", task=pom, run=run)
    git(DEST, "checkout", "--", "pom.xml")
    check("failed_candidate_is_a_reject_record_on_the_same_task", rc == 0 and rej["spent"] == 1)
    d = hook("kanban_request_review", {"reviewer": "reviewer", "summary": "x"}, task=pom, run=run)
    check("no_false_progress_before_acceptance", "OUTCOME_NOT_ACCEPTED" in d.get("message", ""))
    rc, iss, _ = gate("issue", task=pom, run=run)
    edit("pom.xml", "<project>quarkus</project>\n")
    gate("verdict", "--verdict", "ACCEPTED", "--attempt", "2", task=pom, run=run)
    git(DEST, "commit", "-qam", "pom accepted")
    drop(owned("build:rk:pom"))
    rc, acc, _ = gate("accept-commit", "--attempt", "2", "--commit", git(DEST, "rev-parse", "HEAD"),
                        "--classes", "build,compile,tests", task=pom, run=run)
    check("accepted_outcome", rc == 0 and acc["outcome_accepted"], got=acc)
    d = hook("kanban_complete", {"summary": "done"}, task=pom, run=run)
    check("implementer_cannot_complete_its_outcome", "NATIVE_TERMINATOR" in d.get("message", ""))
    check("implementer_review_handoff_allowed", hook("kanban_request_review", {"reviewer": "reviewer", "summary": "x"}, task=pom, run=run) == {})
    rrun = review(pom, run)
    d = hook("kanban_complete", {"summary": "ok"}, task=pom, run=rrun, profile="reviewer", K2_PAVED_ROAD_AUDIT_EXIT="1")
    check("reviewer_complete_refused_on_red_audit", "AUDIT_RED" in d.get("message", ""))
    c = conn()
    ok, _impl = kb.request_changes(c, pom, reason="keep no Spring Boot parent", expected_run_id=rrun)
    stale = kb.complete_task(c, pom, summary="stale approval", expected_run_id=rrun)
    c.close()
    check("changes_requested_returns_the_same_task", ok and status(pom) == "ready" and not stale)
    run3, lock3 = claim(pom)
    rc, iss3, _ = gate("issue", task=pom, run=run3, lock=lock3)
    check("rework_scope_is_the_tasks_own_paths", rc == 0 and iss3["allowed_paths"] == ["pom.xml"]
          and iss3["cluster"].startswith("rework:") and iss3["budget"]["spent"] == 2)
    edit("pom.xml", "<project>quarkus, reworked</project>\n")
    gate("verdict", "--verdict", "ACCEPTED", "--attempt", "3", task=pom, run=run3)
    git(DEST, "commit", "-qam", "pom rework")
    rc, acc, _ = gate("accept-commit", "--attempt", "3", "--commit", git(DEST, "rev-parse", "HEAD"),
                        "--classes", "build,compile,tests", task=pom, run=run3)
    assert rc == 0 and acc["outcome_accepted"], acc
    assert hook("kanban_request_review", {"reviewer": "reviewer", "summary": "x"}, task=pom, run=run3) == {}
    rrun = review(pom, run3)
    assert hook("kanban_complete", {"summary": "ok"}, task=pom, run=rrun, profile="reviewer", K2_PAVED_ROAD_AUDIT_EXIT="0") == {}
    assert complete(pom, rrun)
    c = conn()
    runs = [r.outcome for r in kb.list_runs(c, pom)]
    fails = kb.get_task(c, pom).consecutive_failures
    c.close()
    check("review_history_on_one_task", runs[-4:] == ["review_requested", "changes_requested", "review_requested", "completed"]
          and fails == 0 and status(pom) == "done", runs=runs)

    # -- 4. crash: native run history kept, the stale run refused ---------------------------
    cfg = tid_of("config:rk:cfg")
    run, lock = claim(cfg)
    gate("issue", task=cfg, run=run, lock=lock)
    c = conn()
    dead = subprocess.Popen(["true"])
    dead.wait()
    kb._set_worker_pid(c, cfg, dead.pid)
    crashed = kb.detect_crashed_workers(c)
    if cfg not in crashed:                               # a host check can decline; the operator reclaim is the same end state
        kb.reclaim_task(c, cfg, reason="qualification crash")
    stale_complete = kb.complete_task(c, cfg, summary="late", expected_run_id=run)
    c.close()
    rc, out, _ = gate("issue", task=cfg, run=run)
    d = hook("write_file", {"path": str(DEST / "src/main/resources/application.properties"), "content": "x"}, task=cfg, run=run)
    check("stale_run_refused_after_crash", status(cfg) == "ready" and not stale_complete and rc == 1
          and out.get("refused") == "RUN_STALE" and "RUN_STALE" in d.get("message", ""))
    accept_and_complete("config:rk:cfg")
    c = conn()
    history = [r.outcome for r in kb.list_runs(c, cfg)]
    c.close()
    check("crash_and_restart_preserve_run_history", history[0] in ("crashed", "reclaimed") and history[-1] == "completed", runs=history)

    # -- 5. a committed candidate, then a crash before its record -------------------------
    mapper = tid_of("source:u:dto-mapper")
    run, lock = claim(mapper)
    rc, iss, _ = gate("issue", task=mapper, run=run, lock=lock)
    edit(iss["allowed_paths"][0], "// mapper migrated\n")
    gate("verdict", "--verdict", "ACCEPTED", "--attempt", "1", task=mapper, run=run)
    git(DEST, "add", "-A")
    git(DEST, "commit", "-qm", "mapper, then the worker died")
    head = git(DEST, "rev-parse", "HEAD")
    drop(owned("source:u:dto-mapper"))
    c = conn()
    kb.reclaim_task(c, mapper, reason="worker died after its commit")
    c.close()
    run2, lock2 = claim(mapper)
    rc, iss2, _ = gate("issue", task=mapper, run=run2, lock=lock2)
    recs = board().records(mapper, "accept-commit")
    check("commit_recovered_not_replayed", rc == 0 and len(recs) == 1 and recs[0]["commit"] == head and recs[0]["recovered"]
          and git(DEST, "rev-parse", "HEAD") == head)
    # finishing THAT acceptance on the re-measured tree (advance.py's resume_recovered)
    sys.path.insert(0, str(GOLDEN / "skills" / "migration" / "fix-until-green" / "scripts"))
    os.environ.update(HERMES_KANBAN_TASK=mapper, HERMES_KANBAN_RUN_ID=str(run2), HERMES_PROFILE="implementer")
    import _outcome_bridge as bridge  # noqa: E402
    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = bridge.resume_recovered(DEST, WL, {})
    for k in ("HERMES_KANBAN_TASK", "HERMES_KANBAN_RUN_ID", "HERMES_PROFILE"):
        os.environ.pop(k, None)
    check("recovered_acceptance_finishes_without_a_new_commit", rc == 0 and "kanban_request_review" in buf.getvalue()
          and git(DEST, "rev-parse", "HEAD") == head)
    assert hook("kanban_request_review", {"reviewer": "reviewer", "summary": "x"}, task=mapper, run=run2) == {}
    rrun = review(mapper, run2)
    assert complete(mapper, rrun)

    # -- 6. a proven owner defect: repair as a native prerequisite, no Operator unblock -----
    from planner.paths import LOOP_ACCEPTED, PARITY_DIR
    callee, caller, sid = "src/main/java/com/acme/shop/dto/ItemDto.java", "src/main/java/com/acme/shop/web/ItemController.java", "items-list"
    err_doc = {"exception": "java.lang.NullPointerException",
               "frames": [{"class": "com.acme.shop.dto.ItemDto", "method": "getName", "file": callee, "line": 12},
                          {"class": "com.acme.shop.web.ItemController", "method": "list", "file": caller, "line": 40}],
               "stack_sha256": "a" * 64}

    def scenario(base, verdict, tree, error):
        d = DEST / (LOOP_ACCEPTED / "parity" if base == "baseline" else PARITY_DIR) / "scenarios"
        d.mkdir(parents=True, exist_ok=True)
        doc = {"scenario": sid, "verdict": verdict, "binding": {"candidate_sha256": tree}}
        if error:
            doc["server_error"] = error
        (d / ("%s.json" % sid)).write_text(json.dumps(doc))

    item = tid_of("source:rk:item")
    run, lock = claim(item)
    rc, iss, _ = gate("issue", task=item, run=run, lock=lock)
    scenario("baseline", "FAIL", iss["baseline_tree"], err_doc)
    edit(caller, "// caller changed\n")
    from planner.canonical import product_tree_sha256
    scenario("live", "FAIL", product_tree_sha256(DEST), err_doc)
    WL["items"].append({"id": "rt:items-list", "source": "parity", "kind": "parity", "category": "mandatory", "scenario": sid,
                        "entry_point": "com.acme.shop.web.ItemController#list():http", "path": ""})
    next(c for c in WL["clusters"] if c["id"] == "c:item")["items"].append("rt:items-list")
    save_wl()
    rc, rec, err = gate("verdict", "--verdict", "REVERTED", "--attempt", "1", "--reason", "runtime scenario failed", task=item, run=run)
    git(DEST, "checkout", "--", caller)
    repair = tid_of("repair:source:u:dto-mapper:for:source:rk:item")
    c = conn()
    parents_item = kb.parent_ids(c, item) if hasattr(kb, "parent_ids") else [r[0] for r in c.execute(
        "SELECT parent_id FROM task_links WHERE child_id=?", (item,))]
    m4 = tid_of("assess:m4:g1")
    parents_m4 = [r[0] for r in c.execute("SELECT parent_id FROM task_links WHERE child_id=?", (m4,))]
    blocked = kb.block_task(c, item, kind="dependency", reason="waiting for the owner repair", expected_run_id=run)
    c.close()
    check("owner_repair_published_as_prerequisite", rc == 0 and rec.get("verdict") == "OWNER_RECOVERY" and rec.get("spent") == 0
          and repair in parents_item and repair in parents_m4 and blocked and status(item) == "todo" and status(repair) == "ready")
    WL["items"] = [i for i in WL["items"] if i["id"] != "rt:items-list"]
    for cl in WL["clusters"]:
        cl["items"] = [i for i in cl["items"] if i != "rt:items-list"]
    save_wl()
    rrun_ = None
    run, lock = claim(repair)
    rc, riss, _ = gate("issue", task=repair, run=run, lock=lock)
    edit(callee, "// ItemDto.getName null-safe\n")
    scenario("live", "PASS", product_tree_sha256(DEST), None)
    gate("verdict", "--verdict", "ACCEPTED", "--attempt", "r1", task=repair, run=run)
    git(DEST, "commit", "-qam", "owner repair")
    rc, racc, _ = gate("accept-commit", "--attempt", "r1", "--commit", git(DEST, "rev-parse", "HEAD"), task=repair, run=run)
    assert rc == 0 and racc["outcome_accepted"], racc
    assert hook("kanban_request_review", {"reviewer": "reviewer", "summary": "x"}, task=repair, run=run) == {}
    rrun_ = review(repair, run)
    assert complete(repair, rrun_)
    check("dependency_resumes_without_operator_unblock", status(item) == "ready")
    run, lock = claim(item)
    rc, iss, _ = gate("issue", task=item, run=run, lock=lock)
    rc2, held, _ = gate("restore-held", task=item, run=run)
    check("held_candidate_restored_on_repaired_baseline", rc == 0 and rc2 == 0 and held["files"] == [caller]
          and "caller changed" in (DEST / caller).read_text())
    scenario("live", "PASS", product_tree_sha256(DEST), None)
    gate("verdict", "--verdict", "ACCEPTED", "--attempt", "2", task=item, run=run)
    git(DEST, "commit", "-qam", "item on the repaired baseline")
    drop(owned("source:rk:item"))
    rc, acc, _ = gate("accept-commit", "--attempt", "2", "--commit", git(DEST, "rev-parse", "HEAD"), task=item, run=run)
    check("dependent_accepted_with_no_budget_spent", rc == 0 and acc["outcome_accepted"]
          and NC.budget_state(board(), RUN, board().plan(RUN), NC._node(board().plan(RUN), "source:rk:item"))["spent"] == 0)
    assert hook("kanban_request_review", {"reviewer": "reviewer", "summary": "x"}, task=item, run=run) == {}
    rrun = review(item, run)
    assert complete(item, rrun)

    # -- 7. the remaining repairs, then M4 = verification ACCEPTED -------------------------
    drop(["inc:unlocatable:jndi"])
    plan = board().plan(RUN)
    for n in topo_order(plan["nodes"]):
        if n["role"] != "repair" or status(tid_of(n["outcome_id"])) == "done":
            continue
        cls = "build,compile,tests" + {"runtime": ",runtime", "behavior": ",runtime,parity"}.get(n["class"], "")
        accept_and_complete(n["outcome_id"], classes=cls, scenarios=",".join(n.get("scenarios") or []))
    m4, prep = tid_of("assess:m4:g1"), tid_of("deliver:prepare:c1")
    check("m4_ready_after_every_repair", status(m4) == "ready" and status(prep) == "todo")
    run, lock = claim(m4)
    gate("issue", task=m4, run=run, lock=lock)
    WL["items"].append({"id": "parity:orders-get", "source": "parity", "kind": "parity", "category": "mandatory",
                        "scenario": "orders-get", "entry_point": "ep:com.acme.shop.web.OrderController#get:http", "path": ""})
    WL["clusters"].append({"id": "c:orders-get", "kind": "parity", "status": "open", "path": "src/main/java/com/acme/shop/web/OrderController.java", "order_key": [5, 0, "orders-get"], "items": ["parity:orders-get"],
                           "write_set": ["src/main/java/com/acme/shop/web/OrderController.java"], "retry_key": "rk:orders-get"})
    save_wl()
    vf = DEST / "evidence" / "verdicts" / "m4-verdict.json"
    vf.parent.mkdir(parents=True, exist_ok=True)
    vf.write_text(json.dumps({"card_id": m4, "verdict": "REFUSE", "parity_scenarios": ["orders-get"]}))
    rc, ass, _ = gate("assessment-record", task=m4, run=run)
    d = hook("kanban_request_review", {"reviewer": "reviewer", "summary": "x"}, task=m4, run=run)
    rc2, rep, _ = gate("m4-repair", task=m4, run=run)
    c = conn()
    blocked = kb.block_task(c, m4, kind="dependency", reason="REFUSE retained; repairs are prerequisites", expected_run_id=run)
    c.close()
    fu = tid_of(rep["added"][0]) if rc2 == 0 and rep.get("added") else ""
    check("red_m4_keeps_m5_waiting", rc == 0 and not ass["accepted"] and "ASSESS_NOT_ACCEPTED" in d.get("message", "") and rc2 == 0
          and fu and blocked and status(m4) == "todo" and status(prep) == "todo", added=rep.get("added"))
    accept_and_complete(rep["added"][0], classes="build,compile,tests,runtime,parity", scenarios="orders-get")
    check("m4_resumes_on_its_repairs", status(m4) == "ready")
    run, lock = claim(m4)
    gate("issue", task=m4, run=run, lock=lock)
    vf.write_text(json.dumps({"card_id": m4, "verdict": "PROVISIONAL_ACCEPT",
                              "qualifications": [{"id": "g1-kill-ratio", "class": "deferred", "satisfied": False}]}))
    rc, ass, _ = gate("assessment-record", task=m4, run=run)
    assert rc == 0 and ass["accepted"], ass
    assert hook("kanban_request_review", {"reviewer": "reviewer", "summary": "x"}, task=m4, run=run) == {}
    rrun = review(m4, run)
    d = hook("kanban_complete", {"summary": "verification accepted"}, task=m4, run=rrun, profile="reviewer", K2_PAVED_ROAD_AUDIT_EXIT="0")
    check("accepted_m4_completes", d == {} and complete(m4, rrun))
    check("accepted_m4_releases_m5", status(prep) == "ready")
    # later candidate drift refuses M5 execution
    edit("pom.xml", "<project>drift after M4</project>\n")
    git(DEST, "commit", "-qam", "drift")
    run, lock = claim(prep)
    rc, out, _ = gate("issue", task=prep, run=run, lock=lock)
    check("candidate_drift_refuses_m5", rc == 1 and out.get("refused") == "ISSUE_STALE_CANDIDATE")
    rc, acct, _ = gate("account")
    check("progress_is_a_derived_view", rc == 0 and acct["control"] == "native-cooperative" and acct["additions"] == 2
          and acct["milestones"]["assess:m4:g1"] == "done", account={k: acct.get(k) for k in ("active", "additions", "accepted_historically")})
    return 0


if __name__ == "__main__":
    t0 = time.time()
    rc = 1
    try:
        rc = main()
    finally:
        receipt = {"schema": "rhoai3.native-control-qualification/v1", "runtime": "pinned Hermes tree 8a3bb406 (ws-080 image)",
                   "worker_python": subprocess.run([WORKER_PY, "--version"], capture_output=True, text=True).stdout.strip(),
                   "scope": "real kanban_db lifecycle + real hermes kanban CLI + golden native_gate.py and K2 hook; no model, "
                            "no dispatcher loop, no cluster",
                   "elapsed_s": round(time.time() - t0, 1), "passed": sum(r["passed"] for r in RESULTS), "checks": RESULTS}
        out = os.environ.get("RHOAI3_RECEIPT")
        if out:
            Path(out).write_text(json.dumps(receipt, indent=2))
        print(json.dumps({k: receipt[k] for k in ("passed", "elapsed_s", "worker_python")}))
    raise SystemExit(rc)
