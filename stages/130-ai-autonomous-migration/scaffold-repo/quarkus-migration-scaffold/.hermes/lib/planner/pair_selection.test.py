#!/usr/bin/env python3
"""PARALLEL-M3-PILOT.md: deterministic pair selection and the serial chain around the pair.

Synthetic: the shop plan fixture (lib/planner/fixtures/outcome-initial-shop.json, derived by the real
outcome graph) with a frozen structural model written here. Identical inputs select the same pair;
overlapping, dependent, relying, shared-budget and unresolved pairs stay serial; no pair is reported
as no pair; the chain admits the pair and nothing else at once."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from planner import outcome_graph as OG  # noqa: E402
from planner import pair_selection as PS  # noqa: E402

SHOP = json.loads((HERE / "fixtures" / "outcome-initial-shop.json").read_text())
ITEM, ORDER, MAPPER = "source:rk:item", "source:rk:order", "source:u:dto-mapper"
W = "src/main/java/com/acme/shop/"


def plan():
    return OG.derive_initial_graph(run_id="n1", worklist=SHOP["worklist"], entry_points=SHOP["entry_points"],
                                   oracles=SHOP["oracles"], references=SHOP["references"], provenance=SHOP["provenance"])


def t(path, fqn, refs=(), resolution="full"):
    return {"path": W + path, "fqn": "com.acme.shop." + fqn, "type_refs": ["com.acme.shop." + r for r in refs],
            "resolution": resolution, "methods": [], "fields": []}


def structure(item_refs=("dto.ItemDto",), order_refs=("dto.ItemDto",), order_resolution="full"):
    return {"available": True, "mode": "full", "types": [
        t("web/ItemController.java", "web.ItemController", item_refs),
        t("web/OrderController.java", "web.OrderController", order_refs, order_resolution),
        t("web/RootController.java", "web.RootController"),
        t("dto/ItemDto.java", "dto.ItemDto"), t("dto/ItemMapper.java", "dto.ItemMapper", ("dto.ItemDto",))]}


def chain_view(p, pair):
    """Which repair outcomes could be ready at the same time: simulate the dispatcher over genuine +
    schedule parents, finishing one wave at a time."""
    sched = PS.schedule(p, pair)
    nodes = {n["outcome_id"]: n for n in p["nodes"] if n.get("role") == "repair"}
    parents = {o: (set(n.get("parents") or []) | set(sched.get(o, []))) & set(nodes) for o, n in nodes.items()}
    done, waves = set(), []
    while len(done) < len(nodes):
        ready = sorted(o for o in nodes if o not in done and parents[o] <= done)
        if not ready:
            raise AssertionError("cycle")
        waves.append(ready)
        done |= set(ready)
    return waves


class Selection(unittest.TestCase):
    def test_the_independent_pair_is_selected_with_its_evidence(self):
        sel = PS.select_pair(plan(), structure())
        self.assertEqual(sel["pair"], [ITEM, ORDER])
        ev = sel["evidence"]
        self.assertEqual(ev["writable_scopes"][ITEM], [W + "web/ItemController.java"])
        self.assertNotEqual(ev["budget_keys"][ITEM], ev["budget_keys"][ORDER])
        # shared read-only references (both read ItemDto) are not dependence
        self.assertIn("com.acme.shop.web.ItemController", ev["declared_types"][ITEM])
        # the mapper is a shared prerequisite and the build/config/runtime/behaviour outcomes are not candidates
        reasons = {e["outcome"]: e["reason"] for e in sel["excluded"]}
        self.assertIn("shared prerequisite", reasons[MAPPER])
        self.assertIn("not a compile", reasons["build:rk:pom"])

    def test_identical_inputs_select_the_same_pair(self):
        a, b = PS.select_pair(plan(), structure()), PS.select_pair(copy.deepcopy(plan()), copy.deepcopy(structure()))
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))

    def test_a_pair_that_relies_on_the_others_type_stays_serial(self):
        sel = PS.select_pair(plan(), structure(order_refs=("dto.ItemDto", "web.ItemController")))
        self.assertEqual(sel["pair"], [])
        self.assertTrue(any("relies on com.acme.shop.web.ItemController" in r for x in sel["rejected"] for r in x["reasons"]))
        self.assertIn("no pair", sel["why"])

    def test_an_unresolved_model_is_unknown_and_serial(self):
        self.assertEqual(PS.select_pair(plan(), structure(order_resolution="partial"))["pair"], [])
        self.assertIn("unavailable", PS.select_pair(plan(), None)["why"])

    def test_overlapping_scopes_and_shared_budgets_stay_serial(self):
        p = plan()
        for n in p["nodes"]:
            if n["outcome_id"] == ORDER:
                n["plan_paths"] = [W + "web/ItemController.java"]
        sel = PS.select_pair(p, structure())
        self.assertEqual(sel["pair"], [])
        self.assertTrue(any("overlapping writable scope" in r for x in sel["rejected"] for r in x["reasons"]))
        p = plan()
        key = next(n for n in p["nodes"] if n["outcome_id"] == ITEM)["budget"]["key"]
        for n in p["nodes"]:
            if n["outcome_id"] == ORDER:
                n["budget"] = dict(n["budget"], key=key)
        self.assertTrue(any("shared family budget" in r for x in PS.select_pair(p, structure())["rejected"] for r in x["reasons"]))

    def test_a_dependent_pair_stays_serial(self):
        p = plan()
        for n in p["nodes"]:
            if n["outcome_id"] == ORDER:
                n["parents"] = sorted(set(n["parents"]) | {ITEM})
        self.assertEqual(PS.select_pair(p, structure())["pair"], [])


class Chain(unittest.TestCase):
    def test_only_the_pair_is_ever_ready_together(self):
        p = plan()
        waves = chain_view(p, [ITEM, ORDER])
        self.assertIn([ITEM, ORDER], waves)
        self.assertTrue(all(len(w) == 1 for w in waves if w != [ITEM, ORDER]), waves)
        # every genuine prerequisite of either pair member precedes the pair
        flat = [o for w in waves for o in w]
        for o in (ITEM, ORDER):
            for par in next(n for n in p["nodes"] if n["outcome_id"] == o)["parents"]:
                if par in flat:
                    self.assertLess(flat.index(par), flat.index(ITEM))

    def test_without_a_pair_the_chain_is_fully_serial(self):
        self.assertTrue(all(len(w) == 1 for w in chain_view(plan(), [])))

    def test_apply_pilot_marks_the_pair_records_the_selection_and_reseals(self):
        p = PS.apply_pilot(plan(), structure())
        self.assertEqual(p["execution"]["selection"]["pair"], [ITEM, ORDER])
        nodes = {n["outcome_id"]: n for n in p["nodes"]}
        self.assertEqual((nodes[ITEM]["pilot_pair"], nodes[ORDER]["pilot_pair"]), ([ORDER], [ITEM]))
        self.assertEqual(p["digest"], OG.plan_digest(p))
        # genuine parents are untouched
        self.assertEqual({o: n["parents"] for o, n in nodes.items()},
                         {n["outcome_id"]: n["parents"] for n in plan()["nodes"]})

    def test_a_later_revision_chains_its_new_outcomes_after_the_live_pair(self):
        # ORDER stands in for a newly added outcome: it has no genuine edge to the live pair member,
        # so it waits for it; the runtime outcome already waits for ORDER genuinely, so it gets no edge
        p = plan()
        got = PS.chain_revision(p, [ORDER, "runtime:package:rk:package:spel"], [ITEM])
        self.assertEqual(got, {ORDER: {"schedule_parents": [ITEM]}})


if __name__ == "__main__":
    unittest.main(verbosity=1)
