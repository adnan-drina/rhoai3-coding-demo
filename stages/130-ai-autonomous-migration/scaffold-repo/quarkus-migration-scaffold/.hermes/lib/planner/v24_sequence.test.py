#!/usr/bin/env python3
"""v24: one integrated synthetic sequence over the existing fake native board
(native_board.test.Run) and the loop's specimen harness -- no new framework.

  1. M2 facts from the published plan; the reviewer's structured check refuses
     a contradictory handoff and accepts the generated one;
  2. a rejected candidate that had written a new file: the revert deletes it
     and the retry is told exactly that (loop specimen, advance.py);
  3. an honest checkpoint: the commit is kept, the outcome stays pending and
     the one authoritative line says so;
  4. an early scoped repair accepted on the classes its verification
     executed, with no test class;
  5. a satisfied-no-edit outcome attributed to a witness, never a cause;
  6. M4 refusing an undischarged test obligation (not run, then failing);
  7. the correctly evidenced positive path: M4 accepted on a bound, passing
     suite, and M5 still keeping ship false while an unresolved group is open.
"""
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
HERMES = HERE.parent.parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


NB = _load("native_board_harness_v24", HERE / "native_board.test.py")
sys.path.insert(0, str(HERMES / "kernel"))
sys.path.insert(0, str(HERMES / "skills" / "migration" / "fix-until-green" / "scripts"))
import handoff_facts as HF  # noqa: E402
import _outcome_bridge as B  # noqa: E402
from planner import native_control as NC  # noqa: E402
from planner.outcome_checks import Refusal  # noqa: E402


class Sequence(unittest.TestCase):
    def test_v24_sequence(self):
        r = NB.Run()
        try:
            # 1. M2 facts and the reviewer's structured comparison
            plan = r.plan()
            with tempfile.TemporaryDirectory() as td:
                pf = Path(td) / "plan.r1.json"
                pf.write_text(json.dumps({"revision": plan["revision"], "plan": plan}))
                facts = HF.m2_facts(r.root, pf, task=r.m2, run=str(r.m2_run))
                good = HF.handoff_block(facts)
                bad = json.loads(json.dumps(good))
                bad["facts"]["cards"]["repair"] -= 1
                bad["unresolved"] = bad["unresolved"][1:] + ["unrelated-id"] if bad["unresolved"] else ["unrelated-id"]
                for meta, expect in ((bad, False), (good, True)):
                    show = {"runs": [{"id": r.m2_run, "profile": "implementer", "outcome": "review_requested", "metadata": meta}]}
                    with patch.object(HF, "_show", return_value=show), patch.object(HF, "published_plan_path", return_value=pf):
                        gaps = HF.review_gaps(r.root, "m2", r.m2)
                    self.assertEqual(not gaps, expect, gaps)
            r.release()
            r.drop("inc:unlocatable:jndi")

            # 3. an honest checkpoint: kept on the card, the outcome pending, one authoritative line
            topo = [n for n in NB.OG.topo_order(r.plan()["nodes"]) if n["role"] == "repair"]
            first = topo[0]["outcome_id"]
            tid, run, iss = r.issue(first)
            out = r.accept_on_run(tid, run, iss, classes=("build", "compile"), drop=False)
            self.assertFalse(out["outcome_accepted"])
            so = io.StringIO()
            with patch.object(NC, "accept_commit", return_value=out), patch.object(B, "reissue", return_value=0), \
                    patch.object(B, "_ids", return_value=(tid, run)), contextlib.redirect_stdout(so), \
                    contextlib.redirect_stderr(io.StringIO()):
                B._native_after_accept(r.root, r.board, "c" * 40, r.tree(), {}, {})
            self.assertTrue(so.getvalue().startswith("CHECKPOINT RECORDED; OUTCOME PENDING %s" % first), so.getvalue())

            # 4. early scoped repairs accepted on the classes executed (no tests: the tree does not compile yet)
            iss2 = NC.issue(r.root, r.board, task_id=tid, run_id=run)
            out = r.accept_on_run(tid, run, iss2, classes=("build", "compile"), attempt="2")
            self.assertTrue(out["outcome_accepted"], out)
            r.review_and_complete(tid, run)
            satisfied = 0
            for n in topo[1:]:
                if n["class"] in ("config",) and NB.status(r, r.tid(n["outcome_id"])) != "done":
                    # 5. satisfied, no edit: a witness, not a cause
                    r.drop(*NC.owned(r.plan(), NC._node(r.plan(), n["outcome_id"])))
                    ctid, crun, ciss = r.issue(n["outcome_id"])
                    self.assertTrue(ciss["next"].startswith("SATISFIED"), ciss["next"])
                    self.assertEqual(ciss["satisfied"]["by"]["relation"], "witness")
                    self.assertNotIn("discharged by", ciss["next"])
                    r.review_and_complete(ctid, crun)
                    satisfied += 1
                    continue
                if NB.status(r, r.tid(n["outcome_id"])) == "done":
                    continue
                cls = ("build", "compile") + {"runtime": ("runtime",), "behavior": ("runtime", "parity")}.get(n["class"], ())
                r.accept(n["outcome_id"], classes=cls, scenarios=n.get("scenarios") or ())

            self.assertGreaterEqual(satisfied, 1, "the sequence must exercise a satisfied-no-edit outcome")

            # 6. M4 refuses the undischarged test obligation, whether the suite did not run or failed
            m4 = r.tid("assess:m4:g1")
            for tests in (None, "failed"):
                _t, arun, _o = r.assess("PROVISIONAL_ACCEPT", tests=tests)
                with self.assertRaises(Refusal) as cm:
                    NC.check_terminator(r.root, r.board, task_id=m4, run_id=arun, kind="request_review",
                                        profile="implementer", audit_green=lambda: True)
                self.assertEqual(cm.exception.code, "ASSESS_TESTS_UNMEASURED")
                r.native.block_dependency(m4)

            # 7. the positive path: a bound, executed, passing suite
            _t, arun, _o = r.assess("PROVISIONAL_ACCEPT", tests="passed")
            d = NC.check_terminator(r.root, r.board, task_id=m4, run_id=arun, kind="request_review",
                                    profile="implementer", audit_green=lambda: True)
            self.assertEqual(d["action"], "allow")
            doc = NC._assessment_doc(r.board, m4, NC.latest_assessment(r.board, m4))
            self.assertEqual([u["id"] for u in doc["unresolved_responsibilities"]], [u["id"] for u in r.plan().get("unresolved") or []])
        finally:
            r.close()

        # 2. the rejected candidate that had written a new file (the loop's own harness drives advance.py)
        fug = _load("fug_v24", HERMES / "skills" / "migration" / "fix-until-green" / "scripts" / "fix-until-green.test.py")
        self.assertEqual(fug._revert_deletes_new_file_case(), 0)


if __name__ == "__main__":
    unittest.main(verbosity=1)
