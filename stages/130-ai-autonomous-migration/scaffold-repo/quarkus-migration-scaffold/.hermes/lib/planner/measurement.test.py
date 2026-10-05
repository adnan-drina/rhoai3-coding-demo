#!/usr/bin/env python3
"""v24 WP2: a measurement class is what the verification of THIS candidate
executed, never a stamp; the full test suite an early compile card cannot run
is an explicit M4 obligation naming its origin, and M4 refuses full
acceptance until a bound, executed suite passes."""
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIB = HERE.parent
sys.path.insert(0, str(LIB))
from planner import measurement as M  # noqa: E402
from planner import native_control as NC  # noqa: E402
from planner.outcome_checks import Refusal  # noqa: E402

_spec = importlib.util.spec_from_file_location("native_board_harness", HERE / "native_board.test.py")
NB = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(NB)

T = "a" * 64


def wl(ce=0, ft=0, tree=T, reports=1):
    return {"candidate_sha256": tree, "measure": {"compile_errors": ce, "failing_tests": ft, "known": True, "blocked": []},
            "sources": {"surefire": {"reports": reports} if reports else None}, "runtime": {}}


def run(tree=T, tests=True, rc=0, cp_rc=0):
    return {"candidate_sha256": tree, "mode": "acceptance", "classpath": {"ran": True, "rc": cp_rc},
            "diagnostics": {"ran": True, "rc": 0}, "tests": {"ran": tests, "rc": rc if tests else None}}


class Execution(unittest.TestCase):
    def test_compile_failures_and_no_test_report_give_no_test_credit(self):
        ex = M.execution(wl(ce=233, reports=0), run(tests=False), T)
        self.assertEqual(ex["stages"]["tests"]["state"], "blocked")
        self.assertEqual(M.classes(ex), ["build", "compile"])       # the v23 baseline [4, 233, 0]: no tests
        self.assertEqual(M.tests_status(ex)[0], "unknown")

    def test_a_matching_producer_record_supplies_the_status(self):
        ok = M.execution(wl(), run(), T)
        self.assertEqual((ok["stages"]["tests"]["state"], M.tests_status(ok)[0]), ("passed", "pass"))
        self.assertIn("tests", M.classes(ok))
        bad = M.execution(wl(ft=2), run(rc=1), T)
        self.assertEqual((bad["stages"]["tests"]["state"], M.tests_status(bad)[0]), ("failed", "fail"))

    def test_clean_tree_with_missing_stale_or_wrong_tree_report_refuses(self):
        for ex in (M.execution(wl(reports=0), run(), T),                 # tests ran, no surefire report
                   M.execution(wl(tree="b" * 64), run(tree="b" * 64), T),  # a record of another tree
                   M.execution(wl(), run(tree="c" * 64), T),               # work list and run disagree
                   M.execution(wl(), run(tests=False), T)):                # not run
            self.assertEqual(M.tests_status(ex)[0], "unknown", ex["stages"]["tests"])
            self.assertNotIn("tests", M.classes(ex))
        self.assertEqual(M.classes(M.execution(wl(), run(tree="c" * 64), T)), [])

    def test_a_label_is_never_a_result(self):
        self.assertEqual(M.classes({"bound": True, "stages": {}}), [])
        self.assertEqual(M.classes(None), [])

    def test_needed_classes_read_the_declared_checks(self):
        self.assertEqual(M.needed_classes({"acceptance": {"checks": ["worklist-absent", "measure:compile", "measure:tests"]}}),
                         {"compile", "tests"})
        self.assertEqual(M.needed_classes({"acceptance": {"checks": ["worklist-absent", "measure:compile"]}}), {"compile"})
        self.assertEqual(M.needed_classes({"acceptance": {"checks": ["worklist-absent", "parity:scenarios"]}}), {"parity"})


class ParityStage(unittest.TestCase):
    """Review F3: requested scope, actual execution and the bound receipt's
    verdict are three things; a requested scenario list is never a PASS."""

    def _root(self, receipt=None, mode="disabled"):
        import tempfile
        from planner.worklist import parity_receipt_file
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        root = Path(td.name)
        if receipt is not None:
            f = root / parity_receipt_file(mode)
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps(receipt))
        return root

    @staticmethod
    def receipt(verdict_by_sc, *, tree=T, mode="disabled", overall=None):
        rows = [{"entry_point": "ep:acme.Api#%s():http" % sc, "verdict": v, "scenarios": [sc]} for sc, v in sorted(verdict_by_sc.items())]
        return {"schema": "rhoai3.parity-receipt/v1", "security_mode": mode, "binding": {"mode": "candidate", "candidate_sha256": tree},
                "verdict": overall or ("PASS" if all(v == "PASS" for v in verdict_by_sc.values()) else "FAIL"), "entry_points": rows}

    @staticmethod
    def par(scenarios=(), ran=True, rc=0, mode="disabled"):
        r = run()
        r["runtime"] = {"parity": {"ran": ran, "rc": rc, "scoped": bool(scenarios), "scenarios": list(scenarios),
                                   "read_oracles_rerun": [], "security_mode": mode}}
        return r

    def st(self, run_doc, root):
        return M.execution(wl(), run_doc, T, root)["stages"]["parity"]

    def test_requested_but_not_run(self):
        s = self.st(self.par(["sc:a"], ran=False), self._root())
        self.assertEqual((s["state"], s["requested"], s["scenarios"]), ("not-run", ["sc:a"], []))

    def test_failed_run_without_receipt_is_not_a_pass(self):
        s = self.st(self.par(["sc:a"], rc=1), self._root())
        self.assertEqual(s["state"], "unknown")
        self.assertNotIn("parity", M.classes(M.execution(wl(), self.par(["sc:a"], rc=1), T, self._root())))

    def test_fail_and_inconclusive_verdicts_are_kept(self):
        self.assertEqual(self.st(self.par(["sc:a"], rc=1), self._root(self.receipt({"sc:a": "FAIL"})))["state"], "failed")
        self.assertEqual(self.st(self.par(["sc:a"]), self._root(self.receipt({"sc:a": "INCONCLUSIVE"})))["state"], "unknown")

    def test_wrong_tree_and_wrong_mode_receipts_do_not_count(self):
        self.assertEqual(self.st(self.par(["sc:a"]), self._root(self.receipt({"sc:a": "PASS"}, tree="b" * 64)))["state"], "unknown")
        self.assertEqual(self.st(self.par(["sc:a"], mode="enabled"),
                                 self._root(self.receipt({"sc:a": "PASS"}, mode="disabled"), mode="enabled"))["state"], "unknown")

    def test_scoped_pass_names_only_what_it_measured(self):
        s = self.st(self.par(["sc:a", "sc:b"]), self._root(self.receipt({"sc:a": "PASS", "sc:b": "PASS"})))
        self.assertEqual((s["state"], s["scenarios"]), ("passed", ["sc:a", "sc:b"]))
        s = self.st(self.par(["sc:a", "sc:c"]), self._root(self.receipt({"sc:a": "PASS"})))   # sc:c not in the receipt
        self.assertEqual((s["state"], s["scenarios"]), ("unknown", ["sc:a"]))

    def test_unscoped_pass_by_the_receipt_verdict_and_rc_is_not_a_verdict(self):
        s = self.st(self.par([]), self._root(self.receipt({"sc:a": "PASS", "sc:b": "PASS"})))
        self.assertEqual((s["state"], s["scenarios"]), ("passed", ["sc:a", "sc:b"]))
        s = self.st(self.par([], rc=1), self._root(self.receipt({"sc:a": "PASS"})))       # rc alone decides nothing
        self.assertEqual(s["state"], "passed")


class Placement(unittest.TestCase):
    def test_source_tests_move_to_m4_with_their_origin_and_owner_repairs_keep_them(self):
        plan = NB.derive()
        for n in plan["nodes"]:
            if n.get("class") == "source" and n.get("role") == "repair":
                owner = n
                break
        rep = dict(owner, outcome_id="repair:x:for:y", lineage=[{"repairs": owner["outcome_id"]}],
                   acceptance={"checks": ["measure:compile", "measure:tests"]})
        plan["nodes"].append(rep)
        out = NC.native_plan(plan)
        node = {n["outcome_id"]: n for n in out["nodes"]}
        rows = node["assess:m4:g1"]["acceptance"]["deferred_requirement_checks"]
        self.assertIn({"outcome": owner["outcome_id"], "requirements": sorted(owner.get("requirements") or []),
                       "check": "measure:tests"}, rows)
        self.assertNotIn("measure:tests", node[owner["outcome_id"]]["acceptance"]["checks"])
        self.assertIn("measure:compile", node[owner["outcome_id"]]["acceptance"]["checks"])   # scoped compile stays immediate
        self.assertIn("measure:tests", node["repair:x:for:y"]["acceptance"]["checks"])       # an owner repair runs after compile
        self.assertEqual(NC.native_revision(out), out)                                         # idempotent


class Staging(unittest.TestCase):
    """An early scoped repair progresses without a test run; the suite stays an
    obligation of M4, which refuses until a bound, executed suite passes."""

    def test_early_repair_then_m4_refuses_until_the_suite_passes(self):
        r = NB.Run()
        try:
            r.release()
            r.drop("inc:unlocatable:jndi")
            src = next(n["outcome_id"] for n in NB.OG.topo_order(r.plan()["nodes"]) if n.get("class") == "source")
            # every repair accepted WITHOUT a tests class: the compile tree could not run the suite
            for n in NB.OG.topo_order(r.plan()["nodes"]):
                if n["role"] != "repair" or NB.status(r, r.tid(n["outcome_id"])) == "done":
                    continue
                cls = ("build", "compile") + {"runtime": ("runtime",), "behavior": ("runtime", "parity")}.get(n["class"], ())
                r.accept(n["outcome_id"], classes=cls, scenarios=n.get("scenarios") or ())
            self.assertEqual(NB.status(r, r.tid(src)), "done")
            m4 = r.tid("assess:m4:g1")
            for tests, code in ((None, "ASSESS_TESTS_UNMEASURED"), ("failed", "ASSESS_TESTS_UNMEASURED")):
                tid, run_, out = r.assess("PROVISIONAL_ACCEPT", tests=tests)
                with self.assertRaises(Refusal) as cm:
                    NC.check_terminator(r.root, r.board, task_id=m4, run_id=run_, kind="request_review",
                                        profile="implementer", audit_green=lambda: True)
                self.assertEqual(cm.exception.code, code)
                owed = sum(1 for n in r.plan()["nodes"] if n.get("class") == "source" and n.get("role") == "repair")
                self.assertIn("owed to M4 by %d outcome(s)" % owed, cm.exception.detail)
                self.assertIn("|measure:tests", cm.exception.detail)
                with self.assertRaises(Refusal) as cm:
                    NC.m4_repair(r.root, r.board, task_id=m4, run_id=run_)
                self.assertEqual(cm.exception.code, "M4_TESTS_UNMEASURED")   # never a follow-up per early outcome
                r.native.block_dependency(m4)
                r.native.unblock(m4) if hasattr(r.native, "unblock") else None
            tid, run_, out = r.assess("PROVISIONAL_ACCEPT", tests="passed")
            d = NC.check_terminator(r.root, r.board, task_id=m4, run_id=run_, kind="request_review",
                                    profile="implementer", audit_green=lambda: True)
            self.assertEqual(d["action"], "allow")
        finally:
            r.close()


if __name__ == "__main__":
    unittest.main(verbosity=1)
