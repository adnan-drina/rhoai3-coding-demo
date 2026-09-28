#!/usr/bin/env python3
"""handoff_facts: the v23 M1/M2 handoff discrepancies, reproduced on renamed
synthetic data (no specimen names), and the facts that contradict them."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

KERNEL = Path(__file__).resolve().parent
sys.path.insert(0, str(KERNEL))
import handoff_facts as hf  # noqa: E402


def _w(path: Path, doc) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc), encoding="utf-8")


def _ep(i: int, method: str, path: str, kind: str = "http") -> dict:
    return {"entry_point_id": "ep:acme.Api%d#op():%s" % (i, kind), "kind": kind, "http_method": method, "http_path": path}


def m1_root(td: Path, *, extra: list[dict] | None = None) -> Path:
    """14 captured reads, 19 writes and 1 wildcard path, all HTTP (the v23 shape)."""
    eps = [_ep(i, "GET", "/api/r%d" % i) for i in range(14)]
    eps += [_ep(100 + i, m, "/api/w%d" % i) for i, m in enumerate(["POST"] * 7 + ["PUT"] * 6 + ["DELETE"] * 6)]
    eps += [_ep(200, "GET", "/api/x/*/by/name")]
    eps += extra or []
    _w(td / hf.INVENTORY, {"entry_points": eps})
    for e in eps:
        captured = e["kind"] == "http" and e["http_method"] == "GET" and "*" not in e["http_path"]
        _w(td / hf.READ_ORACLES / ("ep_%s.json" % e["entry_point_id"].split(":")[1].replace("#", "_")),
           {"entry_point": e["entry_point_id"], "status": "CAPTURED" if captured else "INCONCLUSIVE",
            "reason": "prose that the facts never read"})
    for mode, sub, n in (("disabled", "scenarios", 18), ("enabled", "scenarios-enabled", 67)):
        _w(td / hf.READ_ORACLES / sub / "_capture.json", {"status": "ok", "requested": n, "captured": n})
        rows = {"sc:%d" % i: {"capability": "PASS" if i else "FAIL"} for i in range(n)}
        _w(td / hf.READ_ORACLES / sub / "_qualification.json", {"scenarios": rows})
    return td


def m2_plan(td: Path, *, receipt: str = "r-published") -> Path:
    nodes = [{"role": "repair", "class": c} for c in ["source"] * 18 + ["behavior"] * 8 + ["config"] * 3 + ["build"]]
    nodes += [{"role": "assess", "class": "assess"}] + [{"role": "deliver", "class": "deliver"}] * 3
    unresolved = [{"id": "unresolved:verification:http:acme.C%d" % i, "blocks": "ship",
                   "entry_points": ["ep:acme.C%d#m%d():http" % (i, j) for j in range(n)],
                   "requirements": ["req:bv:acme.C%d#m%d" % (i, j) for j in range(n)]}
                  for i, n in enumerate([1, 2, 2, 2, 1, 2, 2])]
    reqs = [{"status": "applicable"}] * 65 + [{"status": "satisfied"}] * 2 + [{"status": "unresolved"}] * 12
    plan = {"revision": 1, "plan": {"policy": "p/v1", "nodes": nodes, "unresolved": unresolved, "requirements": reqs,
                                    "provenance": {"receipt_sha256": "r-published"}}}
    _w(td / "plan.r1.json", plan)
    _w(td / hf.ADMISSION, {"status": "ADMITTED", "receipt_digest": receipt, "blocks": [], "measure": [4, 233, 0]})
    return td / "plan.r1.json"


# the v23 worker texts, verbatim in shape
V23_M1_META = {"coverage_gaps": ["20 of 34 entry points have no read capture (non-HTTP kinds need operator observations)"],
               "limitations": ["reads outside the corpus are 20/34 inconclusive (scheduled/messaging/lifecycle kinds require "
                               "operator-captured observation files)"]}
V23_M2_SUMMARY = ("M2 PLAN published: admission ADMITTED, and the full plan -- 29 repair outcomes/objectives, M4 VERIFY and "
                  "the three M5 delivery stages -- is on the board as 34 native cards. No unresolved BLOCK classes.")


class M1Facts(unittest.TestCase):
    def test_counts_and_classes_come_from_the_inventory(self):
        with tempfile.TemporaryDirectory() as td:
            f = hf.m1_facts(m1_root(Path(td)))
        self.assertEqual(f["entry_points"], {"total": 34, "http": 34, "non_http": 0, "by_kind": {"http": 34}})
        ro = f["read_oracles"]
        self.assertEqual((ro["captured"], ro["inconclusive"]), (14, 20))
        self.assertEqual(ro["inconclusive_by_class"], {"unrequestable-path": 1, "write-in-scenario-corpus": 19})
        self.assertEqual(ro["writes_by_method"], {"DELETE": 6, "POST": 7, "PUT": 6})
        self.assertEqual(f["operator_observations_needed"], 0)
        self.assertEqual(f["scenarios"]["disabled"]["qualification"], {"PASS": 17, "FAIL": 1, "INCONCLUSIVE": 0})
        self.assertEqual(f["scenarios"]["enabled"]["captured"], 67)

    def test_v23_non_http_claim_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            f = hf.m1_facts(m1_root(Path(td)))
        gaps = hf.claim_gaps(f, "M1 baseline established.", V23_M1_META)
        self.assertEqual(len(gaps), 1)
        self.assertIn("0 non-HTTP", gaps[0])
        self.assertIn("write-in-scenario-corpus", gaps[0])
        # the same numbers, classified correctly, pass
        ok = {"coverage_gaps": ["20 of 34 HTTP read oracles inconclusive: 19 writes covered by the scenario corpus, "
                                "1 wildcard path that is not a request"]}
        self.assertEqual(hf.claim_gaps(f, "M1 baseline established.", ok), [])

    def test_a_real_non_http_entry_point_needs_an_observation(self):
        # control: the observation class exists and is then not a contradiction
        with tempfile.TemporaryDirectory() as td:
            f = hf.m1_facts(m1_root(Path(td), extra=[_ep(300, "", "", kind="scheduled")]))
        self.assertEqual((f["entry_points"]["non_http"], f["operator_observations_needed"]), (1, 1))
        self.assertEqual(hf.claim_gaps(f, "", V23_M1_META), [])


class M2Facts(unittest.TestCase):
    def test_cards_and_unresolved_come_from_the_published_plan(self):
        with tempfile.TemporaryDirectory() as td:
            f = hf.m2_facts(Path(td), m2_plan(Path(td)))
        self.assertEqual((f["cards"]["repair"], f["cards"]["milestones"], f["cards"]["total"]), (30, 4, 34))
        self.assertEqual(f["cards"]["milestones_by_role"], {"assess": 1, "deliver": 3})
        un = f["unresolved"]
        self.assertEqual((un["groups"], un["entry_points"], un["requirements"]), (7, 12, 12))
        self.assertEqual((un["blocks"], un["entry_point_kinds"]), ({"ship": 7}, {"http": 12}))
        self.assertEqual(f["requirements"], {"applicable": 65, "satisfied": 2, "unresolved": 12})
        self.assertEqual((f["admission"]["status"], f["admission"]["blocks"]), ("ADMITTED", 0))

    def test_v23_repair_count_and_empty_unresolved_are_refused(self):
        with tempfile.TemporaryDirectory() as td:
            f = hf.m2_facts(Path(td), m2_plan(Path(td)))
        gaps = hf.claim_gaps(f, V23_M2_SUMMARY, {"unresolved": [], "created_cards": ["t_x"] * 34})
        self.assertTrue(any("'29 repair outcomes/objectives'" in g and "30 repair outcomes plus 4 milestones" in g for g in gaps), gaps)
        self.assertTrue(any("metadata.unresolved is empty" in g and "7 unresolved group(s) spanning 12" in g for g in gaps), gaps)
        # "no unresolved BLOCK classes" is about admission blocks: not a contradiction by itself
        self.assertFalse(any("summary says" in g for g in gaps), gaps)
        good = ("30 repair outcomes plus 4 milestones (34 cards); admission has no blocks; 7 unresolved verification "
                "groups spanning 12 HTTP entry points stay ship-blocking.")
        self.assertEqual(hf.claim_gaps(f, good, {"unresolved": f["unresolved"]["ids"]}), [])
        self.assertTrue(hf.claim_gaps(f, "Plan admitted; no unresolved work remains.", {}))

    def test_m2_carrying_the_m1_misclassification_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root = m1_root(Path(td))
            f = hf.m2_facts(root, m2_plan(root))
        carried = {"limitations": ["20 of 34 entry points have no read capture (non-HTTP kinds require operator-captured "
                                   "observation files)"], "unresolved": f["unresolved"]["ids"]}
        gaps = hf.claim_gaps(f, "30 repair outcomes plus 4 milestones.", carried)
        self.assertEqual(len(gaps), 1, gaps)
        self.assertIn("0 non-HTTP", gaps[0])

    def test_a_moved_admission_receipt_is_not_the_plans_input(self):
        with tempfile.TemporaryDirectory() as td:
            f = hf.m2_facts(Path(td), m2_plan(Path(td), receipt="r-later"))
        self.assertFalse(f["admission"]["current_receipt_is_published"])
        self.assertIsNone(f["admission"]["measure"])
        self.assertEqual(f["admission"]["published_under_receipt"], "r-published")

    def test_published_plan_is_the_newest_native_revision(self):
        recs = [{"id": 1, "filename": "plan.r1.json", "stored_path": "/s/plan.r1.json"},
                {"id": 2, "filename": "plan.r2.json", "stored_path": "/s/plan.r2.json"},
                {"id": 3, "filename": "notes.json", "stored_path": "/s/notes.json"}]
        with patch.object(hf, "read_records", return_value=recs):
            self.assertEqual(hf.published_plan_path(Path("."), "t_m2"), Path("/s/plan.r2.json"))
        with tempfile.TemporaryDirectory() as td:
            with patch.object(hf, "read_records", return_value=recs[2:]):
                with self.assertRaises(ValueError):
                    hf.published_plan_path(Path(td), "t_m2")
            # serial-loop/v1 publishes no revision: the frozen admitted semantics carry the same graph
            plan = json.loads(m2_plan(Path(td)).read_text())["plan"]
            _w(Path(td) / hf.PLAN_SEMANTICS, {"frozen": True, "plan": {"graph": plan, "requirements": plan["requirements"]}})
            with patch.object(hf, "read_records", return_value=recs[2:]):
                path = hf.published_plan_path(Path(td), "t_m2")
            self.assertEqual(path, Path(td) / hf.PLAN_SEMANTICS)
            f = hf.m2_facts(Path(td), path)
            self.assertEqual((f["cards"]["repair"], f["unresolved"]["groups"], f["unresolved"]["entry_points"]), (30, 7, 12))


if __name__ == "__main__":
    raise SystemExit(unittest.main())
