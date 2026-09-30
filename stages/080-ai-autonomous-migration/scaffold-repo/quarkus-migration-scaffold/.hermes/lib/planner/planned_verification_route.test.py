"""F1 exit (reliability package review): the planned verification-only unit through the REAL paths.

last repair accepted -> verification-only unit issued with its sealed scope (non-empty scenarios per
security mode) -> the issued projection written by native_gate -> run-verify.sh's own parity plan AND its
per-mode execution region, extracted from the script and run by bash exactly as written (the
run-verify-modes.test.sh technique), with a bounded fake comparator in place of run-parity.py -> run.json
as that region writes it -> measurement.execution -> candidate- and mode-bound judgment
(evaluate_recovered: requirement checks against the issued scope) -> native review.

Negative routes through the same path: a scenario the comparator left unmeasured, a record written in the
other mode, a corpus changed after issuance, a FAIL in one mode. Each stays unaccepted and spends nothing.
The rejection-identity negatives (identity-less rows stay unresolved, voids match by exact identity) are
brief.test.py's and planned_verification.test.py's (VoidedRejectionsInTheBrief) and are kept there.

Run: PYTHONDONTWRITEBYTECODE=1 python3 .hermes/lib/planner/planned_verification_route.test.py
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("planned_verification_for_route", HERE / "planned_verification.test.py")
PV = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(PV)
NC, NG, ME = PV.NC, PV.NG, PV.ME
from planner.paths import LOOP_ISSUED, VERIFY_RUN  # noqa: E402

BEH, EP, DISABLED, ENABLED, HERMES, RUN_VERIFY = PV.BEH, PV.EP, PV.DISABLED, PV.ENABLED, PV.HERMES, PV.RUN_VERIFY

# the fake comparator: what run-parity.py leaves for the scenarios it was asked, in the mode it was asked,
# bound to the candidate the issued projection names; FAKE_* shape the defects the negatives need
FAKE_PARITY = r'''
import json, os, sys
from pathlib import Path
argv = sys.argv[1:]
root = Path(argv[argv.index("--root") + 1])
issued = argv[argv.index("--issued") + 1] if "--issued" in argv else ""
mode = argv[argv.index("--security-mode") + 1] if "--security-mode" in argv else "disabled"
sids = [argv[i + 1] for i, a in enumerate(argv) if a == "--scenario"]
with open(os.environ["FAKE_LOG"], "a") as f:
    f.write(json.dumps({"mode": mode, "scenarios": sids, "issued": issued}) + "\n")
# the real runner binds its verdicts to the candidate through --issued (candidate_binding); the fake is told it
tree = os.environ["FAKE_TREE"] if issued else ""
verdicts = json.loads(os.environ.get("FAKE_VERDICTS") or "{}")
drop = set(filter(None, (os.environ.get("FAKE_DROP") or "").split(",")))
wrong = set(filter(None, (os.environ.get("FAKE_WRONG_MODE") or "").split(",")))
pdir = root / "verification" / "parity"
kept = [s for s in sids if s not in drop]
row = "FAIL" if any(verdicts.get(s, "PASS") == "FAIL" for s in kept) else "PASS"
for s in kept:
    other = "enabled" if mode == "disabled" else "disabled"
    rec_mode = other if s in wrong else mode
    sub = "scenarios" if rec_mode == "disabled" else "scenarios-enabled"
    (pdir / sub).mkdir(parents=True, exist_ok=True)
    (pdir / sub / (s.replace(":", "_") + ".json")).write_text(json.dumps({
        "schema": "rhoai3.scenario-parity/v1", "scenario": s, "entry_point": os.environ["FAKE_EP"],
        "verdict": verdicts.get(s, "PASS"), "security_mode": rec_mode,
        "binding": {"mode": "candidate", "candidate_sha256": tree}}))
name = "receipt.json" if mode == "disabled" else "receipt-%s.json" % mode
pdir.mkdir(parents=True, exist_ok=True)
(pdir / name).write_text(json.dumps({
    "schema": "rhoai3.parity-receipt/v1", "security_mode": mode, "verdict": row,
    "binding": {"mode": "candidate", "candidate_sha256": tree},
    "entry_points": [{"entry_point": os.environ["FAKE_EP"], "verdict": row,
                      "scenarios": [s for s in kept if s not in wrong]}]}))
sys.exit(1 if row == "FAIL" else 0)
'''


def acceptance_region() -> str:
    """run-verify.sh from its parity plan through the end of its marked per-mode execution region."""
    text = RUN_VERIFY.read_text()
    start = text.index('  PARITY_PLAN="$(python3 - "${ROOT}" "${FORCE_PARITY}" <<\'PYEOF\'')
    end = text.index("    # <<< parity-execution", start)
    return text[start:end] + "    # <<< parity-execution\n  fi\n"


class VerificationRoute(unittest.TestCase):
    setUp = PV.PlannedVerification.setUp
    tearDown = PV.PlannedVerification.tearDown
    repair_then_verification_issue = PV.PlannedVerification.repair_then_verification_issue
    judge = PV.PlannedVerification.judge

    def route(self, ver, **fake):
        """Publish the projection and run run-verify's parity plan + per-mode execution for real."""
        r = self.r
        for name in ("planning", "lib"):
            link = r.root / ".hermes" / name
            if not link.exists():
                link.symlink_to(HERMES / name)
        NG.write_issued_projection(r.root, ver)
        tree = r.tree()
        build = r.root / "verification" / "build"
        build.mkdir(parents=True, exist_ok=True)
        (build / "boot.json").write_text(json.dumps({"ran": True, "rc": 0, "ready": True}))
        (r.root / VERIFY_RUN).write_text(json.dumps({
            "candidate_sha256": tree, "mode": "acceptance", "classpath": {"ran": True, "rc": 0},
            "diagnostics": {"ran": True}, "tests": {"ran": True, "rc": 0}}))
        tmp = Path(tempfile.mkdtemp(prefix="pv-route-"))
        (tmp / "region.sh").write_text(acceptance_region())
        (tmp / "run-parity.py").write_text(FAKE_PARITY)
        runner = fake.pop("run_parity_py", str(tmp / "run-parity.py"))
        (tmp / "scripts").mkdir()
        (tmp / "scripts" / "verify.py").write_text("import sys\nsys.exit(0)\n")
        (tmp / "work").mkdir()
        driver = "\n".join([
            "set -euo pipefail",
            'ROOT="$1"; TMP="$2"; FORCE_PARITY=false',
            'RUN="${ROOT}/verification/build/run.json"; WORK="${TMP}/work"; DIAG="${TMP}/diag.json"',
            'SCRIPT_DIR="${TMP}/scripts"; PARITY_RUN_PY="$3"',
            'PARITY_RECEIPT="${ROOT}/verification/parity/receipt.json"',
            'PARITY_BEFORE="${ROOT}/verification/build/parity-before.json"',
            "TEST_ARGS=(); FIND_ARGS=()",
            "now_ms() { echo 0; }",
            'source "${TMP}/region.sh"',
        ])
        fake.setdefault("tree", tree)
        env = dict(os.environ, FAKE_LOG=str(tmp / "calls.log"), FAKE_EP=EP,
                   **{"FAKE_" + k.upper(): (v if isinstance(v, str) else json.dumps(v)) for k, v in fake.items()})
        (tmp / "calls.log").write_text("")
        p = subprocess.run(["bash", "-c", driver, "route", str(r.root), str(tmp), runner], capture_output=True, text=True, env=env)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        calls = [json.loads(x) for x in (tmp / "calls.log").read_text().splitlines() if x.strip()]
        # the worklist the rebuilt verify would leave: this candidate packaged, started, nothing open
        r.worklist.update({"candidate_sha256": tree, "measure": {"known": True, "tuple": [0, 0, 0], "compile_errors": 0,
                                                                 "failing_tests": 0},
                           "runtime": {"package": {"ran": True, "rc": 0}, "boot": {"ran": True, "rc": 0, "ready": True},
                                       "ready": True},
                           "sources": {"surefire": {"reports": 1}}})
        r.save_worklist()
        return calls, json.loads((r.root / VERIFY_RUN).read_text())["runtime"]["parity"]

    def spent(self, tid):
        role, prun, _oid, plan, node = NC.node_context(self.r.board, tid)
        return NC.budget_state(self.r.board, prun, plan, node)["spent"]

    # -- the positive route ----------------------------------------------------------------------
    def test_the_verification_unit_routes_measures_judges_and_reaches_review(self):
        r = self.r
        tid, run, ver = self.repair_then_verification_issue()
        self.assertEqual((ver["allowed_paths"], ver["cluster"].startswith("planned:")), ([], True))
        scope = ver["planned_unit"]["verification"]
        self.assertEqual((scope["scenarios_by_mode"], scope["unresolved"]), ({"disabled": DISABLED, "enabled": ENABLED}, []))
        self.assertTrue(all(scope["corpus_sha256"].get(m) for m in ("disabled", "enabled")))      # sealed to its corpora
        issue_rec = r.board.records(tid, "issue")[-1]
        self.assertEqual(issue_rec["verification"]["scenarios_by_mode"], scope["scenarios_by_mode"])  # on the native record
        calls, par = self.route(ver)
        issued = str(r.root / LOOP_ISSUED)
        self.assertEqual(calls, [{"mode": "disabled", "scenarios": DISABLED, "issued": issued},
                                 {"mode": "enabled", "scenarios": ENABLED, "issued": issued}])
        self.assertEqual((par["rc"], par["trigger"], par["scoped"]), (0, "issued-card", True))
        self.assertEqual({m: v["scenarios"] for m, v in par["modes"].items()}, {"disabled": DISABLED, "enabled": ENABLED})
        before = self.spent(tid)
        out, stage = self.judge(tid, run)
        self.assertEqual(stage["state"], "passed", stage)
        self.assertTrue(out["outcome_accepted"], out)
        self.assertEqual(self.spent(tid), before)
        r.review_and_complete(tid, run)
        self.assertEqual(r.native.task(tid)["status"], "done")

    # -- negatives through the same route ----------------------------------------------------------
    def assert_unaccepted(self, before_route=None, **fake):
        r = self.r
        tid, run, ver = self.repair_then_verification_issue()
        if before_route:
            before_route()
        _calls, par = self.route(ver, **fake)
        before = self.spent(tid)
        out, stage = self.judge(tid, run)
        self.assertFalse(out["outcome_accepted"], (fake, out))
        self.assertEqual(self.spent(tid), before)                                   # a judgment, not a spent attempt
        self.assertNotEqual(r.native.task(tid)["status"], "done")
        return out, stage, par

    def test_a_scenario_the_comparator_left_unmeasured_stays_unaccepted(self):
        out, stage, _par = self.assert_unaccepted(drop=ENABLED[0])
        self.assertNotEqual(stage["state"], "passed")
        self.assertTrue(any(ENABLED[0].split(":", 1)[1] in x for x in out["not_accepted_because"]), out)

    def test_a_record_written_in_the_other_mode_does_not_discharge(self):
        out, _stage, _par = self.assert_unaccepted(wrong_mode=ENABLED[0])
        self.assertTrue(any(ENABLED[0].split(":", 1)[1] in x for x in out["not_accepted_because"]), out)

    def test_a_corpus_changed_after_issuance_stays_unaccepted(self):
        def change():
            p = self.r.root / "verification" / "scenarios" / "corpus.json"
            doc = json.loads(p.read_text())
            doc["scenarios"].append({"id": "sc:items-added-later", "entry_point": EP, "method": "GET", "path": "/items"})
            p.write_text(json.dumps(doc))
        out, _stage, par = self.assert_unaccepted(before_route=change)
        # run-verify compares the ISSUED scope, not today's corpus
        self.assertEqual(par["modes"]["disabled"]["scenarios"], DISABLED)
        self.assertTrue(any("corpus changed" in x for x in out["not_accepted_because"]), out)

    def test_verdicts_bound_to_another_candidate_do_not_discharge(self):
        out, stage, _par = self.assert_unaccepted(tree="0" * 64)
        self.assertNotEqual(stage["state"], "passed", stage)

    def test_a_fail_in_one_mode_is_not_masked_by_the_other(self):
        out, stage, par = self.assert_unaccepted(verdicts={ENABLED[0]: "FAIL"})
        self.assertEqual((par["rc"], par["modes"]["disabled"]["rc"], par["modes"]["enabled"]["rc"]), (1, 0, 1))
        self.assertEqual(stage["state"], "failed", stage)



# ===========================================================================================================
# The merged path on ONE fixture, with scenario STATE: the comparator stage is the REAL run-parity.py and
# compare-scenario-parity.py replaying a DELETE -> GET corpus against a stateful fake clinic (the
# run-parity.test.py fixture: admitted specimen root, source captured in corpus order in both modes).
# The only synthetic hop: the runner measures its admitted specimen root, and its verdict records for the
# ISSUED scenarios are carried into the card's root re-bound to the candidate (the binding run-parity makes
# from --issued); verdicts, setup results and prerequisite gaps are the runner's own.
_rp_spec = importlib.util.spec_from_file_location(
    "run_parity_fixture", HERMES / "skills" / "paved-road" / "paved-road-m4" / "scripts" / "run-parity.test.py")
RP = importlib.util.module_from_spec(_rp_spec)
_rp_spec.loader.exec_module(RP)

AUTH = "sc:auth-"                          # the enabled corpus's ids (one corpus per mode: ids never shared)
DEP_D, DEP_E, DEL_D, DEL_E = "sc:owners-after-delete", AUTH + "owners-after-delete", "sc:delete-visit-1", AUTH + "delete-visit-1"
M_CHECKS = ["parity:" + DEP_D, "parity:" + DEP_E]
M_RID = "req:behavior-verification:" + EP


class Clinic(RP.VisitClinic):
    """VisitClinic with its behaviour switchable from the comparator's process (POST /__control)."""
    visits = {1, 4}
    delete_mode = "ok"
    extra_visit = False

    def do_POST(self):
        cls = type(self)
        if self.path == "/__control":
            doc = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            cls.delete_mode = str(doc.get("delete_mode", "ok"))
            cls.extra_visit = bool(doc.get("extra_visit", False))
            return self._send(200, {"ok": True})
        return self._send(404, {"error": "absent"})


BRIDGE = r"""
import json, os, subprocess, sys, urllib.request
from pathlib import Path
argv = sys.argv[1:]
root = Path(argv[argv.index("--root") + 1])
mode = argv[argv.index("--security-mode") + 1] if "--security-mode" in argv else "disabled"
sids = [argv[i + 1] for i, a in enumerate(argv) if a == "--scenario"]
spec, base = Path(os.environ["SPEC_ROOT"]), os.environ["CLINIC"]
control = json.loads(os.environ.get("CONTROL_" + mode.upper()) or "{}")
req = urllib.request.Request(base + "/__control", data=json.dumps(control).encode(), method="POST")
urllib.request.urlopen(req, timeout=10).read()
urllib.request.urlopen(base + "/__reset", timeout=10).read()          # pristine data, whatever ran before (v29)
cmd = [sys.executable, os.environ["RUNNER"], "--root", str(spec), "--dest-url", base,
       "--reset-cmd", "%s %s" % (sys.executable, os.environ["RESET"])] + [a for s in sids for a in ("--scenario", s)]
if mode != "disabled":
    cmd += ["--security-mode", mode]
p = subprocess.run(cmd, capture_output=True, text=True)
with open(os.environ["FAKE_LOG"], "a") as f:
    f.write(json.dumps({"mode": mode, "scenarios": sids, "rc": p.returncode}) + "\n")
sub = "scenarios" if mode == "disabled" else "scenarios-enabled"
run_name = "_run.json" if mode == "disabled" else "_run-%s.json" % mode
(root / "verification" / "parity" / sub).mkdir(parents=True, exist_ok=True)
run_doc = json.loads((spec / "verification" / "parity" / run_name).read_text())
(root / "verification" / "parity" / run_name).write_text(json.dumps(run_doc))
tree = os.environ["FAKE_TREE"]
wrong = os.environ.get("WRONG_DIR") == mode
verdicts = {}
for s in sids:
    rec = json.loads((spec / "verification" / "parity" / sub / (s.replace(":", "_") + ".json")).read_text())
    rec["binding"] = {"mode": "candidate", "candidate_sha256": tree}
    rec["security_mode"] = mode
    verdicts[s] = rec["verdict"]
    dest_sub = ("scenarios-enabled" if sub == "scenarios" else "scenarios") if wrong else sub
    (root / "verification" / "parity" / dest_sub).mkdir(parents=True, exist_ok=True)
    (root / "verification" / "parity" / dest_sub / (s.replace(":", "_") + ".json")).write_text(json.dumps(rec))
row = "PASS" if verdicts and all(v == "PASS" for v in verdicts.values()) else ("FAIL" if "FAIL" in verdicts.values() else "INCONCLUSIVE")
name = "receipt.json" if mode == "disabled" else "receipt-%s.json" % mode
(root / "verification" / "parity" / name).write_text(json.dumps({
    "schema": "rhoai3.parity-receipt/v1", "security_mode": mode, "verdict": row,
    "binding": {"mode": "candidate", "candidate_sha256": tree},
    "entry_points": [{"entry_point": os.environ["FAKE_EP"], "verdict": row, "scenarios": sids}]}))
sys.exit(0 if row == "PASS" else 1)
"""


class MergedPathWithState(VerificationRoute):
    """repair accepted -> its live row gone -> verification-only unit with its sealed scope (the two dependent
    reads, one per mode) -> run-verify routes each mode -> the real runner replays the unselected DELETE as
    proven setup before its dependent GET -> mode- and candidate-bound judgment -> native review."""

    @classmethod
    def setUpClass(cls):
        os.environ[RP.ENABLED_CRED_ENV] = "%s:%s" % (RP.ENABLED_CRED_USER, RP.ENABLED_CRED_PASSWORD)
        os.environ[RP.NAV_USER_ENV], os.environ[RP.NAV_PASS_ENV] = "nav-user", "nav-secret"
        cls.stub, stub_base = RP._serve()
        cls.clinic = RP.HTTPServer(("127.0.0.1", 0), Clinic)
        import threading
        threading.Thread(target=cls.clinic.serve_forever, daemon=True).start()
        cls.base = "http://127.0.0.1:%d" % cls.clinic.server_address[1]
        cls.td = Path(tempfile.mkdtemp(prefix="merged-path-")).resolve()
        cls.spec = RP._build(cls.td, stub_base)
        cls.reset = RP._reset_script(cls.td, cls.base)
        RP.VisitClinic = Clinic                                       # the capture drives the switchable clinic
        RP._capture_visit_corpus(cls.spec, cls.base, "disabled")
        visit = RP.VISIT_CORPUS
        try:
            RP.VISIT_CORPUS = dict(visit, scenarios=[dict(sc, id=AUTH + sc["id"][3:]) for sc in visit["scenarios"]])
            RP._capture_visit_corpus(cls.spec, cls.base, RP.ENABLED)
        finally:
            RP.VISIT_CORPUS = visit

    @classmethod
    def tearDownClass(cls):
        cls.clinic.shutdown()
        cls.stub.shutdown()

    def setUp(self):
        r = self.r = PV.T.Run(publish=False)
        plan = json.loads(r.plan_file.read_text())
        node = next(n for n in plan["nodes"] if n["outcome_id"] == BEH)
        node["requirements"] = [M_RID]
        node["scenarios"] = [DEP_D]
        node["acceptance"] = dict(node.get("acceptance") or {}, requirement_checks=M_CHECKS)
        node["check_plan"] = [{"requirement": M_RID, "check": c, "stage": "immediate", "prerequisites": []} for c in M_CHECKS]
        plan["requirements"] = [{"id": M_RID, "rule": "behavior-verification", "class": "behavior", "acceptance": M_CHECKS,
                                 "facts": {"kind": "http"}}]
        plan.pop("digest", None)
        plan["digest"] = PV.OG.plan_digest(plan)
        r.plan_file.write_text(json.dumps(plan))
        r.out = r.publish()
        r.release()
        r.drop("inc:unlocatable:jndi")
        for n in PV.OG.topo_order(r.plan()["nodes"]):
            if n["role"] == "repair" and n["class"] != "behavior":
                r.accept(n["outcome_id"], classes=("build", "compile", "tests") + (("runtime",) if n["class"] == "runtime" else ()),
                         scenarios=n.get("scenarios") or ())
        # the card's bound corpora are the specimen's, byte for byte (the scope is sealed to their digests)
        for mode in ("disabled", RP.ENABLED):
            dst = r.root / RP.corpus_path(mode)
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes((self.spec / RP.corpus_path(mode)).read_bytes())
        own = PV.NC._node(r.plan(), BEH)["obligations"]
        r.worklist["items"] += [{"id": o, "category": "mandatory", "kind": "parity", "source": "parity",
                                 "path": PV.ITEM_FILE, "entry_point": o.split("verify:", 1)[1]} for o in own]
        r.worklist["clusters"].append({"id": "c:item-beh", "items": list(own), "kind": "parity", "path": PV.ITEM_FILE,
                                       "status": "open", "write_set": [PV.ITEM_FILE]})
        r.worklist["candidate_sha256"] = r.tree()
        r.save_worklist()
        self.own = own

    def route_state(self, ver, **control):
        tmp = Path(tempfile.mkdtemp(prefix="merged-bridge-"))
        (tmp / "bridge.py").write_text(BRIDGE)
        env = {"SPEC_ROOT": str(self.spec), "CLINIC": self.base, "RUNNER": str(RP.RUNNER), "RESET": str(self.reset)}
        for mode in ("disabled", "enabled"):
            env["CONTROL_" + mode.upper()] = json.dumps(control.get(mode) or {})
        if control.get("wrong_dir"):
            env["WRONG_DIR"] = control["wrong_dir"]
        old = {k: os.environ.get(k) for k in env}
        os.environ.update(env)
        try:
            return self.route(ver, run_parity_py=str(tmp / "bridge.py"))
        finally:
            for k, v in old.items():
                os.environ.pop(k) if v is None else os.environ.__setitem__(k, v)

    def issue_verification(self):
        r = self.r
        tid, run, ver = self.repair_then_verification_issue()
        # the repair's live work-list rows are gone; the planned checks remain and are what is issued
        wl = json.loads((r.root / "evidence" / "planning" / "worklist.json").read_text())
        self.assertFalse({i["id"] for i in wl["items"]} & set(self.own))
        self.assertEqual((ver["allowed_paths"], ver["planned_unit"]["verification"]["scenarios_by_mode"]),
                         ([], {"disabled": [DEP_D], "enabled": [DEP_E]}))
        return tid, run, ver

    def test_the_prerequisite_delete_is_replayed_before_its_read_and_the_card_reaches_review(self):
        r = self.r
        tid, run, ver = self.issue_verification()
        before = self.spent(tid)
        calls, par = self.route_state(ver)
        self.assertEqual([(c["mode"], c["scenarios"]) for c in calls], [("disabled", [DEP_D]), ("enabled", [DEP_E])])
        for mode, dep, setup in (("disabled", DEP_D, DEL_D), ("enabled", DEP_E, DEL_E)):
            run_doc = json.loads((r.root / "verification" / "parity" / (
                "_run.json" if mode == "disabled" else "_run-enabled.json")).read_text())
            # corpus order inside the segment: the delete ran as setup, proven PASS, recorded apart from targets
            self.assertEqual([(x["id"], x["verdict"]) for x in run_doc["scenarios"]["setup"]], [(setup, "PASS")], mode)
            self.assertEqual({x["id"]: x["verdict"] for x in run_doc["scenarios"]["results"]}, {dep: "PASS"}, mode)
        self.assertEqual(par["rc"], 0)
        out, stage = self.judge(tid, run)
        self.assertEqual(stage["state"], "passed", stage)
        self.assertTrue(out["outcome_accepted"], out)
        self.assertEqual(self.spent(tid), before)
        r.review_and_complete(tid, run)
        self.assertEqual(r.native.task(tid)["status"], "done")

    def unaccepted(self, **control):
        r = self.r
        tid, run, ver = self.issue_verification()
        before = self.spent(tid)
        calls, par = self.route_state(ver, **control)
        out, stage = self.judge(tid, run)
        self.assertFalse(out["outcome_accepted"], (control, out))
        self.assertEqual(self.spent(tid), before)                          # a judgment spends nothing
        self.assertNotEqual(r.native.task(tid)["status"], "done")
        return tid, run, out, stage

    def test_a_broken_setup_leaves_the_dependent_unmeasured_never_a_fail(self):
        _tid, _run, out, stage = self.unaccepted(disabled={"delete_mode": "noop"})
        rec = json.loads((self.r.root / "verification" / "parity" / "scenarios" / (DEP_D.replace(":", "_") + ".json")).read_text())
        self.assertEqual(rec["verdict"], "INCONCLUSIVE")
        self.assertIn(DEL_D, rec.get("prerequisite_gap") or rec.get("reason") or "")
        self.assertNotEqual(stage["state"], "failed", stage)           # not an Owner FAIL
        self.assertTrue(any(DEP_D[3:] in x for x in out["not_accepted_because"]), out)

    def test_a_true_difference_after_valid_setup_stays_fail(self):
        _tid, _run, _out, stage = self.unaccepted(enabled={"extra_visit": True})
        self.assertEqual(stage["state"], "failed", stage)

    def test_a_disabled_pass_does_not_discharge_enabled_work(self):
        # the disabled read PASSes after its proven setup; the enabled one's setup is broken
        _tid, _run, out, _stage = self.unaccepted(enabled={"delete_mode": "noop"})
        self.assertTrue(any(DEP_E[3:] in x for x in out["not_accepted_because"]), out)

    def test_wrong_mode_evidence_does_not_discharge(self):
        _tid, _run, out, _stage = self.unaccepted(wrong_dir="enabled")
        self.assertTrue(any(DEP_E[3:] in x for x in out["not_accepted_because"]), out)

    def test_a_genuine_rejection_is_not_voided_by_another_identity_and_renews_no_budget(self):
        r = self.r
        tid, run, _out, _stage = self.unaccepted(enabled={"extra_visit": True})
        NC.record_verdict(r.root, r.board, task_id=tid, run_id=run, verdict="REVERTED", candidate=r.tree(), attempt="m1",
                          reason="the owners list carries a visit the source never had")
        spent = self.spent(tid)
        genuine = r.board.records(tid, "reject")[-1]["key"]
        # a void names an exact native rejection identity: another identity is refused, nothing is voided
        with self.assertRaises(PV.Refusal) as cm:
            NC.void_rejects(r.board, task_id=tid, keys=["reject:%d:other" % run], reason="harness", by="operator")
        self.assertEqual(cm.exception.code, "VOID_UNKNOWN_REJECT")
        self.assertEqual(r.board.records(tid, "reject-voided"), [])
        self.assertEqual(self.spent(tid), spent)                           # no renewal
        import sys as _sys
        _sys.path.insert(0, str(HERMES / "skills" / "migration" / "fix-until-green" / "scripts"))
        import brief as B
        old = os.environ.get("HERMES_KANBAN_TASK")
        os.environ["HERMES_KANBAN_TASK"] = tid
        try:
            idx = B._void_index(r.root, board=r.board)
        finally:
            os.environ.pop("HERMES_KANBAN_TASK") if old is None else os.environ.__setitem__("HERMES_KANBAN_TASK", old)
        self.assertEqual(idx["voided"], {})
        self.assertEqual(B._void_status({"cluster": "x", "reason": "the owners list carries a visit the source never had",
                                         "native_reject": genuine}, idx), ("", ""))


for _name in [n for n in dir(VerificationRoute) if n.startswith("test_")]:
    setattr(MergedPathWithState, _name, None)


if __name__ == "__main__":
    unittest.main(verbosity=1)
