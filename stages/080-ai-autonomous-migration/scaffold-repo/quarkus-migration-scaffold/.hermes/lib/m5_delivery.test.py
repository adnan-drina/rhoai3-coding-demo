#!/usr/bin/env python3
"""M5 delivery contract: idempotent start, blocked prerequisites, pipeline and live refusals."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from m5_delivery import (
    G1_PIN_SCRIPT,
    STAGE_LABELS,
    STAGE_TITLES,
    argv_for_card,
    assert_deployed,
    assess_eligibility,
    compose_verdict,
    deployment_from_app_pods,
    evaluate_g1_pin,
    evaluate_live,
    idempotency_key,
    observe_pipeline,
    original_coverage_obligation_ids,
    plan_cards,
    prepare_candidate,
    preserve_m4_coverage_account,
    read_g1_kill_ratio,
    record_eligibility,
    select_pipeline_run,
    start_delivery,
)
from planner.canonical import product_tree_sha256, sha256_file, write_canonical
from planner.paths import FROZEN_COVERAGE_ACCOUNT, FROZEN_COVERAGE_HISTORY, FROZEN_COVERAGE_SOURCE
from planner.paths import (
    DELIVERY_CANDIDATE,
    DELIVERY_ELIGIBILITY,
    DELIVERY_LIVE,
    DELIVERY_PIPELINE,
    LOOP_CARDS,
    LOOP_STEPS,
    M5_VERDICT,
    WORKLIST,
)

ROUTING_CHECKER = HERE.parent / "skills" / "gates" / "check-release-readiness" / "scripts" / "check-verdict-routing.py"
FACTORY_CHECK = HERE.parent / "skills" / "gates" / "check-release-readiness" / "scripts" / "check-factory-m5.py"
V10_PETTYPE = "sc:delete-referenced-pettypes-1"


def _root() -> Path:
    tmp = tempfile.TemporaryDirectory()
    root = Path(tmp.name)
    return root, tmp


def _write_closed(root: Path, card="t_m4close01", verdict="PROVISIONAL_ACCEPT", ship=False,
                  remaining_gaps=1, outstanding=None, reason="", coverage_rows=None):
    (root / "verification/loop").mkdir(parents=True, exist_ok=True)
    (root / "evidence/verdicts").mkdir(parents=True, exist_ok=True)
    write_canonical(root / LOOP_STEPS, {
        "schema": "rhoai3.loop-steps/v1", "steps": [], "attempts": {},
        "rejected": [{"kind": "close", "cluster": "M4_VERIFY", "card": card, "verdict": verdict,
                      "closed": True, "resumed": False, "parity_receipt_sha256": "a" * 64}],
    })
    account = {"remaining_gaps": remaining_gaps, "retired": 4}
    if coverage_rows is not None:
        account["rows"] = coverage_rows
    write_canonical(root / "evidence/verdicts/m4-verdict.json", {
        "gate": "compose-m4-verdict", "phase": "M4", "verdict": verdict, "ship": ship,
        "card_id": card, "coverage_account": account,
        "failed_floors": [], "floors": [], "reason": reason,
    })
    if outstanding is None:
        outstanding = ([{"kind": "coverage-account", "count": remaining_gaps,
                         "detail": "one remaining coverage gap"}] if remaining_gaps else [])
    write_canonical(root / "verification/loop/release-blockers.json", {
        "schema": "rhoai3.release-blockers/v1", "closed": True, "outstanding": outstanding,
    })
    write_canonical(root / WORKLIST, {"schema": "rhoai3.worklist/v1", "items": []})
    write_canonical(root / "evidence/type-inventory.json", {"schema": "rhoai3.type-inventory/v1", "types": []})


def _pin_data(*, passed=True, candidate_sha=""):
    sha = candidate_sha or "cc" * 20
    if passed:
        measurement = {
            "generated": 100, "attempted": 50, "killed": 40, "survived": 10, "timed_out": 0,
            "coverage_ratio": 0.5, "kill_attempted_ratio": 0.8, "kill_generated_ratio": 0.4,
            "source": "target/pit-reports/mutations.xml", "candidate_sha": sha,
        }
        token, stored = "PASS", True
    else:
        measurement = {
            "generated": 100, "attempted": 10, "killed": 1, "survived": 9, "timed_out": 0,
            "coverage_ratio": 0.1, "kill_attempted_ratio": 0.1, "kill_generated_ratio": 0.01,
            "source": "target/pit-reports/mutations.xml", "candidate_sha": sha,
        }
        token, stored = "pending_threshold", False
    digest = "e" * 64
    tree = "a" * 64
    measurement["mutations_xml_sha256"] = digest
    return {
        "schema": "migration/g1-kill-ratio-pin/v2-dual-denominator",
        "status": "PINNED",
        "candidate_sha": sha,
        "identity": {"candidate_sha": sha, "tree_sha256": tree},
        "scope": "measured live PIT slice",
        "measurement": measurement,
        "provenance": {
            "schema": "migration/pit-measurement/v1",
            "candidate_sha": sha,
            "mutations_xml_sha256": digest,
            "tree_sha256": tree,
        },
        "threshold": {
            "coverage_min": 0.41,
            "kill_attempted_min": 0.60,
            "kill_generated_min": 0.38,
            "source": "declared_engineering_target",
            "rationale": "fixture floor",
            "folklore": False,
        },
        "evaluation_against_measurement": {"pass": stored},
        "g1_kill_ratio": token,
        "g1_kill_ratio_threshold_pinned": True,
    }


def _write_pit_receipt(root: Path, *, candidate_sha: str, digest: str = "e" * 64,
                       git_sha: str = "", tree_sha256: str = "a" * 64) -> None:
    (root / "evidence/derived").mkdir(parents=True, exist_ok=True)
    doc = {
        "schema": "migration/pit-measurement/v1",
        "candidate_sha": candidate_sha,
        "mutations_xml_sha256": digest,
        "source": "target/pit-reports/mutations.xml",
        "tree_sha256": tree_sha256,
    }
    if git_sha:
        doc["git_sha"] = git_sha
    write_canonical(root / "evidence/derived/pit-measurement.json", doc)


def _write_pin(root: Path, *, passed=True, candidate_sha=""):
    (root / "evidence/derived").mkdir(parents=True, exist_ok=True)
    data = _pin_data(passed=passed, candidate_sha=candidate_sha)
    write_canonical(root / "evidence/derived/g1-kill-ratio-pin.json", data)
    _write_pit_receipt(
        root,
        candidate_sha=str(data["candidate_sha"]),
        digest=str(data["measurement"]["mutations_xml_sha256"]),
        tree_sha256=str(data["provenance"]["tree_sha256"]),
    )


def _strip_required_binding(doc: dict, *, field: str) -> None:
    if field == "report":
        if isinstance(doc.get("measurement"), dict):
            doc["measurement"].pop("mutations_xml_sha256", None)
        if isinstance(doc.get("provenance"), dict):
            doc["provenance"].pop("mutations_xml_sha256", None)
        doc.pop("mutations_xml_sha256", None)
    elif field == "tree":
        if isinstance(doc.get("identity"), dict):
            doc["identity"].pop("tree_sha256", None)
        if isinstance(doc.get("provenance"), dict):
            doc["provenance"].pop("tree_sha256", None)
        doc.pop("tree_sha256", None)
    elif field == "candidate":
        doc.pop("candidate_sha", None)
        doc.pop("git_sha", None)
        doc.pop("measured_sha", None)
        for key in ("identity", "measurement", "provenance", "scope"):
            inner = doc.get(key)
            if isinstance(inner, dict):
                inner.pop("candidate_sha", None)
                inner.pop("git_sha", None)
    else:
        raise AssertionError("unknown required binding %s" % field)


def _write_current_account(root: Path, sha: str, rows: list, remaining=0):
    (root / "evidence/verdicts").mkdir(parents=True, exist_ok=True)
    write_canonical(root / "evidence/verdicts/coverage-account.json", {
        "schema": "rhoai3.coverage-account/v1",
        "candidate_sha": sha,
        "summary": {"retired": len(rows), "remaining_gaps": remaining},
        "remaining_gaps": [r["path"] for r in rows if r.get("remaining_gap")],
        "rows": rows,
    })


def _write_discharge(root: Path, sha: str, ids: list, m4_digest: str, schema="rhoai3.coverage-discharge/v1"):
    (root / "verification/delivery").mkdir(parents=True, exist_ok=True)
    write_canonical(root / "verification/delivery/coverage-discharge.json", {
        "schema": schema,
        "candidate_sha": sha,
        "supersedes": {
            "kind": "coverage-account",
            "m4_verdict_sha256": m4_digest,
            "obligation_ids": ids,
        },
    })


def _synthetic_pit(path: Path, *, killed=40, survived=10, no_coverage=50):
    body = ["<mutations>"]
    body.extend('<mutation status="KILLED"/>' for _ in range(killed))
    body.extend('<mutation status="SURVIVED"/>' for _ in range(survived))
    body.extend('<mutation status="NO_COVERAGE"/>' for _ in range(no_coverage))
    body.append("</mutations>")
    path.write_text("".join(body), encoding="utf-8")


def _record_pit(root: Path, xml: Path, sha: str = "") -> subprocess.CompletedProcess:
    argv = [sys.executable, str(G1_PIN_SCRIPT), str(xml),
            "--record-measurement", "--root", str(root)]
    if sha:
        argv.extend(["--candidate-sha", sha])
    return subprocess.run(argv, capture_output=True, text=True, check=False)


def _run_pin_producer(xml: Path, out: Path, sha: str, *, root: Path | None = None) -> subprocess.CompletedProcess:
    root = root or xml.parent
    rec = _record_pit(root, xml, sha)
    if rec.returncode != 0:
        return rec
    return subprocess.run(
        [sys.executable, str(G1_PIN_SCRIPT), str(xml), "-o", str(out),
         "--candidate-sha", sha, "--root", str(root),
         "--coverage-min", "0.41", "--kill-attempted-min", "0.60",
         "--kill-generated-min", "0.38",
         "--source", "declared_engineering_target",
         "--rationale", "synthetic PIT fixture"],
        capture_output=True, text=True, check=False,
    )


def _bind_coverage_snapshot(root: Path, card_id: str, *, verdict_sha256: str = "") -> None:
    preserve_m4_coverage_account(root, card_id=card_id, verdict_sha256=verdict_sha256 or "d" * 64)


def _write_bound_delivery(root: Path, sha: str):
    digest = "sha256:" + "1" * 64
    write_canonical(root / DELIVERY_PIPELINE, {
        "schema": "rhoai3.m5-pipeline/v1", "ok": True, "candidate_sha": sha,
        "pipeline_run": "app-push-1", "image_digest": digest,
    })
    write_canonical(root / "verification/delivery/deployment.json", {
        "schema": "rhoai3.m5-deployment/v1", "ok": True, "candidate_sha": sha,
        "route_url": "https://app.example", "deployed_image": "registry/app@" + digest,
        "image_digest": digest,
    })
    write_canonical(root / DELIVERY_LIVE, {
        "schema": "rhoai3.m5-live/v1", "ok": True, "candidate_sha": sha, "issues": [],
        "deployed_image": "registry/app@" + digest,
    })


def _check_verdict_routing(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROUTING_CHECKER), str(root)],
        capture_output=True, text=True, check=False,
    )


def _git(sha="cafebabedeadbeef0123456789abcdefcafebabe"):
    def run(argv):
        if argv[:2] == ["git", "-C"] and argv[3:5] == ["rev-parse", "HEAD"]:
            return 0, sha + "\n", ""
        if argv[:2] == ["git", "-C"] and "remote" in argv:
            return 0, "https://github.com/example/app.git\n", ""
        if argv[:3] == ["hermes", "kanban", "list"]:
            return 0, "[]", ""
        if argv[:3] == ["hermes", "kanban", "create"]:
            key = argv[argv.index("--idempotency-key") + 1]
            return 0, json.dumps({"task_id": "t_" + key.replace(":", "")[:8]}), ""
        return 1, "", "unexpected %s" % argv
    return run


class Eligibility(unittest.TestCase):
    def test_empty_worklist_is_not_release_eligible(self):
        root, tmp = _root()
        self.addCleanup(tmp.cleanup)
        _write_closed(root)
        elig = assess_eligibility(root, runner=_git())
        self.assertTrue(elig["pipeline_eligible"])
        self.assertTrue(elig["worklist_empty"])
        self.assertFalse(elig["release_eligible"])
        self.assertTrue(any(r.get("kind") == "coverage-account" for r in elig["outstanding"]))
        self.assertFalse(any(r.get("kind") in {"not-shipped", "verdict-reason"} for r in elig["outstanding"]))

    def test_zero_gaps_without_pin_is_not_eligible_and_not_because_m4_ship(self):
        root, tmp = _root()
        self.addCleanup(tmp.cleanup)
        _write_closed(root, remaining_gaps=0, outstanding=[])
        elig = assess_eligibility(root, runner=_git())
        self.assertFalse(elig["m4_ship"])
        self.assertTrue(elig["pipeline_eligible"])
        self.assertFalse(elig["release_eligible"])
        kinds = [r.get("kind") for r in elig["outstanding"]]
        self.assertEqual(kinds, ["g1-kill-ratio"])
        self.assertNotIn("not-shipped", kinds)

    def test_failed_prerequisite_blocks_start(self):
        root, tmp = _root()
        self.addCleanup(tmp.cleanup)
        (root / "verification/loop").mkdir(parents=True)
        write_canonical(root / LOOP_STEPS, {"schema": "rhoai3.loop-steps/v1", "steps": [], "rejected": []})
        result = start_delivery(root, runner=_git(), execute=True)
        self.assertFalse(result["ok"])
        self.assertTrue(result["blocked"])
        self.assertEqual(result["failed_stage"], STAGE_LABELS["prepare"])
        self.assertFalse(result["created"])
        self.assertTrue(any(r["condition"] == "m4-closed" for r in result["eligibility"]["reasons"]))


class DuplicateStart(unittest.TestCase):
    def test_second_start_reuses_cards(self):
        root, tmp = _root()
        self.addCleanup(tmp.cleanup)
        _write_closed(root)
        sha = "aa" * 20
        created = {}

        def run(argv):
            if argv[:2] == ["git", "-C"] and argv[3:5] == ["rev-parse", "HEAD"]:
                return 0, sha + "\n", ""
            if argv[:2] == ["git", "-C"]:
                return 0, "https://github.com/example/app.git\n", ""
            if argv[:3] == ["hermes", "kanban", "list"]:
                cards = [{"id": tid, "idempotency_key": key} for key, tid in created.items()]
                return 0, json.dumps(cards), ""
            if argv[:3] == ["hermes", "kanban", "create"]:
                key = argv[argv.index("--idempotency-key") + 1]
                if key in created:
                    raise AssertionError("duplicate create for %s" % key)
                tid = "t_%s" % (key.split(":")[1][:8] + "0000")
                created[key] = tid
                return 0, json.dumps({"task_id": tid}), ""
            return 1, "", "unexpected"

        first = start_delivery(root, runner=run, execute=True)
        self.assertTrue(first["ok"])
        self.assertEqual(len(first["created"]), 3)
        self.assertFalse(first["reused"])
        second = start_delivery(root, runner=run, execute=True)
        self.assertTrue(second["ok"])
        self.assertFalse(second["created"])
        self.assertEqual(len(second["reused"]), 3)
        planned = plan_cards(first["eligibility"])
        self.assertEqual([p["stage"] for p in planned], ["prepare", "push", "accept"])
        self.assertEqual([p["title"] for p in planned], [
            STAGE_TITLES["prepare"], STAGE_TITLES["push"], STAGE_TITLES["accept"],
        ])
        self.assertEqual(planned[0]["parent"], "t_m4close01")
        self.assertEqual(planned[1]["parent"], "M5_PREPARE")
        self.assertEqual(planned[2]["parent"], "M5_PUSH")
        self.assertEqual([p["idempotency_key"] for p in planned], [
            idempotency_key("prepare", "t_m4close01", sha),
            idempotency_key("push", "t_m4close01", sha),
            idempotency_key("accept", "t_m4close01", sha),
        ])
        minted_titles = [cmd[3] for cmd in first["commands"]]
        self.assertEqual(minted_titles, [
            STAGE_TITLES["prepare"], STAGE_TITLES["push"], STAGE_TITLES["accept"],
        ])

        def _parent(argv):
            return argv[argv.index("--parent") + 1]

        self.assertEqual(_parent(first["commands"][0]), "t_m4close01")
        self.assertEqual(_parent(first["commands"][1]), created[idempotency_key("prepare", "t_m4close01", sha)])
        self.assertEqual(_parent(first["commands"][2]), created[idempotency_key("push", "t_m4close01", sha)])
        self.assertEqual(planned[0]["idempotency_key"], idempotency_key("prepare", "t_m4close01", sha))
        control = json.loads((root / LOOP_CARDS).read_text())["control"]
        self.assertEqual(set(control), {"m5_prepare", "m5_push", "m5_accept"})
        argv = argv_for_card(planned[0], "body", hermes="hermes", parent_id="t_m4close01",
                             workspace="dir:/projects/modernized")
        self.assertEqual(argv[3], STAGE_TITLES["prepare"])
        self.assertNotIn("--initial-status", argv)
        self.assertEqual(argv[argv.index("--assignee") + 1], "implementer")


class PipelineAndDeploy(unittest.TestCase):
    def _candidate(self, root: Path, sha="bb" * 20):
        _write_closed(root)
        prepare_candidate(root, runner=_git(sha))

    def test_wrong_revision_is_refused(self):
        root, tmp = _root()
        self.addCleanup(tmp.cleanup)
        self._candidate(root)
        run = {"metadata": {"name": "app-push-old"}, "spec": {"params": [{"name": "revision", "value": "ff" * 20}]},
               "status": {"conditions": [{"type": "Succeeded", "status": "True"}]}}
        selected = select_pipeline_run([run], "bb" * 20)
        self.assertFalse(selected["ok"])
        self.assertEqual(selected["reason"], "wrong-revision")
        doc = observe_pipeline(root, [run])
        self.assertFalse(doc["ok"])
        self.assertEqual(doc["failed_stage"], STAGE_LABELS["push"])

    def test_duplicate_pipeline_start_refused(self):
        root, tmp = _root()
        self.addCleanup(tmp.cleanup)
        sha = "bb" * 20
        self._candidate(root, sha)
        run = {"metadata": {"name": "app-push-1"}, "spec": {"params": [{"name": "revision", "value": sha}]},
               "status": {"conditions": [{"type": "Succeeded", "status": "True"}],
                          "pipelineResults": [{"name": "IMAGE_DIGEST", "value": "sha256:" + "1" * 64}]}}
        doc = observe_pipeline(root, [run], start_requested=True)
        self.assertFalse(doc["ok"])
        self.assertEqual(doc["reason"], "duplicate-pipeline")

    def test_pipeline_success_without_deployment_refused(self):
        root, tmp = _root()
        self.addCleanup(tmp.cleanup)
        sha = "bb" * 20
        self._candidate(root, sha)
        digest = "sha256:" + "1" * 64
        run = {"metadata": {"name": "app-push-1"}, "spec": {"params": [{"name": "revision", "value": sha}]},
               "status": {"conditions": [{"type": "Succeeded", "status": "True"}],
                          "pipelineResults": [{"name": "IMAGE_DIGEST", "value": digest}]}}
        pipe = observe_pipeline(root, [run])
        self.assertTrue(pipe["ok"])
        dep = assert_deployed(root, deployment={}, service={}, route={}, endpoints={})
        self.assertFalse(dep["ok"])
        self.assertIn("deployment-missing", dep["issues"])

    def test_image_mismatch_refused(self):
        root, tmp = _root()
        self.addCleanup(tmp.cleanup)
        sha = "bb" * 20
        self._candidate(root, sha)
        digest = "sha256:" + "1" * 64
        run = {"metadata": {"name": "app-push-1"}, "spec": {"params": [{"name": "revision", "value": sha}]},
               "status": {"conditions": [{"type": "Succeeded", "status": "True"}],
                          "pipelineResults": [{"name": "IMAGE_DIGEST", "value": digest}]}}
        observe_pipeline(root, [run])
        dep = assert_deployed(root, deployment={
            "spec": {"replicas": 1, "template": {"spec": {"containers": [{"image": "registry/app:" + sha}]}}},
            "status": {"readyReplicas": 1, "containerStatuses": [
                {"imageID": "registry.example/app@sha256:" + "2" * 64}]},
        }, service={"spec": {}}, route={"spec": {"host": "app.example.com", "tls": {"termination": "edge"}}},
            endpoints={"subsets": [{"addresses": [{"ip": "10.0.0.1"}]}]})
        self.assertFalse(dep["ok"])
        self.assertIn("image-mismatch", dep["issues"])

    def test_tag_alone_is_not_digest(self):
        root, tmp = _root()
        self.addCleanup(tmp.cleanup)
        sha = "bb" * 20
        self._candidate(root, sha)
        run = {"metadata": {"name": "app-push-1"}, "spec": {"params": [{"name": "revision", "value": sha}]},
               "status": {"conditions": [{"type": "Succeeded", "status": "True"}]}}
        doc = observe_pipeline(root, [run])
        self.assertFalse(doc["ok"])
        self.assertEqual(doc["reason"], "missing-image-digest")

    def test_taskrun_results_digest_is_accepted(self):
        root, tmp = _root()
        self.addCleanup(tmp.cleanup)
        sha = "bb" * 20
        self._candidate(root, sha)
        digest = "sha256:" + "3" * 64
        run = {"metadata": {"name": "app-push-1"}, "spec": {"params": [{"name": "revision", "value": sha}]},
               "status": {"conditions": [{"type": "Succeeded", "status": "True"}],
                          "results": [{"name": "IMAGE_DIGEST", "value": digest}]}}
        doc = observe_pipeline(root, [run])
        self.assertTrue(doc["ok"])
        self.assertEqual(doc["image_digest"], digest)


class LiveAndVerdict(unittest.TestCase):
    def test_failed_live_acceptance(self):
        result = evaluate_live(
            {"swagger": {"status": 404, "url": "https://app.example/q/swagger-ui"},
             "openapi": {"status": 404, "url": "https://app.example/q/openapi", "body": ""}},
            {"reads": [{"id": "owners", "path": "/api/owners"}], "crud": {"create": {}}},
            "sha256:" + "1" * 64, "disabled")
        self.assertFalse(result["ok"])
        self.assertEqual(result["failed_stage"], STAGE_LABELS["accept"])
        self.assertIn("swagger-unusable", result["issues"])

    def test_localhost_rejected(self):
        result = evaluate_live(
            {"swagger": {"status": 200, "url": "http://localhost:8080/q/swagger-ui"},
             "openapi": {"status": 200, "url": "http://localhost:8080/q/openapi", "body": '{"paths":{"/api/owners":{}}}'},
             "read:owners": {"status": 200, "url": "http://localhost:8080/api/owners"},
             "crud:create": {"status": 201}, "crud:read": {"status": 200}, "crud:delete": {"status": 204}},
            {"reads": [{"id": "owners", "path": "/api/owners"}], "crud": {"create": {}}},
            "sha256:" + "1" * 64, "disabled")
        self.assertFalse(result["ok"])
        self.assertIn("localhost-not-deployed", result["issues"])

    def test_deployed_does_not_erase_qualifications(self):
        root, tmp = _root()
        self.addCleanup(tmp.cleanup)
        _write_closed(root)
        sha = "cc" * 20
        prepare_candidate(root, runner=_git(sha))
        write_canonical(root / DELIVERY_PIPELINE, {
            "schema": "rhoai3.m5-pipeline/v1", "ok": True, "candidate_sha": sha,
            "pipeline_run": "app-push-1", "image_digest": "sha256:" + "1" * 64,
        })
        write_canonical(root / "verification/delivery/deployment.json", {
            "schema": "rhoai3.m5-deployment/v1", "ok": True, "candidate_sha": sha,
            "route_url": "https://app.example", "deployed_image": "registry/app@sha256:" + "1" * 64,
            "image_digest": "sha256:" + "1" * 64,
        })
        write_canonical(root / DELIVERY_LIVE, {
            "schema": "rhoai3.m5-live/v1", "ok": True, "candidate_sha": sha, "issues": [],
            "deployed_image": "registry/app@sha256:" + "1" * 64,
        })
        # eligibility.json from prepare
        record_eligibility(root, runner=_git(sha))
        verdict = compose_verdict(root)
        self.assertEqual(verdict["verdict"], "INCONCLUSIVE")
        self.assertFalse(verdict["ship"])
        self.assertEqual(verdict["deployment_status"], "deployed")
        self.assertTrue(verdict["live_ok"])
        self.assertTrue(verdict["outstanding"])
        self.assertEqual(verdict["routing"], "blocked")
        self.assertFalse(any(r.get("kind") in {"not-shipped", "verdict-reason"} for r in verdict["outstanding"]))
        self.assertEqual(sum(1 for r in verdict["outstanding"] if r.get("kind") == "coverage-account"), 1)

    def test_closed_m4_ship_false_with_release_evidence_is_accept(self):
        root, tmp = _root()
        self.addCleanup(tmp.cleanup)
        _write_closed(root, remaining_gaps=0, outstanding=[])
        _write_pin(root, passed=True)
        sha = "cc" * 20
        prepare_candidate(root, runner=_git(sha))
        _write_bound_delivery(root, sha)
        elig = assess_eligibility(root, runner=_git(sha))
        self.assertFalse(elig["m4_ship"])
        self.assertTrue(elig["release_eligible"])
        self.assertFalse(elig["outstanding"])
        verdict = compose_verdict(root)
        self.assertEqual(verdict["verdict"], "ACCEPT")
        self.assertTrue(verdict["ship"])
        self.assertEqual(verdict["accept_kind"], "full")
        self.assertEqual(verdict["routing"], "close")
        self.assertEqual(verdict["g1_kill_ratio"], "PASS")
        self.assertTrue(verdict["g1_kill_ratio_threshold_pinned"])
        self.assertEqual(verdict["deployment_status"], "deployed")
        self.assertTrue(verdict["live_ok"])
        self.assertFalse(verdict["outstanding"])
        checked = _check_verdict_routing(root)
        self.assertEqual(checked.returncode, 0, checked.stderr + checked.stdout)

    def test_v10_qualifications_remain_inconclusive(self):
        root, tmp = _root()
        self.addCleanup(tmp.cleanup)
        _write_closed(root, remaining_gaps=41, reason="floors met; coverage remains", outstanding=[
            {"kind": "parity-receipt", "count": 13,
             "detail": "13 of 34 entry point(s) did not pass (13 not compared at all)"},
            {"kind": "capability-gap", "count": 1,
             "detail": "PetType qualification %s (source fixture after_effect_status)" % V10_PETTYPE},
            {"kind": "coverage-account", "count": 41, "detail": "41 of 41 retired source(s) still have a remaining gap"},
            {"kind": "coverage-account", "count": 41, "detail": "41 remaining coverage gap(s) from the M4 coverage account"},
            {"kind": "verdict-reason", "count": 0, "detail": "floors met; coverage remains"},
            {"kind": "not-shipped", "count": 0, "detail": "the verdict does not ship (M4 never does)"},
        ])
        write_canonical(root / "evidence/verdicts/coverage-account.json", {
            "schema": "rhoai3.coverage-account/v1",
            "summary": {"retired": 41, "remaining_gaps": 41},
            "remaining_gaps": ["retired-source-still-open"],
        })
        sha = "cc" * 20
        prepare_candidate(root, runner=_git(sha))
        _write_bound_delivery(root, sha)
        elig = assess_eligibility(root, runner=_git(sha))
        self.assertFalse(elig["m4_ship"])
        self.assertTrue(elig["pipeline_eligible"])
        self.assertFalse(elig["release_eligible"])
        kinds = [r.get("kind") for r in elig["outstanding"]]
        self.assertNotIn("not-shipped", kinds)
        self.assertNotIn("verdict-reason", kinds)
        self.assertEqual(kinds.count("coverage-account"), 1)
        self.assertIn("parity-receipt", kinds)
        self.assertIn("capability-gap", kinds)
        self.assertNotIn("cors-gap", kinds)
        self.assertIn("g1-kill-ratio", kinds)
        verdict = compose_verdict(root)
        self.assertEqual(verdict["verdict"], "INCONCLUSIVE")
        self.assertFalse(verdict["ship"])
        self.assertEqual(verdict["routing"], "blocked")
        self.assertEqual(verdict["deployment_status"], "deployed")
        self.assertTrue(verdict["live_ok"])
        self.assertNotEqual(verdict["g1_kill_ratio"], "PASS")
        self.assertFalse(verdict["g1_kill_ratio_threshold_pinned"])
        checked = _check_verdict_routing(root)
        self.assertEqual(checked.returncode, 0, checked.stderr + checked.stdout)

    def test_stale_pipeline_after_candidate_change(self):
        root, tmp = _root()
        self.addCleanup(tmp.cleanup)
        _write_closed(root)
        prepare_candidate(root, runner=_git("dd" * 20))
        write_canonical(root / DELIVERY_PIPELINE, {
            "ok": True, "candidate_sha": "ee" * 20, "pipeline_run": "old",
            "image_digest": "sha256:" + "1" * 64,
        })
        write_canonical(root / "verification/delivery/deployment.json", {
            "ok": True, "candidate_sha": "ee" * 20, "route_url": "https://app.example",
        })
        write_canonical(root / DELIVERY_LIVE, {"ok": True, "candidate_sha": "ee" * 20})
        verdict = compose_verdict(root)
        self.assertEqual(verdict["verdict"], "REFUSE")
        self.assertEqual(verdict["failed_stage"], STAGE_LABELS["push"])
        self.assertTrue(verdict["stale_evidence"])
        self.assertTrue((root / M5_VERDICT).is_file())


class PodFallback(unittest.TestCase):
    def test_ready_app_pod_is_a_deployment_view(self):
        name = "app"
        pods = [{"status": {
            "podIP": "10.0.0.9",
            "containerStatuses": [{
                "name": name, "ready": True,
                "image": "registry/app:abc",
                "imageID": "registry/app@sha256:" + "4" * 64,
            }],
        }}]
        dep = deployment_from_app_pods(pods, name)
        self.assertEqual(dep["status"]["readyReplicas"], 1)
        self.assertIn("sha256:" + "4" * 64, dep["status"]["containerStatuses"][0]["imageID"])

    def test_route_url_uses_ingress_host(self):
        from m5_delivery import route_url
        url = route_url({
            "spec": {"subdomain": "petclinic-v10", "tls": {"termination": "edge"}},
            "status": {"ingress": [{"host": "petclinic-v10.apps.example.com"}]},
        })
        self.assertEqual(url, "https://petclinic-v10.apps.example.com")


GAPS = ["src/main/java/A.java", "src/main/java/B.java"]


class G1Consistency(unittest.TestCase):
    def test_conflicting_candidate_identities_cannot_pass(self):
        data = _pin_data()
        data["identity"] = {"candidate_sha": "dd" * 20}
        scored = evaluate_g1_pin(data, candidate_sha="cc" * 20, rel="pin.json")
        self.assertFalse(scored["pass"])
        self.assertIn("conflict", scored["detail"])

    def test_killed_above_attempted_cannot_pass(self):
        data = _pin_data()
        data["measurement"]["killed"] = 60
        data["measurement"]["kill_attempted_ratio"] = 1.2
        scored = evaluate_g1_pin(data, candidate_sha="cc" * 20, rel="pin.json")
        self.assertFalse(scored["pass"])
        self.assertIn("inconsistent", scored["detail"])

    def test_attempted_above_generated_cannot_pass(self):
        data = _pin_data()
        data["measurement"]["attempted"] = 120
        scored = evaluate_g1_pin(data, candidate_sha="cc" * 20, rel="pin.json")
        self.assertFalse(scored["pass"])
        self.assertIn("inconsistent", scored["detail"])

    def test_stored_eval_disagrees_with_recompute_with_pass_token(self):
        data = _pin_data()
        data["evaluation_against_measurement"] = {
            "pass": True, "coverage_ratio": 0.99, "kill_attempted_ratio": 0.8,
            "kill_generated_ratio": 0.4, "killed": 40, "attempted": 50, "generated": 100,
        }
        scored = evaluate_g1_pin(data, candidate_sha="cc" * 20, rel="pin.json")
        self.assertFalse(scored["pass"])
        self.assertIn("disagrees", scored["detail"])

    def test_stored_eval_disagrees_with_recompute_without_pass_token(self):
        data = _pin_data()
        data.pop("g1_kill_ratio")
        data["evaluation_against_measurement"] = {"pass": False}
        scored = evaluate_g1_pin(data, candidate_sha="cc" * 20, rel="pin.json")
        self.assertFalse(scored["pass"])
        self.assertIn("disagrees", scored["detail"])

    def test_foreign_unbound_contradictory_cannot_accept(self):
        data = _pin_data()
        data["candidate_sha"] = "ff" * 20
        data["identity"] = {"candidate_sha": "ff" * 20}
        data["measurement"]["candidate_sha"] = "ff" * 20
        if isinstance(data.get("provenance"), dict):
            data["provenance"]["candidate_sha"] = "ff" * 20
        self.assertFalse(evaluate_g1_pin(data, candidate_sha="cc" * 20, rel="pin.json")["pass"])
        data = _pin_data()
        data.pop("candidate_sha")
        data.pop("identity")
        data["measurement"].pop("candidate_sha", None)
        data.get("provenance", {}).pop("candidate_sha", None)
        data.get("provenance", {}).pop("git_sha", None)
        scored = evaluate_g1_pin(data, candidate_sha="cc" * 20, rel="pin.json")
        self.assertFalse(scored["pass"])
        self.assertIn("not bound", scored["detail"])
        data = _pin_data()
        data["evaluation_against_measurement"] = {"pass": False}
        scored = evaluate_g1_pin(data, candidate_sha="cc" * 20, rel="pin.json")
        self.assertFalse(scored["pass"])
        self.assertIn("disagrees", scored["detail"])
        root, tmp = _root()
        self.addCleanup(tmp.cleanup)
        _write_closed(root, remaining_gaps=0, outstanding=[])
        data = _pin_data()
        data["identity"] = {"candidate_sha": "dd" * 20}
        (root / "evidence/derived").mkdir(parents=True, exist_ok=True)
        write_canonical(root / "evidence/derived/g1-kill-ratio-pin.json", data)
        sha = "cc" * 20
        prepare_candidate(root, runner=_git(sha))
        _write_bound_delivery(root, sha)
        elig = assess_eligibility(root, runner=_git(sha))
        self.assertFalse(elig["release_eligible"])
        self.assertTrue(any(r.get("kind") == "g1-kill-ratio" for r in elig["outstanding"]))
        self.assertEqual(compose_verdict(root)["verdict"], "INCONCLUSIVE")


class CoverageDischarge(unittest.TestCase):
    def test_duplicate_unrelated_ids_with_foreign_account_cannot_accept(self):
        root, tmp = _root()
        self.addCleanup(tmp.cleanup)
        _write_closed(root, remaining_gaps=2)
        m4 = root / "evidence/verdicts/m4-verdict.json"
        before = m4.read_bytes()
        digest = sha256_file(m4)
        sha = "cc" * 20
        _write_discharge(root, sha, ["unrelated-id", "unrelated-id"], digest)
        _write_current_account(root, "ab" * 20, [
            {"path": "unrelated-id", "remaining_gap": False},
        ], remaining=0)
        _write_pin(root, candidate_sha=sha)
        prepare_candidate(root, runner=_git(sha))
        _write_bound_delivery(root, sha)
        elig = assess_eligibility(root, runner=_git(sha))
        self.assertFalse(elig["release_eligible"])
        self.assertTrue(any(r.get("kind") == "coverage-account" for r in elig["outstanding"]))
        self.assertEqual(compose_verdict(root)["verdict"], "INCONCLUSIVE")
        self.assertEqual(m4.read_bytes(), before)

    def test_unbound_and_unsupported_discharge_leave_gaps_open(self):
        root, tmp = _root()
        self.addCleanup(tmp.cleanup)
        rows = [{"path": p, "remaining_gap": True} for p in GAPS]
        _write_closed(root, remaining_gaps=2, coverage_rows=rows)
        m4 = root / "evidence/verdicts/m4-verdict.json"
        before = m4.read_bytes()
        digest = sha256_file(m4)
        sha = "cc" * 20
        _write_discharge(root, sha, GAPS, digest, schema="rhoai3.not-a-discharge/v0")
        _write_current_account(root, sha, [{"path": p, "remaining_gap": False} for p in GAPS], remaining=0)
        _write_pin(root, candidate_sha=sha)
        prepare_candidate(root, runner=_git(sha))
        _write_bound_delivery(root, sha)
        elig = assess_eligibility(root, runner=_git(sha))
        self.assertFalse(elig["release_eligible"])
        self.assertTrue(any(r.get("kind") == "coverage-account" for r in elig["outstanding"]))
        write_canonical(root / "verification/delivery/coverage-discharge.json", {
            "schema": "rhoai3.coverage-discharge/v1",
            "candidate_sha": sha,
            "supersedes": {"kind": "coverage-account", "m4_verdict_sha256": digest,
                           "obligation_ids": GAPS},
        })
        (root / "evidence/verdicts/coverage-account.json").write_text(
            json.dumps({
                "schema": "rhoai3.coverage-account/v1",
                "summary": {"retired": 2, "remaining_gaps": 0},
                "remaining_gaps": [],
                "rows": [{"path": p, "remaining_gap": False} for p in GAPS],
            }) + "\n", encoding="utf-8")
        elig = assess_eligibility(root, runner=_git(sha))
        self.assertFalse(elig["release_eligible"])
        self.assertTrue(any(r.get("kind") == "coverage-account" for r in elig["outstanding"]))
        self.assertEqual(m4.read_bytes(), before)

    def test_valid_discharge_preserves_m4_bytes_and_accepts(self):
        root, tmp = _root()
        self.addCleanup(tmp.cleanup)
        rows = [{"path": p, "remaining_gap": True} for p in GAPS]
        _write_closed(root, remaining_gaps=2, coverage_rows=rows,
                      outstanding=[{"kind": "coverage-account", "count": 2, "ids": GAPS,
                                    "detail": "two remaining coverage gaps"}])
        m4 = root / "evidence/verdicts/m4-verdict.json"
        before = m4.read_bytes()
        digest = sha256_file(m4)
        sha = "cc" * 20
        _write_discharge(root, sha, GAPS, digest)
        _write_current_account(root, sha, [{"path": p, "remaining_gap": False} for p in GAPS], remaining=0)
        _write_pin(root, candidate_sha=sha)
        prepare_candidate(root, runner=_git(sha))
        _write_bound_delivery(root, sha)
        elig = assess_eligibility(root, runner=_git(sha))
        self.assertFalse(elig["m4_ship"])
        self.assertTrue(elig["release_eligible"])
        self.assertFalse(elig["outstanding"])
        verdict = compose_verdict(root)
        self.assertEqual(verdict["verdict"], "ACCEPT")
        self.assertEqual(m4.read_bytes(), before)
        self.assertEqual(sha256_file(m4), digest)


class ProducerToConsumer(unittest.TestCase):
    def test_real_producer_pin_passes_m5_unchanged_for_measured_candidate(self):
        root, tmp = _root()
        self.addCleanup(tmp.cleanup)
        sha = "cc" * 20
        xml = root / "mutations.xml"
        _synthetic_pit(xml)
        pin_path = root / "evidence/derived/g1-kill-ratio-pin.json"
        pin_path.parent.mkdir(parents=True, exist_ok=True)
        proc = _run_pin_producer(xml, pin_path, sha)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(pin_path.read_text(encoding="utf-8"))
        self.assertEqual(data.get("candidate_sha"), sha)
        scored = evaluate_g1_pin(data, candidate_sha=sha, rel="evidence/derived/g1-kill-ratio-pin.json")
        self.assertTrue(scored["pass"], scored)
        _write_closed(root, remaining_gaps=0, outstanding=[])
        prepare_candidate(root, runner=_git(sha))
        _write_bound_delivery(root, sha)
        elig = assess_eligibility(root, runner=_git(sha))
        self.assertTrue(elig["release_eligible"])
        self.assertEqual(compose_verdict(root)["verdict"], "ACCEPT")
        self.assertEqual(compose_verdict(root)["g1_kill_ratio"], "PASS")

    def test_real_producer_pin_rejects_foreign_candidate_unchanged(self):
        root, tmp = _root()
        self.addCleanup(tmp.cleanup)
        measured = "cc" * 20
        foreign = "ff" * 20
        xml = root / "mutations.xml"
        _synthetic_pit(xml)
        pin_path = root / "evidence/derived/g1-kill-ratio-pin.json"
        pin_path.parent.mkdir(parents=True, exist_ok=True)
        proc = _run_pin_producer(xml, pin_path, measured)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(pin_path.read_text(encoding="utf-8"))
        scored = evaluate_g1_pin(data, candidate_sha=foreign, rel="evidence/derived/g1-kill-ratio-pin.json")
        self.assertFalse(scored["pass"])
        self.assertIn("foreign", scored["detail"])
        _write_closed(root, remaining_gaps=0, outstanding=[])
        prepare_candidate(root, runner=_git(foreign))
        _write_bound_delivery(root, foreign)
        elig = assess_eligibility(root, runner=_git(foreign))
        self.assertFalse(elig["release_eligible"])
        self.assertTrue(any(r.get("kind") == "g1-kill-ratio" for r in elig["outstanding"]))
        self.assertEqual(compose_verdict(root)["verdict"], "INCONCLUSIVE")

    def test_producer_refuses_unbound_measurement(self):
        root, tmp = _root()
        self.addCleanup(tmp.cleanup)
        xml = root / "mutations.xml"
        _synthetic_pit(xml)
        out = root / "pin.json"
        proc = subprocess.run(
            [sys.executable, str(G1_PIN_SCRIPT), str(xml), "-o", str(out),
             "--coverage-min", "0.41", "--kill-attempted-min", "0.60",
             "--source", "declared_engineering_target", "--rationale", "unbound"],
            capture_output=True, text=True, check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse(out.is_file())

    def test_producer_resolves_candidate_from_root(self):
        root, tmp = _root()
        self.addCleanup(tmp.cleanup)
        sha = "cc" * 20
        write_canonical(root / "verification/delivery/candidate.json", {
            "schema": "rhoai3.m5-candidate/v1", "candidate_sha": sha, "ok": True,
        })
        xml = root / "mutations.xml"
        _synthetic_pit(xml)
        rec = _record_pit(root, xml, sha)
        self.assertEqual(rec.returncode, 0, rec.stderr)
        pin_path = root / "evidence/derived/g1-kill-ratio-pin.json"
        pin_path.parent.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run(
            [sys.executable, str(G1_PIN_SCRIPT), str(xml), "-o", str(pin_path),
             "--root", str(root),
             "--coverage-min", "0.41", "--kill-attempted-min", "0.60",
             "--kill-generated-min", "0.38",
             "--source", "declared_engineering_target",
             "--rationale", "synthetic PIT fixture via --root"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(pin_path.read_text(encoding="utf-8"))
        self.assertEqual(data.get("candidate_sha"), sha)
        self.assertEqual(data.get("provenance", {}).get("candidate_sha"), sha)
        scored = evaluate_g1_pin(data, candidate_sha=sha, rel="evidence/derived/g1-kill-ratio-pin.json")
        self.assertTrue(scored["pass"], scored)

    def test_unchanged_xml_refuses_newer_delivery_candidate(self):
        root, tmp = _root()
        self.addCleanup(tmp.cleanup)
        a, b = "aa" * 20, "bb" * 20
        xml = root / "mutations.xml"
        _synthetic_pit(xml)
        write_canonical(root / "verification/build/run.json", {
            "schema": "rhoai3.verify-run/v1", "candidate_sha256": a,
        })
        rec = _record_pit(root, xml, a)
        self.assertEqual(rec.returncode, 0, rec.stderr)
        pin = root / "evidence/derived/g1-kill-ratio-pin.json"
        pin.parent.mkdir(parents=True, exist_ok=True)

        def pin_for(sha: str) -> subprocess.CompletedProcess:
            write_canonical(root / "verification/delivery/candidate.json", {
                "schema": "rhoai3.m5-candidate/v1", "candidate_sha": sha, "ok": True,
            })
            return subprocess.run(
                [sys.executable, str(G1_PIN_SCRIPT), str(xml), "-o", str(pin),
                 "--root", str(root),
                 "--coverage-min", "0.41", "--kill-attempted-min", "0.60",
                 "--kill-generated-min", "0.38",
                 "--source", "declared_engineering_target",
                 "--rationale", "synthetic PIT fixture"],
                capture_output=True, text=True, check=False,
            )

        first = pin_for(a)
        self.assertEqual(first.returncode, 0, first.stderr)
        old_pin = json.loads(pin.read_text(encoding="utf-8"))
        self.assertEqual(old_pin["candidate_sha"], a)
        second = pin_for(b)
        self.assertNotEqual(second.returncode, 0, second.stderr)
        self.assertTrue(
            "conflicting" in second.stderr or "provenance" in second.stderr,
            second.stderr,
        )
        still = json.loads(pin.read_text(encoding="utf-8"))
        self.assertEqual(still["candidate_sha"], a)
        _write_closed(root, remaining_gaps=0, outstanding=[])
        prepare_candidate(root, runner=_git(b))
        _write_bound_delivery(root, b)
        self.assertFalse(read_g1_kill_ratio(root, candidate_sha=b)["pass"])
        self.assertEqual(compose_verdict(root)["verdict"], "INCONCLUSIVE")

    def test_matching_measurement_pins_release_eligible(self):
        root, tmp = _root()
        self.addCleanup(tmp.cleanup)
        sha = "bb" * 20
        xml = root / "mutations.xml"
        _synthetic_pit(xml)
        write_canonical(root / "verification/build/run.json", {
            "schema": "rhoai3.verify-run/v1", "candidate_sha256": sha,
        })
        write_canonical(root / "verification/delivery/candidate.json", {
            "schema": "rhoai3.m5-candidate/v1", "candidate_sha": sha, "ok": True,
        })
        rec = _record_pit(root, xml, sha)
        self.assertEqual(rec.returncode, 0, rec.stderr)
        pin = root / "evidence/derived/g1-kill-ratio-pin.json"
        pin.parent.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run(
            [sys.executable, str(G1_PIN_SCRIPT), str(xml), "-o", str(pin),
             "--root", str(root),
             "--coverage-min", "0.41", "--kill-attempted-min", "0.60",
             "--kill-generated-min", "0.38",
             "--source", "declared_engineering_target",
             "--rationale", "synthetic matching measurement"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(pin.read_text(encoding="utf-8"))
        self.assertEqual(data["candidate_sha"], sha)
        scored = evaluate_g1_pin(data, candidate_sha=sha, rel="evidence/derived/g1-kill-ratio-pin.json")
        self.assertTrue(scored["pass"], scored)
        _write_closed(root, remaining_gaps=0, outstanding=[])
        prepare_candidate(root, runner=_git(sha))
        _write_bound_delivery(root, sha)
        elig = assess_eligibility(root, runner=_git(sha))
        self.assertTrue(elig["release_eligible"], elig["outstanding"])
        self.assertEqual(compose_verdict(root)["verdict"], "ACCEPT")

    def test_producer_refuses_missing_measurement_provenance(self):
        root, tmp = _root()
        self.addCleanup(tmp.cleanup)
        sha = "cc" * 20
        write_canonical(root / "verification/delivery/candidate.json", {
            "schema": "rhoai3.m5-candidate/v1", "candidate_sha": sha, "ok": True,
        })
        xml = root / "mutations.xml"
        _synthetic_pit(xml)
        out = root / "pin.json"
        proc = subprocess.run(
            [sys.executable, str(G1_PIN_SCRIPT), str(xml), "-o", str(out),
             "--root", str(root),
             "--coverage-min", "0.41", "--kill-attempted-min", "0.60",
             "--source", "declared_engineering_target", "--rationale", "no receipt"],
            capture_output=True, text=True, check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("provenance", proc.stderr)
        self.assertFalse(out.is_file())

    def test_stripped_pin_without_receipt_cannot_accept(self):
        root, tmp = _root()
        self.addCleanup(tmp.cleanup)
        sha = "aa" * 20
        xml = root / "mutations.xml"
        _synthetic_pit(xml)
        pin = root / "evidence/derived/g1-kill-ratio-pin.json"
        pin.parent.mkdir(parents=True, exist_ok=True)
        proc = _run_pin_producer(xml, pin, sha, root=root)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        receipt = root / "evidence/derived/pit-measurement.json"
        receipt.rename(receipt.with_suffix(".preserved.json"))
        data = json.loads(pin.read_text(encoding="utf-8"))
        data.pop("provenance", None)
        data.get("measurement", {}).pop("mutations_xml_sha256", None)
        write_canonical(pin, data)
        _write_closed(root, remaining_gaps=0, outstanding=[])
        prepare_candidate(root, runner=_git(sha))
        _write_bound_delivery(root, sha)
        self.assertFalse(receipt.is_file())
        self.assertFalse(read_g1_kill_ratio(root, candidate_sha=sha)["pass"])
        self.assertEqual(compose_verdict(root)["verdict"], "INCONCLUSIVE")

    def test_embedded_digest_without_receipt_cannot_accept(self):
        """Architect embedded-provenance-counterexample: a digest string is not a receipt."""
        for embedded in ("not-a-digest", "e" * 64):
            with self.subTest(embedded=embedded[:16]):
                root, tmp = _root()
                self.addCleanup(tmp.cleanup)
                sha = "aa" * 20
                xml = root / "mutations.xml"
                _synthetic_pit(xml)
                pin = root / "evidence/derived/g1-kill-ratio-pin.json"
                pin.parent.mkdir(parents=True, exist_ok=True)
                proc = _run_pin_producer(xml, pin, sha, root=root)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                receipt = root / "evidence/derived/pit-measurement.json"
                receipt.rename(receipt.with_suffix(".preserved.json"))
                data = json.loads(pin.read_text(encoding="utf-8"))
                data.get("measurement", {}).pop("mutations_xml_sha256", None)
                data["provenance"] = {"mutations_xml_sha256": embedded}
                write_canonical(pin, data)
                _write_closed(root, remaining_gaps=0, outstanding=[])
                prepare_candidate(root, runner=_git(sha))
                _write_bound_delivery(root, sha)
                self.assertFalse(receipt.is_file())
                self.assertFalse(read_g1_kill_ratio(root, candidate_sha=sha)["pass"])
                self.assertEqual(compose_verdict(root)["verdict"], "INCONCLUSIVE")
                write_canonical(root / "evidence/preflight/factory.json", {
                    "phase": "FACTORY", "status": "factory_ready",
                })
                factory = subprocess.run(
                    [sys.executable, "-B", str(FACTORY_CHECK), str(root)],
                    capture_output=True, text=True, check=False,
                )
                self.assertNotEqual(factory.returncode, 0, factory.stdout + factory.stderr)

    def test_malformed_or_mismatched_receipt_cannot_accept(self):
        sha = "cc" * 20
        digest = "e" * 64
        tree = "a" * 64
        cases = (
            {"schema": "not-pit-measurement", "candidate_sha": sha,
             "mutations_xml_sha256": digest, "tree_sha256": tree},
            {"schema": "migration/pit-measurement/v1", "candidate_sha": sha,
             "mutations_xml_sha256": "not-a-digest", "tree_sha256": tree},
            {"schema": "migration/pit-measurement/v1", "candidate_sha": "dd" * 20,
             "mutations_xml_sha256": digest, "tree_sha256": tree},
            {"schema": "migration/pit-measurement/v1", "candidate_sha": sha,
             "mutations_xml_sha256": "f" * 64, "tree_sha256": tree},
            {"schema": "migration/pit-measurement/v1", "candidate_sha": sha,
             "mutations_xml_sha256": digest, "tree_sha256": "b" * 64},
        )
        for receipt in cases:
            with self.subTest(receipt=receipt):
                root, tmp = _root()
                self.addCleanup(tmp.cleanup)
                _write_closed(root, remaining_gaps=0, outstanding=[])
                _write_pin(root, passed=True, candidate_sha=sha)
                write_canonical(root / "evidence/derived/pit-measurement.json", receipt)
                prepare_candidate(root, runner=_git(sha))
                _write_bound_delivery(root, sha)
                self._assert_g1_blocks_release(root, sha)

    def test_missing_pin_report_binding_cannot_accept(self):
        """Architect missing-pin-report-binding: omitted pin digest is not optional."""
        root, tmp = _root()
        self.addCleanup(tmp.cleanup)
        sha = "aa" * 20
        xml = root / "mutations.xml"
        _synthetic_pit(xml)
        pin = root / "evidence/derived/g1-kill-ratio-pin.json"
        pin.parent.mkdir(parents=True, exist_ok=True)
        proc = _run_pin_producer(xml, pin, sha, root=root)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        receipt = root / "evidence/derived/pit-measurement.json"
        receipt_doc = json.loads(receipt.read_text(encoding="utf-8"))
        receipt_doc["mutations_xml_sha256"] = "f" * 64
        write_canonical(receipt, receipt_doc)
        data = json.loads(pin.read_text(encoding="utf-8"))
        data.get("measurement", {}).pop("mutations_xml_sha256", None)
        data.get("provenance", {}).pop("mutations_xml_sha256", None)
        write_canonical(pin, data)
        _write_closed(root, remaining_gaps=0, outstanding=[])
        prepare_candidate(root, runner=_git(sha))
        _write_bound_delivery(root, sha)
        self.assertFalse(bool(
            data.get("provenance", {}).get("mutations_xml_sha256")
            or data.get("measurement", {}).get("mutations_xml_sha256")
        ))
        self._assert_g1_blocks_release(root, sha)

    def test_missing_required_binding_cannot_accept(self):
        for side, field in (
            ("pin", "report"), ("pin", "tree"), ("pin", "candidate"),
            ("receipt", "report"), ("receipt", "tree"), ("receipt", "candidate"),
        ):
            with self.subTest(side=side, field=field):
                root, tmp = _root()
                self.addCleanup(tmp.cleanup)
                sha = "aa" * 20
                xml = root / "mutations.xml"
                _synthetic_pit(xml)
                pin_path = root / "evidence/derived/g1-kill-ratio-pin.json"
                pin_path.parent.mkdir(parents=True, exist_ok=True)
                proc = _run_pin_producer(xml, pin_path, sha, root=root)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                receipt_path = root / "evidence/derived/pit-measurement.json"
                pin = json.loads(pin_path.read_text(encoding="utf-8"))
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                self.assertTrue(pin.get("provenance", {}).get("mutations_xml_sha256"))
                self.assertTrue(pin.get("provenance", {}).get("tree_sha256") or pin.get("identity", {}).get("tree_sha256"))
                self.assertTrue(receipt.get("mutations_xml_sha256"))
                self.assertTrue(receipt.get("tree_sha256"))
                target = pin if side == "pin" else receipt
                _strip_required_binding(target, field=field)
                write_canonical(pin_path if side == "pin" else receipt_path, target)
                _write_closed(root, remaining_gaps=0, outstanding=[])
                prepare_candidate(root, runner=_git(sha))
                _write_bound_delivery(root, sha)
                self._assert_g1_blocks_release(root, sha)

    def _assert_g1_blocks_release(self, root: Path, sha: str) -> None:
        self.assertFalse(read_g1_kill_ratio(root, candidate_sha=sha)["pass"])
        self.assertEqual(compose_verdict(root)["verdict"], "INCONCLUSIVE")
        routing = _check_verdict_routing(root)
        self.assertEqual(routing.returncode, 0, routing.stderr + routing.stdout)
        write_canonical(root / "evidence/preflight/factory.json", {
            "phase": "FACTORY", "status": "factory_ready",
        })
        factory = subprocess.run(
            [sys.executable, "-B", str(FACTORY_CHECK), str(root)],
            capture_output=True, text=True, check=False,
        )
        self.assertNotEqual(factory.returncode, 0, factory.stdout + factory.stderr)

    def test_real_git_commit_and_product_tree_are_distinct(self):
        root, tmp = _root()
        self.addCleanup(tmp.cleanup)

        def git(*args: str) -> str:
            return subprocess.run(
                ["git", "-C", str(root), *args],
                check=True, capture_output=True, text=True,
            ).stdout.strip()

        git("init", "-q")
        (root / "pom.xml").write_text("<project/>\n", encoding="utf-8")
        git("add", "pom.xml")
        subprocess.run(
            ["git", "-C", str(root), "-c", "user.name=Fixture",
             "-c", "user.email=fixture@example.invalid", "commit", "-qm", "synthetic"],
            check=True, capture_output=True, text=True,
        )
        sha = git("rev-parse", "HEAD")
        tree = product_tree_sha256(root)
        self.assertNotEqual(sha, tree)
        self.assertEqual(len(sha), 40)
        self.assertEqual(len(tree), 64)
        write_canonical(root / "verification/delivery/candidate.json", {
            "schema": "rhoai3.m5-candidate/v1", "candidate_sha": sha, "ok": True,
        })
        write_canonical(root / "verification/build/run.json", {
            "schema": "rhoai3.verify-run/v1", "candidate_sha256": tree,
        })
        xml = root / "mutations.xml"
        _synthetic_pit(xml)
        rec = _record_pit(root, xml, "")
        self.assertEqual(rec.returncode, 0, rec.stderr)
        pin = root / "evidence/derived/g1-kill-ratio-pin.json"
        pin.parent.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run(
            [sys.executable, str(G1_PIN_SCRIPT), str(xml), "-o", str(pin),
             "--root", str(root),
             "--coverage-min", "0.41", "--kill-attempted-min", "0.60",
             "--kill-generated-min", "0.38",
             "--source", "declared_engineering_target",
             "--rationale", "synthetic git+tree"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(pin.read_text(encoding="utf-8"))
        self.assertEqual(data["candidate_sha"], sha)
        self.assertEqual(data.get("identity", {}).get("git_sha") or sha, sha)
        self.assertEqual(data.get("provenance", {}).get("tree_sha256"), product_tree_sha256(root))
        self.assertNotEqual(data["candidate_sha"], data["provenance"]["tree_sha256"])
        scored = evaluate_g1_pin(data, candidate_sha=sha, rel="pin.json")
        self.assertTrue(scored["pass"], scored)


COMPOSER = HERE.parent / "skills" / "gates" / "compose-m4-verdict" / "scripts" / "compose-coverage-account.py"
BINDER = HERE.parent / "skills" / "gates" / "compose-m4-verdict" / "scripts" / "bind-m4-verdict.py"
SYNTHETIC_GAPS = ["src/main/java/a/GapOne.java", "src/main/java/a/GapTwo.java"]
LATER_GAPS = ["src/main/java/a/LaterOne.java", "src/main/java/a/LaterTwo.java"]
DECISIONS_HEAD = """schema: rhoai3.decisions/v2

adrs:
  - id: ADR-001
    status: accepted
    title: Destination platform
  - id: ADR-009
    status: accepted
    title: Retire the thing

destination_platform:
  id: quarkus-rhbq-3.27
  adr: ADR-001

thresholds:
  max_attempts: 3
  adr: ADR-001

not_applicable: []

datasource:
  adr: ADR-001
  db_kind: postgresql
  db_version: "16"
  jdbc_extension: io.quarkus:quarkus-jdbc-postgresql
  profile: prod
  instance: fixture-isolated-postgres
  jdbc_url_env: FIXTURE_DB_URL
  username_env: FIXTURE_DB_USER
  password_env: FIXTURE_DB_PASSWORD
  reset_procedure: drop and recreate, then apply schema and seed
  schema_owner: destination-orm
  schema_sql: ""
  seed_sql: ""
  hibernate_generation: none
  source_baseline_db_kind: hsqldb

retired_sources:
"""


def _decisions_yaml(*, replaced: bool, gaps: list | None = None) -> str:
    rows = []
    for path in (gaps or SYNTHETIC_GAPS):
        row = "  - path: %s\n    adr: ADR-009\n    reason: synthetic fixture retirement" % path
        if replaced:
            row += "\n    replaced_by: [ep-ok]"
        rows.append(row)
    return DECISIONS_HEAD + "\n".join(rows) + "\n"


def _write_parity(root: Path, *, passed: bool) -> None:
    (root / "verification/parity").mkdir(parents=True, exist_ok=True)
    write_canonical(root / "verification/parity/receipt.json", {
        "schema": "rhoai3.parity-receipt/v1",
        "verdict": "PASS" if passed else "FAIL",
        "entry_points": [{"entry_point": "ep-ok", "verdict": "PASS" if passed else "FAIL", "reason": "synthetic"}],
        "coverage_gaps": [],
    })


def _link_hermes(root: Path) -> None:
    dest = root / ".hermes"
    if dest.exists() or dest.is_symlink():
        return
    dest.symlink_to(HERE.parent, target_is_directory=True)


class ReleaseEvidenceIntegration(unittest.TestCase):
    """Producer-to-validator path. Synthetic fixtures, not dest v10 / not live PIT."""

    def test_composer_then_pin_then_release_checks_accept(self):
        root, tmp = _root()
        self.addCleanup(tmp.cleanup)
        sha = "cc" * 20
        _link_hermes(root)
        (root / "decisions.yaml").write_text(_decisions_yaml(replaced=False), encoding="utf-8")
        _write_parity(root, passed=False)
        (root / "verification/build").mkdir(parents=True, exist_ok=True)
        write_canonical(root / "verification/build/run.json", {
            "schema": "rhoai3.verify-run/v1", "candidate_sha256": sha,
        })
        proc = subprocess.run([sys.executable, str(COMPOSER), str(root)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        _bind_coverage_snapshot(root, "t_m4close01")
        frozen = root / FROZEN_COVERAGE_ACCOUNT
        self.assertTrue(frozen.is_file())
        frozen_bytes = frozen.read_bytes()
        original_ids = json.loads(frozen_bytes.decode())["remaining_gaps"]
        self.assertEqual(original_ids, SYNTHETIC_GAPS)
        src = json.loads((root / FROZEN_COVERAGE_SOURCE).read_text(encoding="utf-8"))
        self.assertEqual(src.get("card_id"), "t_m4close01")

        (root / "decisions.yaml").write_text(_decisions_yaml(replaced=True), encoding="utf-8")
        _write_parity(root, passed=True)
        write_canonical(root / "verification/delivery/candidate.json", {
            "schema": "rhoai3.m5-candidate/v1", "candidate_sha": sha, "ok": True,
        })
        proc = subprocess.run([sys.executable, str(COMPOSER), str(root)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        live = json.loads((root / "evidence/verdicts/coverage-account.json").read_text())
        self.assertEqual(live.get("summary", {}).get("remaining_gaps"), 0)
        self.assertEqual(live.get("candidate_sha"), sha)
        self.assertEqual(frozen.read_bytes(), frozen_bytes)

        _write_closed(root, remaining_gaps=2, outstanding=[
            {"kind": "coverage-account", "count": 2, "ids": SYNTHETIC_GAPS,
             "detail": "two remaining coverage gaps"},
        ])
        m4 = root / "evidence/verdicts/m4-verdict.json"
        before = m4.read_bytes()
        digest = sha256_file(m4)
        self.assertEqual(original_coverage_obligation_ids(root), SYNTHETIC_GAPS)
        _write_discharge(root, sha, SYNTHETIC_GAPS, digest)

        xml = root / "mutations.xml"
        _synthetic_pit(xml)
        rec = _record_pit(root, xml, sha)
        self.assertEqual(rec.returncode, 0, rec.stderr)
        pin_path = root / "evidence/derived/g1-kill-ratio-pin.json"
        pin_path.parent.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run(
            [sys.executable, str(G1_PIN_SCRIPT), str(xml), "-o", str(pin_path),
             "--root", str(root),
             "--coverage-min", "0.41", "--kill-attempted-min", "0.60",
             "--kill-generated-min", "0.38",
             "--source", "declared_engineering_target",
             "--rationale", "synthetic PIT fixture"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)

        prepare_candidate(root, runner=_git(sha))
        _write_bound_delivery(root, sha)
        elig = assess_eligibility(root, runner=_git(sha))
        self.assertTrue(elig["release_eligible"], elig["outstanding"])
        verdict = compose_verdict(root)
        self.assertEqual(verdict["verdict"], "ACCEPT")
        self.assertEqual(m4.read_bytes(), before)
        self.assertEqual(frozen.read_bytes(), frozen_bytes)
        checked = _check_verdict_routing(root)
        self.assertEqual(checked.returncode, 0, checked.stderr + checked.stdout)
        write_canonical(root / "evidence/preflight/factory.json", {
            "phase": "FACTORY", "status": "factory_ready",
        })
        factory = subprocess.run(
            [sys.executable, str(FACTORY_CHECK), str(root)],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(factory.returncode, 0, factory.stderr)

    def test_unresolved_original_identities_cannot_discharge(self):
        root, tmp = _root()
        self.addCleanup(tmp.cleanup)
        sha = "cc" * 20
        _write_closed(root, remaining_gaps=2)
        digest = sha256_file(root / "evidence/verdicts/m4-verdict.json")
        _write_discharge(root, sha, ["unrelated-id", "unrelated-id"], digest)
        _write_current_account(root, sha, [{"path": "unrelated-id", "remaining_gap": False}], remaining=0)
        _write_pin(root, candidate_sha=sha)
        prepare_candidate(root, runner=_git(sha))
        _write_bound_delivery(root, sha)
        self.assertIsNone(original_coverage_obligation_ids(root))
        elig = assess_eligibility(root, runner=_git(sha))
        self.assertFalse(elig["release_eligible"])
        self.assertTrue(any(r.get("kind") == "coverage-account" for r in elig["outstanding"]))
        self.assertEqual(compose_verdict(root)["verdict"], "INCONCLUSIVE")


class CoveragePreservation(unittest.TestCase):
    """Per-M4 bind/close snapshots. Synthetic fixtures, not dest v10."""

    def _compose(self, root: Path, sha: str, *, gaps: list) -> None:
        (root / "decisions.yaml").write_text(_decisions_yaml(replaced=False, gaps=gaps), encoding="utf-8")
        _write_parity(root, passed=False)
        (root / "verification/build").mkdir(parents=True, exist_ok=True)
        write_canonical(root / "verification/build/run.json", {
            "schema": "rhoai3.verify-run/v1", "candidate_sha256": sha,
        })
        proc = subprocess.run([sys.executable, str(COMPOSER), str(root)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_successive_m4s_select_the_discharged_card(self):
        root, tmp = _root()
        self.addCleanup(tmp.cleanup)
        _link_hermes(root)
        a, b = "aa" * 20, "bb" * 20
        self._compose(root, a, gaps=SYNTHETIC_GAPS)
        _bind_coverage_snapshot(root, "t_first")
        first_bytes = (root / FROZEN_COVERAGE_ACCOUNT).read_bytes()
        self._compose(root, b, gaps=LATER_GAPS)
        live = json.loads((root / "evidence/verdicts/coverage-account.json").read_text())
        self.assertEqual(live["remaining_gaps"], LATER_GAPS)
        self.assertEqual((root / FROZEN_COVERAGE_ACCOUNT).read_bytes(), first_bytes)
        _bind_coverage_snapshot(root, "t_second")
        current = json.loads((root / FROZEN_COVERAGE_ACCOUNT).read_text())
        self.assertEqual(current["remaining_gaps"], LATER_GAPS)
        src = json.loads((root / FROZEN_COVERAGE_SOURCE).read_text())
        self.assertEqual(src.get("card_id"), "t_second")
        hist = list((root / FROZEN_COVERAGE_HISTORY / "t_first").rglob("coverage-account.json"))
        self.assertTrue(hist)
        self.assertEqual(json.loads(hist[0].read_text())["remaining_gaps"], SYNTHETIC_GAPS)
        _write_closed(root, card="t_second", remaining_gaps=2, outstanding=[
            {"kind": "coverage-account", "count": 2, "ids": LATER_GAPS,
             "detail": "two remaining coverage gaps"},
        ])
        self.assertEqual(original_coverage_obligation_ids(root), LATER_GAPS)
        _write_closed(root, card="t_first", remaining_gaps=2, outstanding=[
            {"kind": "coverage-account", "count": 2, "ids": SYNTHETIC_GAPS,
             "detail": "two remaining coverage gaps"},
        ])
        self.assertEqual(original_coverage_obligation_ids(root), SYNTHETIC_GAPS)

    def test_foreign_snapshot_is_not_this_m4s_original(self):
        root, tmp = _root()
        self.addCleanup(tmp.cleanup)
        _link_hermes(root)
        self._compose(root, "bb" * 20, gaps=LATER_GAPS)
        _bind_coverage_snapshot(root, "t_foreign")
        _write_closed(root, card="t_current", remaining_gaps=2, outstanding=[])
        self.assertIsNone(original_coverage_obligation_ids(root))
        live = json.loads((root / "evidence/verdicts/coverage-account.json").read_text())
        self.assertEqual(live["remaining_gaps"], LATER_GAPS)
        self.assertEqual(
            json.loads((root / FROZEN_COVERAGE_SOURCE).read_text()).get("card_id"),
            "t_foreign",
        )

    def test_missing_snapshot_does_not_copy_later_live(self):
        root, tmp = _root()
        self.addCleanup(tmp.cleanup)
        _link_hermes(root)
        self._compose(root, "aa" * 20, gaps=SYNTHETIC_GAPS)
        self._compose(root, "bb" * 20, gaps=LATER_GAPS)
        _write_closed(root, card="t_current", remaining_gaps=2, outstanding=[])
        self.assertFalse((root / FROZEN_COVERAGE_ACCOUNT).is_file())
        self.assertIsNone(original_coverage_obligation_ids(root))
        live = json.loads((root / "evidence/verdicts/coverage-account.json").read_text())
        self.assertEqual(live["remaining_gaps"], LATER_GAPS)
        original_coverage_obligation_ids(root)
        self.assertFalse((root / FROZEN_COVERAGE_ACCOUNT).is_file())
        self.assertIsNone(original_coverage_obligation_ids(root))

    def test_outstanding_rows_does_not_backfill_missing_snapshot(self):
        root, tmp = _root()
        self.addCleanup(tmp.cleanup)
        import importlib.util
        scripts = HERE.parent / "skills" / "migration" / "fix-until-green" / "scripts"
        if str(scripts) not in sys.path:
            sys.path.insert(0, str(scripts))
        spec = importlib.util.spec_from_file_location("resume_after_m4_itest", scripts / "resume-after-m4.py")
        resume = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(resume)
        _write_closed(root, card="t_old_close", remaining_gaps=1, outstanding=[])
        _write_current_account(root, "bb" * 20, [{"path": "src/main/java/LaterGap.java", "remaining_gap": True}], remaining=1)
        verdict = json.loads((root / "evidence/verdicts/m4-verdict.json").read_text())
        self.assertFalse((root / FROZEN_COVERAGE_ACCOUNT).is_file())
        rows = resume.outstanding_rows(verdict, {"verdict": "PASS", "entry_points": []}, root)
        cov = [r for r in rows if r.get("kind") == "coverage-account"]
        self.assertFalse((root / FROZEN_COVERAGE_ACCOUNT).is_file())
        self.assertTrue(cov)
        self.assertNotIn("ids", cov[0])
        self.assertIsNone(original_coverage_obligation_ids(root))

    def test_bind_retry_does_not_backfill_missing_snapshot(self):
        root, tmp = _root()
        self.addCleanup(tmp.cleanup)
        card = "t_bindretry"
        (root / "verification/loop").mkdir(parents=True, exist_ok=True)
        write_canonical(root / "verification/loop/issued.json", {
            "schema": "rhoai3.loop-issued/v1", "cluster": "M4_VERIFY", "kind": "close",
            "attempt": 1, "idempotency_key": "k4:M4_VERIFY:1:" + "a" * 16,
            "receipt_sha256": "a" * 64, "task_id": card,
        })
        (root / "verification/parity").mkdir(parents=True, exist_ok=True)
        write_canonical(root / "verification/parity/receipt.json", {
            "schema": "rhoai3.parity-receipt/v1", "receipt_sha256": "a" * 64,
            "entry_points": [], "verdict": "PASS",
        })
        (root / "evidence/verdicts").mkdir(parents=True, exist_ok=True)
        write_canonical(root / "evidence/verdicts/m4-verdict.json", {
            "gate": "compose-m4-verdict", "phase": "M4", "verdict": "PROVISIONAL_ACCEPT",
            "ship": False, "failed_floors": [], "floors": [],
            "coverage_account": {"remaining_gaps": 1, "retired": 4},
        })
        _write_current_account(root, "aa" * 20, [{"path": "src/main/java/a/GapOne.java", "remaining_gap": True}], remaining=1)
        first = subprocess.run(
            [sys.executable, str(BINDER), "--root", str(root)],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
        self.assertTrue((root / FROZEN_COVERAGE_ACCOUNT).is_file())
        (root / FROZEN_COVERAGE_ACCOUNT).unlink()
        src = root / FROZEN_COVERAGE_SOURCE
        if src.is_file():
            src.unlink()
        _write_current_account(root, "bb" * 20, [{"path": "src/main/java/LaterGap.java", "remaining_gap": True}], remaining=1)
        retry = subprocess.run(
            [sys.executable, str(BINDER), "--root", str(root)],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(retry.returncode, 0, retry.stderr + retry.stdout)
        self.assertIn("already bound", retry.stdout)
        self.assertFalse((root / FROZEN_COVERAGE_ACCOUNT).is_file())
        self.assertIsNone(original_coverage_obligation_ids(root))


if __name__ == "__main__":
    unittest.main()
