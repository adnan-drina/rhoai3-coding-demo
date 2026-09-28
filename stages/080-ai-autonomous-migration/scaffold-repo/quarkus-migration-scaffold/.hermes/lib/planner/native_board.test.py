#!/usr/bin/env python3
"""Native cooperative control (outcome-board/v2): publication, same-task
review and rework, the semantic budget, owner recovery on native
prerequisites, M4 = verification ACCEPTED, M5 by read-back, crash recovery and
the K2 hook -- against the architect's bounded acceptance list
(tmp/native-hermes-review-20260927/NATIVE-SOLUTION-REVIEW.md).

SYNTHETIC evidence: an in-memory FakeNative board with the pinned review,
dependency and completion semantics, real git, the real classifier and the
real K2 hook script. Native behaviour on the exact runtime is qualified
separately (stages/080-ai-autonomous-migration/hermes-runtime/tests/
rhoai3_outcome_board/test_native_control.py).

Run: PYTHONDONTWRITEBYTECODE=1 python3 .hermes/lib/planner/native_board.test.py
"""
from __future__ import annotations

import base64
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIB = HERE.parent
KERNEL = LIB.parent / "kernel"
for p in (LIB, KERNEL):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from planner import native_control as NC  # noqa: E402
from planner import native_publish as NP  # noqa: E402
from planner import outcome_graph as OG  # noqa: E402
from planner import outcome_hook as HK  # noqa: E402
from planner import outcome_protocol as P  # noqa: E402
from planner.outcome_checks import VERDICT, WORKLIST, Refusal  # noqa: E402
from planner.outcome_native import FakeNative, NativeError  # noqa: E402

FIX = HERE / "fixtures"
SHOP = json.loads((FIX / "outcome-initial-shop.json").read_text())


def git(root, *a):
    return subprocess.run(["git", "-C", str(root), *a], capture_output=True, text=True, check=True).stdout.strip()


def derive(run_id="n1"):
    return OG.derive_initial_graph(run_id=run_id, worklist=SHOP["worklist"], entry_points=SHOP["entry_points"],
                                   oracles=SHOP["oracles"], references=SHOP["references"], provenance=SHOP["provenance"])


def mirror_layout(root: Path) -> None:
    for name in ("lib", "kernel", "planning", "skills"):
        os.symlink(LIB.parent / name, Path(root) / ".hermes" / name)


class Run:
    """A disposable destination in qualification mode (outcome-board/v2), a
    FakeNative board with the M2 card claimed, and (optionally) the shop plan
    published through native_publish."""

    def __init__(self, publish=True, run_id="n1"):
        self.tmp = Path(tempfile.mkdtemp(prefix="nc-"))
        self.root = self.tmp / "dest"
        self.root.mkdir()
        (self.root / "run-defaults.json").write_text(json.dumps({"schema": "rhoai3.run-defaults/v1", "budget": {},
                                                                 "configuration": {"board_protocol": P.NATIVE}}))
        (self.root / ".hermes").mkdir()
        (self.root / ".hermes" / "pins.json").write_text(json.dumps({"pins": {"planner": {"outcome_board": {"execution": "qualification"}}}}))
        git(self.root, "init", "-q")
        git(self.root, "config", "user.email", "t@t")
        git(self.root, "config", "user.name", "t")
        for c in SHOP["worklist"]["clusters"]:
            for p in c["write_set"]:
                f = self.root / p
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_text("// %s v0\n" % p)
        self.worklist = copy.deepcopy(SHOP["worklist"])
        self.save_worklist()
        shutil.copy(LIB.parents[1] / "decisions.yaml", self.root / "decisions.yaml")
        (self.root / ".gitignore").write_text("verification/\nevidence/\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "baseline")
        self.native = FakeNative(self.tmp)
        self.board = NC.Board(self.native, author="implementer")
        self.m2 = self.native.create(title="M2 PLAN", body="plan", assignee="implementer", parents=[], key="m2-plan",
                                     skills=["paved-road-m2"], workspace="", max_retries=1)
        self.m2_run, _ = self.native.claim(self.m2)
        self.run_id = run_id
        self.plan_file = self.tmp / "plan.json"
        self.plan_file.write_text(json.dumps(derive(run_id)))
        self.out = None
        if publish:
            self.out = self.publish()

    def publish(self):
        return NP.publish_initial(self.root, self.board, m2=self.m2, plan_file=str(self.plan_file))

    def plan(self):
        return self.board.plan(self.run_id)

    def tid(self, oid):
        return self.board.task_of(self.run_id, NC._node(self.plan(), oid))

    def release(self):
        """M2: implementer requests review (read-back green), reviewer completes."""
        d = NC.check_terminator(self.root, self.board, task_id=self.m2, run_id=self.m2_run, kind="request_review",
                                profile="implementer", audit_green=lambda: False)
        assert d["action"] == "allow", d
        self.native.request_review(self.m2)
        run, _ = self.native.claim_review(self.m2)
        d = NC.check_terminator(self.root, self.board, task_id=self.m2, run_id=run, kind="complete", profile="reviewer",
                                audit_green=lambda: True)
        assert d["action"] == "allow", d
        self.native.complete(self.m2)

    def save_worklist(self):
        p = self.root / WORKLIST
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.worklist))

    def drop(self, *ids):
        self.worklist["items"] = [i for i in self.worklist["items"] if i["id"] not in ids]
        for c in self.worklist["clusters"]:
            c["items"] = [i for i in c["items"] if i not in ids]
        self.worklist["clusters"] = [c for c in self.worklist["clusters"] if c["items"]]
        self.save_worklist()

    def edit(self, rel, text):
        f = self.root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text)

    def tree(self):
        return NC._product_tree(self.root)

    def claim(self, oid):
        tid = self.tid(oid)
        run, lock = self.native.claim(tid)
        return tid, run, lock

    def issue(self, oid):
        tid, run, lock = self.claim(oid)
        iss = NC.issue(self.root, self.board, task_id=tid, run_id=run, claim_lock=lock)
        return tid, run, iss

    def accept_on_run(self, tid, run, iss, *, classes=("build", "compile", "tests"), scenarios=(), attempt="1", edit=True,
                      drop=True):
        oid = iss["outcome_id"]
        node = NC._node(self.plan(), oid)
        if edit and iss["allowed_paths"]:
            self.edit(iss["allowed_paths"][0], "// %s accepted by %s attempt %s\n" % (iss["allowed_paths"][0], oid, attempt))
        NC.check_write(self.board, task_id=tid, run_id=run, rel_paths=list(iss["allowed_paths"]))
        NC.record_verdict(self.root, self.board, task_id=tid, run_id=run, verdict="ACCEPTED", candidate=self.tree(), attempt=attempt)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "accept %s %s" % (oid, attempt), "--allow-empty")
        if drop:
            self.drop(*NC.owned(self.plan(), node))
        return NC.accept_commit(self.root, self.board, task_id=tid, run_id=run, attempt=attempt,
                                commit=git(self.root, "rev-parse", "HEAD"),
                                measurement={"classes": list(classes), "scenarios": list(scenarios)})

    def review_and_complete(self, tid, run, *, audit=True):
        d = NC.check_terminator(self.root, self.board, task_id=tid, run_id=run, kind="request_review", profile="implementer",
                                audit_green=lambda: False)
        assert d["action"] == "allow", d
        self.native.request_review(tid)
        rrun, _ = self.native.claim_review(tid)
        d = NC.check_terminator(self.root, self.board, task_id=tid, run_id=rrun, kind="complete", profile="reviewer",
                                audit_green=lambda: audit)
        assert d["action"] == "allow", d
        self.native.complete(tid)
        return rrun

    def accept(self, oid, **kw):
        tid, run, iss = self.issue(oid)
        out = self.accept_on_run(tid, run, iss, **kw)
        assert out["outcome_accepted"], out
        self.review_and_complete(tid, run)
        return tid

    def accept_all_repairs(self):
        for n in OG.topo_order(self.plan()["nodes"]):
            if n["role"] != "repair" or (self.native.task(self.tid(n["outcome_id"])) or {}).get("status") == "done":
                continue
            cls = ("build", "compile", "tests") + {"runtime": ("runtime",), "behavior": ("runtime", "parity")}.get(n["class"], ())
            self.accept(n["outcome_id"], classes=cls, scenarios=n.get("scenarios") or ())

    def assess(self, verdict, *, new_items=(), new_clusters=()):
        tid, run, iss = self.issue("assess:m4:g1")
        for it in new_items:
            self.worklist["items"].append(it)
        for c in new_clusters:
            self.worklist["clusters"].append(c)
        self.save_worklist()
        v = self.root / VERDICT
        v.parent.mkdir(parents=True, exist_ok=True)
        v.write_text(json.dumps({"card_id": tid, "verdict": verdict,
                                 "parity_scenarios": ["items-list", "items-get-1", "items-get-missing", "orders-create"]}))
        out = NC.record_assessment(self.root, self.board, task_id=tid, run_id=run, verdict_doc=json.loads(v.read_text()))
        return tid, run, out

    def close(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


def status(r, tid):
    return (r.native.task(tid) or {}).get("status")


# ===========================================================================
class Selection(unittest.TestCase):
    """outcome-board/v2 selects native cooperative control: no authority
    service, no store, measurement trust still required for enabled."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="nc-sel-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def root(self, protocol, execution=None, trust=None):
        r = self.tmp / ("r%d" % len(list(self.tmp.iterdir())))
        (r / ".hermes").mkdir(parents=True)
        (r / "run-defaults.json").write_text(json.dumps({"schema": "rhoai3.run-defaults/v1", "configuration": {"board_protocol": protocol}}))
        ob = {"execution": execution} if execution else {}
        if trust:
            ob["measurement_trust"] = trust
        (r / ".hermes" / "pins.json").write_text(json.dumps({"pins": {"planner": {"outcome_board": ob} if ob else {}}}))
        return r

    def test_native_selection_and_gate(self):
        r = self.root(P.NATIVE)
        sel = P.select_protocol(r)
        self.assertTrue(sel.outcome and sel.native)
        self.assertEqual(P.execution_gate(r)[0][0], "OUTCOME_EXECUTION_DISABLED")
        self.assertEqual(P.execution_gate(self.root(P.NATIVE, "qualification")), [])
        self.assertEqual(P.authority_endpoint(P.select_protocol(self.root(P.NATIVE, "enabled"))), "")
        self.assertEqual(P.execution_gate(self.root(P.NATIVE, "enabled"))[0][0], "MEASUREMENT_TRUST_UNDECIDED")
        self.assertEqual(P.execution_gate(self.root(P.NATIVE, "enabled", "cooperative-receipts")), [])   # no F1 service
        # v1 is unchanged: enabled still needs the protected service
        self.assertEqual(P.execution_gate(self.root(P.OUTCOME, "enabled", "cooperative-receipts"))[0][0], "AUTHORITY_UNPROTECTED")

    def test_mixed_state(self):
        r = self.root(P.NATIVE, "qualification")
        (r / P.STORE_DIR).mkdir(parents=True)
        (r / P.STORE_FILE).write_bytes(b"")
        self.assertEqual(P.execution_gate(r)[0][0], "PROTOCOL_MIXED")
        r = self.root(P.NATIVE, "qualification")
        (r / "verification" / "loop").mkdir(parents=True)
        (r / "verification" / "loop" / "issued.json").write_text(json.dumps({"idempotency_key": "k4:c:1:abcd"}))
        self.assertEqual(P.execution_gate(r)[0][0], "PROTOCOL_MIXED")

    def test_governed_request_and_selection_must_agree(self):
        from unittest import mock
        from planner import run_control
        r = self.root(None)
        (r / "run-defaults.json").write_text(json.dumps({"schema": "rhoai3.run-defaults/v1", "configuration": {}}))
        cases = [((P.NATIVE, P.NATIVE), []), ((P.NATIVE, P.OUTCOME), ["PROTOCOL_MISMATCH"]),
                 ((P.OUTCOME, P.NATIVE), ["PROTOCOL_MISMATCH"]), ((P.NATIVE, P.SERIAL), ["PROTOCOL_DOWNGRADED"]),
                 ((P.NATIVE, None), ["PROTOCOL_UNBOUND"]), ((None, P.NATIVE), ["PROTOCOL_UNREQUESTED"])]
        for (req, selected), want in cases:
            decl = {"board_protocol_requested": req is not None, "board_protocol": req}
            contract = {"board_protocol": selected} if selected else {}
            if selected in P.OUTCOMES:
                contract["outcome_board"] = {"execution": "disabled"}
            with mock.patch.object(run_control, "in_use", return_value=True), \
                    mock.patch.object(run_control, "declared", return_value=decl), \
                    mock.patch.object(run_control, "contract", return_value=(contract, [])):
                sel = P.select_protocol(r)
            self.assertEqual([c for c, _ in sel.errors], want, (req, selected, sel.errors))
            if not want:
                self.assertTrue(sel.native)


# ===========================================================================
class Publication(unittest.TestCase):
    """Deterministic publication: every known node once, contracts attached,
    M3 held behind the open M2, resumable without duplicates."""

    def tearDown(self):
        for r in getattr(self, "runs", []):
            r.close()

    def mk(self, **kw):
        r = Run(**kw)
        self.runs = getattr(self, "runs", []) + [r]
        return r

    def inventory(self, r):
        plan = r.plan()
        tasks = r.board.run_tasks(r.run_id)
        by_task = {row["id"]: oid for oid, row in tasks.items()}
        inv = {}
        for oid, row in tasks.items():
            t = r.native.task(row["id"])
            inv[oid] = {"parents": sorted(by_task.get(p, "M2" if p == r.m2 else p) for p in t["parents"]),
                        "contract": NC.sha256(r.board.attachment(row["id"], NC.CONTRACT)[0]),
                        "assignee": t["assignee"], "skills": t["skills"]}
        return plan["digest"], inv

    def test_initial_publication(self):
        r = self.mk()
        self.assertEqual(r.out["gaps"], [])
        plan = r.plan()
        self.assertEqual(plan["revision"], 1)
        self.assertEqual(plan["control"], "native-cooperative")
        self.assertEqual(len(r.out["created"]), len(plan["nodes"]))
        for n in plan["nodes"]:
            tid = r.tid(n["outcome_id"])
            self.assertTrue(tid, n["outcome_id"])
            self.assertEqual(r.native.task(tid)["assignee"], "implementer")          # M5 stages too: no grants
            self.assertEqual(status(r, tid), "todo")                                  # held behind the open M2
            c = r.board.contract(tid)
            self.assertEqual((c["outcome_id"], c["control"]), (n["outcome_id"], "native-cooperative"))
        self.assertIn(r.m2, r.native.task(r.tid("build:rk:pom"))["parents"])
        self.assertIn(r.tid("assess:m4:g1"), r.native.task(r.tid("deliver:prepare:c1"))["parents"])
        creates = sum(1 for c in r.native.calls if c[0] == "create")
        again = r.publish()                                                           # replay: nothing new
        self.assertEqual((again["gaps"], sum(1 for c in r.native.calls if c[0] == "create")), ([], creates))
        # the M2 release: implementer review, reviewer completion; M3 roots become ready natively
        r.release()
        self.assertEqual(status(r, r.tid("build:rk:pom")), "ready")
        self.assertEqual(status(r, r.tid("source:rk:item")), "todo")

    def test_m2_cannot_complete_on_partial_publication(self):
        r = self.mk(publish=False)
        with self.assertRaises(Refusal) as cm:
            NC.check_terminator(r.root, r.board, task_id=r.m2, run_id=r.m2_run, kind="request_review", profile="implementer",
                                audit_green=lambda: True)
        self.assertEqual(cm.exception.code, "M2_PUBLICATION_INCOMPLETE")
        r.native.fail_after = {"after-create": 3}                                      # a crash after the 4th create
        with self.assertRaises(NativeError):
            r.publish()
        with self.assertRaises(Refusal) as cm:
            NC.check_terminator(r.root, r.board, task_id=r.m2, run_id=r.m2_run, kind="request_review", profile="implementer",
                                audit_green=lambda: True)
        self.assertEqual(cm.exception.code, "M2_READBACK")
        # nothing published so far can run: every node waits on the open M2
        self.assertTrue(all(status(r, row["id"]) == "todo" for row in r.board.run_tasks(r.run_id).values()))
        out = r.publish()                                                             # resume
        self.assertEqual(out["gaps"], [])
        keys = [t["idempotency_key"] for t in r.native.tasks.values() if NC.parse_key(t["idempotency_key"])]
        self.assertEqual(len(keys), len(set(keys)))                                   # no duplicates
        self.assertEqual(len(keys), len(r.plan()["nodes"]))

    def test_duplicate_mismatch_and_archived_identities_stop(self):
        r = self.mk()
        node = NC._node(r.plan(), "build:rk:pom")
        key = NC.native_key(r.run_id, node)
        # a second live task under the same key (the pinned create races): read-back and publish stop
        r.native.n += 1
        dup = "t_%08x" % (0x9000 + r.native.n)
        r.native.tasks[dup] = dict(r.native.tasks[r.tid("build:rk:pom")], id=dup)
        self.assertTrue(any("2 live tasks" in g for g in NP.readback(r.board, r.plan())))
        with self.assertRaises(Refusal) as cm:
            r.publish()
        self.assertEqual(cm.exception.code, "PUBLICATION_DUPLICATE")
        del r.native.tasks[dup]
        # a key match with other fields is not a reuse
        r.native.tasks[r.tid("build:rk:pom")]["title"] = "something else"
        with self.assertRaises(Refusal) as cm:
            r.publish()
        self.assertEqual(cm.exception.code, "PUBLICATION_MISMATCH")
        r.native.tasks[r.tid("build:rk:pom")]["title"] = node["title"]
        # an archived identity is never re-created
        r.native.archive(r.native.by_key(key)[0]["id"])
        with self.assertRaises(Refusal) as cm:
            r.publish()
        self.assertEqual(cm.exception.code, "PUBLICATION_ARCHIVED")

    def test_equal_inventories_from_frozen_inputs(self):
        a, b = self.mk(), self.mk()
        self.assertEqual(self.inventory(a), self.inventory(b))

    def test_a_different_plan_cannot_replace_revision_one(self):
        r = self.mk()
        other = derive(r.run_id)
        other["nodes"] = other["nodes"][:-1]
        other["digest"] = OG.plan_digest(other)
        r.plan_file.write_text(json.dumps(other))
        with self.assertRaises(Refusal) as cm:
            r.publish()
        self.assertEqual(cm.exception.code, "PUBLICATION_REPLAN")


# ===========================================================================
class SameTaskReview(unittest.TestCase):
    """One native task per outcome: a failed candidate, a reviewer's change
    request and the accepted candidate are runs of the SAME task; nothing is
    progress until the reviewer completes it on the current tree."""

    def setUp(self):
        self.r = Run()
        self.r.release()

    def tearDown(self):
        self.r.close()

    def test_failed_then_changes_requested_then_accepted(self):
        r = self.r
        tid, run, iss = r.issue("build:rk:pom")
        self.assertEqual((iss["cluster"], iss["allowed_paths"]), ("c:pom", ["pom.xml"]))
        # attempt 1: rejected by the measure -> reject record, same task, same run continues
        r.edit("pom.xml", "<project>broken</project>\n")
        out = NC.record_verdict(r.root, r.board, task_id=tid, run_id=run, verdict="REVERTED", candidate=r.tree(), attempt="1",
                                reason="compile red")
        self.assertEqual((out["spent"], out["exhausted"]), (1, False))
        git(r.root, "checkout", "--", "pom.xml")
        # nothing is accepted: review and completion refuse
        for kind, prof in (("request_review", "implementer"), ("complete", "reviewer")):
            with self.assertRaises(Refusal) as cm:
                NC.check_terminator(r.root, r.board, task_id=tid, run_id=run, kind=kind, profile=prof, audit_green=lambda: True)
            self.assertEqual(cm.exception.code, "OUTCOME_NOT_ACCEPTED")
        iss2 = NC.issue(r.root, r.board, task_id=tid, run_id=run)                     # reissue in the same run
        self.assertEqual(iss2["issue_id"], 2)
        acc = r.accept_on_run(tid, run, iss2, attempt="2")
        self.assertTrue(acc["outcome_accepted"], acc)
        # the implementer may not complete its own outcome; it hands it to review
        with self.assertRaises(Refusal) as cm:
            NC.check_terminator(r.root, r.board, task_id=tid, run_id=run, kind="complete", profile="implementer",
                                audit_green=lambda: True)
        self.assertEqual(cm.exception.code, "NATIVE_TERMINATOR")
        r.native.request_review(tid)
        rrun, _ = r.native.claim_review(tid)
        with self.assertRaises(Refusal) as cm:                                          # the audit is red
            NC.check_terminator(r.root, r.board, task_id=tid, run_id=rrun, kind="complete", profile="reviewer",
                                audit_green=lambda: False)
        self.assertEqual(cm.exception.code, "OUTCOME_AUDIT_RED")
        # the reviewer requests changes: another run of the SAME task, one unit of budget
        r.native.request_changes(tid, "the pom keeps a Spring Boot parent")
        self.assertEqual(status(r, tid), "ready")
        self.assertEqual(NC.budget_state(r.board, r.run_id, r.plan(), NC._node(r.plan(), "build:rk:pom"))["spent"], 2)
        run3, lock3 = r.native.claim(tid)
        iss3 = NC.issue(r.root, r.board, task_id=tid, run_id=run3, claim_lock=lock3)
        self.assertEqual(iss3["cluster"], "rework:build:rk:pom:%d" % run3)            # the paths its own commits changed
        self.assertEqual(iss3["allowed_paths"], ["pom.xml"])
        acc = r.accept_on_run(tid, run3, iss3, attempt="3", drop=False)
        self.assertTrue(acc["outcome_accepted"], acc)
        r.review_and_complete(tid, run3)
        self.assertEqual(status(r, tid), "done")
        outcomes = [x.get("outcome") for x in r.native.runs(tid)]
        self.assertEqual(outcomes, ["review_requested", "changes_requested", "review_requested", "completed"])
        self.assertEqual(len([t for t in r.native.tasks.values() if t.get("idempotency_key") == NC.native_key(r.run_id, NC._node(r.plan(), "build:rk:pom"))]), 1)

    def test_stale_wrong_run_and_missing_evidence_refuse(self):
        r = self.r
        tid, run, iss = r.issue("build:rk:pom")
        # a write outside the issued scope, and a write under another run id
        with self.assertRaises(Refusal) as cm:
            NC.check_write(r.board, task_id=tid, run_id=run, rel_paths=["src/main/java/com/acme/shop/web/ItemController.java"])
        self.assertEqual(cm.exception.code, "WRITE_OUTSIDE_ISSUE")
        with self.assertRaises(Refusal) as cm:
            NC.check_write(r.board, task_id=tid, run_id=run + 7, rel_paths=["pom.xml"])
        self.assertEqual(cm.exception.code, "RUN_STALE")
        with self.assertRaises(Refusal) as cm:
            NC.check_write(r.board, task_id=tid, run_id=run, rel_paths=[".hermes/kernel/pre_tool_call.sh"])
        self.assertEqual(cm.exception.code, "STORE_WRITE_REFUSED")
        # accepted, then the tree moves: the acceptance no longer applies (stale candidate)
        acc = r.accept_on_run(tid, run, iss)
        self.assertTrue(acc["outcome_accepted"])
        r.edit("pom.xml", "<project>edited after acceptance</project>\n")
        with self.assertRaises(Refusal) as cm:
            NC.check_terminator(r.root, r.board, task_id=tid, run_id=run, kind="request_review", profile="implementer",
                                audit_green=lambda: True)
        self.assertEqual(cm.exception.code, "OUTCOME_NOT_ACCEPTED")
        self.assertIn("accepted on tree", cm.exception.detail)
        git(r.root, "checkout", "--", "pom.xml")
        # a missing work list is never an empty one
        wl = (r.root / WORKLIST).read_text()
        (r.root / WORKLIST).unlink()
        with self.assertRaises(Refusal) as cm:
            NC.check_terminator(r.root, r.board, task_id=tid, run_id=run, kind="request_review", profile="implementer",
                                audit_green=lambda: True)
        self.assertEqual(cm.exception.code, "OUTCOME_NOT_ACCEPTED")
        (r.root / WORKLIST).write_text(wl)
        # a contract that is not this task's refuses the issue
        other = r.tid("config:rk:cfg")
        att = r.native.attach_[tid][0]
        Path(att["stored_path"]).write_bytes(Path(r.native.attach_[other][0]["stored_path"]).read_bytes())
        with self.assertRaises(Refusal) as cm:
            NC.issue(r.root, r.board, task_id=tid, run_id=run)
        self.assertEqual(cm.exception.code, "CONTRACT_FOREIGN")

    def test_out_of_scope_candidate_is_never_accepted(self):
        r = self.r
        tid, run, iss = r.issue("build:rk:pom")
        r.edit("src/main/java/com/acme/shop/web/ItemController.java", "// not mine\n")
        with self.assertRaises(Refusal) as cm:
            NC.record_verdict(r.root, r.board, task_id=tid, run_id=run, verdict="ACCEPTED", candidate=r.tree(), attempt="1")
        self.assertEqual(cm.exception.code, "ACCEPT_OUT_OF_SCOPE")


# ===========================================================================
class Budget(unittest.TestCase):
    """The semantic repair budget is the family's rejected attempts and change
    requests; quota waits, crashes and dependency waits spend nothing."""

    def test_exhaustion_is_bounded_and_waits_are_free(self):
        r = Run()
        try:
            r.release()
            tid, run, iss = r.issue("build:rk:pom")
            node = NC._node(r.plan(), "build:rk:pom")
            limit = node["budget"]["limit"]
            # a crashed run and a rate-limited requeue: no spend
            r.native.end_run(tid, "ready", "crashed")
            run, _ = r.native.claim(tid)
            r.native.end_run(tid, "ready", "rate_limited")
            run, _ = r.native.claim(tid)
            self.assertEqual(NC.budget_state(r.board, r.run_id, r.plan(), node)["spent"], 0)
            NC.issue(r.root, r.board, task_id=tid, run_id=run)
            for i in range(limit):
                out = NC.record_verdict(r.root, r.board, task_id=tid, run_id=run, verdict="REVERTED",
                                        candidate="%064x" % i, attempt=str(i), reason="red")
            self.assertEqual((out["spent"], out["exhausted"]), (limit, True))
            # the replayed verdict of the same attempt spends nothing more
            again = NC.record_verdict(r.root, r.board, task_id=tid, run_id=run, verdict="REVERTED", candidate="%064x" % 0,
                                      attempt="0", reason="red")
            self.assertEqual(again["spent"], limit)
            with self.assertRaises(Refusal) as cm:
                NC.issue(r.root, r.board, task_id=tid, run_id=run)
            self.assertEqual(cm.exception.code, "ISSUE_BUDGET_EXHAUSTED")
            self.assertIn("kanban_block kind=needs_input", cm.exception.detail)
        finally:
            r.close()


# ===========================================================================
class OwnerRecovery(unittest.TestCase):
    """A dependency repair on native prerequisites: the dependent's runtime
    failure, proven on the baseline and thrown in an accepted owner's file,
    holds the candidate (attachment, no attempt spent), publishes ONE owner
    repair linked repair -> dependent (never the reverse), and the dependent
    resumes by native promotion; the repair is accepted only when the failing
    scenario passes on its tree."""

    OWNER, DEP, SID = "source:u:dto-mapper", "source:rk:item", "items-list"
    CALLEE = "src/main/java/com/acme/shop/dto/ItemDto.java"
    CALLER = "src/main/java/com/acme/shop/web/ItemController.java"
    ERROR = {"exception": "java.lang.NullPointerException",
             "frames": [{"class": "com.acme.shop.dto.ItemDto", "method": "getName", "file": CALLEE, "line": 12},
                        {"class": "com.acme.shop.web.ItemController", "method": "list", "file": CALLER, "line": 40}],
             "stack_sha256": "a" * 64}

    def setUp(self):
        self.r = Run()
        self.r.release()
        for oid in ("build:rk:pom", "config:rk:cfg", self.OWNER):
            self.r.accept(oid)

    def tearDown(self):
        self.r.close()

    def record(self, base, verdict, tree, error):
        from planner.paths import LOOP_ACCEPTED, PARITY_DIR
        d = self.r.root / (LOOP_ACCEPTED / "parity" if base == "baseline" else PARITY_DIR) / "scenarios"
        d.mkdir(parents=True, exist_ok=True)
        doc = {"scenario": self.SID, "verdict": verdict, "binding": {"candidate_sha256": tree}}
        if error:
            doc["server_error"] = error
        (d / ("%s.json" % self.SID)).write_text(json.dumps(doc))

    def runtime_item(self, present):
        wl = self.r.worklist
        wl["items"] = [i for i in wl["items"] if i["id"] != "rt:items-list"]
        for c in wl["clusters"]:
            c["items"] = [i for i in c["items"] if i != "rt:items-list"]
        if present:
            wl["items"].append({"id": "rt:items-list", "source": "parity", "kind": "parity", "category": "mandatory",
                                "scenario": self.SID, "entry_point": "com.acme.shop.web.ItemController#list():http", "path": ""})
            next(c for c in wl["clusters"] if c["id"] == "c:item")["items"].append("rt:items-list")
        self.r.save_worklist()

    def fail_dependent(self, baseline_verdict, attempt="1"):
        r = self.r
        tid, run, iss = r.issue(self.DEP)
        if baseline_verdict:
            self.record("baseline", baseline_verdict, iss["baseline_tree"], self.ERROR if baseline_verdict == "FAIL" else None)
        r.edit(self.CALLER, "// caller changed, attempt %s\n" % attempt)
        cand = r.tree()
        self.record("live", "FAIL", cand, self.ERROR)
        self.runtime_item(True)
        out = NC.record_verdict(r.root, r.board, task_id=tid, run_id=run, verdict="REVERTED", candidate=cand, attempt=attempt,
                                reason="runtime scenario %s failed" % self.SID)
        git(r.root, "checkout", "--", self.CALLER)
        return tid, run, iss, out

    def test_repair_as_prerequisite_resumes_without_operator(self):
        r = self.r
        m4 = r.tid("assess:m4:g1")
        tid, run, iss, out = self.fail_dependent("FAIL")
        self.assertEqual((out["verdict"], out["owner"], out["spent"]), ("OWNER_RECOVERY", self.OWNER, 0), out)
        self.assertEqual(out["held_paths"], [self.CALLER])
        fid = NC.owner_repair_id(self.OWNER, self.DEP)
        plan = r.plan()
        self.assertEqual(plan["revision"], 2)
        ftid = r.tid(fid)
        self.assertTrue(ftid)
        self.assertIn(ftid, r.native.task(tid)["parents"])                            # repair -> dependent
        self.assertIn(ftid, r.native.task(m4)["parents"])                             # repair -> open M4
        self.assertNotIn(tid, r.native.task(ftid)["parents"])                          # never the reverse
        self.assertEqual(NC._node(plan, fid)["budget"], NC._node(plan, self.OWNER)["budget"])
        self.assertEqual(NP.readback(r.board, plan), [])
        # completion names the terminator; the dependency block is allowed and lands the card in todo
        with self.assertRaises(Refusal) as cm:
            NC.check_terminator(r.root, r.board, task_id=tid, run_id=run, kind="request_review", profile="implementer",
                                audit_green=lambda: True)
        self.assertEqual(cm.exception.code, "OWNER_REPAIR_PENDING")
        self.assertEqual(NC.check_terminator(r.root, r.board, task_id=tid, run_id=run, kind="block", profile="implementer",
                                             audit_green=lambda: True)["action"], "allow")
        r.native.block_dependency(tid)
        self.assertEqual(status(r, tid), "todo")
        # the repair: accepted only when the failing scenario PASSES on its own tree
        rtid, rrun, riss = r.issue(fid)
        self.assertEqual(riss["cluster"], "planned:%s:1" % fid)
        self.assertIn(self.CALLEE, riss["allowed_paths"])
        self.runtime_item(False)
        acc = r.accept_on_run(rtid, rrun, riss, attempt="r1", drop=False)
        self.assertFalse(acc["outcome_accepted"])
        self.assertTrue(acc["repair_evidence_gaps"])
        riss2 = NC.issue(r.root, r.board, task_id=rtid, run_id=rrun)
        r.edit(self.CALLEE, "// ItemDto.getName null-safe, measured\n")
        self.record("live", "PASS", r.tree(), None)
        acc = r.accept_on_run(rtid, rrun, riss2, attempt="r2", edit=False, drop=False)
        self.assertTrue(acc["outcome_accepted"], acc)
        r.review_and_complete(rtid, rrun)
        # native promotion: the dependent is ready again, no Operator unblock
        self.assertEqual(status(r, tid), "ready")
        run3, lock3 = r.native.claim(tid)
        iss3 = NC.issue(r.root, r.board, task_id=tid, run_id=run3, claim_lock=lock3)
        self.assertNotEqual(iss3["baseline_commit"], iss["baseline_commit"])
        self.assertTrue(iss3["held_candidate"])
        held = NC.restore_held(r.root, r.board, task_id=tid, run_id=run3)
        for rel, b64 in held["files"].items():
            (r.root / rel).write_bytes(base64.b64decode(b64))
        self.assertIn("attempt 1", (r.root / self.CALLER).read_text())
        self.record("live", "PASS", r.tree(), None)
        acc = r.accept_on_run(tid, run3, iss3, attempt="2", edit=False)
        self.assertTrue(acc["outcome_accepted"], acc)
        dep_node = NC._node(r.plan(), self.DEP)
        self.assertEqual(NC.budget_state(r.board, r.run_id, r.plan(), dep_node)["spent"], 0)   # no budget spent or reset
        r.review_and_complete(tid, run3)
        self.assertEqual(len([t for t in r.native.tasks.values()
                              if t.get("idempotency_key") == NC.native_key(r.run_id, NC._node(r.plan(), fid))]), 1)

    def test_interrupted_repair_publication_resumes_once(self):
        r = self.r
        r.native.fail_after = {"after-create": 0}                                     # crash right after the repair's create
        with self.assertRaises(NativeError):
            self.fail_dependent("FAIL")
        tid = r.tid(self.DEP)
        git(r.root, "checkout", "--", self.CALLER)
        r.native.end_run(tid, "ready", "crashed")
        run2, lock2 = r.native.claim(tid)
        with self.assertRaises(Refusal) as cm:                                          # the next run resumes the publication
            NC.issue(r.root, r.board, task_id=tid, run_id=run2, claim_lock=lock2)
        self.assertEqual(cm.exception.code, "OWNER_REPAIR_PENDING")
        fid = NC.owner_repair_id(self.OWNER, self.DEP)
        rows = r.native.by_key(NC.native_key(r.run_id, NC._node(r.plan(), fid)))
        self.assertEqual(len(rows), 1)
        self.assertIn(rows[0]["id"], r.native.task(tid)["parents"])
        self.assertEqual(NP.readback(r.board, r.plan()), [])

    def test_regression_and_ambiguity_transfer_nothing(self):
        tid, run, iss, out = self.fail_dependent("PASS")
        self.assertEqual((out["verdict"], out["spent"]), ("REVERTED", 1))
        self.assertEqual(self.r.plan()["revision"], 1)
        r2 = Run()
        try:
            r2.release()
            for oid in ("build:rk:pom", "config:rk:cfg", self.OWNER):
                r2.accept(oid)
            self.r, keep = r2, self.r
            tid, run, iss, out = self.fail_dependent(None)
            self.assertEqual((out["verdict"], out["spent"]), ("REVERTED", 1))
            self.assertEqual([c["cls"] for c in r2.board.records(tid, "cause-report")], ["ambiguous"])
            self.assertEqual(r2.plan()["revision"], 1)
        finally:
            self.r = keep
            r2.close()


# ===========================================================================
class M4VerificationAccepted(unittest.TestCase):
    """M4 means verification ACCEPTED: a red M4 keeps M5 waiting, its repairs
    become its prerequisites, the same task resumes, and only an accepted,
    candidate-bound M4 releases delivery; later drift refuses M5."""

    def setUp(self):
        self.r = Run()
        self.r.release()
        self.r.drop("inc:unlocatable:jndi")
        self.r.accept_all_repairs()

    def tearDown(self):
        self.r.close()

    def test_red_m4_waits_on_repairs_then_releases_delivery(self):
        r = self.r
        m4, prep = r.tid("assess:m4:g1"), r.tid("deliver:prepare:c1")
        self.assertEqual(status(r, m4), "ready")
        new = {"id": "parity:orders-get", "source": "parity", "kind": "parity", "category": "mandatory",
               "scenario": "orders-get", "entry_point": "ep:com.acme.shop.web.OrderController#get:http", "path": ""}
        cl = {"id": "c:orders-get", "kind": "parity", "status": "open", "path": "src/main/java/com/acme/shop/web/OrderController.java", "order_key": [5, 0, "orders-get"], "items": ["parity:orders-get"],
              "write_set": ["src/main/java/com/acme/shop/web/OrderController.java"], "retry_key": "rk:orders-get"}
        tid, run, out = r.assess("REFUSE", new_items=[new], new_clusters=[cl])
        self.assertFalse(out["accepted"])
        with self.assertRaises(Refusal) as cm:                                          # red M4 is never completed
            NC.check_terminator(r.root, r.board, task_id=m4, run_id=run, kind="request_review", profile="implementer",
                                audit_green=lambda: True)
        self.assertEqual(cm.exception.code, "ASSESS_NOT_ACCEPTED")
        rep = NC.m4_repair(r.root, r.board, task_id=m4, run_id=run)
        self.assertEqual(rep["added"], ["followup:behavior:http:com.acme.shop.web.OrderController:g2"])
        again = NC.m4_repair(r.root, r.board, task_id=m4, run_id=run)                 # replay: nothing twice
        self.assertTrue(again["replayed"])
        fid = rep["added"][0]
        ftid = r.tid(fid)
        self.assertIn(ftid, r.native.task(m4)["parents"])                              # repair -> M4
        self.assertNotIn(m4, r.native.task(ftid)["parents"])
        self.assertEqual(NC._node(r.plan(), fid)["budget"],
                         NC._node(r.plan(), "behavior:http:com.acme.shop.web.OrderController")["budget"])
        r.native.block_dependency(m4)
        self.assertEqual((status(r, m4), status(r, prep)), ("todo", "todo"))           # M5 keeps waiting
        # the repair, then M4 resumes natively on the repaired candidate
        r.accept(fid, classes=("build", "compile", "tests", "runtime", "parity"), scenarios=("orders-get",))
        self.assertEqual(status(r, m4), "ready")
        tid, run2, out = r.assess("PROVISIONAL_ACCEPT")
        self.assertTrue(out["accepted"])
        r.review_and_complete(m4, run2)
        self.assertEqual(status(r, prep), "ready")                                     # accepted M4 releases M5
        self.assertEqual(NC.m4_closure(r.root, r.native)["verdict"], "PROVISIONAL_ACCEPT")
        run5, lock5 = r.native.claim(prep)
        NC.issue(r.root, r.board, task_id=prep, run_id=run5, claim_lock=lock5)
        # later candidate drift refuses M5 execution
        r.native.end_run(prep, "ready", "crashed")
        r.edit("pom.xml", "<project>drift after M4</project>\n")
        git(r.root, "commit", "-qam", "drift")
        run6, lock6 = r.native.claim(prep)
        with self.assertRaises(Refusal) as cm:
            NC.issue(r.root, r.board, task_id=prep, run_id=run6, claim_lock=lock6)
        self.assertEqual(cm.exception.code, "ISSUE_STALE_CANDIDATE")
        acc = NC.progress_account(r.root, r.board, r.run_id)
        self.assertEqual(acc["additions"], 1)
        self.assertEqual(acc["awaiting_revalidation"], acc["accepted_historically"])   # drift: proof no longer applies

    def test_assessment_bound(self):
        r = self.r
        m4 = r.tid("assess:m4:g1")
        for i in range(NC.MAX_ASSESSMENT_GENERATIONS):
            tid, run, out = r.assess("REFUSE", new_items=[{"id": "cfg:%d" % i, "source": "mta", "kind": "incident",
                                                           "category": "mandatory", "path": "src/main/resources/application.properties"}],
                                     new_clusters=[{"id": "c:cfg%d" % i, "kind": "config", "status": "open", "path": "src/main/resources/application.properties", "order_key": [1, 0, "cfg"], "items": ["cfg:%d" % i],
                                                    "write_set": ["src/main/resources/application.properties"], "retry_key": "rk:cfg%d" % i}])
            if i + 1 >= NC.MAX_ASSESSMENT_GENERATIONS:
                with self.assertRaises(Refusal) as cm:
                    NC.m4_repair(r.root, r.board, task_id=m4, run_id=run)
                self.assertEqual(cm.exception.code, "ASSESSMENT_BOUND")
                break
            rep = NC.m4_repair(r.root, r.board, task_id=m4, run_id=run)
            r.native.block_dependency(m4)
            for oid in rep["added"]:
                r.accept(oid)
            r.drop("cfg:%d" % i)
            self.assertEqual(status(r, m4), "ready")


# ===========================================================================
class CrashRecovery(unittest.TestCase):
    """A committed candidate followed by a crash before its record recovers
    without replaying a product mutation; stale completion is native."""

    def test_commit_then_crash_before_record(self):
        r = Run()
        try:
            r.release()
            tid, run, iss = r.issue("build:rk:pom")
            r.edit("pom.xml", "<project>quarkus</project>\n")
            cand = r.tree()
            NC.record_verdict(r.root, r.board, task_id=tid, run_id=run, verdict="ACCEPTED", candidate=cand, attempt="1")
            git(r.root, "commit", "-qam", "accepted, then the worker died")
            head = git(r.root, "rev-parse", "HEAD")
            r.drop(*NC.owned(r.plan(), NC._node(r.plan(), "build:rk:pom")))
            r.native.end_run(tid, "ready", "crashed")                                  # no accept-commit record
            run2, lock2 = r.native.claim(tid)
            iss2 = NC.issue(r.root, r.board, task_id=tid, run_id=run2, claim_lock=lock2)
            self.assertEqual(iss2["baseline_commit"], head)
            rec = r.board.records(tid, "accept-commit")
            self.assertEqual((len(rec), rec[0]["commit"], rec[0]["recovered"]), (1, head, True))
            out = NC.evaluate_recovered(r.root, r.board, task_id=tid, run_id=run2,
                                        measurement={"classes": ["build", "compile", "tests"], "scenarios": []})
            self.assertTrue(out["outcome_accepted"], out)
            self.assertEqual(git(r.root, "rev-parse", "HEAD"), head)                   # nothing committed again
            self.assertIsNone(NC.evaluate_recovered(r.root, r.board, task_id=tid, run_id=run2,
                                                    measurement={"classes": ["build"], "scenarios": []}))
            r.review_and_complete(tid, run2)
        finally:
            r.close()

    def test_uncommitted_acceptance_aborts_to_a_retained_candidate(self):
        r = Run()
        try:
            r.release()
            tid, run, iss = r.issue("build:rk:pom")
            r.edit("pom.xml", "<project>quarkus</project>\n")
            NC.record_verdict(r.root, r.board, task_id=tid, run_id=run, verdict="ACCEPTED", candidate=r.tree(), attempt="1")
            r.native.end_run(tid, "ready", "crashed")                                  # died before the commit
            run2, lock2 = r.native.claim(tid)
            iss2 = NC.issue(r.root, r.board, task_id=tid, run_id=run2, claim_lock=lock2)
            self.assertTrue(iss2["retained_candidate"])
            self.assertEqual([x["key"].split(":")[0] for x in r.board.records(tid) if x["kind"] == "accept-aborted"], ["accept-aborted"])
        finally:
            r.close()


# ===========================================================================
class Delivery(unittest.TestCase):
    """An uncertain push reads the remote back and reuses what landed."""

    def test_push_recovered_by_read_back(self):
        r = Run()
        try:
            remote = r.tmp / "remote.git"
            subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
            git(r.root, "remote", "add", "origin", str(remote))
            r.release()
            r.drop("inc:unlocatable:jndi")
            r.accept_all_repairs()
            tid, run, out = r.assess("PROVISIONAL_ACCEPT")
            m4 = r.tid("assess:m4:g1")
            r.review_and_complete(m4, run)
            prep, push = r.tid("deliver:prepare:c1"), r.tid("deliver:push:c1")
            head = git(r.root, "rev-parse", "HEAD")
            d = r.root / "verification" / "delivery"
            d.mkdir(parents=True, exist_ok=True)
            (d / "candidate.json").write_text(json.dumps({"candidate_sha": head, "ok": True, "pipeline_eligible": True, "m4_card": m4}))
            (d / "eligibility.json").write_text(json.dumps({"candidate_sha": head, "pipeline_eligible": True}))
            run5, lock5 = r.native.claim(prep)
            NC.issue(r.root, r.board, task_id=prep, run_id=run5, claim_lock=lock5)
            r.review_and_complete(prep, run5)
            self.assertEqual(status(r, push), "ready")
            prun, plock = r.native.claim(push)
            NC.issue(r.root, r.board, task_id=push, run_id=prun, claim_lock=plock)
            # a crashed earlier run already pushed: the read-back records it, nothing is pushed again
            git(r.root, "push", "-q", "origin", "%s:refs/heads/main" % head)
            calls = []
            out = NC.push(r.root, r.board, task_id=push, run_id=prun, pusher=lambda argv: calls.append(argv))
            self.assertEqual((out["state"], out["already"], calls), ("landed", True, []))
            self.assertEqual(NC.push(r.root, r.board, task_id=push, run_id=prun)["already"], True)
            ok, facts, reasons = NC.stage_evidence(r.root, r.board, r.run_id, r.plan(), "push")
            self.assertFalse(any(x.startswith("PUSH_NOT_LANDED") for x in reasons), reasons)
        finally:
            r.close()


# ===========================================================================
class K2Hook(unittest.TestCase):
    """The real kernel/pre_tool_call.sh as a separate process on a v2 run."""

    HOOK = KERNEL / "pre_tool_call.sh"

    def setUp(self):
        self.r = Run()
        mirror_layout(self.r.root)
        self.r.release()
        self.tid, self.run, self.iss = self.r.issue("build:rk:pom")
        self.r.native.sync()

    def tearDown(self):
        self.r.close()

    def hook(self, tool, inp, **env):
        e = dict(os.environ, HERMES_WRITE_SAFE_ROOT=str(self.r.root), K2_ALLOW_ROOT=str(self.r.root),
                 HERMES_PROFILE="implementer", HERMES_KANBAN_TASK=self.tid, HERMES_KANBAN_RUN_ID=str(self.run),
                 HERMES_KANBAN_DB=self.r.native.db_path, HERMES_HOME=str(self.r.tmp / "home"), PYTHONDONTWRITEBYTECODE="1")
        e.update(env)
        payload = {"hook_event_name": "pre_tool_call", "tool_name": tool, "tool_input": inp, "cwd": str(self.r.root)}
        p = subprocess.run(["bash", str(self.HOOK)], input=json.dumps(payload), capture_output=True, text=True, env=e,
                           cwd=str(self.r.root))
        return json.loads(p.stdout or "{}")

    def test_decisions(self):
        root = self.r.root
        self.assertEqual(self.hook("write_file", {"path": str(root / "pom.xml"), "content": "x"}), {})
        out = self.hook("write_file", {"path": str(root / "src/main/java/com/acme/shop/web/ItemController.java"), "content": "x"})
        self.assertIn("WRITE_OUTSIDE_ISSUE", out.get("message", ""))
        out = self.hook("write_file", {"path": str(root / "src/main/java/com/acme/shop/web/ItemController.java"), "content": "x"},
                        K2_FILES_WRITABLE="src/main/java/com/acme/shop/web/ItemController.java", K2_CARD_PHASE="M3")
        self.assertIn("WRITE_OUTSIDE_ISSUE", out.get("message", ""))
        out = self.hook("kanban_complete", {"summary": "done"})
        self.assertIn("NATIVE_TERMINATOR", out.get("message", ""))
        out = self.hook("kanban_request_review", {"reviewer": "reviewer", "summary": "x"})
        self.assertIn("OUTCOME_NOT_ACCEPTED", out.get("message", ""))
        self.assertEqual(self.hook("kanban_block", {"reason": "x", "kind": "dependency"}), {})
        out = self.hook("write_file", {"path": str(root / "pom.xml"), "content": "x"}, HERMES_KANBAN_RUN_ID=str(self.run + 99))
        self.assertIn("RUN_ENDED", out.get("message", ""))           # a run that is not the task's current run
        # forging a domain record or a reserved attachment is refused by name
        out = self.hook("kanban_comment", {"body": '[native-control] {"kind":"accept-commit","key":"x"}'})
        self.assertIn("native_gate.py", out.get("message", ""))
        out = self.hook("terminal", {"command": "hermes kanban attach %s /tmp/x.json --name contract.json" % self.tid})
        self.assertIn("native-control artifacts", out.get("message", ""))
        out = self.hook("kanban_create", {"title": "x"})
        self.assertIn("graph mutation", out.get("message", ""))
        # an M1-style card (neither M2 nor a v2 node) keeps the serial rules: the branch answers None
        m1 = self.r.native.create(title="M1 ANALYZE", body="m1", assignee="implementer", parents=[], key="m1-analyze",
                                  skills=["paved-road-m1"], workspace="", max_retries=1)
        self.r.native.sync()
        saved = os.environ.get("HERMES_KANBAN_DB")
        os.environ["HERMES_KANBAN_DB"] = self.r.native.db_path
        try:
            self.assertIsNone(HK.terminator(str(root), kind="complete", profile="reviewer",
                                            env={"HERMES_KANBAN_TASK": m1, "HERMES_KANBAN_RUN_ID": "1"}, audit_green=lambda: True))
        finally:
            if saved is None:
                os.environ.pop("HERMES_KANBAN_DB", None)
            else:
                os.environ["HERMES_KANBAN_DB"] = saved
        (root / ".hermes" / "pins.json").write_text(json.dumps({"pins": {"planner": {"outcome_board": {"execution": "disabled"}}}}))
        out = self.hook("write_file", {"path": str(root / "pom.xml"), "content": "x"})
        self.assertIn("OUTCOME_EXECUTION_DISABLED", out.get("message", ""))


# ===========================================================================
class AdvanceBridge(unittest.TestCase):
    """advance.py's calls on a v2 node: same card, board records, review handoff."""

    def test_bridge_records_and_hands_to_review(self):
        import contextlib
        import io
        sys.path.insert(0, str(LIB.parent / "skills" / "migration" / "fix-until-green" / "scripts"))
        import _outcome_bridge as B
        r = Run()
        mirror_layout(r.root)
        saved = {k: os.environ.get(k) for k in ("HERMES_KANBAN_TASK", "HERMES_KANBAN_RUN_ID", "HERMES_KANBAN_DB")}
        try:
            r.release()
            tid, run, iss = r.issue("build:rk:pom")
            r.native.sync()
            os.environ.update(HERMES_KANBAN_TASK=tid, HERMES_KANBAN_RUN_ID=str(run), HERMES_KANBAN_DB=r.native.db_path)

            # the bridge's board: the same fake (the K2Hook case covers the KanbanNative read path)
            orig = NC.board_for
            NC.board_for = lambda root, native=None: NC.Board(r.native, author="implementer")
            try:
                self.assertTrue(B.active(r.root))
                out, err = io.StringIO(), io.StringIO()
                r.edit("pom.xml", "<project>broken</project>\n")
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    self.assertEqual(B.record(r.root, "REVERTED", r.tree(), "compile red"), 0)
                git(r.root, "checkout", "--", "pom.xml")
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    self.assertEqual(B.reissue(r.root), 0)
                self.assertIn("CONTINUE THIS CARD", out.getvalue())
                self.assertTrue((r.root / "verification" / "loop" / "issued.json").is_file())
                r.edit("pom.xml", "<project>quarkus</project>\n")
                cand = r.tree()
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    self.assertEqual(B.record(r.root, "ACCEPTED", cand), 0)
                git(r.root, "commit", "-qam", "accepted")
                r.drop(*NC.owned(r.plan(), NC._node(r.plan(), "build:rk:pom")))
                wl = json.loads((r.root / WORKLIST).read_text())
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    self.assertEqual(B.after_accept(r.root, git(r.root, "rev-parse", "HEAD"), cand, wl, {}), 0)
                self.assertIn("kanban_request_review reviewer=reviewer", out.getvalue())
                self.assertEqual([x["kind"] for x in r.board.records(tid)],
                                 ["issue", "reject", "issue", "accept-begin", "accept-commit"])
            finally:
                NC.board_for = orig
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
            r.close()


if __name__ == "__main__":
    unittest.main(verbosity=1)
