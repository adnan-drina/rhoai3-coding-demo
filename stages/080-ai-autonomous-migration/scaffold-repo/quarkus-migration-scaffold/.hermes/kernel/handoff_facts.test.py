#!/usr/bin/env python3
"""handoff_facts v2: structured, bound handoff facts and their reviewer
comparison. The v23 discrepancies and the review-of-2c2264e1 counterexamples
(tmp/v23-run/implementation-review-2c2264e1/counterexamples.json), reproduced
on renamed synthetic data (no specimen names)."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

KERNEL = Path(__file__).resolve().parent
sys.path.insert(0, str(KERNEL))
import handoff_facts as hf  # noqa: E402
from planner.canonical import digest  # noqa: E402  (handoff_facts put .hermes/lib on the path)


def _w(path: Path, doc) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc), encoding="utf-8")


def _ep(i: int, method: str, path: str, kind: str = "http") -> dict:
    return {"entry_point_id": "ep:acme.Api%d#op():%s" % (i, kind), "kind": kind, "http_method": method, "http_path": path}


def m1_root(td: Path, *, extra: list[dict] | None = None, scenario_eps: int = 7, corpus: bool = True,
            mode_of_capture: str = "") -> Path:
    """14 captured reads, 19 writes and one wildcard route, all HTTP (the v23
    shape). ``scenario_eps`` of the writes have a captured, PASS-qualified
    scenario in the disabled mode; one more has only a FAIL (a source fact)."""
    eps = [_ep(i, "GET", "/api/r%d" % i) for i in range(14)]
    writes = [_ep(100 + i, m, "/api/w%d" % i) for i, m in enumerate(["POST"] * 7 + ["PUT"] * 6 + ["DELETE"] * 6)]
    eps += writes + [_ep(200, "GET", "/api/x/*/by/name")] + (extra or [])
    _w(td / hf.INVENTORY, {"entry_points": eps})
    bundle = {"entry_points": [e["entry_point_id"] for e in eps]}
    _w(td / hf.BUNDLE, bundle)
    for e in eps:
        captured = e["kind"] == "http" and e["http_method"] == "GET" and "*" not in e["http_path"]
        _w(td / hf.READ_ORACLES / ("ep_%s.json" % e["entry_point_id"].split(":")[1].replace("#", "_")),
           {"entry_point": e["entry_point_id"], "status": "CAPTURED" if captured else "INCONCLUSIVE",
            "reason": "prose that the facts never read"})
    scen = [{"id": "sc:w%d" % i, "entry_point": w["entry_point_id"]} for i, w in enumerate(writes[:scenario_eps + 1])]
    for mode, sub in hf.MODES.items():
        rows = scen if mode == "disabled" else []
        if corpus:
            _w(td / "verification" / sub / "corpus.json", {"scenarios": rows})
        csha = hashlib.sha256((td / "verification" / sub / "corpus.json").read_bytes()).hexdigest() if corpus else ""
        common = {"evidence_bundle_sha256": digest(bundle), "corpus_sha256": csha, "security_mode": mode_of_capture or mode}
        _w(td / hf.READ_ORACLES / sub / "_capture.json",
           dict(common, status="ok", requested=len(rows), captured=len(rows), scenarios=[r["id"] for r in rows]))
        _w(td / hf.READ_ORACLES / sub / "_qualification.json",
           dict(common, scenarios={r["id"]: {"capability": "FAIL" if i == scenario_eps else "PASS"} for i, r in enumerate(rows)}))
    return td


def m2_plan(td: Path, *, receipt: str = "r-published") -> Path:
    nodes = [{"role": "repair", "class": c} for c in ["source"] * 18 + ["behavior"] * 8 + ["config"] * 3 + ["build"]]
    nodes += [{"role": "assess", "class": "assess"}] + [{"role": "deliver", "class": "deliver"}] * 3
    unresolved = [{"id": "unresolved:verification:http:acme.C%d" % i, "blocks": "ship",
                   "entry_points": ["ep:acme.C%d#m%d():http" % (i, j) for j in range(n)],
                   "requirements": ["req:bv:acme.C%d#m%d" % (i, j) for j in range(n)]}
                  for i, n in enumerate([1, 2, 2, 2, 1, 2, 2])]
    reqs = [{"status": "applicable"}] * 65 + [{"status": "satisfied"}] * 2 + [{"status": "unresolved"}] * 12
    plan = {"revision": 1, "plan": {"policy": "p/v1", "digest": "d-plan", "nodes": nodes, "unresolved": unresolved,
                                    "requirements": reqs, "provenance": {"receipt_sha256": "r-published"}}}
    _w(td / "plan.r1.json", plan)
    _w(td / hf.ADMISSION, {"status": "ADMITTED", "receipt_digest": receipt, "blocks": []})
    return td / "plan.r1.json"


class M1Facts(unittest.TestCase):
    def test_counts_come_from_the_inventory_and_bound_captures(self):
        with tempfile.TemporaryDirectory() as td:
            f = hf.m1_facts(m1_root(Path(td)), task="t_m1", run="3")
        self.assertEqual(f["entry_points"], {"total": 34, "http": 34, "non_http": 0, "by_kind": {"http": 34}})
        ro = f["read_oracles"]
        self.assertEqual((ro["captured"], ro["inconclusive"]), (14, 20))
        self.assertEqual(ro["not_captured_by_suitability"], {"needs-request-fixture": 1, "write-requires-scenario": 19})
        cov = f["coverage"]
        # 14 reads + 7 writes with a passing scenario; the FAIL-only write, the other 11 writes and the wildcard stay unverified
        self.assertEqual((cov["read_oracle"], cov["scenario_passed"]["disabled"], cov["covered"], cov["unverified"]), (14, 7, 21, 13))
        self.assertEqual(cov["source_qualification_fail"]["disabled"], ["sc:w7"])
        self.assertEqual(f["operator_observations_needed"], 0)
        self.assertEqual(f["binding"]["run"], "3")

    def test_a_write_without_a_scenario_is_unverified_not_covered(self):
        # review F3: one POST, no corpus and no capture -- suitability is not coverage
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ep = _ep(1, "POST", "/api/w")
            _w(root / hf.INVENTORY, {"entry_points": [ep]})
            _w(root / hf.BUNDLE, {"x": 1})
            _w(root / hf.READ_ORACLES / "ep_acme.Api1_op().json", {"entry_point": ep["entry_point_id"], "status": "INCONCLUSIVE"})
            f = hf.m1_facts(root)
        self.assertEqual(f["read_oracles"]["not_captured_by_suitability"], {"write-requires-scenario": 1})
        self.assertEqual((f["coverage"]["covered"], f["coverage"]["unverified"]), (0, 1))
        self.assertFalse(f["scenarios"]["disabled"]["bound"])

    def test_an_unbound_capture_covers_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            f = hf.m1_facts(m1_root(Path(td), mode_of_capture="enabled"))  # the disabled capture claims the enabled mode
        self.assertEqual(f["coverage"]["scenario_passed"]["disabled"], 0)
        self.assertIn("security mode", f["scenarios"]["disabled"]["unbound_reason"])

    def test_a_real_non_http_entry_point_needs_an_observation(self):
        with tempfile.TemporaryDirectory() as td:
            f = hf.m1_facts(m1_root(Path(td), extra=[_ep(300, "", "", kind="scheduled")]))
        self.assertEqual((f["entry_points"]["non_http"], f["operator_observations_needed"]), (1, 1))


class M2Facts(unittest.TestCase):
    def test_cards_and_unresolved_come_from_the_published_plan(self):
        with tempfile.TemporaryDirectory() as td:
            f = hf.m2_facts(Path(td), m2_plan(Path(td)), task="t_m2", run="7")
        self.assertEqual((f["cards"]["repair"], f["cards"]["milestones"], f["cards"]["total"]), (30, 4, 34))
        un = f["unresolved"]
        self.assertEqual((un["groups"], un["entry_points"], un["requirements"], un["blocks"]), (7, 12, 12, {"ship": 7}))
        self.assertEqual(f["admission"], {"status": "ADMITTED", "blocks": 0})
        self.assertEqual(f["binding"]["plan_digest"], "d-plan")

    def test_a_moved_admission_receipt_is_not_the_plans_input(self):
        with tempfile.TemporaryDirectory() as td:
            f = hf.m2_facts(Path(td), m2_plan(Path(td), receipt="r-later"))
        self.assertEqual(f["admission"], {"status": "admitted at publication", "blocks": None})
        self.assertEqual(f["binding"]["published_under_receipt"], "r-published")

    def test_published_plan_is_the_newest_native_revision_else_frozen_semantics(self):
        recs = [{"id": 1, "filename": "plan.r1.json", "stored_path": "/s/plan.r1.json"},
                {"id": 2, "filename": "plan.r2.json", "stored_path": "/s/plan.r2.json"},
                {"id": 3, "filename": "notes.json", "stored_path": "/s/notes.json"}]
        with patch.object(hf, "read_records", return_value=recs):
            self.assertEqual(hf.published_plan_path(Path("."), "t_m2"), Path("/s/plan.r2.json"))
        with tempfile.TemporaryDirectory() as td:
            with patch.object(hf, "read_records", return_value=recs[2:]):
                with self.assertRaises(ValueError):
                    hf.published_plan_path(Path(td), "t_m2")
            plan = json.loads(m2_plan(Path(td)).read_text())["plan"]
            _w(Path(td) / hf.PLAN_SEMANTICS, {"frozen": True, "plan": {"graph": plan, "requirements": plan["requirements"]}})
            with patch.object(hf, "read_records", return_value=recs[2:]):
                path = hf.published_plan_path(Path(td), "t_m2")
            self.assertEqual(hf.m2_facts(Path(td), path)["cards"]["repair"], 30)


class HandoffComparison(unittest.TestCase):
    def _facts(self, td: Path, phase: str) -> dict:
        return hf.m1_facts(m1_root(td), task="t_m1", run="3") if phase == "m1" else \
            hf.m2_facts(td, m2_plan(td), task="t_m2", run="7")

    def test_the_generated_block_passes_and_the_narrative_is_not_parsed(self):
        with tempfile.TemporaryDirectory() as td:
            for phase in ("m1", "m2"):
                f = self._facts(Path(td), phase)
                meta = dict(hf.handoff_block(f), note="34 HTTP entry points, 0 non-HTTP; no operator observations needed.")
                self.assertEqual(hf.handoff_gaps(f, meta), [], phase)

    def test_review_counterexamples(self):
        with tempfile.TemporaryDirectory() as td:
            f = self._facts(Path(td), "m2")
            # "Plan published." with no facts or unresolved metadata
            self.assertIn("metadata.facts is missing", hf.handoff_gaps(f, {})[0])
            # a published plan with seven ids and metadata naming one unrelated id
            meta = dict(hf.handoff_block(f), unresolved=["unrelated-id"])
            gaps = hf.handoff_gaps(f, meta)
            self.assertTrue(any("omits 7 plan id(s)" in g for g in gaps) and any("does not: unrelated-id" in g for g in gaps), gaps)

    def test_v23_m2_claims_are_refused(self):
        with tempfile.TemporaryDirectory() as td:
            f = self._facts(Path(td), "m2")
            meta = hf.handoff_block(f)
            meta["facts"]["cards"] = dict(meta["facts"]["cards"], repair=29)
            meta["unresolved"] = []
            gaps = hf.handoff_gaps(f, meta)
            self.assertTrue(any("facts.cards differs" in g for g in gaps), gaps)
            self.assertTrue(any("omits 7 plan id(s)" in g for g in gaps), gaps)

    def test_v23_m1_misclassification_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            f = self._facts(Path(td), "m1")
            meta = hf.handoff_block(f)
            meta["facts"]["operator_observations_needed"] = 20
            self.assertTrue(any("operator_observations_needed differs" in g for g in hf.handoff_gaps(f, meta)))

    def test_missing_required_field_and_duplicate_ids_refuse(self):
        with tempfile.TemporaryDirectory() as td:
            f = self._facts(Path(td), "m2")
            meta = hf.handoff_block(f)
            del meta["facts"]["unresolved"]
            meta["unresolved"] = meta["unresolved"] + meta["unresolved"][:1]
            gaps = hf.handoff_gaps(f, meta)
            self.assertTrue(any("facts.unresolved is missing" in g for g in gaps), gaps)
            self.assertTrue(any("repeats" in g for g in gaps), gaps)

    def test_the_factual_summary_must_be_the_generated_one(self):
        with tempfile.TemporaryDirectory() as td:
            f = self._facts(Path(td), "m2")
            meta = dict(hf.handoff_block(f), factual_summary="29 repair outcomes")
            self.assertTrue(any("factual_summary" in g for g in hf.handoff_gaps(f, meta)))

    def test_review_reads_the_latest_implementer_run(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            plan = m2_plan(root)
            good = hf.handoff_block(hf.m2_facts(root, plan, task="t_m2", run="7"))
            show = {"runs": [{"id": 7, "profile": "implementer", "outcome": "review_requested", "metadata": good},
                             {"id": 8, "profile": "reviewer", "outcome": "changes_requested"},
                             {"id": 9, "profile": "implementer", "outcome": "review_requested", "metadata": json.dumps(good)}]}
            with patch.object(hf, "_show", return_value=show), \
                    patch.object(hf, "published_plan_path", return_value=plan):
                gaps = hf.review_gaps(root, "m2", "t_m2")
            self.assertTrue(gaps and all("run 9" in g for g in gaps) and any("binding differs" in g for g in gaps), gaps)
            show["runs"][2]["outcome"] = "blocked"
            with patch.object(hf, "_show", return_value=show), patch.object(hf, "published_plan_path", return_value=plan):
                gaps = hf.review_gaps(root, "m2", "t_m2")
            self.assertTrue(gaps and "did not request review" in gaps[0], gaps)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
