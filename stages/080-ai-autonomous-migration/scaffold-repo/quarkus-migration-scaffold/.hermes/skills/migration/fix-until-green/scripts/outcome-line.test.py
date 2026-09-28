#!/usr/bin/env python3
"""v24 WP4: one authoritative outcome line, and a brief that leads with the
retry state and the required shape.

v23 t_71d9117b read "OK: ACCEPTED" (the checkpoint) and not "OUTCOME NOT YET
ACCEPTED" (the outcome), then blocked on a file the revert had deleted; the
PetType/Specialty/Visit briefs named @ApplicationScoped and @Typed only inside
a 64K section the printed digest never showed."""
from __future__ import annotations

import contextlib
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _outcome_bridge as B  # noqa: E402
import brief as BR  # noqa: E402
from planner import native_control as NC  # noqa: E402  (the scripts put .hermes/lib on the path)


class OutcomeLine(unittest.TestCase):
    def _after(self, out: dict) -> tuple[str, str]:
        so, se = io.StringIO(), io.StringIO()
        with patch.object(NC, "accept_commit", return_value=out), patch.object(B, "reissue", return_value=0), \
                patch.object(B, "_ids", return_value=("t_x", 7)), contextlib.redirect_stdout(so), contextlib.redirect_stderr(se):
            self.assertEqual(B._native_after_accept(Path("."), object(), "c" * 40, "d" * 64, {}, {}), 0)
        return so.getvalue(), se.getvalue()

    def test_an_incomplete_checkpoint_is_never_described_as_accepted(self):
        out, err = self._after({"outcome_id": "objective:x", "outcome_accepted": False,
                                "not_accepted_because": ["check unit:fragment-implementation is fail: PetImpl.java does not exist"]})
        first = out.strip().splitlines()[0]
        self.assertTrue(first.startswith("CHECKPOINT RECORDED; OUTCOME PENDING objective:x"), first)
        self.assertIn("PetImpl.java does not exist", first)
        self.assertIn("Do not kanban_complete or request review", first)
        self.assertNotIn("ACCEPTED", (out + err).replace("NOT accepted", ""))

    def test_an_accepted_outcome_is_handed_to_review(self):
        out, _err = self._after({"outcome_id": "objective:x", "outcome_accepted": True})
        self.assertTrue(out.startswith("OUTCOME ACCEPTED objective:x"), out)
        self.assertIn("kanban_request_review reviewer=reviewer", out)


class BriefDigest(unittest.TestCase):
    BRIEF = {
        "cluster": {"id": "planned:objective:repo:1", "kind": "compile", "path": "a/PetRepositoryImpl.java"},
        "_retry_state": {
            "last_rejection": {"reason": "INTRODUCED_COMPILE_DIAGNOSTIC: cannot find symbol class Typed",
                               "legal_next": "fix the named symbols in the same write set"},
            "deleted_by_last_revert": ["a/PetRepositoryImpl.java"],
            "write_set_files_absent": ["a/PetRepositoryImpl.java"],
            "refusals": [{"refusal": "INTRODUCED_COMPILE_DIAGNOSTIC", "times": 2}],
            "budget": {"family": {"key": "rk:family:f", "spent": 2, "limit": 12, "shared": True, "means": "GOVERNS"}}},
        "planned_requirements": [{
            "id": "req:repository-architecture:SpringDataPetTypeRepository<-PetTypeRepositoryOverride",
            "subject": "acme.SpringDataPetTypeRepository<-acme.PetTypeRepositoryOverride",
            "acceptance": ["unit:fragment-implementation", "structure:single-injectable-implementation", "gate:package"],
            "recipe": {"id": "spring-data-fragment-impl",
                       "architecture": "the <Fragment>Impl in the fragment's package, @ApplicationScoped and @Typed to the fragment"}}],
        "write_set": ["a/PetRepositoryImpl.java"], "items": [], "measure": {"tuple": [0, 94, 0]}, "procedure": "p", "rule": "r",
    }

    def test_retry_state_and_required_shape_lead_the_digest(self):
        text = BR.brief_digest(self.BRIEF, "brief-x")
        lines = text.splitlines()
        cluster_at = next(i for i, l in enumerate(lines) if l.startswith("cluster "))
        head = "\n".join(lines[:cluster_at])
        self.assertIn("the last revert DELETED: a/PetRepositoryImpl.java", head)
        self.assertIn("INTRODUCED_COMPILE_DIAGNOSTIC x2", head)
        self.assertIn("@ApplicationScoped and @Typed to the fragment", head)          # both CDI requirements, before any edit
        self.assertIn("checks now: unit:fragment-implementation, structure:single-injectable-implementation", head)
        self.assertIn("budget family: key rk:family:f, 2 of 12 spent (GOVERNS)", head)   # one limit, one count
        self.assertNotIn("of 3", head)

    def test_every_obligation_is_listed_with_its_symbol(self):
        # v24 run t_90e674d6: 3 of 97 items shown; the worker grepped the 143K items section for two runs
        items = [{"path": "a/S%d.java" % (i % 4), "line": i, "rule_id": "compiler.err.cant.resolve.location",
                  "message": "cannot find symbol\n  symbol: class DataAccessException",
                  "advice": {"symbol": {"kind": "class", "name": "DataAccessException"},
                             "imported_as": "org.springframework.dao.DataAccessException"}} for i in range(97)]
        text = BR.brief_digest(dict(self.BRIEF, items=items), "brief-x")
        self.assertEqual(text.count("class DataAccessException (imported as org.springframework.dao.DataAccessException)"), 97)
        self.assertIn("line 96 compiler.err.cant.resolve.location", text)
        self.assertNotIn("more (see the items section)", text)

    def test_the_rejected_patch_names_what_it_introduced_in_the_write_set(self):
        # v24 run t_e5f21725: after the revert the worker grepped a 100-error mvn output for its file, halted
        rej = {"loci_before": [{"id": "e1", "path": "a/R.java", "line": 3, "detail": "old"}],
               "loci_after": [{"id": "e1", "path": "a/R.java", "line": 3, "detail": "old"},
                              {"id": "e2", "path": "a/R.java", "line": 21, "detail": "cannot find symbol\n  symbol: class HttpServerResponse"},
                              {"id": "e3", "path": "b/Other.java", "line": 9, "detail": "elsewhere"}]}
        rows = BR._introduced(rej, ["a/R.java"])
        self.assertEqual(rows, ["a/R.java:21 cannot find symbol symbol: class HttpServerResponse"])
        rs = dict(self.BRIEF["_retry_state"], introduced_in_write_set=rows)
        text = BR.brief_digest(dict(self.BRIEF, _retry_state=rs), "brief-x")
        self.assertIn("the rejected patch introduced", text)
        self.assertIn("a/R.java:21 cannot find symbol symbol: class HttpServerResponse", text)


if __name__ == "__main__":
    unittest.main(verbosity=1)
