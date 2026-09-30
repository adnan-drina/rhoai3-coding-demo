#!/usr/bin/env python3
"""completion_map selftest (M-1).

(c) the saved v29 plan revision 1 (a checked-in, byte-identical gzip of
tmp/v29-watch/v29-plan.r1.json): 80 requirements, 7 ship-blocking
verification groups over 12 distinct entry points, each mapped individually
with an owner, prerequisites and an exit -- counted from the plan, never from a
constant in the module; missing oracles never render as an empty successful
plan (an empty work list, a zero measure, finished cards and an absent plan all
leave them open or unknown); only the M4-bound parity evidence closes one;
(a) the v29 false green reads "runtime behavior unresolved; measurement
invalid"; (d) the same inputs give the same map and digest. Specimen-agnostic
cases use neutral names.
"""
from __future__ import annotations

import ast
import copy
import gzip
import hashlib
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import completion_map as CM  # noqa: E402
from planner.yamlite import load_yaml  # noqa: E402

GOLDEN = HERE.parents[1]
V29 = HERE / "planner" / "fixtures" / "v29-plan.r1.json.gz"
V29_SHA256 = "ea9b5f8768a31ba30e812732e11e7611745cee3aaf4a51755b3d45060e804345"  # sha256 of tmp/v29-watch/v29-plan.r1.json
TREE = "d" * 64


def v29_plan() -> dict:
    raw = gzip.decompress(V29.read_bytes())
    assert hashlib.sha256(raw).hexdigest() == V29_SHA256, "the fixture is not the saved v29 plan r1"
    return CM.normalize_plan(json.loads(raw.decode("utf-8")))


def golden_decisions() -> dict:
    return load_yaml(GOLDEN / "decisions.yaml")


def neutral_plan(eps=("ep:a.web.ItemsResource#create(a.Item):http", "ep:a.web.ItemsResource#list():http")) -> dict:
    """A two-repository, one-behavior plan with neutral names and one unresolved group."""
    def repo(n: str) -> dict:
        return {"outcome_id": "objective:selected-repository-implementation:%s" % n, "role": "repair", "class": "source",
                "recipes": ["fragment-impl@1"], "objective": {"family": "selected-repository-implementation"},
                "plan_paths": ["src/main/java/a/repo/%sStoreImpl.java" % n, "src/main/java/a/repo/Data%sStore.java" % n],
                "check_plan": [{"check": "parity:sc:x", "stage": "later", "prerequisites": []}]}
    nodes = [repo("A"), repo("B"),
             {"outcome_id": "behavior:http:a.web.ItemsResource", "role": "repair", "class": "behavior", "check_plan": []},
             {"outcome_id": "assess:m4:g1", "role": "assess", "class": "assess"}]
    reqs = [{"id": "req:behavior-verification:%s" % e, "rule": "behavior-verification/v1", "status": "unresolved", "subject": e} for e in eps]
    reqs.append({"id": "req:generator-configuration:g:plugin|x", "rule": "generator-configuration/v1", "status": "applicable",
                 "subject": "g:plugin|x"})
    return CM.normalize_plan({"schema": "rhoai3.native-plan/v1", "revision": 1, "plan": {
        "digest": "p" * 64, "run_id": "run-x", "policy": "compatibility-objectives/v1", "nodes": nodes, "requirements": reqs,
        "unresolved": [{"id": "unresolved:verification:http:a.web.ItemsResource", "kind": "verification-responsibility",
                        "blocks": "ship", "entry_points": list(eps), "requirements": [r["id"] for r in reqs[:len(eps)]],
                        "reason": "no captured oracle for %d http entry point(s)" % len(eps)}]}})


def frames(n: str) -> list:
    loop = [{"class": "a.repo.%sStoreImpl" % n, "method": "find"}, {"class": "a.repo.Data%sStore" % n, "method": "find"}]
    return loop * 3


def false_green(plan: dict) -> dict:
    """v29 I-11 continued, minimally: compile/package/boot pass, measure [0,0,0],
    an EMPTY work list, the seal still blocking on a lifted cluster, every live
    verdict INCONCLUSIVE ("receipt not authoritative") over a recorded FAIL."""
    refused = "receipt not authoritative: admission-receipt.json status INCONCLUSIVE"
    live = {sid: {"scenario": sid, "verdict": "INCONCLUSIVE", "reason": refused, "binding": {"mode": "sealed"}}
            for sid in ("sc:read-a", "sc:read-b", "sc:create-a")}
    recorded = {"sc:read-a": {"scenario": "sc:read-a", "verdict": "FAIL", "entry_point": "ep:a.web.AResource#get():http",
                              "server_error": {"exception": "java.lang.StackOverflowError", "frames": frames("A")}},
                "sc:read-b": {"scenario": "sc:read-b", "verdict": "FAIL", "entry_point": "ep:a.web.BResource#get():http",
                              "server_error": {"exception": "java.lang.StackOverflowError", "frames": frames("B")}}}
    return {
        "plans": [plan], "decisions": {}, "missing": {"m1_facts": "m1-facts.json is absent"},
        "admission": {"status": "INCONCLUSIVE", "blocks": [{"class": "MANUAL_CLUSTER", "subject": "c:srv", "detail": "deferred"}]},
        "deferred": {"clusters": [], "reasons": {}},
        "worklist": {"items": [], "clusters": [], "candidate_sha256": TREE, "measure": {"known": True, "compile_errors": 0}},
        "state": {"measure": {"known": True, "tuple": [0, 0, 0]}, "head": "c:srv"},
        "steps": {"steps": [{"verdict": "baseline", "cluster": "", "card": ""}],
                  "rejected": [{"cluster": "c:srv", "card": "t_x", "at": "2026-09-30T05:00:00Z",
                                "reason": "sc:cors-actual answered 500: StackOverflowError in the fragment implementation"}]},
        "package": {"ran": True, "rc": 0}, "boot": {"ran": True, "rc": 0, "ready": True},
        "parity": {"disabled": {"receipt": None, "records": live, "receipt_scenarios": {}, "receipt_entry_points": {}}},
        "accepted_parity": {"disabled": {"records": recorded}},
        "parity_evidence": (None, "no M4 verdict"), "m4_verdict": None, "m5": {},
    }


class V29PlanInventory(unittest.TestCase):
    """(c) the saved v29 r1 plan, counted from the plan."""

    def setUp(self):
        self.plan = v29_plan()
        self.inputs = {"plans": [self.plan], "decisions": golden_decisions(), "missing": {}, "parity_evidence": (None, "no M4 verdict")}

    def test_counts(self):
        inv = CM.inventory(self.plan)
        self.assertEqual(inv["requirements"], 80)
        self.assertEqual(inv["requirements_by_status"], {"applicable": 66, "satisfied": 2, "unresolved": 12})
        self.assertEqual((inv["verification_groups"], inv["ship_blocking_verification_groups"]), (7, 7))
        self.assertEqual(inv["unresolved_entry_points"], 12)
        self.assertEqual(inv["unresolved_entry_point_kinds"], {"http": 12})
        self.assertEqual((inv["repair_outcomes"], inv["milestone_nodes"]), (30, 4))
        self.assertEqual(inv["repair_outcomes_by_class"], {"behavior": 8, "build": 1, "config": 3, "source": 18})
        repo = [v for k, v in inv["later_checks_by_outcome"].items() if ":selected-repository-implementation:" in k]
        self.assertEqual((len(repo), min(repo), max(repo)), (7, 3, 34))    # "seven repository objectives carry 3..34 later checks"

    def test_each_entry_point_is_a_blocker_with_owner_prerequisites_and_exit(self):
        cm = CM.build(self.inputs)
        rows = cm["release_blockers"]
        self.assertEqual(len(rows), 12)
        self.assertEqual(len({r["entry_point"] for r in rows}), 12)
        self.assertEqual(len({r["id"] for r in rows}), 7)
        for r in rows:
            self.assertEqual((r["status"], r["capability"], r["blocks"], r["kind"]), ("open", "unknown", "ship", "http"))
            self.assertIn(r["owner"], CM.OWNERS)
            self.assertTrue(r["prerequisites"] and r["exit"] and r["requirement"].endswith(r["entry_point"]))
            self.assertIn("disabled, enabled", r["exit"])                   # both owed security modes
        self.assertEqual(cm["security_modes"], ["disabled", "enabled"])
        self.assertEqual(cm["release_blocker_summary"]["by_owner"], {"source-capture": 12})
        self.assertEqual(cm["contract"]["active_profiles"], sorted(golden_decisions()["build_profiles"]["active"]))
        self.assertEqual(cm["contract"]["generator_toolchains"], ["org.openapitools:openapi-generator-maven-plugin|jaxrs-spec"])
        self.assertEqual(cm["contract"]["http_behavior"]["by_kind"], {"http": 34})
        self.assertTrue(any("unanalysed, not absent" in x for x in cm["contract"]["limitations"]))

    def test_a_captured_entry_point_is_owned_by_the_destination_check(self):
        m1 = {"coverage": {"unverified_entry_points": [r["entry_point"] for r in CM.build(self.inputs)["release_blockers"]][1:]}}
        cm = CM.build(dict(self.inputs, m1_facts=m1))
        self.assertEqual(cm["release_blocker_summary"]["by_owner"], {"destination-behavior-check": 1, "source-capture": 11})


class MissingOraclesNeverVanish(unittest.TestCase):

    def test_empty_work_list_zero_measure_and_finished_cards_keep_them_open(self):
        inp = false_green(v29_plan())
        inp["admission"] = {"status": "ADMITTED", "blocks": []}
        inp["steps"] = {"steps": [{"verdict": "accepted", "cluster": "c:%d" % i} for i in range(40)], "rejected": []}
        cm = CM.build(inp)
        self.assertEqual(cm["release_blocker_summary"]["open"], 12)
        behavior = next(m for m in cm["milestones"] if m["id"] == "application-behavior-preserved")
        self.assertNotEqual(behavior["state"], CM.DEMONSTRATED)
        self.assertTrue(any("12 release blocker(s) open" in g for g in behavior["gaps"]))

    def test_no_plan_is_unknown_not_none(self):
        cm = CM.build({"plans": [], "missing": {"plan": "plan-semantics.json is absent"}})
        self.assertFalse(cm["release_blocker_summary"]["known"])
        self.assertIsNone(cm["inventory"])
        self.assertIn("unknown", "\n".join(CM.render_lines(cm)))
        self.assertNotIn("0 open of 0", "\n".join(CM.render_lines(cm)))

    def test_only_m4_bound_parity_pass_in_every_owed_mode_closes_one(self):
        plan = neutral_plan()
        ep = plan["unresolved"][0]["entry_points"][0]
        dec = golden_decisions()
        half = CM.build({"plans": [plan], "decisions": dec, "parity_evidence": ({"disabled": {ep: "PASS"}, "enabled": {ep: "FAIL"}}, "")})
        self.assertEqual([r["status"] for r in half["release_blockers"]], ["open", "open"])
        full = CM.build({"plans": [plan], "decisions": dec, "parity_evidence": ({"disabled": {ep: "PASS"}, "enabled": {ep: "PASS"}}, "")})
        self.assertEqual(sorted(r["status"] for r in full["release_blockers"]), ["closed", "open"])


class FalseGreen(unittest.TestCase):
    """(a) the v29 false-green snapshot."""

    def test_headline(self):
        cm = CM.build(false_green(neutral_plan()))
        self.assertEqual(cm["headline"]["state"], "runtime behavior unresolved; measurement invalid")
        self.assertFalse(cm["measurement"]["valid"])
        f = "\n".join(cm["measurement"]["findings"])
        for text in ("stale seal: MANUAL_CLUSTER on c:srv", "not measured: receipt not authoritative",
                     "INCONCLUSIVE over a recorded FAIL", "empty work list"):
            self.assertIn(text, f)
        self.assertEqual(cm["headline"]["last_demonstrated_milestone"], "target-structurally-viable")
        self.assertTrue(cm["headline"]["next_missing_prerequisite"]["prerequisite"].startswith("a valid measurement"))
        self.assertEqual(cm["headline"]["oldest_unresolved_cause"]["cluster"], "c:srv")
        self.assertEqual(cm["headline"]["release_verdict"]["ship"], False)

    def test_the_same_snapshot_admitted_and_measured_is_not_invalid(self):
        inp = false_green(neutral_plan())
        inp["admission"] = {"status": "ADMITTED", "blocks": []}
        for r in inp["parity"]["disabled"]["records"].values():
            r.update(verdict="FAIL", reason="status 500 vs 200", binding={"candidate_sha256": TREE})
        cm = CM.build(inp)
        self.assertTrue(cm["measurement"]["valid"])
        self.assertEqual(cm["headline"]["state"], "runtime behavior unresolved")   # no receipt on this tree: unknown, not failing

    def test_recursion_across_repositories_is_one_causal_group_keeping_each_check(self):
        cm = CM.build(false_green(neutral_plan()))
        gs = cm["causal_groups"]["groups"]
        self.assertEqual(len(gs), 1)
        g = gs[0]
        self.assertEqual((g["exception"], g["producer"]["family"], g["producer"]["recipes"]),
                         ("java.lang.StackOverflowError", "selected-repository-implementation", ["fragment-impl@1"]))
        self.assertEqual(len(g["owners"]), 2)
        self.assertEqual([c["scenario"] for c in g["checks"]], ["sc:read-a", "sc:read-b"])

    def test_no_shared_producer_no_group(self):
        inp = false_green(neutral_plan())
        rec = inp["accepted_parity"]["disabled"]["records"]
        rec["sc:read-b"]["server_error"]["frames"] = [{"class": "a.repo.DataBStore", "method": "find"}]   # no recursion shown
        cm = CM.build(inp)
        self.assertEqual(cm["causal_groups"]["groups"], [])
        self.assertEqual(cm["causal_groups"]["ungrouped_failures"], 2)


class Delivery(unittest.TestCase):
    """(b) a deployed, live-checked, INCONCLUSIVE application: its URL, ship=false."""

    def test_deployed_but_inconclusive(self):
        inp = false_green(neutral_plan())
        inp["admission"] = {"status": "ADMITTED", "blocks": []}
        inp["parity"]["disabled"]["records"] = {}
        url = "https://app.example.test"
        inp["m5"] = {"verdict": {"verdict": "INCONCLUSIVE", "ship": False, "deployment_status": "deployed", "live_ok": True,
                                 "candidate_sha": "c" * 40, "pipeline_run": "pr-1", "image_digest": "sha256:" + "e" * 64,
                                 "route_url": url, "reason": "deployed and live-checked; outstanding release qualifications remain",
                                 "outstanding": [{"kind": "plan-unresolved", "id": "unresolved:x", "count": 2}]},
                     "live": {"ok": True, "issues": []}}
        cm = CM.build(inp)
        self.assertEqual(cm["headline"]["state"], "deployed at %s; not released (M5 INCONCLUSIVE, ship=false)" % url)
        self.assertEqual(cm["headline"]["release_verdict"], {"phase": "M5", "verdict": "INCONCLUSIVE", "ship": False, "url": url})
        self.assertEqual((cm["distinctions"]["delivery"], cm["distinctions"]["full_release"]), (CM.DEMONSTRATED, CM.NOT_DEMONSTRATED))
        self.assertEqual(cm["release_blocker_summary"]["open"], 2)       # delivery never closes a missing oracle


class Repeatable(unittest.TestCase):
    """(d) the same inputs yield an identical map."""

    def test_same_inputs_same_map_and_digest(self):
        inp = false_green(v29_plan())
        a = CM.build(copy.deepcopy(inp))
        shuffled = copy.deepcopy(inp)
        shuffled["plans"][0]["unresolved"].reverse()
        shuffled["plans"][0]["nodes"].reverse()
        shuffled["accepted_parity"]["disabled"]["records"] = dict(reversed(list(shuffled["accepted_parity"]["disabled"]["records"].items())))
        b = CM.build(shuffled)
        self.assertEqual(a["digest"], b["digest"])
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))
        self.assertEqual(a["digest"], CM._digest({k: v for k, v in a.items() if k != "digest"}))

    def test_source_is_specimen_agnostic_and_py39(self):
        text = (HERE / "completion_map.py").read_text(encoding="utf-8")
        for literal in ("petclinic", "Petclinic", "spring", "Owner", "openapi", "v29"):
            self.assertNotIn(literal, text, literal)
        ast.parse(text, feature_version=(3, 9))
        ast.parse(Path(__file__).read_text(encoding="utf-8"), feature_version=(3, 9))


if __name__ == "__main__":
    unittest.main()
