"""The four conflict files of merge 45b421a2: both branches' behaviours survive TOGETHER.

Each case exercises one behaviour of the reliability package and one of next/after-v28 on the same input,
where the focused suites test them apart:

  worklist.py           an unauthoritative comparison keeps the last authoritative FAIL as history (package
                        229d59b3) AND a file's parity failures form one cluster per security mode (next 95bf6d51)
  requirement_checks.py repository effects judged on status/body, not header findings (package f9c6337a) AND a
                        scenario judged only in its expected mode, on a record bound to the candidate (next
                        7d77d14f / 68152b24)
  native_control.py     the lock-bound retirement of an expired issuance (cf164288, ruled) AND the scenario-
                        bearing verification-only issuance (next 7d77d14f / 945db1ab): a retired verification
                        projection is history, and the next run is issued the same sealed scope
  brief.py              typed repair as the unit's first action (package 8ffdfd9d) AND exact void identities
                        with honest unresolved history (next 602f696c / 68152b24 / 945db1ab) in ONE rendered brief

Other pairs are covered by name elsewhere (reported with the merge): schedule execution on a verification-only
unit (schedule_lifecycle.test.py), recipe ownership of a package finding (compatibility_objectives.test.py),
bounded evidence selectors under K2 (kernel/evidence_selectors_policy.test.py), the verification-only unit
end to end (planned_verification_route.test.py).

Run: PYTHONDONTWRITEBYTECODE=1 python3 .hermes/lib/planner/merge_pairs.test.py
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
HERMES = HERE.parent.parent
GOLDEN = HERMES.parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERMES / "skills" / "migration" / "fix-until-green" / "scripts"))
from planner import requirement_checks as RC  # noqa: E402
from planner.canonical import write_canonical  # noqa: E402
from planner.paths import PARITY_DIR  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class WorklistPair(unittest.TestCase):
    def test_history_of_an_enabled_fail_is_kept_in_its_own_mode_cluster(self):
        from planner.worklist import cluster_items, parity_items, sha256_bytes
        path = "src/main/java/com/acme/ledger/AccountResource.java"
        ep = "ep:com.acme.ledger.AccountResource#list():http"
        bundle = {"entry_points": [{"id": ep, "path": path}]}
        dis_fail = {"schema": "rhoai3.scenario-parity/v1", "entry_point": ep, "scenario": "sc:list", "verdict": "FAIL",
                    "reason": "status 500 vs 200", "receipt_sha256": "r1", "binding": {"mode": "sealed"}}
        en_fail = dict(dis_fail, scenario="sc:auth-list", security_mode="enabled")
        en_refused = {"schema": "rhoai3.scenario-parity/v1", "entry_point": ep, "scenario": "sc:auth-list",
                      "security_mode": "enabled", "verdict": "INCONCLUSIVE", "unauthoritative": True,
                      "reason": "receipt not authoritative: worklist digest ed65 != sealed efcb", "last_authoritative": en_fail}
        with tempfile.TemporaryDirectory(prefix="pair-worklist-") as td:
            root = Path(td)
            for sub, name, doc in (("scenarios", "sc_list.json", dis_fail), ("scenarios-enabled", "sc_auth-list.json", en_refused)):
                (root / PARITY_DIR / sub).mkdir(parents=True, exist_ok=True)
                (root / PARITY_DIR / sub / name).write_text(json.dumps(doc))
            items = parity_items(root, bundle, receipt={})
        by_sc = {i.get("scenario"): i for i in items}
        self.assertEqual(set(by_sc), {"sc:list", "sc:auth-list"}, items)
        self.assertTrue(by_sc["sc:auth-list"].get("pending_remeasure"))              # history, not a fresh FAIL
        self.assertTrue(by_sc["sc:auth-list"]["message"].startswith("NOT RE-MEASURED"))
        self.assertFalse(by_sc["sc:list"].get("pending_remeasure"))
        self.assertEqual((by_sc["sc:list"].get("security_mode") or "disabled", by_sc["sc:auth-list"].get("security_mode")),
                         ("disabled", "enabled"))
        for i in items:
            i["path"] = path
        clusters = {c["id"]: c["items"] for c in cluster_items(items, {path: 0}, set())}
        base = "c:%s" % sha256_bytes(path.encode("utf-8"))[:12]
        enabled = "c:%s" % sha256_bytes((path + "#enabled").encode("utf-8"))[:12]
        self.assertEqual(clusters, {base: [by_sc["sc:list"]["id"]], enabled: [by_sc["sc:auth-list"]["id"]]})


class RequirementChecksPair(unittest.TestCase):
    """A repository effect's scenario is judged in the mode its bound corpus assigns, on a record bound to the
    candidate; a header-only finding on it still leaves the effect discharged, a body finding still fails it."""

    TREE = "t" * 64
    EFFECTS = "behavior:repository-effects:p.Frag"

    def world(self, *, record_dir="scenarios-enabled", receipt=True, record_tree=None):
        td = tempfile.mkdtemp(prefix="pair-rc-")
        root = Path(td)
        for rel, ids in (("verification/scenarios/corpus.json", ["sc:list"]),
                         ("verification/scenarios-enabled/corpus.json", ["sc:auth-list"])):
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(json.dumps({"scenarios": [{"id": s} for s in ids]}))
        receipts = {}
        for mode, sid, sub in (("disabled", "sc:list", "scenarios"), ("enabled", "sc:auth-list", record_dir)):
            (root / PARITY_DIR / sub).mkdir(parents=True, exist_ok=True)
            (root / PARITY_DIR / sub / (sid.replace(":", "_") + ".json")).write_text(json.dumps({
                "schema": "rhoai3.scenario-parity/v1", "scenario": sid, "verdict": "PASS", "security_mode": mode,
                "binding": {"mode": "candidate", "candidate_sha256": record_tree or self.TREE}}))
            if receipt or mode == "disabled":
                receipts[mode] = {"schema": "rhoai3.parity-receipt/v1", "security_mode": mode, "verdict": "PASS",
                                  "binding": {"mode": "candidate", "candidate_sha256": self.TREE},
                                  "entry_points": [{"entry_point": "ep:x", "verdict": "PASS", "scenarios": [sid]}]}
        return root, receipts

    def effect(self, root, receipts, *items):
        req = {"id": "req:repo", "acceptance": [self.EFFECTS],
               "facts": {"verification": [{"member": "p.Frag#findAll()", "status": "applicable", "scenarios": ["sc:list"]},
                                          {"member": "p.Frag#save(p.E)", "status": "applicable", "scenarios": ["sc:auth-list"]}]}}
        return RC.measure(root, [req], worklist={"items": list(items), "measure": {"known": True}},
                          scenarios=["sc:list", "sc:auth-list"], tree=self.TREE, receipts=receipts)[self.EFFECTS]

    def test_both_behaviours_hold_on_one_effect(self):
        root, receipts = self.world()
        self.assertEqual(self.effect(root, receipts)["status"], RC.PASS)
        cors = {"id": "i1", "scenario": "sc:auth-list", "cause": "cors-response", "advice": {}}
        self.assertEqual(self.effect(root, receipts, cors)["status"], RC.PASS)            # header-only: discharged
        body = {"id": "i2", "scenario": "sc:auth-list", "cause": "response", "advice": {}}
        self.assertEqual(self.effect(root, receipts, body)["status"], RC.FAIL)            # a body finding fails it
        # the enabled scenario's PASS only in the DISABLED directory: not its mode's evidence
        root, receipts = self.world(record_dir="scenarios")
        got = self.effect(root, receipts)
        self.assertEqual(got["status"], RC.UNKNOWN, got)
        # no enabled receipt bound to the candidate: unknown, never a discharged effect
        root, receipts = self.world(receipt=False)
        self.assertEqual(self.effect(root, receipts)["status"], RC.UNKNOWN)
        # a record of another candidate: unknown
        root, receipts = self.world(record_tree="s" * 64)
        self.assertEqual(self.effect(root, receipts)["status"], RC.UNKNOWN)


PV = _load("planned_verification_for_pairs", HERE / "planned_verification.test.py")


class NativeControlPair(unittest.TestCase):
    setUp = PV.PlannedVerification.setUp
    tearDown = PV.PlannedVerification.tearDown
    repair_then_verification_issue = PV.PlannedVerification.repair_then_verification_issue

    def test_an_expired_verification_projection_retires_and_the_next_run_gets_the_same_sealed_scope(self):
        r = self.r
        NC, NG = PV.NC, PV.NG
        from planner.paths import LOOP_ISSUED
        tid, run, ver = self.repair_then_verification_issue()
        for name in ("planning", "lib"):
            link = r.root / ".hermes" / name
            if not link.exists():
                link.symlink_to(HERMES / name)
        NG.write_issued_projection(r.root, ver)
        judged = (r.root / LOOP_ISSUED).read_bytes()
        self.assertEqual(json.loads(judged)["verification"]["scenarios_by_mode"],
                         {"disabled": PV.DISABLED, "enabled": PV.ENABLED})
        r.native.end_run(tid, "ready", "gave_up")                              # the run ended without a verdict
        self.assertEqual(NC.issuance_state(r.root, r.board)["state"], "expired")
        out = NC.retire_issuance(r.root, r.board, by="operator", reason="run %d ended" % run)
        self.assertFalse((r.root / LOOP_ISSUED).exists())
        self.assertEqual((r.root / out["retired"]).read_bytes(), judged)        # the judged bytes, as history
        self.assertEqual(len(r.board.records(tid, "issuance-retired")), 1)
        run2, lock2 = r.native.claim(tid)
        ver2 = NC.issue(r.root, r.board, task_id=tid, run_id=run2, claim_lock=lock2)
        self.assertEqual((ver2["cluster"], ver2["allowed_paths"]), (ver["cluster"], []))
        self.assertEqual(ver2["planned_unit"]["verification"]["scenarios_by_mode"],
                         ver["planned_unit"]["verification"]["scenarios_by_mode"])
        self.assertEqual(r.board.records(tid, "issue")[-1]["verification"]["corpus_sha256"],
                         ver["planned_unit"]["verification"]["corpus_sha256"])


class BriefPair(unittest.TestCase):
    def test_typed_first_action_and_exact_void_history_in_one_brief(self):
        import brief as mod
        from planner.paths import LOOP_DIR, LOOP_ISSUED, LOOP_STEPS, WORKLIST
        from planner.worklist import batch_scope_digest, handler_parameters, symbol_renames, unit_target_symbols
        task, cid, rk = "t_pair0001", "u:hp1", "rk:unit:u:hp1"
        retired = "org.springframework.web.util.UriComponentsBuilder"
        rel = "src/main/java/q/web/LedgerController.java"
        sites = [{"path": rel, "type": "q.web.LedgerController", "member": "addEntry",
                  "signature": "addEntry(java.lang.String,UriComponentsBuilder)", "parameter": "ucBuilder"}]
        rows = handler_parameters(GOLDEN)["undocumented"]
        targets = unit_target_symbols([{"kind": "type", "fqn": retired, "path": rel}], symbol_renames(GOLDEN), {}, None,
                                      {retired: sites}, rows)
        voided_reason = "the unit's compile obligation err:1 is still reported"

        class Board:
            def records(self, t, kind=None):
                recs = {"reject": [{"key": "reject:5:aaaa", "run": 5, "candidate": "a" * 64, "cluster": cid, "reason": voided_reason},
                                   {"key": "reject:6:bbbb", "run": 6, "candidate": "b" * 64, "cluster": cid, "reason": voided_reason}],
                        "reject-voided": [{"reject": "reject:5:aaaa", "reason": "harness: stale catalog"}]}
                return list(recs.get(kind, [])) if t == task else []

        with tempfile.TemporaryDirectory(prefix="pair-brief-") as td:
            root = Path(td)
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text("package q.web;\npublic class LedgerController { }\n", encoding="utf-8")
            scope = {"schema": "rhoai3.batch-scope/v4", "kind": "unit", "rule": "unit/diagnostic-family/v1",
                     "cluster": cid, "unit_id": cid, "family_key": retired, "writable_paths": [rel],
                     "symbols": [{"kind": "type", "fqn": retired, "path": rel}], "target_symbols": targets,
                     "members": [{"path": rel, "type": "q.web.LedgerController", "member_id": "", "occurrence": 0,
                                  "state": "reported", "identity": "diag:1"}],
                     "evidence": [], "completion": [], "bounds": {"files": 1, "sites": 1, "symbols": 1},
                     "measured": ["err:1"], "inputs": {"candidate_sha256": "c0"}}
            scope["digest"] = batch_scope_digest(scope)
            sp = Path("evidence/planning/batch-scope/u-hp1") / ("%s.json" % scope["digest"][:32])
            write_canonical(root / sp, scope)
            cluster = {"id": cid, "kind": "compile", "path": rel, "write_set": [rel], "items": ["err:1"], "label": retired,
                       "retry_key": rk, "batch_scope": {"path": sp.as_posix(), "digest": scope["digest"], "rule": scope["rule"],
                                                        "kind": "unit", "unit_id": cid, "members": 1}}
            write_canonical(root / WORKLIST, {"schema": "rhoai3.worklist/v1", "head": cid, "unit_formation": "v1",
                                              "measure": {"tuple": [0, 1, 0], "known": True, "blocked": []},
                                              "clusters": [cluster], "not_counted": [],
                                              "items": [{"id": "err:1", "source": "javac", "kind": "compile", "category": "mandatory",
                                                         "path": rel, "line": 3, "identity": "diag:1",
                                                         "rule_id": "compiler.err.cant.resolve.location",
                                                         "message": "cannot find symbol\n  symbol:   class UriComponentsBuilder"}]})
            write_canonical(root / LOOP_ISSUED, {"schema": "rhoai3.loop-issued/v1", "cluster": cid, "task_id": task, "write_set": [rel]})
            base = {"cluster": cid, "card": task, "retry_key": rk, "changed": [rel]}
            write_canonical(root / LOOP_STEPS, {"steps": [], "rejected": [
                dict(base, reason=voided_reason, native_run=6, candidate_sha256="b" * 64, legal_next="genuine next"),  # genuine
                dict(base, reason=voided_reason, native_reject="reject:5:aaaa", legal_next="voided"),                 # voided exactly
                dict(base, reason=voided_reason, legal_next="Do not repeat this patch")]})                             # identity-less
            cat = root / ".hermes" / "planning" / "catalogs" / "compat-mapping.json"
            cat.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(GOLDEN / ".hermes" / "planning" / "catalogs" / "compat-mapping.json", cat)
            prev, env = mod._native_board, os.environ.get("HERMES_KANBAN_TASK")
            mod._native_board = lambda _root: Board()
            os.environ["HERMES_KANBAN_TASK"] = task
            try:
                out, err = io.StringIO(), io.StringIO()
                with redirect_stdout(out), redirect_stderr(err):
                    rc = mod.main(["--root", str(root)])
                full = json.loads((root / LOOP_DIR / "brief-u-hp1.json").read_text())
            finally:
                mod._native_board = prev
                os.environ.pop("HERMES_KANBAN_TASK") if env is None else os.environ.__setitem__("HERMES_KANBAN_TASK", env)
        text = out.getvalue()
        self.assertEqual(rc, 0, err.getvalue()[:400])
        # package: the typed repair leads
        self.assertIn("FIRST ACTION (typed repair, handler-uri-parameter): python3 .hermes/skills/migration/fix-until-green/"
                      "scripts/typed-repair.py --root . --cluster u:hp1", text)
        self.assertTrue(str(full.get("procedure") or "").startswith("FIRST: python3"))
        # next: the exact void is counted and removed; the genuine refusal drives the retry guidance; the
        # identity-less row is disclosed as unresolved and issues no prohibition
        self.assertEqual([r.get("native_reject") for r in full.get("voided_attempts") or []], ["reject:5:aaaa"])
        self.assertIn("1 earlier rejection(s) of this family were VOIDED", text)
        self.assertIn("legal next: genuine next", text)
        self.assertIn("UNRESOLVED history: 1", text)
        self.assertNotIn("legal next: Do not repeat this patch", text)


if __name__ == "__main__":
    unittest.main(verbosity=1)
