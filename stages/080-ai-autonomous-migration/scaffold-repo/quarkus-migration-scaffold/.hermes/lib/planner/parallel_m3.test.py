#!/usr/bin/env python3
"""PARALLEL-M3-PILOT.md qualification (synthetic and real-git layers).

Synthetic board: FakeNative, the published graph read back and walked the way the native dispatcher
promotes dependents. Real git: actual `git worktree` checkouts of a disposable destination.
Native-runtime evidence (the pinned Hermes CLI materializing worktrees) is a separate layer."""
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("native_board_harness_pilot", HERE / "native_board.test.py")
NB = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(NB)
sys.path.insert(0, str(HERE.parent))
from planner import native_control as NC  # noqa: E402
from planner import pair_selection as PS  # noqa: E402

ITEM, ORDER = "source:rk:item", "source:rk:order"
W = "src/main/java/com/acme/shop/"


def structure(order_refs=("dto.ItemDto",)):
    def t(path, fqn, refs=()):
        return {"path": W + path, "fqn": "com.acme.shop." + fqn, "type_refs": ["com.acme.shop." + r for r in refs],
                "resolution": "full", "methods": [], "fields": []}
    return {"available": True, "mode": "full", "types": [
        t("web/ItemController.java", "web.ItemController", ("dto.ItemDto",)),
        t("web/OrderController.java", "web.OrderController", order_refs),
        t("web/RootController.java", "web.RootController"),
        t("dto/ItemDto.java", "dto.ItemDto"), t("dto/ItemMapper.java", "dto.ItemMapper", ("dto.ItemDto",))]}


def ready_waves(r) -> list[list[str]]:
    """Walk the published board as the native dispatcher would: take every ready repair outcome, finish
    it, promote dependents; return what was ready together at each step."""
    waves = []
    for _ in range(40):
        ready = sorted(t["id"] for t in r.native.tasks.values() if t["status"] == "ready"
                       and (r.board.node_of(t["id"]) or ("",))[0] == "repair")
        if not ready:
            break
        waves.append(sorted(r.board.node_of(t)[2] for t in ready))
        for tid in ready:
            r.native.complete(tid)
    return waves


class PilotPublication(unittest.TestCase):
    def test_a_pilot_run_publishes_the_pair_in_worktrees_inside_one_serial_chain(self):
        r = NB.Run(pilot=True, structure=structure())
        try:
            plan = r.plan()
            self.assertEqual(plan["execution"]["selection"]["pair"], [ITEM, ORDER])
            for oid in (ITEM, ORDER):
                t = r.native.task(r.tid(oid))
                path, branch = PS.worktree_of(str(r.root.resolve()), oid)
                self.assertEqual((t["workspace_path"], t["branch_name"]), ("worktree:" + path, branch))
            others = [t for t in r.native.tasks.values() if r.board.node_of(t["id"]) and r.board.node_of(t["id"])[2] not in (ITEM, ORDER)]
            self.assertTrue(all(str(t["workspace_path"]).startswith("dir:") for t in others))
            from planner.native_publish import readback
            self.assertEqual(readback(r.board, plan), [])
            r.release()
            waves = ready_waves(r)
            self.assertIn([ITEM, ORDER], waves)
            self.assertTrue(all(len(w) == 1 for w in waves if w != [ITEM, ORDER]), waves)
        finally:
            r.close()

    def test_a_serial_run_is_unchanged(self):
        r = NB.Run(pilot=False, structure=structure())
        try:
            self.assertNotIn("execution", r.plan())
            self.assertTrue(all(not t.get("branch_name") for t in r.native.tasks.values()))
        finally:
            r.close()

    def test_a_pilot_run_with_no_qualifying_pair_publishes_a_plain_chain_and_says_so(self):
        r = NB.Run(pilot=True, structure=structure(order_refs=("dto.ItemDto", "web.ItemController")))
        try:
            sel = r.plan()["execution"]["selection"]
            self.assertEqual(sel["pair"], [])
            self.assertIn("no pair", sel["why"])
            r.release()
            self.assertTrue(all(len(w) == 1 for w in ready_waves(r)))
        finally:
            r.close()


if __name__ == "__main__":
    unittest.main(verbosity=1)
