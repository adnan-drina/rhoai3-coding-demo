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


class IssuedOwnership(unittest.TestCase):
    """Architect review 2026-09-29 §3 / v24 run t_dbde15ae: the Profile card shares repository paths with
    six repository-architecture requirements owned by other cards; its digest must not advertise their
    checks as due now."""
    REQ = {"id": "req:repository-architecture:X", "subject": "a.SpringDataX<-a.X", "status": "applicable",
           "acceptance": ["unit:fragment-implementation", "structure:single-injectable-implementation", "gate:package"],
           "recipe": {"id": "spring-data-fragment-impl", "architecture": "the <Fragment>Impl, @ApplicationScoped"}}

    def test_a_card_not_owning_the_requirement_shows_only_its_issued_checks(self):
        b = dict(BriefDigest.BRIEF, planned_requirements=[],
                 issued_checks={"outcome": "source:u:profile", "checks_now": ["worklist-absent", "measure:compile"],
                                "requirements": [], "other_owners_on_these_paths": [self.REQ["id"]]})
        b["_retry_state"] = {}
        text = BR.brief_digest(b, "brief-p")
        self.assertIn("CHECKS THIS CARD IS JUDGED BY NOW (its issued contract, source:u:profile): worklist-absent, measure:compile", text)
        self.assertIn("1 requirement(s) on these files belong to OTHER cards", text)
        self.assertNotIn("unit:fragment-implementation", text)
        self.assertNotIn("REQUIRED SHAPE", text)

    def test_an_owning_card_is_judged_by_its_issued_checks_only(self):
        b = dict(BriefDigest.BRIEF, planned_requirements=[self.REQ],
                 issued_checks={"outcome": "req:X", "checks_now": ["unit:fragment-implementation"],
                                "requirements": [self.REQ["id"]]})
        b["_retry_state"] = {}
        text = BR.brief_digest(b, "brief-o")
        self.assertIn("  X -- checks now: unit:fragment-implementation\n", text)
        self.assertNotIn("checks now: unit:fragment-implementation, structure", text)


class ObjectiveLiveness(unittest.TestCase):
    """v24 runs t_90e674d6 / t_e5f41dc2: a composite objective was told it was not open at its first brief."""
    ISSUED = {"cluster": "objective:objective:dao:1", "items": ["err:a", "err:b"], "item_identities": {"err:b": "diag:B|x"},
              "write_set": ["a/S.java"], "kind": "compile", "task_id": "t_o"}

    def test_open_while_any_constituent_is_reported(self):
        doc = {"head": "u:other", "items": [{"id": "err:a"}, {"id": "err:zz"}]}
        row = BR._issued_not_open(self.ISSUED, doc)
        self.assertNotIn("not_open", row)
        self.assertEqual(row["items"], ["err:a"])
        self.assertIn("1 of 2", row["liveness"])

    def test_a_rehashed_constituent_is_matched_by_identity(self):
        doc = {"head": "u:other", "items": [{"id": "err:new", "identity": "diag:B|x"}]}
        self.assertEqual(BR._issued_not_open(self.ISSUED, doc)["items"], ["err:new"])

    def test_not_open_only_when_no_constituent_is_reported(self):
        row = BR._issued_not_open(self.ISSUED, {"head": "u:other", "items": [{"id": "err:zz"}]})
        self.assertIn("not_open", row)


class Selectors(unittest.TestCase):
    def _root(self, td, measured_matches=True):
        from pathlib import Path as P
        root = P(td)
        doc = {"candidate_sha256": "c" * 64,
               "items": [{"id": "err:%d" % i, "path": "a/R.java" if i % 2 else "a/S.java", "line": i,
                          "rule_id": "compiler.err.cant.resolve.location", "message": "cannot find symbol\n  symbol: class HttpServerResponse",
                          "advice": {"symbol": {"kind": "class", "name": "HttpServerResponse"}}} for i in range(200)]}
        now = "c" * 64 if measured_matches else "d" * 64
        return root, doc, now

    def test_file_selector_is_bounded_and_names_the_candidate(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            root, doc, now = self._root(td)
            with patch.object(BR, "candidate_sha256", return_value=now):
                out = BR.select_facts(doc, root, file="/projects/modernized/a/R.java")
        self.assertIn("IS that candidate", out.splitlines()[0])
        self.assertIn("100 measured obligation(s) at a/R.java", out)
        self.assertEqual(sum(1 for l in out.splitlines() if l.startswith("  err:")), BR.SELECT_LIMIT)
        self.assertIn("20 more", out)

    def test_a_query_after_a_revert_says_the_tree_is_not_the_measured_candidate(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            root, doc, now = self._root(td, measured_matches=False)
            with patch.object(BR, "candidate_sha256", return_value=now):
                out = BR.select_facts(doc, root, symbol="HttpServerResponse")
        self.assertIn("NOT the measured candidate: run run-verify.sh", out)

    def test_an_empty_answer_is_stated_as_the_answer(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            root, doc, now = self._root(td)
            with patch.object(BR, "candidate_sha256", return_value=now):
                out = BR.select_facts(doc, root, file="a/None.java")
        self.assertIn("0 measured obligations at a/None.java. That is the answer", out)
        self.assertIn("do not re-run this query unchanged", out)


if __name__ == "__main__":
    unittest.main(verbosity=1)
