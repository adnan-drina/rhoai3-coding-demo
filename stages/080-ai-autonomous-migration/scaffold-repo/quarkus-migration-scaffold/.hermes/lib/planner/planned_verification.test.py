"""v29 Owner: a planned verification-only unit, end to end.

The last repair of a behavior outcome is accepted; no repair cluster is open; the outcome's planned
behavior-verification checks are still unknown. The next issue is a planned unit with an EMPTY write set
that carries its complete verification scope (scenarios per security mode, from the admitted plan and the
bound corpora); the projection carries it; run-verify's parity plan compares every required mode; the
multi-mode stage and the requirement checks judge only measured PASS records of this tree; the outcome
is accepted and goes to native review. Negative cases: a missing scenario, an INCONCLUSIVE record, a stale
receipt, and a disabled PASS beside an enabled FAIL each leave the outcome unfinished.

Run: PYTHONDONTWRITEBYTECODE=1 python3 .hermes/lib/planner/planned_verification.test.py
"""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
HERMES = HERE.parent.parent
_spec = importlib.util.spec_from_file_location("native_board_planned_verification", HERE / "native_board.test.py")
T = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(T)
sys.path.insert(0, str(HERMES / "kernel"))
from planner import measurement as ME  # noqa: E402
from planner import native_control as NC  # noqa: E402
from planner import outcome_graph as OG  # noqa: E402
from planner.outcome_checks import Refusal  # noqa: E402
from planner.paths import LOOP_ISSUED, VERIFY_RUN  # noqa: E402
import native_gate as NG  # noqa: E402

BEH = "behavior:http:com.acme.shop.web.ItemController"
EP = "ep:com.acme.shop.web.ItemController#list():http"
ITEM_FILE = "src/main/java/com/acme/shop/web/ItemController.java"
RID = "req:behavior-verification:" + EP
CHECKS = ["parity:sc:items-list", "parity:sc:auth-anonymous-items-list", "location:" + EP]
# items-create measures the Location; items-get-1 / items-get-missing / items-list are the outcome's own scenarios
DISABLED = ["sc:items-create", "sc:items-get-1", "sc:items-get-missing", "sc:items-list"]
ENABLED = ["sc:auth-anonymous-items-list"]
RUN_VERIFY = HERMES / "skills" / "migration" / "fix-until-green" / "scripts" / "run-verify.sh"


def parity_plan_program() -> str:
    text = RUN_VERIFY.read_text()
    m = re.search(r'PARITY_PLAN="\$\(python3 - [^\n]*\n(.*?)\nPYEOF\n', text, re.S)
    assert m, "could not extract the parity plan from run-verify.sh"
    return m.group(1)


class PlannedVerification(unittest.TestCase):
    def setUp(self):
        r = self.r = T.Run(publish=False)
        plan = json.loads(r.plan_file.read_text())
        node = next(n for n in plan["nodes"] if n["outcome_id"] == BEH)
        node["requirements"] = [RID]
        node["acceptance"] = dict(node.get("acceptance") or {}, requirement_checks=CHECKS)
        node["check_plan"] = [{"requirement": RID, "check": c, "stage": "immediate", "prerequisites": []} for c in CHECKS]
        plan["requirements"] = [{"id": RID, "rule": "behavior-verification", "class": "behavior", "acceptance": CHECKS,
                                 "facts": {"kind": "http", "location": {"builds_location": True, "coverage": ["sc:items-create"]}}}]
        plan.pop("digest", None)
        plan["digest"] = OG.plan_digest(plan)
        r.plan_file.write_text(json.dumps(plan))
        r.out = r.publish()
        r.release()
        r.drop("inc:unlocatable:jndi")
        for n in OG.topo_order(r.plan()["nodes"]):
            if n["role"] == "repair" and n["class"] != "behavior":
                r.accept(n["outcome_id"], classes=("build", "compile", "tests") + (("runtime",) if n["class"] == "runtime" else ()),
                         scenarios=n.get("scenarios") or ())
        for mode_dir, sids in (("scenarios", DISABLED), ("scenarios-enabled", ENABLED)):
            p = r.root / "verification" / mode_dir / "corpus.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps({"schema": "rhoai3.scenario-corpus/v1",
                                     "scenarios": [{"id": s, "entry_point": EP, "method": "GET", "path": "/items"} for s in sids]}))
        # the behavior outcome's last repair: a cluster of its own verify obligations
        own = NC._node(r.plan(), BEH)["obligations"]
        r.worklist["items"] += [{"id": o, "category": "mandatory", "kind": "parity", "source": "parity", "path": ITEM_FILE,
                                 "entry_point": o.split("verify:", 1)[1]} for o in own]
        r.worklist["clusters"].append({"id": "c:item-beh", "items": list(own), "kind": "parity", "path": ITEM_FILE,
                                       "status": "open", "write_set": [ITEM_FILE]})
        r.worklist["candidate_sha256"] = r.tree()
        r.save_worklist()

    def tearDown(self):
        self.r.close()

    # -- the chain up to the verification issue ------------------------------
    def repair_then_verification_issue(self):
        r = self.r
        tid, run, iss = r.issue(BEH)
        self.assertEqual(iss["cluster"], "c:item-beh")
        acc = r.accept_on_run(tid, run, iss)                                   # last repair accepted, cluster closed
        self.assertFalse(acc["outcome_accepted"])                              # its checks are still unknown
        r.worklist["candidate_sha256"] = r.tree()
        r.save_worklist()
        ver = NC.issue(r.root, r.board, task_id=tid, run_id=run)
        return tid, run, ver

    def evidence(self, tree, *, enabled_verdict="PASS", record_verdicts=None, enabled_tree=None, drop=()):
        """What run-verify leaves after comparing both modes: a receipt per mode bound to its candidate,
        one verdict record per scenario, and run.json naming the modes it ran."""
        r = self.r
        verdicts = {s: "PASS" for s in DISABLED + ENABLED}
        verdicts.update({s: enabled_verdict for s in ENABLED})
        verdicts.update(record_verdicts or {})
        pdir = r.root / "verification" / "parity"
        for mode, sids, rname, sub, bound in (("disabled", DISABLED, "receipt.json", "scenarios", tree),
                                              ("enabled", ENABLED, "receipt-enabled.json", "scenarios-enabled", enabled_tree or tree)):
            (pdir / sub).mkdir(parents=True, exist_ok=True)
            kept = [s for s in sids if s not in drop]
            row_v = "FAIL" if any(verdicts[s] == "FAIL" for s in kept) else "PASS"
            (pdir / rname).write_text(json.dumps({
                "schema": "rhoai3.parity-receipt/v1", "security_mode": mode, "verdict": row_v,
                "binding": {"mode": "candidate", "candidate_sha256": bound},
                "entry_points": [{"entry_point": EP, "verdict": row_v, "scenarios": kept}]}))
            for s in kept:
                (pdir / sub / ("%s.json" % s.replace(":", "_"))).write_text(json.dumps({
                    "schema": "rhoai3.scenario-parity/v1", "scenario": s, "entry_point": EP, "verdict": verdicts[s],
                    "security_mode": mode, "binding": {"mode": "candidate", "candidate_sha256": bound}}))
        run_doc = {"candidate_sha256": tree, "mode": "acceptance", "classpath": {"ran": True, "rc": 0},
                   "diagnostics": {"ran": True}, "tests": {"ran": True, "rc": 0},
                   "runtime": {"parity": {"ran": True, "rc": 0, "trigger": "issued-card", "scoped": True,
                                          "scenarios": DISABLED + ENABLED, "security_mode": "disabled",
                                          "modes": {"disabled": {"rc": 0, "scenarios": DISABLED},
                                                    "enabled": {"rc": 0, "scenarios": ENABLED}}}}}
        (r.root / VERIFY_RUN).parent.mkdir(parents=True, exist_ok=True)
        (r.root / VERIFY_RUN).write_text(json.dumps(run_doc))
        r.worklist.update({"candidate_sha256": tree, "measure": {"known": True, "tuple": [0, 0, 0], "compile_errors": 0,
                                                                 "failing_tests": 0},
                           "runtime": {"package": {"ran": True, "rc": 0}, "boot": {"ran": True, "rc": 0, "ready": True},
                                       "ready": True},
                           "sources": {"surefire": {"reports": 1}}})
        r.save_worklist()
        return run_doc

    def judge(self, tid, run):
        r = self.r
        wl = json.loads((r.root / "evidence" / "planning" / "worklist.json").read_text())
        run_doc = json.loads((r.root / VERIFY_RUN).read_text())
        ex = ME.execution(wl, run_doc, "", r.root)
        m = {"classes": ME.classes(ex), "scenarios": list(ex["stages"]["parity"].get("scenarios") or []), "execution": ex}
        return NC.evaluate_recovered(r.root, r.board, task_id=tid, run_id=run, measurement=m), ex["stages"]["parity"]

    # -- the transition ---------------------------------------------------------
    def test_repair_accepted_then_verification_issued_measured_judged_and_reviewed(self):
        r = self.r
        tid, run, ver = self.repair_then_verification_issue()
        self.assertTrue(ver["cluster"].startswith("planned:"), ver["cluster"])
        self.assertEqual(ver["allowed_paths"], [])                             # verification only: no product edit
        scope = ver["planned_unit"]["verification"]
        self.assertEqual(scope["scenarios_by_mode"], {"disabled": DISABLED, "enabled": ENABLED})
        self.assertEqual(scope["unresolved"], [])
        # the projection carries it, beside the planned-unit gate (the card reads the decided schemas)
        for name in ("planning", "lib"):                                         # as mirror_layout does
            link = r.root / ".hermes" / name
            if not link.exists():
                link.symlink_to(HERMES / name)
        NG.write_issued_projection(r.root, ver)
        issued = json.loads((r.root / LOOP_ISSUED).read_text())
        self.assertEqual((issued["gate"], issued["verification"]["scenarios_by_mode"]),
                         ("planned-unit", {"disabled": DISABLED, "enabled": ENABLED}))
        # the worker is told the one executable action, and a unit without a scope is a named harness error
        sys.path.insert(0, str(HERMES / "skills" / "migration" / "fix-until-green" / "scripts"))
        import brief as B
        nxt = B.verification_next(issued, ver["cluster"])
        self.assertIn("VERIFICATION ONLY", nxt)
        self.assertIn("4 disabled-mode scenario(s), 1 enabled-mode scenario(s)", nxt)
        self.assertIn("run-verify.sh --root . --mode acceptance", nxt)
        self.assertIn("HARNESS ERROR VERIFICATION_SCOPE_MISSING", B.verification_next(dict(issued, verification=None), ver["cluster"]))
        # run-verify compares every required mode, one after the other, and nothing else
        boot = r.root / "verification" / "build" / "boot.json"
        boot.parent.mkdir(parents=True, exist_ok=True)
        boot.write_text(json.dumps({"ran": True, "rc": 0, "ready": True}))
        plan_out = subprocess.run([sys.executable, "-c", parity_plan_program(), str(r.root), "false"],
                                  capture_output=True, text=True, check=True).stdout.splitlines()
        self.assertIn("run-mode:disabled:%s" % ",".join(DISABLED), plan_out)
        self.assertIn("run-mode:enabled:%s" % ",".join(ENABLED), plan_out)
        self.assertEqual(plan_out[0], "run:" + ",".join(DISABLED + ENABLED))
        # both modes measured PASS on this tree -> every check judged PASS -> the outcome is accepted
        self.evidence(r.tree())
        out, stage = self.judge(tid, run)
        self.assertEqual(stage["state"], "passed", stage)
        self.assertTrue(out["outcome_accepted"], out)
        r.review_and_complete(tid, run)                                        # the native review lifecycle
        self.assertEqual(r.native.task(tid)["status"], "done")

    def assert_unfinished(self, **kw):
        r = self.r
        tid, run, _ver = self.repair_then_verification_issue()
        self.evidence(r.tree(), **kw)
        out, stage = self.judge(tid, run)
        self.assertFalse(out["outcome_accepted"], (kw, out))
        return stage

    def test_a_missing_scenario_leaves_it_unfinished(self):
        self.assertNotEqual(self.assert_unfinished(drop=ENABLED)["state"], "passed")

    def test_an_inconclusive_record_leaves_it_unfinished(self):
        self.assert_unfinished(record_verdicts={"sc:items-create": "INCONCLUSIVE"})   # the Location's scenario

    def test_a_stale_enabled_receipt_leaves_it_unfinished(self):
        self.assertEqual(self.assert_unfinished(enabled_tree="0" * 64)["state"], "unknown")

    def test_disabled_pass_beside_enabled_fail_fails(self):
        self.assertEqual(self.assert_unfinished(enabled_verdict="FAIL")["state"], "failed")

    def test_an_enabled_scenario_never_passes_on_disabled_evidence(self):
        """Architect review of 7d77d14f, reproduced verbatim: the enabled scenario's PASS moved into the disabled
        receipt and scenario directory (labelled disabled), the enabled receipt row left with no scenarios, both
        receipts bound to the right candidate. No enabled measurement exists: it must stay unaccepted."""
        r = self.r
        tid, run, _ver = self.repair_then_verification_issue()
        self.evidence(r.tree())
        parity = r.root / "verification" / "parity"
        sid = ENABLED[0]
        disabled = json.loads((parity / "receipt.json").read_text())
        disabled["entry_points"][0]["scenarios"].append(sid)
        (parity / "receipt.json").write_text(json.dumps(disabled))
        enabled = json.loads((parity / "receipt-enabled.json").read_text())
        enabled["entry_points"][0]["scenarios"] = []
        (parity / "receipt-enabled.json").write_text(json.dumps(enabled))
        name = sid.replace(":", "_") + ".json"
        record = json.loads((parity / "scenarios-enabled" / name).read_text())
        record["security_mode"] = "disabled"
        (parity / "scenarios" / name).write_text(json.dumps(record))
        (parity / "scenarios-enabled" / name).unlink()
        out, stage = self.judge(tid, run)
        self.assertFalse(out["outcome_accepted"], out)
        self.assertNotEqual(stage["state"], "passed", stage)

    def test_a_wrong_mode_record_in_the_right_directory_does_not_discharge(self):
        r = self.r
        tid, run, _ver = self.repair_then_verification_issue()
        self.evidence(r.tree())
        name = ENABLED[0].replace(":", "_") + ".json"
        p = r.root / "verification" / "parity" / "scenarios-enabled" / name
        rec = json.loads(p.read_text())
        rec["security_mode"] = "disabled"
        p.write_text(json.dumps(rec))
        out, _stage = self.judge(tid, run)
        self.assertFalse(out["outcome_accepted"], out)

    def test_an_unresolvable_target_is_a_named_harness_refusal(self):
        r = self.r
        (r.root / "verification" / "scenarios-enabled" / "corpus.json").unlink()
        tid, run, iss = r.issue(BEH)
        r.accept_on_run(tid, run, iss)
        r.worklist["candidate_sha256"] = r.tree()
        r.save_worklist()
        with self.assertRaises(Refusal) as cm:
            NC.issue(r.root, r.board, task_id=tid, run_id=run)
        self.assertEqual(cm.exception.code, "VERIFICATION_SCOPE_UNRESOLVED")
        self.assertIn("auth-anonymous-items-list", cm.exception.detail)


class VoidedRejectionsInTheBrief(unittest.TestCase):
    """v29 run 85 spent its whole run re-reading previous_attempts, where six rejections the Operator had voided
    as harness-caused were listed as attempts to avoid. The brief keeps them as history, out of the retry state."""

    def test_a_voided_rejection_is_recognised_and_an_unvoided_one_is_not(self):
        import os
        sys.path.insert(0, str(HERMES / "skills" / "migration" / "fix-until-green" / "scripts"))
        import brief as B
        r = T.Run()
        try:
            r.release()
            tid, run, iss = r.issue("build:rk:pom")
            for i, why in enumerate(("harness: mixed modes", "a real regression")):
                NC.record_verdict(r.root, r.board, task_id=tid, run_id=run, verdict="REVERTED", candidate="%064x" % i,
                                  attempt=str(i), reason=why)
            first = r.board.records(tid, "reject")[0]["key"]
            NC.void_rejects(r.board, task_id=tid, keys=[first], reason="LOOP_MIXED_SECURITY_MODE was the harness", by="operator")
            old = os.environ.get("HERMES_KANBAN_TASK")
            os.environ["HERMES_KANBAN_TASK"] = tid
            try:
                got = B._void_index(r.root, board=r.board)
            finally:
                os.environ.pop("HERMES_KANBAN_TASK") if old is None else os.environ.__setitem__("HERMES_KANBAN_TASK", old)
            self.assertEqual(got["voided"], {first: "LOOP_MIXED_SECURITY_MODE was the harness"})   # by exact identity
            second = r.board.records(tid, "reject")[1]
            row = {"cluster": iss["cluster"], "reason": "a real regression", "native_reject": second["key"]}
            self.assertEqual(B._void_status(row, got), ("", ""))                                   # the genuine one stays
            self.assertEqual(B._void_status(dict(row, native_reject=first), got)[0], "voided")
            # reasons that differ only after their first 300 characters: identity decides, not the prefix
            long_a, long_b = "x" * 300 + " first", "x" * 300 + " second"
            idx = {"voided": {"reject:9:a": "harness"}, "by_run": {}, "reasons": {(iss["cluster"], long_a[:300])}}
            self.assertEqual(B._void_status({"cluster": iss["cluster"], "reason": long_b, "native_reject": "reject:9:b"}, idx), ("", ""))
            # an identity-less row sharing a voided prefix is kept and flagged, never hidden
            self.assertEqual(B._void_status({"cluster": iss["cluster"], "reason": long_b}, idx)[0], "unresolved")
        finally:
            r.close()


class OneModePerRepairCluster(unittest.TestCase):
    """v29 Owner run 82: the verification measured failures in both security modes at one controller; one
    cluster held them all and every repair was refused LOOP_MIXED_SECURITY_MODE (ADR-014), the revert hid the
    failures and issuance alternated. A file's parity failures now form one cluster per mode."""

    def test_both_modes_at_one_file_form_two_single_mode_clusters(self):
        from planner.worklist import cluster_items, issued_parity_plan, sha256_bytes
        f = "src/main/java/com/acme/shop/web/ItemController.java"
        items = [{"id": "parity:d1", "source": "parity", "kind": "parity", "path": f, "security_mode": "disabled",
                  "scenario": "sc:items-create", "category": "mandatory"},
                 {"id": "parity:e1", "source": "parity", "kind": "parity", "path": f, "security_mode": "enabled",
                  "scenario": "sc:auth-anonymous-items-list", "category": "mandatory"}]
        got = {c["id"]: c["items"] for c in cluster_items(items, {f: 0}, set())}
        base = "c:%s" % sha256_bytes(f.encode("utf-8"))[:12]
        self.assertEqual(got[base], ["parity:d1"])                              # the default mode keeps the file's id
        self.assertEqual(len(got), 2)
        self.assertEqual([v for k, v in got.items() if k != base], [["parity:e1"]])
        for it in items:                                                        # each is a single-mode repair card
            plan = issued_parity_plan({"security_mode": it["security_mode"], "scenarios": [it["scenario"]], "items": [it["id"]]})
            self.assertEqual((plan["kind"], plan["mode"]), ("run", it["security_mode"]))
        # a disabled-only file keeps the file's id; an enabled-only file is identified by file AND mode
        # (c:<sha(path#enabled)>): the same id whether or not the file also has disabled failures
        self.assertEqual([c["id"] for c in cluster_items(items[:1], {f: 0}, set())], [base])
        enabled_id = "c:%s" % sha256_bytes((f + "#enabled").encode("utf-8"))[:12]
        self.assertEqual([c["id"] for c in cluster_items(items[1:], {f: 0}, set())], [enabled_id])
        self.assertIn(enabled_id, got)

    def test_the_owner_reaches_both_mode_clusters_one_at_a_time_under_one_budget(self):
        from planner.worklist import cluster_items
        f = "src/main/java/com/acme/shop/web/ItemController.java"
        items = [{"id": "parity:d1", "source": "parity", "kind": "parity", "path": f, "security_mode": "disabled",
                  "scenario": "sc:items-create", "category": "mandatory"},
                 {"id": "parity:e1", "source": "parity", "kind": "parity", "path": f, "security_mode": "enabled",
                  "scenario": "sc:auth-anonymous-items-list", "category": "mandatory"}]
        wl = {"items": items, "clusters": cluster_items(items, {f: 0}, set())}
        node = {"role": "repair", "outcome_id": BEH, "clusters": [], "budget": {"key": "rk:family:x", "limit": 3}}
        own = {"parity:d1", "parity:e1"}                                        # ownership is by item, not by cluster id
        first, _ = NC._allowed_paths(node, wl, own)
        closed = [dict(c, status="closed") if c["id"] == first else c for c in wl["clusters"]]
        second, _ = NC._allowed_paths(node, dict(wl, clusters=closed), own)
        self.assertEqual({first, second}, {c["id"] for c in wl["clusters"]})
        self.assertNotEqual(first, second)
        # one outcome, one family budget: both mode clusters spend against the node's key
        self.assertEqual(node["budget"]["key"], "rk:family:x")


if __name__ == "__main__":
    unittest.main(verbosity=1)
