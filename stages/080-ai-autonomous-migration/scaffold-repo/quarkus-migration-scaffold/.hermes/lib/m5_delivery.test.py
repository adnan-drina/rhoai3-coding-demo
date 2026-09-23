#!/usr/bin/env python3
"""M5 delivery contract: idempotent start, blocked prerequisites, pipeline and live refusals."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from m5_delivery import (
    argv_for_card,
    assert_deployed,
    assess_eligibility,
    compose_verdict,
    deployment_from_app_pods,
    evaluate_live,
    idempotency_key,
    observe_pipeline,
    plan_cards,
    prepare_candidate,
    record_eligibility,
    select_pipeline_run,
    start_delivery,
)
from planner.canonical import write_canonical
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


def _root() -> Path:
    tmp = tempfile.TemporaryDirectory()
    root = Path(tmp.name)
    return root, tmp


def _write_closed(root: Path, card="t_m4close01", verdict="PROVISIONAL_ACCEPT", ship=False):
    (root / "verification/loop").mkdir(parents=True)
    (root / "evidence/verdicts").mkdir(parents=True)
    write_canonical(root / LOOP_STEPS, {
        "schema": "rhoai3.loop-steps/v1", "steps": [], "attempts": {},
        "rejected": [{"kind": "close", "cluster": "M4_VERIFY", "card": card, "verdict": verdict,
                      "closed": True, "resumed": False, "parity_receipt_sha256": "a" * 64}],
    })
    write_canonical(root / "evidence/verdicts/m4-verdict.json", {
        "gate": "compose-m4-verdict", "phase": "M4", "verdict": verdict, "ship": ship,
        "card_id": card, "coverage_account": {"remaining_gaps": 1, "retired": 4},
        "failed_floors": [], "floors": [],
    })
    write_canonical(root / "verification/loop/release-blockers.json", {
        "schema": "rhoai3.release-blockers/v1", "closed": True, "outstanding": [
            {"kind": "coverage-account", "count": 1, "detail": "one remaining coverage gap"},
        ],
    })
    write_canonical(root / WORKLIST, {"schema": "rhoai3.worklist/v1", "items": []})
    write_canonical(root / "evidence/type-inventory.json", {"schema": "rhoai3.type-inventory/v1", "types": []})


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

    def test_failed_prerequisite_blocks_start(self):
        root, tmp = _root()
        self.addCleanup(tmp.cleanup)
        (root / "verification/loop").mkdir(parents=True)
        write_canonical(root / LOOP_STEPS, {"schema": "rhoai3.loop-steps/v1", "steps": [], "rejected": []})
        result = start_delivery(root, runner=_git(), execute=True)
        self.assertFalse(result["ok"])
        self.assertTrue(result["blocked"])
        self.assertEqual(result["failed_stage"], "M5-A")
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
        self.assertEqual(planned[0]["idempotency_key"], idempotency_key("prepare", "t_m4close01", sha))
        control = json.loads((root / LOOP_CARDS).read_text())["control"]
        self.assertEqual(set(control), {"m5_prepare", "m5_push", "m5_accept"})
        argv = argv_for_card(planned[0], "body", hermes="hermes", parent_id="t_m4close01",
                             workspace="dir:/projects/modernized")
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
        self.assertEqual(doc["failed_stage"], "M5-B")

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
        self.assertEqual(result["failed_stage"], "M5-C")
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
        self.assertEqual(verdict["failed_stage"], "M5-B")
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


if __name__ == "__main__":
    unittest.main()
