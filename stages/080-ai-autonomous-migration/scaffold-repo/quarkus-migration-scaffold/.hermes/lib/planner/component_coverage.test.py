#!/usr/bin/env python3
"""H-20 early gate (v31): every application-wide source component is owned by the plan at M2.

Run: PYTHONDONTWRITEBYTECODE=1 python3 .hermes/lib/planner/component_coverage.test.py
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from planner.component_coverage import bootstrap_annotations, unplanned  # noqa: E402

CATALOGS = HERE.parent.parent / "planning" / "catalogs"
CC = json.loads((CATALOGS / "cross-cutting.json").read_text())
CATALOG = json.loads((CATALOGS / "compat-mapping.json").read_text())
ADVICE = "org.springframework.web.bind.annotation.ControllerAdvice"
APP = "org.springframework.boot.autoconfigure.SpringBootApplication"
CONFIG = "org.springframework.context.annotation.Configuration"
FILTER = "jakarta.servlet.Filter"


def world(base):
    p = "src/main/java/" + base.replace(".", "/")
    t = lambda fqn, path, anns=(), sups=(): {"fqn": "%s.%s" % (base, fqn), "path": "%s/%s" % (p, path),  # noqa: E731
                                             "annotations": [{"fqn": a, "values": {}} for a in anns], "supertypes": list(sups)}
    return {"advice": t("web.Errors", "web/Errors.java", [ADVICE]),
            "app": t("Main", "Main.java", [APP]),
            "config": t("sec.Cfg", "sec/Cfg.java", [CONFIG]),
            "filter": t("web.Audit", "web/Audit.java", sups=[FILTER]),
            "plain": t("model.Item", "model/Item.java"),
            "test": dict(t("web.TestAdvice", "x.java", [ADVICE]), path="src/test/java/%s/web/TestAdvice.java" % base.replace(".", "/"))}


class Coverage(unittest.TestCase):
    def check(self, base):
        w = world(base)
        types = list(w.values())
        boot = bootstrap_annotations(CATALOG)
        self.assertEqual(boot, [APP])                                   # the bootstrap deletes the main class by catalog
        got = unplanned(types, cross_cutting=CC, plan_nodes=[], requirements=[], retired_paths=[], bootstrap_annotations=boot)
        self.assertEqual({g["fqn"]: g["classified_by"] for g in got},
                         {w["advice"]["fqn"]: [ADVICE], w["config"]["fqn"]: [CONFIG], w["filter"]["fqn"]: [FILTER]})
        # owned: a node's plan path, a requirement's path, a retirement; the plain type and test sources never count
        got = unplanned(types, cross_cutting=CC, plan_nodes=[{"plan_paths": [w["advice"]["path"]]}],
                        requirements=[{"paths": [w["filter"]["path"]]}], retired_paths=[w["config"]["path"]],
                        bootstrap_annotations=boot)
        self.assertEqual(got, [])
        # without the bootstrap row the main class is a component like any other
        got = unplanned([w["app"]], cross_cutting=CC, plan_nodes=[], requirements=[], retired_paths=[], bootstrap_annotations=[])
        self.assertEqual([g["fqn"] for g in got], [w["app"]["fqn"]])

    def test_the_v31_shape(self):
        self.check("org.acme.clinic")

    def test_a_renamed_twin(self):
        self.check("com.example.ledger")


if __name__ == "__main__":
    unittest.main()
