#!/usr/bin/env python3
"""R-3 first-package census: every failure, its evidence, who can reach it; the gate bound to its tree.

Run: PYTHONDONTWRITEBYTECODE=1 python3 .hermes/lib/planner/runtime_census.test.py
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from planner import native_control as NC  # noqa: E402
from planner.native_control import Refusal  # noqa: E402
from planner.runtime_census import CENSUS, census  # noqa: E402


def world(base):
    p = "src/main/java/" + base.replace(".", "/")
    types = [{"fqn": "%s.repo.ItemStoreImpl" % base, "path": "%s/repo/ItemStoreImpl.java" % p},
             {"fqn": "%s.web.ItemResource" % base, "path": "%s/web/ItemResource.java" % p},
             {"fqn": "%s.web.Errors" % base, "path": "%s/web/Errors.java" % p}]
    eps = [{"id": "ep:%s.web.ItemResource#create():http" % base, "type": "%s.web.ItemResource" % base}]
    nodes = [{"outcome_id": "behavior:http:%s.web.ItemResource" % base, "role": "repair", "class": "behavior",
              "plan_paths": ["%s/web/ItemResource.java" % p], "requirements": [],
              "acceptance": {"requirement_checks": ["parity:sc:create-items"]}},
             {"outcome_id": "requirement:adapter-behavior:x", "role": "repair", "class": "behavior", "plan_paths": [],
              "requirements": ["req:adapter-behavior:cors"], "acceptance": {"requirement_checks": []}},
             {"outcome_id": "objective:repo", "role": "repair", "class": "source", "plan_paths": ["%s/repo/ItemStoreImpl.java" % p],
              "requirements": [], "acceptance": {"requirement_checks": []}}]
    return types, eps, {"nodes": nodes, "requirements": []}, p


def rec(sid, reason, ep="", excerpt=None):
    r = {"scenario": sid, "verdict": "FAIL", "reason": reason, "entry_point": ep}
    if excerpt:
        r["server_error"] = {"exception": "jakarta.persistence.OptimisticLockException", "excerpt": excerpt}
    return r


class Census(unittest.TestCase):
    def run_case(self, base, status):
        types, eps, plan, p = world(base)
        ep = eps[0]["id"]
        records = {
            "sc:create-items": rec("sc:create-items", "status 500 vs 201; body a vs b", ep,
                                   ["\tat %s.repo.ItemStoreImpl.save(ItemStoreImpl.java:62)" % base]),
            "sc:cors-items": rec("sc:cors-items", "header Access-Control-Allow-Origin None vs *"),
            "sc:read-x": rec("sc:read-x", "status 200 vs 200; effect eff:x"),
            "sc:refused": rec("sc:refused", "status 500 vs 400", "", ["\tat %s.web.Errors.on(Errors.java:9)" % base]),
        }
        return census(records=records, plan=plan, native_status=status, entry_points=eps, types=types, tree="T1"), p

    def check(self, base):
        open_all = lambda o: "ready"                                     # noqa: E731
        doc, p = self.run_case(base, open_all)
        by = {f["scenario"]: f for f in doc["failures"]}
        # the server error's product frame is the causal site: reachable by the repository's owner, not the handler's card
        self.assertEqual(by["sc:create-items"]["reachable_by"], ["objective:repo"])
        self.assertEqual(by["sc:create-items"]["evidenced_files"], ["%s/repo/ItemStoreImpl.java" % p])
        self.assertEqual(by["sc:cors-items"]["reachable_by"], ["requirement:adapter-behavior:x"])
        self.assertEqual([u["scenario"] for u in doc["unreachable"]], ["sc:refused"])     # its evidence: a file nobody owns
        self.assertEqual([u["scenario"] for u in doc["unattributed"]], ["sc:read-x"])     # no file named: never a gate
        # the owners done: the repository frame is reachable by nobody open any more
        doc2, _ = self.run_case(base, lambda o: "done" if o == "objective:repo" or o.startswith("behavior:") else "ready")
        self.assertIn("sc:create-items", [u["scenario"] for u in doc2["unreachable"]])

    def test_a_source_answer_through_its_advice_needs_the_advice_owned(self):
        """H-20 at the first package: the source refused through its exception advice; the destination's 500 names
        the repository frame. Only a card owning the advice can reproduce the answer -- with none, unreachable."""
        base = "org.acme.clinic"
        types, eps, plan, p = world(base)
        shapes = [{"fqn": "%s.web.Errors" % base, "path": "%s/web/Errors.java" % p, "body_keys": [["code", "detail"]]}]
        src = {"sc:refused": {"status": 400, "body": '{"code": "X", "detail": "constraint"}'}}
        recs = {"sc:refused": rec("sc:refused", "status 500 vs 400; body a vs b", eps[0]["id"],
                                  ["\tat %s.repo.ItemStoreImpl.save(ItemStoreImpl.java:62)" % base])}
        doc = census(records=recs, plan=plan, native_status=lambda o: "ready", entry_points=eps, types=types, tree="T",
                     source_responses=src, advice_shapes=shapes)
        self.assertEqual([u["scenario"] for u in doc["unreachable"]], ["sc:refused"])
        self.assertEqual(doc["unreachable"][0]["source_advice"], "%s.web.Errors" % base)
        plan["nodes"].append({"outcome_id": "requirement:exception-advice:e", "role": "repair", "class": "source",
                              "plan_paths": ["%s/web/Errors.java" % p], "requirements": [], "acceptance": {}})
        doc = census(records=recs, plan=plan, native_status=lambda o: "ready", entry_points=eps, types=types, tree="T",
                     source_responses=src, advice_shapes=shapes)
        self.assertEqual(doc["failures"][0]["reachable_by"], ["requirement:exception-advice:e"])

    def test_the_census(self):
        self.check("org.acme.clinic")

    def test_a_renamed_twin(self):
        self.check("com.example.ledger")

    def test_the_gate_binds_to_its_tree(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / CENSUS).parent.mkdir(parents=True)
            (root / CENSUS).write_text(json.dumps({"tree": "T1", "unreachable": [{"scenario": "sc:refused", "evidenced_files": ["a/Errors.java"]}]}))
            with self.assertRaises(Refusal) as cm:
                NC._census_gate(root, "T1", "behavior:http:x")
            self.assertEqual(cm.exception.code, "RUNTIME_CENSUS_UNREACHABLE")
            self.assertIn("sc:refused", cm.exception.detail)
            NC._census_gate(root, "T2", "behavior:http:x")                  # another tree: history, not a gate
            (root / CENSUS).write_text(json.dumps({"tree": "T1", "unreachable": []}))
            NC._census_gate(root, "T1", "behavior:http:x")


if __name__ == "__main__":
    unittest.main()
