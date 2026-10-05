#!/usr/bin/env python3
"""R-1 coverage by scenario kind over the run's own corpus (M-3: uncovered kinds are listed, never assumed).

Run: PYTHONDONTWRITEBYTECODE=1 python3 .hermes/lib/planner/rehearsal_coverage.test.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from planner.rehearsal_coverage import coverage, resource  # noqa: E402


def sc(sid, kind, path):
    return {"id": sid, "path": path, "derived_from": {"kind": kind}}


class Coverage(unittest.TestCase):
    def check(self, res):
        corpora = {"disabled": [sc("sc:create-%s" % res, "create", "/api/%s" % res),
                                sc("sc:create-refused-%s" % res, "create-refused", "/api/%s" % res),
                                sc("sc:delete-referenced-%s-1" % res, "delete-referenced", "/api/%s/1" % res),
                                sc("sc:read-%s" % res, "read", "/api/%s" % res)],
                   "enabled": [sc("sc:auth-allowed-create-%s" % res, "auth-allowed", "/api/%s" % res)]}
        verdicts = {"disabled": {"sc:create-%s" % res: "PASS", "sc:create-refused-%s" % res: "FAIL",
                                 "sc:delete-referenced-%s-1" % res: "INCONCLUSIVE"}, "enabled": {}}
        doc = coverage(corpora, verdicts)
        states = {(r["mode"], r["kind"]): r["state"] for r in doc["cells"]}
        self.assertEqual(states, {("disabled", "create"): "PASS", ("disabled", "create-refused"): "FAIL",
                                  ("disabled", "delete-referenced"): "INCONCLUSIVE", ("disabled", "read"): "not-compared",
                                  ("enabled", "auth-allowed"): "not-compared"})
        self.assertEqual({(r["mode"], r["kind"]) for r in doc["uncovered"]}, {("disabled", "read"), ("enabled", "auth-allowed")})
        self.assertEqual({r["resource"] for r in doc["cells"]}, {res})
        self.assertEqual(doc["summary"], {"cells": 5, "pass": 1, "fail": 1, "not_compared": 2})

    def test_kinds_by_resource(self):
        self.check("pets")

    def test_a_renamed_resource(self):
        self.check("ledgers")

    def test_resource_of_a_path(self):
        self.assertEqual(resource("/api/pettypes/{petTypeId}"), "pettypes")
        self.assertEqual(resource("/petclinic/api/owners/1"), "petclinic")      # a context path is a segment like any other
        self.assertEqual(resource("/"), "(root)")


if __name__ == "__main__":
    unittest.main()
