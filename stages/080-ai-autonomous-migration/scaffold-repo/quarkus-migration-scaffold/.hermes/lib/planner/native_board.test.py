#!/usr/bin/env python3
"""Native cooperative control (outcome-board/v2): publication, same-task
review and rework, the semantic budget, owner recovery on native
prerequisites, M4 = verification ACCEPTED, M5 by read-back, crash recovery and
the K2 hook -- against the architect's bounded acceptance list
(tmp/native-hermes-review-20260927/NATIVE-SOLUTION-REVIEW.md).

SYNTHETIC evidence: an in-memory FakeNative board with the pinned review,
dependency and completion semantics, real git, the real classifier and the
real K2 hook script. Historical native behaviour was qualified separately
on the exact runtime; the retired test_native_control.py suite is in Git history.

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

    def __init__(self, publish=True, run_id="n1", pilot=False, structure=None):
        self.tmp = Path(tempfile.mkdtemp(prefix="nc-"))
        self.root = self.tmp / "dest"
        self.root.mkdir()
        conf = {"board_protocol": P.NATIVE}
        if pilot:
            conf["parallel_m3"] = "m3-pair-pilot/v1"   # pinned in the initial commit below
        (self.root / "run-defaults.json").write_text(json.dumps({"schema": "rhoai3.run-defaults/v1", "budget": {},
                                                                 "configuration": conf}))
        if structure is not None:
            b = self.root / "evidence" / "planning" / "evidence-bundle.json"
            b.parent.mkdir(parents=True, exist_ok=True)
            b.write_text(json.dumps({"structure": structure}))
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
        (self.root / ".gitignore").write_text("verification/\nevidence/\n.worktrees/\n")
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

    def verified(self, tests="passed"):
        """The verification of the CURRENT tree as run-verify records it: the
        worklist and run.json bound to it, the suite executed (``tests``:
        passed | failed | None for a verification that ran no tests)."""
        from planner.paths import VERIFY_RUN
        tree = self.tree()
        m = dict(self.worklist.get("measure") or {}, compile_errors=0, failing_tests=1 if tests == "failed" else 0)
        self.worklist.update(candidate_sha256=tree, measure=m,
                             sources=dict(self.worklist.get("sources") or {}, surefire={"reports": 1} if tests else None))
        self.save_worklist()
        run = {"candidate_sha256": tree, "mode": "acceptance", "classpath": {"ran": True, "rc": 0},
               "diagnostics": {"ran": True, "rc": 0}, "tests": {"ran": bool(tests), "rc": 0 if tests == "passed" else 1}}
        (self.root / VERIFY_RUN).parent.mkdir(parents=True, exist_ok=True)
        (self.root / VERIFY_RUN).write_text(json.dumps(run))

    def assess(self, verdict, *, new_items=(), new_clusters=(), tests="passed"):
        tid, run, iss = self.issue("assess:m4:g1")
        for it in new_items:
            self.worklist["items"].append(it)
        for c in new_clusters:
            self.worklist["clusters"].append(c)
        self.save_worklist()
        self.verified(tests)   # v24: M4 owns the full suite (measure:tests); the positive path carries its evidence
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

    def test_the_m2_handoff_names_its_direct_children_apart_from_chained_cards(self):
        """v26 M2 review: the handoff said every published card was a child of M2; Hermes's completion guard
        treats only cards linked to M2 itself as its children."""
        r = self.mk()
        out = NC.handoff(r.root, r.board, task_id=r.m2)
        md = out["metadata"]
        linked = sorted(tid for tid, t in ((row["id"], r.native.task(row["id"])) for row in r.board.run_tasks(r.run_id).values())
                        if r.m2 in (t.get("parents") or []))
        self.assertEqual(sorted(md["direct_children"]), linked)
        self.assertEqual(sorted(md["direct_children"] + md["chained_descendants"]), sorted(md["created_cards"]))
        self.assertTrue(md["chained_descendants"], "the fixture chains M4/M5 below the repair outcomes")
        self.assertIn("%d are this card's direct children, %d are chained below them"
                      % (len(md["direct_children"]), len(md["chained_descendants"])), out["summary"])
        # every published card body states what it is judged by; a source outcome does not promise tests
        for row in r.board.run_tasks(r.run_id).values():
            body = str(r.native.task(row["id"]).get("body") or "")
            self.assertNotIn("pass its tests", body)

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

    def test_a_procedural_change_request_on_a_moved_tree_is_judged_again_without_a_charge(self):
        """v24 run t_e2932aa0: the reviewer requested changes for a missing skill_view line on an accepted
        outcome; other cards then moved the tree. The unchanged rework is judged again ON THE CURRENT TREE
        (accept-evaluated), spends nothing, and only then may be handed to review."""
        r = self.r
        tid, run, iss = r.issue("build:rk:pom")
        self.assertTrue(r.accept_on_run(tid, run, iss, attempt="1")["outcome_accepted"])
        r.native.request_review(tid)
        r.native.claim_review(tid)
        r.native.request_changes(tid, "procedural: the skill_view line is missing from the run log")
        node = NC._node(r.plan(), "build:rk:pom")
        spent = NC.budget_state(r.board, r.run_id, r.plan(), node)["spent"]
        r.edit("src/main/java/other/Moved.java", "// another card's accepted work\n")      # the tree moves
        git(r.root, "add", "-A")
        git(r.root, "commit", "-qm", "another card")
        run2, lock2 = r.native.claim(tid)
        iss2 = NC.issue(r.root, r.board, task_id=tid, run_id=run2, claim_lock=lock2)
        self.assertTrue(iss2["cluster"].startswith("rework:"))
        self.assertFalse(NC.handoff(r.root, r.board, task_id=tid)["metadata"]["accepted_on_current_tree"])
        with self.assertRaises(Refusal):
            NC.check_terminator(r.root, r.board, task_id=tid, run_id=run2, kind="request_review", profile="implementer",
                                audit_green=lambda: False)
        out = NC.evaluate_unchanged_rework(r.root, r.board, task_id=tid, run_id=run2,
                                           measurement={"classes": ["build", "compile", "tests"], "scenarios": []})
        self.assertTrue(out and out["outcome_accepted"], out)
        self.assertTrue(NC.handoff(r.root, r.board, task_id=tid)["metadata"]["accepted_on_current_tree"])
        self.assertEqual(NC.budget_state(r.board, r.run_id, r.plan(), node)["spent"], spent)          # nothing spent
        d = NC.check_terminator(r.root, r.board, task_id=tid, run_id=run2, kind="request_review", profile="implementer",
                                audit_green=lambda: False)
        self.assertEqual(d["action"], "allow", d)
        rec = [x for x in r.board.records(tid, "accept-evaluated")][-1]
        self.assertEqual((rec.get("basis"), rec.get("accepted_commit")), ("rework-unchanged", out["commit"]))

    def test_a_changed_own_path_is_not_an_unchanged_rework(self):
        r = self.r
        tid, run, iss = r.issue("build:rk:pom")
        self.assertTrue(r.accept_on_run(tid, run, iss, attempt="1")["outcome_accepted"])
        r.native.request_review(tid)
        r.native.claim_review(tid)
        r.native.request_changes(tid, "the pom keeps a Spring Boot parent")
        run2, lock2 = r.native.claim(tid)
        NC.issue(r.root, r.board, task_id=tid, run_id=run2, claim_lock=lock2)
        r.edit("pom.xml", "<project>edited for the change request</project>\n")
        self.assertIsNone(NC.evaluate_unchanged_rework(r.root, r.board, task_id=tid, run_id=run2,
                                                       measurement={"classes": ["build"], "scenarios": []}))

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
class NativeRetryContext(unittest.TestCase):
    """V26-6 item 2: the same card's NEXT native run is told why its predecessor stopped, what it repeated
    and what that returned, the last loop step it completed, what it left in the tree, and whether the
    verification it already ran still describes the tree -- read from the native run rows, the execution
    ledger the K2 hooks write and the verifier's own record, through brief.py's real board path.
    v26 t_4fd2dcec run 15: three identical dependency greps, read_cycle_no_new_content_halt."""

    GREP = 'grep -n "quarkus-undertow\\|servlet" pom.xml'
    STOP = ("STOP WORKER_TOOL_LOOP: tool terminal, guardrail read_cycle_no_new_content_halt, count 3 (args_sha256 "
            "438f5e2076bd7f44)")

    def _ledger(self, home: Path, tid: str, run: int) -> None:
        logs = home / "kanban" / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        calls = [("brief", "python3 .hermes/skills/migration/fix-until-green/scripts/brief.py --root .", "brief ..."),
                 ("verify", "bash .hermes/skills/migration/fix-until-green/scripts/run-verify.sh --root . | tail -3",
                  "VERIFY EXIT 0: procedure completed; compilation FAILED (230 compile error(s)); tests not run")] + \
                [("g%d" % i, self.GREP, "(no match: pom.xml declares no Servlet dependency)") for i in range(3)]
        with (logs / ("%s.exec.jsonl" % tid)).open("w") as fh:
            for cid, cmd, out in calls:
                base = {"task": tid, "run": str(run), "tool_call_id": cid, "command": cmd}
                fh.write(json.dumps(dict(base, phase="start")) + "\n")
                fh.write(json.dumps(dict(base, phase="end", exit_code=0 if cid != "g0" else 1, output_tail=out,
                                         output_chars=len(out))) + "\n")

    def test_the_retry_receives_its_predecessors_context_through_the_native_board(self):
        sys.path.insert(0, str(LIB.parent / "skills" / "migration" / "fix-until-green" / "scripts"))
        import brief as BR
        r = Run()
        mirror_layout(r.root)
        keys = ("HERMES_KANBAN_TASK", "HERMES_KANBAN_RUN_ID", "HERMES_KANBAN_DB", "HERMES_HOME")
        saved = {k: os.environ.get(k) for k in keys}
        orig = NC.board_for
        try:
            r.release()
            tid, run1, _iss = r.issue("build:rk:pom")
            home = Path(r.tmp) / "hermes-home"
            self._ledger(home, tid, run1)
            cand = r.tree()
            rec = {"schema": "rhoai3.last-verify/v2", "status": "finished", "card": tid, "run": str(run1), "rc": 0,
                   "procedure": "completed", "compilation": "failed", "compile_errors": 230, "tests": "not-run",
                   "candidate_sha256": cand}
            (r.root / "verification" / "loop").mkdir(parents=True, exist_ok=True)
            (r.root / "verification" / "loop" / "last-verify.json").write_text(json.dumps(rec))
            # the guardrail ends run 1; the dispatcher gives the same card a new native run
            r.native.end_run(tid, "ready", "crashed")
            r.native.runs_[run1]["error"] = self.STOP
            run2, _lock = r.native.claim(tid)
            r.native.sync()
            os.environ.update(HERMES_KANBAN_TASK=tid, HERMES_KANBAN_RUN_ID=str(run2), HERMES_KANBAN_DB=r.native.db_path,
                              HERMES_HOME=str(home))
            NC.board_for = lambda root, native=None: NC.Board(r.native, author="implementer")
            pr = BR._previous_run(r.root)
            self.assertEqual((pr["run"], pr["outcome"], pr["kind"]), (str(run1), "crashed", "halted-investigation"))
            self.assertIn("read_cycle_no_new_content_halt", pr["stop"])
            self.assertEqual((pr["repeated"]["command"], pr["repeated"]["times"]), (self.GREP, 3))
            self.assertIn("pom.xml declares no Servlet dependency", pr["repeated"]["result_tail"])
            self.assertEqual(pr["last_loop_step"], {"script": "run-verify.sh", "exit_code": 0})
            # the verification the crashed run completed still describes this tree: it is not to be repeated
            vs = BR.verification_state(rec, tid, BR.candidate_sha256(r.root))
            self.assertEqual(vs["state"], "current", vs)
            # a tree edited since is stale evidence, never reused
            r.edit("pom.xml", "<project>edited after the crash</project>\n")
            self.assertEqual(BR.verification_state(rec, tid, BR.candidate_sha256(r.root))["state"], "stale")
            self.assertEqual(BR._previous_run(r.root)["left_in_tree"], ["pom.xml"])
            # without the ledger the repeated call and the last step stay unknown
            (home / "kanban" / "logs" / ("%s.exec.jsonl" % tid)).unlink()
            pr = BR._previous_run(r.root)
            self.assertEqual((pr["repeated"], pr["last_loop_step"], pr["kind"]), (None, None, "halted-investigation"))
        finally:
            NC.board_for = orig
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
            r.close()


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
                # the verification of THIS candidate, as run-verify records it (v24: classes are what it executed)
                wl.update(candidate_sha256=cand, measure=dict(wl.get("measure") or {}, compile_errors=0, failing_tests=0))
                run_doc = {"candidate_sha256": cand, "mode": "acceptance", "classpath": {"ran": True, "rc": 0},
                           "diagnostics": {"ran": True, "rc": 0}, "tests": {"ran": False}}
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    self.assertEqual(B.after_accept(r.root, git(r.root, "rev-parse", "HEAD"), cand, wl, run_doc), 0)
                self.assertIn("kanban_request_review reviewer=reviewer", out.getvalue())
                acc = [x for x in r.board.records(tid) if x["kind"] == "accept-commit"][-1]
                self.assertNotIn("tests", acc["measurement"]["classes"])   # no test ran: no tests class
                self.assertEqual(acc["measurement"]["execution"]["tests"]["state"], "not-run")
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


# ===========================================================================
class LifecycleReconciliation(unittest.TestCase):
    """v29 I-11: a run the loop guard stopped left verification/loop/issued.json and its unjudged edits
    behind, and voiding the rejections a harness defect caused restored the budget but not the cluster
    its exhaustion had deferred. The native board decides whether an issuance is live; an expired one
    is kept as history; a budget-derived deferral is lifted only when the effective spend is below the
    limit, once, without minting; a stopped run's edits inside its own issue are set aside at the next issue."""

    def setUp(self):
        self.r = Run()
        self.r.release()

    def tearDown(self):
        self.r.close()

    def exhaust(self):
        from planner.paths import LOOP_DEFERRED
        r = self.r
        tid, run, iss = r.issue("build:rk:pom")
        node = NC._node(r.plan(), "build:rk:pom")
        key, limit = node["budget"]["key"], node["budget"]["limit"]
        for i in range(limit):
            NC.record_verdict(r.root, r.board, task_id=tid, run_id=run, verdict="REVERTED", candidate="%064x" % i,
                              attempt=str(i), reason="red")
        p = r.root / LOOP_DEFERRED
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"schema": "rhoai3.loop-deferred/v1", "clusters": [iss["cluster"], "c:other"], "reasons": {
            iss["cluster"]: "%d of %d attempt(s) spent against %s; last: red" % (limit, limit, key),
            "c:other": "3 of 3 attempt(s) spent against rk:family:someone-else; last: red"}}))
        r.native.end_run(tid, "blocked", "needs_input")
        return tid, run, iss, key, limit, p

    def test_voiding_the_rejections_lifts_only_their_deferral_once(self):
        r = self.r
        tid, _run, iss, key, limit, p = self.exhaust()
        # still exhausted: the deferral stands
        got = NC.reconcile_deferrals(r.root, r.board, task_id=tid, by="operator", reason="x")
        self.assertEqual((got["lifted"], len(got["kept"])), ([], 1))
        self.assertIn(iss["cluster"], json.loads(p.read_text())["clusters"])
        with self.assertRaises(Refusal):
            NC.reconcile_deferrals(r.root, r.board, task_id=tid, by="implementer", reason="x")
        NC.void_rejects(r.board, task_id=tid, keys=[x["key"] for x in r.board.records(tid, "reject")], reason="harness",
                        by="operator")
        got = NC.reconcile_deferrals(r.root, r.board, task_id=tid, by="operator", reason="harness")
        self.assertEqual(got["lifted"], [iss["cluster"]])
        doc = json.loads(p.read_text())
        self.assertEqual(doc["clusters"], ["c:other"])                     # another family's deferral stands
        self.assertIn("c:other", doc["reasons"])
        self.assertEqual(len(r.board.records(tid, "reject")), limit)        # the rejections stay on the record
        self.assertEqual(NC._node(r.plan(), "build:rk:pom")["budget"]["limit"], limit)   # the limit is unchanged
        # idempotent: a repeat lifts nothing and records nothing
        again = NC.reconcile_deferrals(r.root, r.board, task_id=tid, by="operator", reason="harness")
        self.assertEqual(again["lifted"], [])
        self.assertEqual(len(r.board.records(tid, "deferral-lifted")), 1)

    def test_an_interrupted_reconciliation_resumes_to_one_record(self):
        from planner import canonical
        r = self.r
        tid, _run, iss, _key, _limit, p = self.exhaust()
        NC.void_rejects(r.board, task_id=tid, keys=[x["key"] for x in r.board.records(tid, "reject")], reason="h",
                        by="operator")
        orig = canonical.write_canonical

        def boom(*a, **k):
            raise OSError("interrupted")
        canonical.write_canonical = boom
        try:
            with self.assertRaises(OSError):
                NC.reconcile_deferrals(r.root, r.board, task_id=tid, by="operator", reason="h")
        finally:
            canonical.write_canonical = orig
        self.assertIn(iss["cluster"], json.loads(p.read_text())["clusters"])   # nothing half-written
        got = NC.reconcile_deferrals(r.root, r.board, task_id=tid, by="operator", reason="h")
        self.assertEqual(got["lifted"], [iss["cluster"]])
        self.assertEqual(len(r.board.records(tid, "deferral-lifted")), 1)     # the record was not duplicated

    def test_a_seal_still_blocking_on_a_lifted_cluster_is_resealed_once(self):
        """v29 I-11: the lifted cluster kept its MANUAL_CLUSTER block, the parity composer refused against the
        stale seal and the sweep overwrote every FAIL with INCONCLUSIVE."""
        from planner import pipeline, worklist as W
        from planner.paths import ADMISSION_RECEIPT
        r = self.r
        tid, _run, iss, _key, _limit, _p = self.exhaust()
        seal = r.root / ADMISSION_RECEIPT
        seal.parent.mkdir(parents=True, exist_ok=True)
        seal.write_text(json.dumps({"status": "INCONCLUSIVE", "blocks": [
            {"class": "MANUAL_CLUSTER", "subject": iss["cluster"]}, {"class": "MANUAL_CLUSTER", "subject": "c:other"}]}))
        calls = []
        orig = (pipeline.admit, W.build_worklist)

        def admit(root, **k):
            calls.append("admit")
            seal.write_text(json.dumps({"status": "INCONCLUSIVE", "blocks": [{"class": "MANUAL_CLUSTER", "subject": "c:other"}]}))
            return {"status": "INCONCLUSIVE"}
        pipeline.admit, W.build_worklist = admit, (lambda root, **k: calls.append("build"))
        try:
            NC.void_rejects(r.board, task_id=tid, keys=[x["key"] for x in r.board.records(tid, "reject")], reason="h",
                            by="operator")
            got = NC.reconcile_deferrals(r.root, r.board, task_id=tid, by="operator", reason="h")
            self.assertEqual((got["lifted"], calls), ([iss["cluster"]], ["build", "admit"]))
            # the block that remains is another family's, still deferred: nothing to re-seal
            NC.reconcile_deferrals(r.root, r.board, task_id=tid, by="operator", reason="h")
            self.assertEqual(calls, ["build", "admit"])
            # interrupted before the re-seal: the repeat re-seals although nothing is left to lift
            seal.write_text(json.dumps({"status": "INCONCLUSIVE", "blocks": [{"class": "MANUAL_CLUSTER", "subject": iss["cluster"]}]}))
            again = NC.reconcile_deferrals(r.root, r.board, task_id=tid, by="operator", reason="h")
            self.assertEqual((again["lifted"], calls[-2:]), ([], ["build", "admit"]))
        finally:
            pipeline.admit, W.build_worklist = orig

    def test_an_amendment_granted_in_an_earlier_run_keeps_its_authority(self):
        """v29 run 76: the amendment granted in run 73 was projected without granted_before_sha256, and
        advance.py rejected a correct candidate as 'amendment(s) without authority'."""
        r = self.r
        tid, run, iss = r.issue("build:rk:pom")
        rel = "src/main/java/com/acme/shop/web/ItemController.java"
        if not (r.root / rel).is_file():
            r.edit(rel, "class ItemController {}\n")
            git(r.root, "add", "-A")
            git(r.root, "commit", "-qm", "fixture")
        NC.amend(r.root, r.board, task_id=tid, run_id=run, cluster=iss["cluster"], rel=rel,
                 row={"reason": "the stack's product frame is here", "locus": "parity: thrown in this file"})
        r.native.end_run(tid, "ready", "gave_up")
        run2, lock2 = r.native.claim(tid)
        again = NC.issue(r.root, r.board, task_id=tid, run_id=run2, claim_lock=lock2)
        self.assertIn(rel, again["allowed_paths"])
        row = next(a for a in again["amendments"] if a["path"] == rel)
        # advance.py's authority predicate: granted_before_sha256 present and not dirty at grant
        self.assertTrue(row["granted_before_sha256"] and not row["dirty_at_grant"], row)
        # a record written before the digest was kept takes the content at HEAD, which the issue proved clean
        legacy = {"path": rel, "reason": "r", "locus": "l"}
        self.assertEqual(NC.amendment_projection(r.root, NC._head(r.root), legacy)["granted_before_sha256"],
                         row["granted_before_sha256"])

    def projection(self, tid, run):
        from planner.paths import LOOP_ISSUED
        p = self.r.root / LOOP_ISSUED
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"task_id": tid, "cluster": "c:x", "idempotency_key": "outcome:v2:n1:o:c:x:issue1:r%d" % run}))
        return p

    def test_an_issuance_is_live_while_its_card_runs_and_is_kept_as_history_once_expired(self):
        r = self.r
        tid, run, _iss = r.issue("build:rk:pom")
        p = self.projection(tid, run)
        self.assertEqual(NC.issuance_state(r.root, r.board)["state"], "live")
        with self.assertRaises(Refusal) as cm:
            NC.retire_issuance(r.root, r.board, by="operator", reason="x")
        self.assertEqual(cm.exception.code, "ISSUANCE_NOT_EXPIRED")
        # a newer claim on the same card is live too: a surviving or new worker owns it
        r.native.end_run(tid, "ready", "gave_up")
        r.native.claim(tid)
        st = NC.issuance_state(r.root, r.board)
        self.assertEqual(st["state"], "live")
        self.assertIn("newer claim", st["why"])
        # a retained candidate is not expired either
        r.native.end_run(tid, "blocked", "needs_input")
        r.board.record(tid, "pending", "pending:test", candidate="c" * 64)
        self.assertEqual(NC.issuance_state(r.root, r.board)["state"], "retained")
        with self.assertRaises(Refusal):
            NC.retire_issuance(r.root, r.board, by="operator", reason="x")
        r.board.record(tid, "reject", "reject:test", candidate="c" * 64)     # the pending row is closed
        self.assertEqual(NC.issuance_state(r.root, r.board)["state"], "expired")
        body = p.read_bytes()
        got = NC.retire_issuance(r.root, r.board, by="operator", reason="stopped run")
        self.assertFalse(p.exists())
        self.assertEqual((r.root / got["retired"]).read_bytes(), body)       # history, byte for byte
        self.assertEqual(NC.retire_issuance(r.root, r.board, by="operator", reason="again")["retired"], None)
        self.assertEqual(len(r.board.records(tid, "issuance-retired")), 1)

    def test_a_stopped_runs_edits_inside_its_issue_are_set_aside_at_the_next_issue(self):
        r = self.r
        tid, run, iss = r.issue("build:rk:pom")
        r.edit(iss["allowed_paths"][0], "<project>left by a stopped worker</project>\n")
        r.native.end_run(tid, "ready", "gave_up")                          # no terminator ran
        run2, lock2 = r.native.claim(tid)
        again = NC.issue(r.root, r.board, task_id=tid, run_id=run2, claim_lock=lock2)   # v29 run 76: no drift refusal
        self.assertEqual(again["outcome_id"], "build:rk:pom")
        ab = r.board.records(tid, NC.ABANDONED)
        self.assertEqual((len(ab), ab[0]["run"], ab[0]["paths"]), (1, run, [iss["allowed_paths"][0]]))
        self.assertIsNotNone(r.board.attachment(tid, ab[0]["attachment"]))
        self.assertEqual(git(r.root, "status", "--porcelain", "--", iss["allowed_paths"][0]), "")
        self.assertIsNone(NC.parked_pending(r.board, tid))                 # evidence, never a candidate to restore
        # control: an edit outside what the stopped run was issued is still the drift refusal
        r.native.end_run(tid, "ready", "gave_up")
        run3, lock3 = r.native.claim(tid)
        r.edit("src/main/java/com/acme/shop/Unrelated.java", "class Unrelated {}\n")
        with self.assertRaises(Refusal) as cm:
            NC.issue(r.root, r.board, task_id=tid, run_id=run3, claim_lock=lock3)
        self.assertEqual(cm.exception.code, "ISSUE_BASELINE_DRIFT")

    def test_a_parked_candidates_comparison_does_not_survive_the_park(self):
        """H-19 (v31): the Owner card parked its candidate; the parity records its last comparison left were bound to
        that candidate, and the next card's checkpoint snapshotted them into the ACCEPTED baseline -- a tree HEAD
        never held. Parking restores the accepted reports, as a revert does."""
        r = self.r
        mirror_layout(r.root)
        tid, run, iss = r.issue("build:rk:pom")
        from planner.paths import LOOP_ACCEPTED, PARITY_DIR
        snap = r.root / LOOP_ACCEPTED / "parity" / "scenarios"
        live = r.root / PARITY_DIR / "scenarios"
        snap.mkdir(parents=True, exist_ok=True)
        live.mkdir(parents=True, exist_ok=True)
        accepted = {"schema": "rhoai3.scenario-parity/v1", "scenario": "sc:x", "verdict": "FAIL", "reason": "header content-type a vs b",
                    "binding": {"mode": "candidate", "candidate_sha256": "accepted-tree"}}
        (snap / "sc_x.json").write_text(json.dumps(accepted))
        r.edit(iss["allowed_paths"][0], "<project>candidate</project>\n")
        (live / "sc_x.json").write_text(json.dumps(dict(accepted, reason="", verdict="PASS",
                                                        binding={"mode": "candidate", "candidate_sha256": r.tree()})))
        got = NC.park(r.root, r.board, task_id=tid, run_id=run)
        self.assertTrue(got["reports_restored"])
        self.assertEqual(json.loads((live / "sc_x.json").read_text()), accepted)   # the accepted comparison, not the candidate's

    def test_a_crashed_cards_edits_are_set_aside_onto_it_when_another_card_issues(self):
        """H-15 (v31 t_0ad06b42): a card's run crashed with its candidate in the shared tree and the card BLOCKED,
        so its next run never came; every other ready card refused ISSUE_BASELINE_DRIFT. The next card to issue
        proves the edits are the crashed run's (issued paths, run window, ended) and sets them aside onto THAT card."""
        r = self.r
        ta, ra, ia = r.issue("build:rk:pom")
        rel = ia["allowed_paths"][0]
        r.edit(rel, "<project>left by a crashed worker</project>\n")
        r.native.end_run(ta, "blocked", "crashed")                         # no terminator ran; the card waits
        tb, rb, ib = r.issue("config:rk:cfg")                              # no drift refusal
        self.assertEqual(ib["outcome_id"], "config:rk:cfg")
        ab = r.board.records(ta, NC.ABANDONED)
        self.assertEqual((len(ab), ab[0]["run"], ab[0]["paths"]), (1, ra, [rel]))     # onto the crashed card
        self.assertIsNotNone(r.board.attachment(ta, ab[0]["attachment"]))
        self.assertEqual(r.board.records(tb, NC.ABANDONED), [])
        self.assertEqual(git(r.root, "status", "--porcelain", "--", rel), "")

    def test_an_edit_no_ended_run_owns_still_refuses_another_cards_issue(self):
        """H-15 control: an edit outside what any ended run was issued is nobody's to set aside."""
        r = self.r
        ta, ra, ia = r.issue("build:rk:pom")
        r.native.end_run(ta, "blocked", "crashed")
        r.edit("src/main/java/com/acme/shop/Unrelated.java", "class Unrelated {}\n")
        tid = r.tid("config:rk:cfg")
        run, lock = r.native.claim(tid)
        with self.assertRaises(Refusal) as cm:
            NC.issue(r.root, r.board, task_id=tid, run_id=run, claim_lock=lock)
        self.assertEqual(cm.exception.code, "ISSUE_BASELINE_DRIFT")
        self.assertEqual(r.board.records(ta, NC.ABANDONED), [])

    def test_a_repeated_issue_keeps_the_current_runs_edits(self):
        """V29-3 (architect reproduction of 0dd677ba): old stopped run -> new issue -> new legitimate edit ->
        repeated issue parked the CURRENT worker's repair under the older run and reset it."""
        r = self.r
        tid, old, iss = r.issue("build:rk:pom")
        rel = iss["allowed_paths"][0]
        r.edit(rel, "<project>left by the stopped run</project>\n")
        r.native.end_run(tid, "ready", "gave_up")                          # no terminator ran
        run, lock = r.native.claim(tid)
        first = NC.issue(r.root, r.board, task_id=tid, run_id=run, claim_lock=lock, replay_unchanged=True)
        self.assertEqual([a["run"] for a in r.board.records(tid, NC.ABANDONED)], [old])   # the old run's leftovers
        import native_gate as NG
        from planner.paths import LOOP_ISSUED
        mirror_layout(r.root)
        key = NG.write_issued_projection(r.root, first)
        proj = json.loads((r.root / LOOP_ISSUED).read_text())
        proj["continuations"] = [{"n": 1, "reported": ["x"]}]                # the loop wrote onto its projection
        (r.root / LOOP_ISSUED).write_text(json.dumps(proj))
        live = "<project>legitimate current-run repair</project>\n"
        r.edit(rel, live)
        # architect review cf164288: a re-issue over unjudged edits -- replayed or not -- refuses and changes nothing
        for replay in (True, False):
            with self.assertRaises(Refusal) as cm:
                NC.issue(r.root, r.board, task_id=tid, run_id=run, claim_lock=lock, replay_unchanged=replay)
            self.assertEqual(cm.exception.code, "ISSUE_BASELINE_DRIFT")
            self.assertEqual((r.root / rel).read_text(), live)               # byte-identical
        self.assertEqual(json.loads((r.root / LOOP_ISSUED).read_text())["continuations"], proj["continuations"])
        self.assertEqual([a["run"] for a in r.board.records(tid, NC.ABANDONED)], [old])   # nothing new attributed
        self.assertEqual(len([x for x in r.board.records(tid, "issue") if x["run"] == run]), 1)
        # an edit outside what this run was issued: the drift refusal, and still nothing is set aside
        r.edit("src/main/java/com/acme/shop/Unrelated.java", "class Unrelated {}\n")
        with self.assertRaises(Refusal) as cm:
            NC.issue(r.root, r.board, task_id=tid, run_id=run, claim_lock=lock, replay_unchanged=True)
        self.assertEqual(cm.exception.code, "ISSUE_BASELINE_DRIFT")
        self.assertEqual((r.root / rel).read_text(), live)
        self.assertEqual(len(r.board.records(tid, NC.ABANDONED)), 1)

    def test_leftovers_of_a_run_not_proven_ended_are_not_abandoned(self):
        r = self.r
        tid, old, iss = r.issue("build:rk:pom")
        r.edit(iss["allowed_paths"][0], "<project>still being written</project>\n")
        r.native.end_run(tid, "ready", "gave_up")
        r.native.runs_[old]["status"] = "running"                            # the native row says the worker lives
        run, lock = r.native.claim(tid)
        with self.assertRaises(Refusal) as cm:
            NC.issue(r.root, r.board, task_id=tid, run_id=run, claim_lock=lock)
        self.assertEqual(cm.exception.code, "ISSUE_BASELINE_DRIFT")
        self.assertEqual(r.board.records(tid, NC.ABANDONED), [])

    def expired_projection(self):
        r = self.r
        tid, run, _iss = r.issue("build:rk:pom")
        r.native.end_run(tid, "ready", "gave_up")
        p = self.projection(tid, run)
        self.assertEqual(NC.issuance_state(r.root, r.board)["state"], "expired")
        return tid, run, p

    def new_projection(self, tid, run):
        return json.dumps({"task_id": tid, "cluster": "c:x", "idempotency_key": "outcome:v2:n1:o:c:x:issue1:r%d" % run})

    def test_a_claim_made_while_the_record_is_written_keeps_its_projection(self):
        """V29-2 (architect reproduction): a new claim wrote its issued.json between the liveness check and the
        unlink, and the retirement deleted it. The judged projection is moved aside by digest before anything is
        recorded, so a projection written afterwards is never the one removed."""
        r = self.r
        tid, old, p = self.expired_projection()
        old_bytes = p.read_bytes()
        record, seen = r.board.record, {}

        def claim_before_unlink(task, kind, key, **fields):
            got = record(task, kind, key, **fields)
            if kind == "issuance-retired":
                run, _lock = r.native.claim(tid)
                p.write_text(self.new_projection(tid, run))
                seen["run"] = run
            return got
        r.board.record = claim_before_unlink
        try:
            NC.retire_issuance(r.root, r.board, by="operator", reason="race")
        finally:
            r.board.record = record
        self.assertEqual(p.read_text(), self.new_projection(tid, seen["run"]))           # the new run keeps its own
        hist = list((r.root / NC.ISSUED_HISTORY).glob("issued.%s.r%d.*.json" % (tid, old)))
        self.assertEqual([h.read_bytes() for h in hist], [old_bytes])                    # the old one is history
        self.assertEqual(NC.issuance_state(r.root, r.board)["state"], "live")
        with self.assertRaises(Refusal):                                                  # a delayed retirement
            NC.retire_issuance(r.root, r.board, by="operator", reason="late event")
        self.assertTrue(p.is_file())
        self.assertEqual(len(r.board.records(tid, "issuance-retired")), 1)

    def test_a_projection_written_just_before_the_move_is_put_back(self):
        from unittest import mock
        r = self.r
        tid, old, p = self.expired_projection()
        real = os.rename
        newer = json.dumps({"task_id": tid, "cluster": "c:y", "idempotency_key": "outcome:v2:n1:o:c:y:issue2:r%d" % old})

        def swap_then_move(src, dst):
            if str(src) == str(p):
                p.write_text(newer)                    # the writer won the slot an instant before the move
            return real(src, dst)
        with mock.patch.object(NC.os, "rename", swap_then_move):
            with self.assertRaises(Refusal) as cm:
                NC.retire_issuance(r.root, r.board, by="operator", reason="race")
        self.assertEqual(cm.exception.code, "ISSUANCE_CHANGED")
        self.assertEqual(p.read_text(), newer)
        self.assertEqual(list(p.parent.glob(p.name + NC.RETIRING + "*")), [])
        self.assertEqual(r.board.records(tid, "issuance-retired"), [])                   # nothing recorded

    def test_a_claim_made_after_the_move_does_not_lose_the_judged_projection(self):
        from unittest import mock
        r = self.r
        tid, old, p = self.expired_projection()
        body = p.read_bytes()
        real, seen = os.rename, {}

        def move_then_claim(src, dst):
            out = real(src, dst)
            if str(src) == str(p):
                seen["run"] = r.native.claim(tid)[0]
            return out
        with mock.patch.object(NC.os, "rename", move_then_claim):
            got = NC.retire_issuance(r.root, r.board, by="operator", reason="race")
        self.assertEqual((r.root / got["retired"]).read_bytes(), body)                   # the judged bytes, archived
        self.assertFalse(p.exists())                                                      # the slot is the new run's
        self.assertEqual(len(r.board.records(tid, "issuance-retired")), 1)
        self.assertEqual(NC.issuance_state(r.root, r.board)["state"], "none")

    def test_a_live_or_unknown_run_refuses_retirement(self):
        r = self.r
        tid, old, p = self.expired_projection()
        r.native.runs_[old]["status"] = "running"                                        # a surviving worker
        st = NC.issuance_state(r.root, r.board)
        self.assertEqual(st["state"], "live", st)
        with self.assertRaises(Refusal):
            NC.retire_issuance(r.root, r.board, by="operator", reason="x")
        r.native.runs_[old]["status"] = "ended"
        p.write_text(self.new_projection(tid, 9999))                                     # a run the board never had
        self.assertEqual(NC.issuance_state(r.root, r.board)["state"], "unbound")
        with self.assertRaises(Refusal):
            NC.retire_issuance(r.root, r.board, by="operator", reason="x")
        self.assertTrue(p.is_file())

    def test_an_interrupted_retirement_is_safe_on_restart(self):
        r = self.r
        tid, old, p = self.expired_projection()
        body = p.read_bytes()
        from unittest import mock
        real_unlink = Path.unlink

        def crash(self_, *a, **k):
            if NC.RETIRING in self_.name:
                raise OSError("killed between the record and the removal")
            return real_unlink(self_, *a, **k)
        with mock.patch.object(Path, "unlink", crash):
            with self.assertRaises(OSError):
                NC.retire_issuance(r.root, r.board, by="operator", reason="x")
        self.assertFalse(p.exists())
        self.assertEqual(len(list(p.parent.glob(p.name + NC.RETIRING + "*"))), 1)
        got = NC.retire_issuance(r.root, r.board, by="operator", reason="x")            # restart finishes it
        self.assertEqual(got["state"], "none")
        self.assertEqual((r.root / got["retired"]).read_bytes(), body)
        self.assertEqual(list(p.parent.glob(p.name + NC.RETIRING + "*")), [])
        self.assertEqual(len(list((r.root / NC.ISSUED_HISTORY).glob("*.json"))), 1)
        self.assertEqual(len(r.board.records(tid, "issuance-retired")), 1)
        # a leftover whose name does not carry its own digest is refused and never deleted
        leftover = p.parent / (p.name + NC.RETIRING + "0" * 16)
        leftover.write_text(self.new_projection(tid, old))
        with self.assertRaises(Refusal) as cm:
            NC.retire_issuance(r.root, r.board, by="operator", reason="x")
        self.assertEqual(cm.exception.code, "RETIRING_CORRUPT")
        self.assertTrue(leftover.is_file())

    def test_void_and_reconcile_conserve_the_account_and_agree_with_admission(self):
        """V29-1: an authorized void lifts only its now-invalid exhaustion hold; an unrelated blocker that merely
        names the key stays; repetition and a crash between the void and the reconciliation are idempotent (no
        double credit, no extra allowance, no mint); the effective spend and allowance are reported; the same card
        is issued the lifted cluster again."""
        from planner.paths import LOOP_DEFERRED, LOOP_STEPS
        r = self.r
        tid, _run, iss, key, limit, p = self.exhaust()
        doc = json.loads(p.read_text())
        doc["clusters"].append("c:held")
        doc["reasons"]["c:held"] = "Operator hold against %s: the pom waits on a platform decision" % key
        p.write_text(json.dumps(doc))
        r.board.record(tid, "issue", "issue:held", run=0, cluster="c:held", allowed_paths=[])   # the card was issued it
        steps = r.root / LOOP_STEPS
        steps.parent.mkdir(parents=True, exist_ok=True)
        steps.write_text(json.dumps({"steps": [], "attempts": {key: limit}}))
        steps_bytes = steps.read_bytes()
        creates = len([c for c in r.native.calls if c[0] == "create"])
        before = NC.effective_budget(r.board, tid)
        self.assertEqual((before["spent"], before["remaining"], before["exhausted"]), (limit, 0, True))
        keys = [x["key"] for x in r.board.records(tid, "reject")]
        # interrupted: the void landed, the reconciliation never ran
        self.assertEqual(len(NC.void_rejects(r.board, task_id=tid, keys=keys, reason="harness", by="operator")), limit)
        self.assertIn(iss["cluster"], json.loads(p.read_text())["clusters"])
        # the repeat of the whole Operator step: nothing is credited twice
        self.assertEqual(NC.void_rejects(r.board, task_id=tid, keys=keys, reason="harness", by="operator"), [])
        got = NC.reconcile_deferrals(r.root, r.board, task_id=tid, by="operator", reason="harness")
        self.assertEqual(got["lifted"], [iss["cluster"]])
        self.assertEqual([k["cluster"] for k in got["kept"]], ["c:held"])                 # the unrelated blocker stays
        eff = got["effective"]
        self.assertEqual(eff["before"], eff["after"])                                     # reconciling moves no budget
        self.assertEqual((eff["after"]["spent"], eff["after"]["remaining"], eff["after"]["limit"], eff["after"]["voided"]),
                         (0, limit, limit, limit))
        doc = json.loads(p.read_text())
        self.assertEqual(sorted(doc["clusters"]), ["c:held", "c:other"])
        again = NC.reconcile_deferrals(r.root, r.board, task_id=tid, by="operator", reason="harness")
        self.assertEqual((again["lifted"], again["effective"]["after"]), ([], eff["after"]))
        self.assertEqual(len(r.board.records(tid, "deferral-lifted")), 1)
        self.assertEqual(steps.read_bytes(), steps_bytes)                                 # no legacy allowance
        self.assertEqual(len([c for c in r.native.calls if c[0] == "create"]), creates)   # nothing minted
        self.assertEqual(len(r.board.records(tid, "reject")), limit)                      # rejections conserved
        # the same native card is issued the lifted cluster again, spending from the restored account
        run2, lock2 = r.native.claim(tid)
        nxt = NC.issue(r.root, r.board, task_id=tid, run_id=run2, claim_lock=lock2)
        self.assertEqual((nxt["cluster"], nxt["budget"]["spent"]), (iss["cluster"], 0))

    def test_a_stale_work_list_naming_a_lifted_cluster_is_resealed(self):
        from planner import pipeline, worklist as W
        from planner.paths import ADMISSION_RECEIPT
        r = self.r
        tid, _run, iss, _key, _limit, _p = self.exhaust()
        seal = r.root / ADMISSION_RECEIPT
        seal.parent.mkdir(parents=True, exist_ok=True)
        seal.write_text(json.dumps({"status": "ADMITTED", "blocks": []}))
        r.worklist["deferred"] = [iss["cluster"]]                                        # sealed before the lift
        r.save_worklist()
        calls = []
        orig = (pipeline.admit, W.build_worklist)
        pipeline.admit, W.build_worklist = (lambda root, **k: calls.append("admit") or {"status": "ADMITTED"}), \
            (lambda root, **k: calls.append("build"))
        try:
            NC.void_rejects(r.board, task_id=tid, keys=[x["key"] for x in r.board.records(tid, "reject")], reason="h",
                            by="operator")
            NC.reconcile_deferrals(r.root, r.board, task_id=tid, by="operator", reason="h")
        finally:
            pipeline.admit, W.build_worklist = orig
        self.assertEqual(calls, ["build", "admit"])

    def test_a_sibling_in_the_same_budget_family_is_reconciled_with_it(self):
        from planner.paths import LOOP_DEFERRED
        r = self.r
        tid, _run, iss, key, limit, p = self.exhaust()
        sib_tid, sib_run, sib = r.issue("config:rk:cfg")
        r.native.end_run(sib_tid, "blocked", "needs_input")
        doc = json.loads(p.read_text())
        doc["clusters"].append(sib["cluster"])
        doc["reasons"][sib["cluster"]] = "%d of %d attempt(s) spent against %s; last: red" % (limit, limit, key)
        p.write_text(json.dumps(doc))
        plan_of = r.board.plan

        def shared(run_id):
            plan = copy.deepcopy(plan_of(run_id))
            for n in plan["nodes"]:
                if n["outcome_id"] == "config:rk:cfg":
                    n["budget"] = dict(n["budget"], key=key)                                # one family, one account
            return plan
        r.board.plan = shared
        try:
            NC.void_rejects(r.board, task_id=tid, keys=[x["key"] for x in r.board.records(tid, "reject")], reason="h",
                            by="operator")
            got = NC.reconcile_deferrals(r.root, r.board, task_id=tid, by="operator", reason="h")
        finally:
            r.board.plan = plan_of
        self.assertEqual(sorted(got["lifted"]), sorted([iss["cluster"], sib["cluster"]]))
        self.assertEqual(json.loads(p.read_text())["clusters"], ["c:other"])

    def interrupted_rejection(self, extra=True):
        """Card A's run is REJECTED on the native board and stopped before its revert ran (I-11 run 75)."""
        r = self.r
        tid, run, iss = r.issue("build:rk:pom")
        rel = iss["allowed_paths"][0]
        other = [c for c in r.worklist["clusters"] if rel not in c["write_set"]][0]["write_set"][0]
        r.edit(rel, "<project>rejected candidate</project>\n")
        if extra:
            r.edit(other, "// rejected edit outside the write set\n")                  # why it was rejected
            r.edit("src/main/java/com/acme/shop/NewAdapter.java", "class NewAdapter {}\n")
        cand = r.tree()
        NC.record_verdict(r.root, r.board, task_id=tid, run_id=run, verdict="REVERTED", candidate=cand, attempt="1",
                          reason="changed path(s) outside the write set")
        return tid, run, iss, cand

    def test_an_interrupted_rejection_is_set_aside_before_another_card_works(self):
        """V29-3: dirty rejected bytes never become the baseline of a later card; they are preserved on the card
        that rejected them, and the restore is verified before work continues."""
        r = self.r
        tid, run, iss, cand = self.interrupted_rejection()
        dirty = {rel: (r.root / rel).read_bytes() for rel in NC._changed_vs_head(r.root)[1]}
        r.native.end_run(tid, "ready", "gave_up")                                        # no terminator ran
        committed = NC.commit_product_tree(r.root, NC._head(r.root))
        btid, brun, b = r.issue("config:rk:cfg")
        self.assertEqual(b["baseline_tree"], committed)                                   # never the rejected bytes
        self.assertEqual(r.tree(), committed)
        ab = r.board.records(tid, NC.ABANDONED)
        self.assertEqual((len(ab), ab[0]["run"], ab[0]["paths"]), (1, run, sorted(dirty)))
        files = json.loads(r.board.attachment(tid, ab[0]["attachment"])[0])["files"]
        self.assertEqual({k: base64.b64decode(v) for k, v in files.items()}, dirty)     # the rejected patch, byte for byte
        link = r.board.records(tid, "rejected-set-aside")
        self.assertEqual((len(link), link[0]["reject"]), (1, "reject:%d:1" % run))
        self.assertEqual(r.board.records(btid, NC.ABANDONED), [])                        # never attributed to B
        # restart: repeating B's issue sets nothing aside again
        again = NC.issue(r.root, r.board, task_id=btid, run_id=brun, replay_unchanged=True)
        self.assertTrue(again["replayed"])
        self.assertEqual(len(r.board.records(tid, NC.ABANDONED)), 1)

    def test_unrelated_edits_beside_a_rejected_candidate_are_never_discarded(self):
        r = self.r
        tid, run, iss, cand = self.interrupted_rejection()
        r.native.end_run(tid, "ready", "gave_up")
        r.edit("README.user.md", "an operator's note\n")                                # not the rejected tree
        before = {rel: (r.root / rel).read_bytes() for rel in NC._changed_vs_head(r.root)[1]}
        btid, brun, lock = r.claim("config:rk:cfg")
        with self.assertRaises(Refusal) as cm:
            NC.issue(r.root, r.board, task_id=btid, run_id=brun, claim_lock=lock)
        self.assertEqual(cm.exception.code, "ISSUE_BASELINE_DRIFT")
        self.assertEqual({rel: (r.root / rel).read_bytes() for rel in before}, before)
        self.assertEqual(r.board.records(tid, NC.ABANDONED), [])

    def test_an_interrupted_set_aside_resumes_on_restart(self):
        from unittest import mock
        r = self.r
        tid, run, iss, cand = self.interrupted_rejection()
        r.native.end_run(tid, "ready", "gave_up")
        real, n = NC._git, {"checkout": 0}

        def killed(root, *a, **k):
            if a and a[0] == "checkout":
                n["checkout"] += 1
                if n["checkout"] == 2:
                    raise OSError("killed during the restore")
            return real(root, *a, **k)
        btid, brun, lock = r.claim("config:rk:cfg")
        with mock.patch.object(NC, "_git", killed):
            with self.assertRaises(OSError):
                NC.issue(r.root, r.board, task_id=btid, run_id=brun, claim_lock=lock)
        self.assertTrue(NC._changed_vs_head(r.root)[1])                                  # half restored
        self.assertNotEqual(r.tree(), cand)
        b = NC.issue(r.root, r.board, task_id=btid, run_id=brun, claim_lock=lock)       # restart
        self.assertEqual(b["baseline_tree"], NC.commit_product_tree(r.root, NC._head(r.root)))
        self.assertEqual(NC._changed_vs_head(r.root)[1], [])
        self.assertEqual(len(r.board.records(tid, NC.ABANDONED)), 1)

    def test_a_runs_own_interrupted_rejection_is_set_aside_on_its_next_issue(self):
        r = self.r
        tid, run, iss, cand = self.interrupted_rejection(extra=False)
        nxt = NC.issue(r.root, r.board, task_id=tid, run_id=run)                         # the loop's re-issue
        self.assertEqual((nxt["issue_id"], nxt["replayed"]), (2, False))
        self.assertEqual(NC._changed_vs_head(r.root)[1], [])
        ab = r.board.records(tid, NC.ABANDONED)
        self.assertEqual((len(ab), ab[0]["run"]), (1, run))
        # an older rejection of this run (before its latest issue) never matches a later identical edit
        r.edit(iss["allowed_paths"][0], "<project>rejected candidate</project>\n")
        with self.assertRaises(Refusal) as cm:                                            # unjudged edits: refused
            NC.issue(r.root, r.board, task_id=tid, run_id=run, replay_unchanged=True)
        self.assertEqual(cm.exception.code, "ISSUE_BASELINE_DRIFT")
        self.assertEqual((r.root / iss["allowed_paths"][0]).read_text(), "<project>rejected candidate</project>\n")
        self.assertEqual(len(r.board.records(tid, NC.ABANDONED)), 1)


if __name__ == "__main__":
    unittest.main(verbosity=1)
