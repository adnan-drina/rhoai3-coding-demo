#!/usr/bin/env python3
"""PARALLEL-M3-PILOT.md qualification (synthetic and real-git layers).

Synthetic board: FakeNative, the published graph read back and walked the way the native dispatcher
promotes dependents. Real git: actual `git worktree` checkouts of a disposable destination.
Native-runtime evidence (the pinned Hermes CLI materializing worktrees) is a separate layer."""
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("native_board_harness_pilot", HERE / "native_board.test.py")
NB = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(NB)
sys.path.insert(0, str(HERE.parent))
from planner import native_control as NC  # noqa: E402
from planner import pair_selection as PS  # noqa: E402
from planner import pilot as PL  # noqa: E402
sys.path.insert(0, str(HERE.parent.parent / "kernel"))

ITEM, ORDER = "source:rk:item", "source:rk:order"
W = "src/main/java/com/acme/shop/"


def structure(order_refs=("dto.ItemDto",)):
    def t(path, fqn, refs=()):
        return {"path": W + path, "fqn": "com.acme.shop." + fqn, "type_refs": ["com.acme.shop." + r for r in refs],
                "resolution": "full", "methods": [], "fields": []}
    return {"available": True, "mode": "full", "types": [
        t("web/ItemController.java", "web.ItemController", ("dto.ItemDto",)),
        t("web/OrderController.java", "web.OrderController", order_refs),
        t("web/RootController.java", "web.RootController"),
        t("dto/ItemDto.java", "dto.ItemDto"), t("dto/ItemMapper.java", "dto.ItemMapper", ("dto.ItemDto",))]}


def ready_waves(r) -> list[list[str]]:
    """Walk the published board as the native dispatcher would: take every ready repair outcome, finish
    it, promote dependents; return what was ready together at each step."""
    waves = []
    for _ in range(40):
        ready = sorted(t["id"] for t in r.native.tasks.values() if t["status"] == "ready"
                       and (r.board.node_of(t["id"]) or ("",))[0] == "repair")
        if not ready:
            break
        waves.append(sorted(r.board.node_of(t)[2] for t in ready))
        for tid in ready:
            r.native.complete(tid)
    return waves


class ExecutionPolicy(unittest.TestCase):
    """The policy is pinned by the destination's INITIAL commit; the dispatcher cap follows it."""

    def _dest(self, initial, later=None, working=None, protocol="outcome-board/v2"):
        import tempfile
        td = Path(tempfile.mkdtemp(prefix="pol-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(td, ignore_errors=True))

        def write(value):
            conf = {"board_protocol": protocol}
            if value is not None:
                conf["parallel_m3"] = value
            (td / "run-defaults.json").write_text(json.dumps({"schema": "rhoai3.run-defaults/v1", "configuration": conf}))
        write(initial)
        (td / ".hermes").mkdir()
        (td / ".hermes" / "pins.json").write_text(json.dumps({"pins": {"planner": {"outcome_board": {"execution": "qualification"}}}}))
        NB.git(td, "init", "-q")
        NB.git(td, "config", "user.email", "t@t")
        NB.git(td, "config", "user.name", "t")
        NB.git(td, "add", "-A")
        NB.git(td, "commit", "-qm", "initial commit")
        if later is not None:
            write(later)
            NB.git(td, "commit", "-qam", "later")
        if working is not None:
            write(working)
        return td

    def test_the_initial_commit_decides(self):
        from planner.execution_policy import PILOT, SERIAL, pinned_policy
        self.assertEqual(pinned_policy(self._dest("m3-pair-pilot/v1"))["policy"], PILOT)
        self.assertEqual(pinned_policy(self._dest("deferred"))["policy"], SERIAL)
        self.assertEqual(pinned_policy(self._dest(None))["policy"], SERIAL)
        # a run created serial never becomes a pilot: not by a later commit, not by an edit of the tree
        self.assertEqual(pinned_policy(self._dest("deferred", later="m3-pair-pilot/v1"))["policy"], SERIAL)
        self.assertEqual(pinned_policy(self._dest("deferred", working="m3-pair-pilot/v1"))["policy"], SERIAL)
        # nor does a pilot declaration on another board protocol
        self.assertEqual(pinned_policy(self._dest("m3-pair-pilot/v1", protocol="serial-loop/v1"))["policy"], SERIAL)

    def test_the_dispatcher_cap_follows_the_policy(self):
        from planner.execution_policy import PILOT, SERIAL, max_in_progress
        self.assertEqual((max_in_progress(PILOT), max_in_progress(SERIAL)), (2, 1))


class PilotPublication(unittest.TestCase):
    def test_a_pilot_run_publishes_the_pair_in_worktrees_inside_one_serial_chain(self):
        r = NB.Run(pilot=True, structure=structure())
        try:
            plan = r.plan()
            self.assertEqual(plan["execution"]["selection"]["pair"], [ITEM, ORDER])
            for oid in (ITEM, ORDER):
                t = r.native.task(r.tid(oid))
                path, branch = PS.worktree_of(str(r.root.resolve()), oid)
                self.assertEqual((t["workspace_path"], t["branch_name"]), ("worktree:" + path, branch))
            others = [t for t in r.native.tasks.values() if r.board.node_of(t["id"]) and r.board.node_of(t["id"])[2] not in (ITEM, ORDER)]
            self.assertTrue(all(str(t["workspace_path"]).startswith("dir:") for t in others))
            from planner.native_publish import readback
            self.assertEqual(readback(r.board, plan), [])
            r.release()
            waves = ready_waves(r)
            self.assertIn([ITEM, ORDER], waves)
            self.assertTrue(all(len(w) == 1 for w in waves if w != [ITEM, ORDER]), waves)
        finally:
            r.close()

    def test_publication_follows_the_schedule_chain_not_only_genuine_parents(self):
        """v29 M2: publication refused PUBLICATION_PARENT -- objective:controller-request-boundary parent
        source:u:cd4a81a71d9f has no native task yet. The node after the pair depends on both pair members
        only through the schedule chain; ordered by genuine parents and the order hint alone, it was created
        before the pair member whose hint sorts later."""
        r = NB.Run(pilot=True, structure=structure(), publish=False)
        try:
            plan = json.loads(r.plan_file.read_text())
            for n in plan["nodes"]:
                if n["outcome_id"] == ORDER:
                    n["order_hint"] = ["~~~ sorts after every other hint"]
                if n["outcome_id"] == "runtime:package:rk:package:spel":
                    # like v29's objective card: a genuine dependency on ONE pair member only
                    n["parents"] = [p for p in n["parents"] if p != ORDER]
            plan.pop("digest", None)
            plan["digest"] = NB.OG.plan_digest(plan)
            r.plan_file.write_text(json.dumps(plan))
            r.out = r.publish()
            from planner.native_publish import published_parents, readback
            pub = r.plan()
            self.assertEqual(readback(r.board, pub), [])
            succ = [n for n in pub["nodes"] if ORDER in (n.get("schedule_parents") or []) and ORDER not in (n.get("parents") or [])]
            self.assertTrue(succ, "the fixture must have a node that waits on the pair member only through the chain")
            for n in succ:
                self.assertIn(r.tid(ORDER), r.native.task(r.tid(n["outcome_id"]))["parents"])
            self.assertTrue(all(set(published_parents(n)) <= {m["outcome_id"] for m in pub["nodes"]} | {"control:m2"}
                                for n in pub["nodes"]))
        finally:
            r.close()

    def test_a_serial_run_is_unchanged(self):
        r = NB.Run(pilot=False, structure=structure())
        try:
            self.assertNotIn("execution", r.plan())
            self.assertTrue(all(not t.get("branch_name") for t in r.native.tasks.values()))
        finally:
            r.close()

    def test_a_pilot_run_with_no_qualifying_pair_publishes_a_plain_chain_and_says_so(self):
        r = NB.Run(pilot=True, structure=structure(order_refs=("dto.ItemDto", "web.ItemController")))
        try:
            sel = r.plan()["execution"]["selection"]
            self.assertEqual(sel["pair"], [])
            self.assertIn("no pair", sel["why"])
            r.release()
            self.assertTrue(all(len(w) == 1 for w in ready_waves(r)))
        finally:
            r.close()


class Worktrees:
    """A pilot run driven to its pair, with REAL git worktrees made the way the pinned runtime makes them
    (``git worktree add -b <branch> <path> HEAD`` from the destination) and the loop's board side driven
    through the production native_control / pilot code. run-verify.sh and advance.py on the main tree are
    replaced by a runner that measures the combined tree and records verdicts exactly as the bridge does."""

    def __init__(self, decisions=None):
        import os as _os
        self.os = _os
        self.r = NB.Run(pilot=True, structure=structure())
        NB.mirror_layout(self.r.root)       # the pinned harness (tracked in a real destination)
        self.r.release()
        for oid in ("build:rk:pom", "config:rk:cfg", "source:u:dto-mapper"):
            self.r.accept(oid, classes=("build", "compile", "tests"))
        self.decisions = decisions or {}
        self.observed = {}           # task -> the main tree's pair files as verification saw them
        self.fail_verify_once = set()
        self.saved_env = {k: self.os.environ.get(k) for k in ("HERMES_KANBAN_TASK", "HERMES_KANBAN_RUN_ID", PL.INTEGRATION_ENV)}
        self.orig = NC.board_for
        NC.board_for = lambda root, native=None: NC.Board(self.r.native, author="implementer")

    def close(self):
        NC.board_for = self.orig
        for k, v in self.saved_env.items():
            (self.os.environ.pop(k, None) if v is None else self.os.environ.__setitem__(k, v))
        self.r.close()

    def env(self, tid, run):
        self.os.environ.update(HERMES_KANBAN_TASK=tid, HERMES_KANBAN_RUN_ID=str(run))
        self.os.environ.pop(PL.INTEGRATION_ENV, None)

    def start(self, oid):
        """The dispatcher claims the task; the runtime materializes its worktree; the worker issues."""
        tid = self.r.tid(oid)
        path, branch = PS.worktree_of(str(self.r.root.resolve()), oid)
        NB.git(self.r.root, "worktree", "add", "-q", "-b", branch, path, "HEAD")
        if not (Path(path) / ".hermes" / "lib").exists():
            NB.mirror_layout(Path(path))   # a real worktree carries the tracked harness; the fixture links it
        run, _lock = self.r.native.claim(tid)
        self.env(tid, run)
        wt = Path(path)
        PL.seed(wt, task=tid, run=run)
        iss = NC.issue(wt, self.r.board, task_id=tid, run_id=run)
        from native_gate import write_issued_projection
        write_issued_projection(wt, iss)
        return tid, run, wt, iss

    def accept_in_worktree(self, tid, run, wt, iss, text=None):
        """The worktree loop accepts a candidate (advance.py through the bridge, worktree namespace)."""
        self.env(tid, run)
        rel = iss["allowed_paths"][0]
        (wt / rel).write_text(text or "// %s repaired in its worktree\n" % rel)
        cand = NC._product_tree(wt)
        att = PL.attempt_key(wt, cand)
        self.assert_(att.startswith("wt-"))
        NC.record_verdict(wt, self.r.board, task_id=tid, run_id=run, verdict="ACCEPTED", candidate=cand, attempt=att)
        NB.git(wt, "add", "-A")
        NB.git(wt, "commit", "-qm", "accept %s in worktree" % tid)
        commit = NB.git(wt, "rev-parse", "HEAD")
        steps_p = wt / "verification" / "loop" / "steps.json"
        steps = json.loads(steps_p.read_text()) if steps_p.is_file() else {"steps": []}
        steps["steps"].append({"card": tid, "commit": commit, "verdict": "accepted"})
        steps_p.parent.mkdir(parents=True, exist_ok=True)
        steps_p.write_text(json.dumps(steps))
        self._drop_owned(wt, tid)
        return NC.accept_commit(wt, self.r.board, task_id=tid, run_id=run, attempt=att, commit=commit,
                                measurement={"classes": ["build", "compile", "tests"]}, extra={"pilot": "worktree"})

    def _drop_owned(self, root, tid):
        oid = self.r.board.node_of(tid)[2]
        owned = NC.owned(self.r.plan(), NC._node(self.r.plan(), oid))
        wl_p = root / NB.WORKLIST
        wl = json.loads(wl_p.read_text())
        wl["items"] = [i for i in wl["items"] if i["id"] not in owned]
        for c in wl["clusters"]:
            c["items"] = [i for i in c["items"] if i not in owned]
        wl["clusters"] = [c for c in wl["clusters"] if c["items"]]
        wl_p.write_text(json.dumps(wl))
        if root == self.r.root:
            self.r.worklist = wl

    def runner(self, argv, env, log):
        canon = self.r.root
        tid = env["HERMES_KANBAN_TASK"]
        run = int(env["HERMES_KANBAN_RUN_ID"])
        saved = self.os.environ.get(PL.INTEGRATION_ENV)
        self.os.environ[PL.INTEGRATION_ENV] = "1"
        try:
            if argv[1].endswith("run-verify.sh"):
                if tid in self.fail_verify_once:
                    self.fail_verify_once.discard(tid)
                    raise KeyboardInterrupt("interrupted after the apply, before verification")
                self.observed[tid] = {p: (canon / p).read_text() for p in (W + "web/ItemController.java", W + "web/OrderController.java")}
                return 0
            cand = NC._product_tree(canon)
            att = PL.attempt_key(canon, cand)
            la = canon / "verification" / "loop" / "last-advance.json"
            if self.decisions.get(tid) == "reject":
                NC.record_verdict(canon, self.r.board, task_id=tid, run_id=run, verdict="REVERTED", candidate=cand,
                                  attempt=att, reason="combined tree regressed")
                NB.git(canon, "reset", "-q", "--hard", "HEAD")      # advance.py's revert of the candidate paths
                la.write_text(json.dumps({"card": tid, "verdict": "REVERTED", "reason": "combined tree regressed"}))
                return 1
            NC.record_verdict(canon, self.r.board, task_id=tid, run_id=run, verdict="ACCEPTED", candidate=cand, attempt=att)
            NB.git(canon, "add", "-A")
            NB.git(canon, "commit", "-qm", "integrate %s" % tid)
            commit = NB.git(canon, "rev-parse", "HEAD")
            steps_p = canon / "verification" / "loop" / "steps.json"
            steps = json.loads(steps_p.read_text()) if steps_p.is_file() else {"steps": []}
            steps["steps"].append({"card": tid, "commit": commit, "verdict": "accepted", "pilot_wt_commit": env[PL.WT_COMMIT_ENV]})
            steps_p.parent.mkdir(parents=True, exist_ok=True)
            steps_p.write_text(json.dumps(steps))
            self._drop_owned(canon, tid)
            NC.accept_commit(canon, self.r.board, task_id=tid, run_id=run, attempt=att, commit=commit,
                             measurement={"classes": ["build", "compile", "tests"]}, extra={"pilot": "integration"})
            la.write_text(json.dumps({"card": tid, "verdict": "ACCEPTED"}))
            return 0
        finally:
            (self.os.environ.pop(PL.INTEGRATION_ENV, None) if saved is None else self.os.environ.__setitem__(PL.INTEGRATION_ENV, saved))

    def integrate(self, tid, run, wt):
        self.env(tid, run)
        return PL.integrate(wt, self.r.board, task_id=tid, run_id=run, runner=self.runner)

    def assert_(self, cond):
        assert cond


class Qualification(unittest.TestCase):
    def setUp(self):
        self.w = Worktrees()
        self.addCleanup(self.w.close)

    def test_the_pair_runs_isolated_integrates_serially_and_the_second_is_verified_combined(self):
        w, r = self.w, self.w.r
        head0 = NB.git(r.root, "rev-parse", "HEAD")
        (ta, ra, wa, ia), (tb, rb, wb, ib) = w.start(ITEM), w.start(ORDER)
        # both live at once, each in its own worktree from the same verified baseline
        self.assertEqual({r.native.task(ta)["status"], r.native.task(tb)["status"]}, {"running"})
        self.assertEqual(PL.seeded(wa)["canonical_head"], PL.seeded(wb)["canonical_head"])
        self.assertEqual(PL.seeded(wa)["canonical_head"], head0)
        # isolated mutable state: separate issuance projections, neither in the main tree
        self.assertEqual(json.loads((wa / "verification/loop/issued.json").read_text())["task_id"], ta)
        self.assertEqual(json.loads((wb / "verification/loop/issued.json").read_text())["task_id"], tb)
        w.accept_in_worktree(ta, ra, wa, ia)
        w.accept_in_worktree(tb, rb, wb, ib)
        self.assertEqual(NB.git(r.root, "status", "--porcelain", "--", "src"), "")      # the main tree untouched
        self.assertNotIn("repaired", (wb / ia["allowed_paths"][0]).read_text())       # A's edit is not in B's tree
        # the terminator refuses an unintegrated pair outcome
        with self.assertRaises(NC.Refusal) as cm:
            NC.check_terminator(r.root, r.board, task_id=ta, run_id=ra, kind="request_review", profile="implementer",
                                audit_green=lambda: False)
        self.assertEqual(cm.exception.code, "PILOT_NOT_INTEGRATED")
        a = w.integrate(ta, ra, wa)
        self.assertEqual(a["status"], "INTEGRATED")
        b = w.integrate(tb, rb, wb)
        self.assertEqual(b["status"], "INTEGRATED")
        # the second integration was verified on the COMBINED tree: A's change was already in it
        self.assertIn("repaired", w.observed[tb][ia["allowed_paths"][0]])
        self.assertIn("repaired", w.observed[tb][ib["allowed_paths"][0]])
        self.assertEqual(NB.git(r.root, "rev-list", "--count", "%s..HEAD" % head0), "2")
        # replaying an integration applies nothing twice
        again = w.integrate(ta, ra, wa)
        self.assertTrue(again["replayed"])
        self.assertEqual(NB.git(r.root, "rev-list", "--count", "%s..HEAD" % head0), "2")
        # M4 waits until both pair outcomes are done; A still stands after B's integration (sibling tolerance)
        m4 = r.tid("assess:m4:g1")
        r.review_and_complete(ta, ra)
        self.assertEqual(r.native.task(m4)["status"], "todo")
        r.review_and_complete(tb, rb)

    def test_a_sibling_integration_in_flight_does_not_unaccept_the_integrated_member(self):
        """v29 t_0b68019a: its reviewer ran while the sibling's integration had applied its candidate to the main
        tree (integrate-begin; not yet verified or committed). Completion refused OUTCOME_NOT_ACCEPTED ("the tree is
        now ...") and the reviewer blocked asking the Operator. The sibling's own transaction explains exactly
        those uncommitted paths; anything else uncommitted still refuses."""
        w, r = self.w, self.w.r
        (ta, ra, wa, ia), (tb, rb, wb, ib) = w.start(ITEM), w.start(ORDER)
        w.accept_in_worktree(ta, ra, wa, ia)
        w.accept_in_worktree(tb, rb, wb, ib)
        self.assertEqual(w.integrate(ta, ra, wa)["status"], "INTEGRATED")
        w.fail_verify_once.add(tb)
        with self.assertRaises(KeyboardInterrupt):
            w.integrate(tb, rb, wb)
        self.assertTrue(NB.git(r.root, "status", "--porcelain", "--", "src"))   # B's candidate sits uncommitted on main
        plan = r.plan()
        node = NC._node(plan, ITEM)
        ok, why = NC.outcome_acceptance(r.root, r.board, ta, plan, node)
        self.assertTrue(ok, why)
        (r.root / W / "web" / "Stray.java").write_text("class Stray {}\n")        # not the sibling's: still refused
        ok, why = NC.outcome_acceptance(r.root, r.board, ta, plan, node)
        self.assertFalse(ok)

    def test_one_workers_rollback_leaves_its_sibling_and_the_main_tree_intact(self):
        w, r = self.w, self.w.r
        (ta, ra, wa, ia), (tb, rb, wb, ib) = w.start(ITEM), w.start(ORDER)
        (wa / ia["allowed_paths"][0]).write_text("// half-done edit\n")
        (wb / ib["allowed_paths"][0]).write_text("// sibling work in progress\n")
        NB.git(wa, "checkout", "--", ".")                                   # A rolls back its candidate
        self.assertEqual((wb / ib["allowed_paths"][0]).read_text(), "// sibling work in progress\n")
        self.assertEqual(NB.git(r.root, "status", "--porcelain", "--", "src"), "")
        self.assertTrue((wb / "verification/loop/issued.json").is_file())

    def test_an_interrupted_integration_resumes_without_applying_twice(self):
        w, r = self.w, self.w.r
        head0 = NB.git(r.root, "rev-parse", "HEAD")
        ta, ra, wa, ia = w.start(ITEM)
        w.accept_in_worktree(ta, ra, wa, ia)
        w.fail_verify_once.add(ta)
        with self.assertRaises(KeyboardInterrupt):
            w.integrate(ta, ra, wa)
        # the candidate is half-applied on the main tree, recorded as begun
        self.assertNotEqual(NB.git(r.root, "status", "--porcelain", "--", "src"), "")
        out = w.integrate(ta, ra, wa)
        self.assertEqual(out["status"], "INTEGRATED")
        self.assertEqual(NB.git(r.root, "rev-list", "--count", "%s..HEAD" % head0), "1")
        self.assertEqual(len(r.board.records(ta, "integrated")), 1)

    def test_a_conflict_returns_to_same_card_rework_without_spending_or_completing(self):
        w, r = self.w, self.w.r
        (ta, ra, wa, ia), (tb, rb, wb, ib) = w.start(ITEM), w.start(ORDER)
        w.accept_in_worktree(ta, ra, wa, ia)
        self.assertEqual(w.integrate(ta, ra, wa)["status"], "INTEGRATED")
        # B's candidate also edits A's file on its old baseline (an overlap the selection would never pick,
        # forced here): it cannot apply over A's integration
        (wb / ia["allowed_paths"][0]).write_text("// B's conflicting view\n")
        plan = r.plan()
        node = NC._node(plan, ORDER)
        spent0 = NC.budget_state(r.board, r.run_id, plan, node)["spent"]
        issues = [x for x in r.board.records(tb, "issue") if int(x["run"]) == rb]
        forced = dict(issues[-1], allowed_paths=sorted(set(issues[-1]["allowed_paths"]) | {ia["allowed_paths"][0]}))
        r.board.record(tb, "issue", "issue:%d:99" % rb, **{k: v for k, v in forced.items() if k not in ("key", "kind", "v", "_id")})
        w.accept_in_worktree(tb, rb, wb, ib)
        out = w.integrate(tb, rb, wb)
        self.assertEqual(out["status"], "CONFLICT")
        self.assertEqual(NB.git(r.root, "status", "--porcelain", "--", "src"), "")           # main tree unchanged
        self.assertEqual(NC.budget_state(r.board, r.run_id, plan, node)["spent"], spent0)    # no attempt spent
        with self.assertRaises(NC.Refusal):
            NC.check_terminator(r.root, r.board, task_id=tb, run_id=rb, kind="request_review", profile="implementer",
                                audit_green=lambda: False)
        rb2 = PL.rebase(wb, r.board, task_id=tb, run_id=rb)
        self.assertEqual(rb2["status"], "REBASED")
        self.assertIn("kept at refs/pilot/", rb2["outcome"])
        self.assertEqual(NB.git(wb, "rev-parse", "HEAD"), NB.git(r.root, "rev-parse", "HEAD"))

    def test_a_rejected_combined_tree_is_a_genuine_rejection_and_restores_the_main_tree(self):
        w = self.w
        w.decisions = {}
        r = w.r
        (ta, ra, wa, ia), (tb, rb, wb, ib) = w.start(ITEM), w.start(ORDER)
        w.accept_in_worktree(ta, ra, wa, ia)
        w.accept_in_worktree(tb, rb, wb, ib)
        self.assertEqual(w.integrate(ta, ra, wa)["status"], "INTEGRATED")
        head_a = NB.git(r.root, "rev-parse", "HEAD")
        plan = r.plan()
        node = NC._node(plan, ORDER)
        spent0 = NC.budget_state(r.board, r.run_id, plan, node)["spent"]
        w.decisions[tb] = "reject"
        out = w.integrate(tb, rb, wb)
        self.assertEqual((out["status"], out["verdict"]), ("REJECTED", "REVERTED"))
        self.assertEqual(NB.git(r.root, "rev-parse", "HEAD"), head_a)                        # A's accepted state kept
        self.assertEqual(NB.git(r.root, "status", "--porcelain", "--", "src"), "")
        self.assertEqual(NC.budget_state(r.board, r.run_id, plan, node)["spent"], spent0 + 1)
        self.assertEqual(r.native.task(r.tid("assess:m4:g1"))["status"], "todo")


if __name__ == "__main__":
    unittest.main(verbosity=1)
