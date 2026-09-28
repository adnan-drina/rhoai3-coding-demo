#!/usr/bin/env python3
"""v24 (architect decision 2026-09-28), the loop side: on a governed native card
advance.py's rejection projects the native family account -- one key, one count,
one limit -- instead of adding its own count against decisions.max_attempts.
The third rejection continues when the published limit is twelve, the twelfth
defers, a replay does not count twice, an inconsistent account refuses, the
REVERTED line shows the account's numbers, and the legacy loop still defers at
decisions.max_attempts."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
_spec = importlib.util.spec_from_file_location("fug_harness_budget", HERE / "fix-until-green.test.py")
FUG = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(FUG)
import advance as ADV  # noqa: E402
import _outcome_bridge as B  # noqa: E402
from planner import specimens  # noqa: E402
from planner.canonical import load_json, write_canonical  # noqa: E402
from planner.paths import LOOP_DEFERRED, LOOP_ISSUED, LOOP_STEPS, MTA_FINDINGS, WORKLIST  # noqa: E402

KEY, LIMIT = "rk:family:t:repositories", 12


class LoopProjection(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory(prefix="fam-")
        self.addCleanup(td.cleanup)
        spec = specimens.specimen("http")
        self.root = specimens.build_dest(Path(td.name) / "dest", spec, decisions=specimens.admitted_decisions(max_attempts=3))
        owner = FUG._write_uri_controllers(self.root, FUG._BUILDER)[0]
        specimens.prepare_loop(self.root, errors=[(owner, 3, "cannot find symbol class UriComponentsBuilder",
                                                   "compiler.err.cant.resolve.location")])
        self.cluster = next(c for c in load_json(self.root / WORKLIST)["clusters"] if owner in (c.get("write_set") or []))
        self.account = {"key": KEY, "spent": 0, "limit": LIMIT}

    def issue(self, governed=True):
        FUG._issue_cluster(self.root, self.cluster, "t_fam")
        if governed:
            doc = load_json(self.root / LOOP_ISSUED)
            doc.update(budget_authority="native", retry_key=KEY,
                       native_budget={"key": KEY, "spent": self.account["spent"], "limit": LIMIT, "shared": True})
            write_canonical(self.root / LOOP_ISSUED, doc)

    def reject(self, charge=True):
        """One rejection; the native record (bridge.record) charges the family first."""
        if charge:
            self.account["spent"] += 1
        acct = dict(self.account, exhausted=self.account["spent"] >= LIMIT)
        err = io.StringIO()
        with patch.object(B, "native_budget", return_value=acct), patch.object(B, "active", return_value=False), \
                contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            rc = ADV._reject(self.root, load_json(self.root / LOOP_STEPS), self.cluster["id"], "t_fam",
                             load_json(self.root / WORKLIST), "red", [], mint=False)
        return rc, err.getvalue()

    def deferred(self):
        p = self.root / LOOP_DEFERRED
        return self.cluster["id"] in (load_json(p).get("clusters") or []) if p.is_file() else False

    def test_the_third_continues_and_the_twelfth_defers(self):
        for n in range(1, LIMIT + 1):
            self.issue()
            rc, err = self.reject()
            steps = load_json(self.root / LOOP_STEPS)
            self.assertEqual(steps["attempts"][KEY], n)                       # a projection of the native count
            row = steps["rejected"][-1]["budget"]
            self.assertEqual((row["spent"], row["limit"]), (n, LIMIT))
            if n < LIMIT:
                self.assertIn("rejected attempt %d of %d on the family budget %s" % (n, LIMIT, KEY), err)
                self.assertFalse(self.deferred(), "deferred at %d of %d" % (n, LIMIT))
            else:   # the twelfth charge exhausts the family: the same numbers, and the loop stops
                self.assertIn("after %d of %d attempt(s) against %s" % (n, LIMIT, KEY), err)
        self.assertTrue(self.deferred())

    def test_a_replay_is_not_counted_twice(self):
        self.issue()
        self.reject()
        self.issue()
        self.reject(charge=False)       # the native record already held this rejection (same attempt key)
        self.assertEqual(load_json(self.root / LOOP_STEPS)["attempts"][KEY], 1)

    def test_an_inconsistent_account_refuses(self):
        self.issue()
        err = io.StringIO()
        with patch.object(B, "native_budget", return_value={"key": "rk:other", "spent": 1, "limit": LIMIT}), \
                patch.object(B, "active", return_value=False), contextlib.redirect_stderr(err):
            rc = ADV._reject(self.root, load_json(self.root / LOOP_STEPS), self.cluster["id"], "t_fam",
                             load_json(self.root / WORKLIST), "red", [], mint=False)
        self.assertEqual(rc, 1)
        self.assertIn("LOOP_BUDGET_INCONSISTENT", err.getvalue())
        with patch.object(B, "native_budget", return_value=None), patch.object(B, "active", return_value=False), \
                contextlib.redirect_stderr(io.StringIO()):
            self.issue()
            self.assertEqual(ADV._reject(self.root, load_json(self.root / LOOP_STEPS), self.cluster["id"], "t_fam",
                                         load_json(self.root / WORKLIST), "red", [], mint=False), 1)

    def test_the_legacy_loop_still_defers_at_max_attempts(self):
        for _n in range(3):
            self.issue(governed=False)
            with patch.object(B, "active", return_value=False), contextlib.redirect_stderr(io.StringIO()), \
                    contextlib.redirect_stdout(io.StringIO()):
                ADV._reject(self.root, load_json(self.root / LOOP_STEPS), self.cluster["id"], "t_fam",
                            load_json(self.root / WORKLIST), "red", [], mint=False)
        self.assertTrue(self.deferred())


class ReworkUnchanged(unittest.TestCase):
    """v24 run t_e2932aa0: a procedural change request on an accepted card; the no-op advance.py was
    REVERTED ("did not decrease") and charged the family. An unchanged rework candidate is not an attempt."""
    def _dest(self, td):
        spec = specimens.specimen("http")
        root = specimens.build_dest(Path(td) / "dest", spec, decisions=specimens.admitted_decisions(max_attempts=3))
        owner = FUG._write_uri_controllers(root, FUG._BUILDER)[0]
        errors = [(owner, 3, "cannot find symbol class UriComponentsBuilder", "compiler.err.cant.resolve.location")]
        specimens.prepare_loop(root, errors=errors)
        cluster = next(c for c in load_json(root / WORKLIST)["clusters"] if owner in (c.get("write_set") or []))
        return root, cluster, errors

    def test_an_unchanged_rework_candidate_is_not_judged_or_charged(self):
        with tempfile.TemporaryDirectory(prefix="rework-") as td:
            root, cluster, errors = self._dest(td)
            rework = dict(cluster, id="rework:source:c:x:26")
            FUG._issue_cluster(root, rework, "t_rw")
            specimens.verify(root, errors=errors, failures=[], findings=load_json(root / MTA_FINDINGS))
            p = FUG._advance(root, rework["id"], "t_rw")
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            self.assertIn("REWORK UNCHANGED rework:source:c:x:26", p.stdout)
            steps = load_json(root / LOOP_STEPS)
            self.assertEqual(steps.get("rejected") or [], [])
            self.assertEqual(steps.get("attempts") or {}, {})
            self.assertEqual(load_json(root / "verification" / "loop" / "last-advance.json")["verdict"], "OK")

    def test_an_unchanged_ordinary_candidate_is_still_judged(self):
        with tempfile.TemporaryDirectory(prefix="rework-ctl-") as td:
            root, cluster, errors = self._dest(td)
            FUG._issue_cluster(root, cluster, "t_ctl")
            specimens.verify(root, errors=errors, failures=[], findings=load_json(root / MTA_FINDINGS))
            p = FUG._advance(root, cluster["id"], "t_ctl")
            self.assertNotIn("REWORK UNCHANGED", p.stdout)
            self.assertTrue(load_json(root / LOOP_STEPS).get("rejected"), p.stdout + p.stderr)
            # the K2 hook lifts the post-[exit 1] lockout only on this recorded REVERTED (v24 run t_e5f41dc2)
            last = load_json(root / "verification" / "loop" / "last-advance.json")
            self.assertEqual((last["card"], last["verdict"], last["rc"]), ("t_ctl", "REVERTED", 1))

    def test_a_refusal_is_recorded_as_refused(self):
        with tempfile.TemporaryDirectory(prefix="rework-ref-") as td:
            root, cluster, errors = self._dest(td)
            FUG._issue_cluster(root, cluster, "t_ref")
            p = FUG._advance(root, "c:not-issued", "t_ref")          # LOOP_NOT_ISSUED: exit 1, no verdict
            self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
            self.assertEqual(load_json(root / "verification" / "loop" / "last-advance.json")["verdict"], "REFUSED")


if __name__ == "__main__":
    unittest.main(verbosity=1)
