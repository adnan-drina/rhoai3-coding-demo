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
import json
import os
import sys
import tempfile
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


class LastVerification(unittest.TestCase):
    def test_the_digest_names_the_verifiers_own_exit(self):
        b = dict(BriefDigest.BRIEF, last_verify={"rc": 1, "mode": "acceptance", "card": "t_x", "run": "7", "finished_at": "T"})
        text = BR.brief_digest(b, "brief-v")
        self.assertIn("LAST VERIFICATION: exit 1 (acceptance, card t_x, run 7, T)", text)


class PreviousRun(unittest.TestCase):
    """V26-6 item 2 (v25 t_e5f21725 run 18): the retry did not know its predecessor repeated a grep five times,
    nor where the loop stood."""
    GREP = 'mvn compile | grep -E "RootRestController|HttpServerResponse" ; echo "EXIT: $?"'
    RUNS = [{"id": 17, "outcome": "crashed", "error": "STOP WORKER_TOOL_LOOP: tool terminal, guardrail identical_call_streak_halt"},
            {"id": 18, "outcome": None}]

    def _ledger(self):
        rows = []
        for i, cmd in enumerate(["python3 .hermes/skills/migration/fix-until-green/scripts/brief.py --root .",
                                 "bash .hermes/skills/migration/fix-until-green/scripts/run-verify.sh --root . | tail -40"]
                                + [self.GREP] * 5):
            rows += [{"phase": "start", "run": "17", "tool_call_id": "c%d" % i, "command": cmd},
                     {"phase": "end", "run": "17", "tool_call_id": "c%d" % i, "exit_code": 0}]
        return rows

    def test_the_retry_learns_what_its_predecessor_repeated_and_where_it_stopped(self):
        pr = BR.previous_run_context(self.RUNS, self._ledger(), "18", ["src/main/java/a/R.java"])
        self.assertEqual((pr["run"], pr["outcome"]), ("17", "crashed"))
        self.assertEqual((pr["repeated"]["times"], pr["repeated"]["command"]), (5, self.GREP))
        self.assertEqual(pr["last_loop_step"], {"script": "run-verify.sh", "exit_code": 0})
        text = BR.brief_digest(dict(BriefDigest.BRIEF, previous_run=pr), "brief-p")
        self.assertIn("PREVIOUS RUN of this card (run 17) ended crashed", text)
        self.assertIn("it repeated", text)
        self.assertIn("left in the working tree: src/main/java/a/R.java", text)

    def test_no_context_without_an_earlier_run_that_stopped(self):
        self.assertIsNone(BR.previous_run_context([{"id": 18, "outcome": None}], [], "18", []))
        self.assertIsNone(BR.previous_run_context([{"id": 17, "outcome": "review_requested"}, {"id": 18, "outcome": None}], [], "18", []))

    def test_a_run_without_ledger_rows_keeps_unknowns_unknown(self):
        pr = BR.previous_run_context(self.RUNS, [], "18", [])
        self.assertIsNone(pr["repeated"])
        self.assertIsNone(pr["last_loop_step"])

    def test_a_halted_investigation_carries_the_bounded_answer_it_already_had(self):
        # v26 t_4fd2dcec run 15: three identical dependency greps, then read_cycle_no_new_content_halt
        ledger = self._ledger()
        for r in ledger:
            if r["phase"] == "end" and r["tool_call_id"] == "c6":
                r.update(output_tail="x" * 1000 + "RootRestController.java:41 cannot find symbol HttpServletResponse",
                         output_chars=1066)
        pr = BR.previous_run_context(self.RUNS, ledger, "18", [], task="t_x")
        self.assertEqual(pr["kind"], "halted-investigation")
        self.assertEqual(len(pr["repeated"]["result_tail"]), BR.RESULT_TAIL)
        self.assertTrue(pr["repeated"]["result_tail"].endswith("cannot find symbol HttpServletResponse"))
        text = BR.brief_digest(dict(BriefDigest.BRIEF, previous_run=pr), "brief-h")
        self.assertIn("HALTED INVESTIGATION", text)
        self.assertIn("no candidate was judged or rejected", text)
        self.assertIn("what it returned (last 400 of 1066 characters)", text)

    def test_a_token_budget_stop_is_a_halted_investigation(self):
        # v32: RUN_TOKEN_BUDGET_EXHAUSTED ends the run as timed_out; the reading was cut off, nothing was judged
        runs = [{"id": 17, "outcome": "timed_out", "error": "RUN_TOKEN_BUDGET_EXHAUSTED: 12000417 of 12000000 input tokens"},
                {"id": 18, "outcome": None}]
        pr = BR.previous_run_context(runs, [], "18", [], task="t_x")
        self.assertEqual((pr["kind"], pr["outcome"]), ("halted-investigation", "timed_out"))
        self.assertTrue(pr["stop"].startswith("RUN_TOKEN_BUDGET_EXHAUSTED"))

    def test_an_unrecorded_result_is_unknown_not_empty(self):
        pr = BR.previous_run_context(self.RUNS, self._ledger(), "18", [], task="t_x")
        self.assertIsNone(pr["repeated"]["result_tail"])
        self.assertIn("what it returned: not recorded (unknown)",
                      BR.brief_digest(dict(BriefDigest.BRIEF, previous_run=pr), "brief-u"))

    def test_a_rejected_candidate_is_named_with_its_rejection(self):
        la = {"card": "t_x", "run": "17", "verdict": "REVERTED"}
        rej = [{"card": "t_x", "reason": "INTRODUCED_COMPILE_DIAGNOSTIC package jakarta.servlet.http does not exist"}]
        pr = BR.previous_run_context(self.RUNS, self._ledger(), "18", ["a/R.java"], task="t_x", last_advance=la, rejected=rej)
        self.assertEqual((pr["kind"], pr["verdict"]), ("rejected-candidate", "REVERTED"))
        text = BR.brief_digest(dict(BriefDigest.BRIEF, previous_run=pr), "brief-r")
        self.assertIn("REJECTED CANDIDATE: advance.py REVERTED its patch (INTRODUCED_COMPILE_DIAGNOSTIC", text)
        # a receipt of another run or card is not this run's judgement
        for other in ({"card": "t_x", "run": "16", "verdict": "REVERTED"}, {"card": "t_y", "run": "17", "verdict": "REVERTED"}):
            self.assertEqual(BR.previous_run_context(self.RUNS, [], "18", [], task="t_x", last_advance=other)["kind"],
                             "halted-investigation")


class CapabilityGap(unittest.TestCase):
    """V26-6 item 1: an owned Servlet use that no recipe qualifies is named before the first edit."""

    def test_the_gap_is_named_and_the_qualified_shape_is_printed(self):
        reqs = [{"id": "req:h:1", "status": "unresolved", "subject": "z.gateway.Dump#dump(javax.servlet.http.HttpServletResponse)|out",
                 "recipe": None, "acceptance": [], "unknowns": ["capability gap servlet-response-member: the handler calls getWriter, "
                                                                "which no qualified recipe translates"]},
                {"id": "req:h:2", "status": "applicable", "subject": "a.RootRestController#redirectToSwagger(x)|response",
                 "recipe": {"id": "servlet-redirect-response", "architecture": "ResponseEntity<Void> 302 Found with Location "
                                                                              "uriInfo.getBaseUriBuilder().path(<target>).build()"},
                 "acceptance": ["unit:handler-parameter-sites", "gate:augmentation"], "unknowns": []}]
        b = dict(BriefDigest.BRIEF, planned_requirements=reqs)
        b["_retry_state"] = {}
        text = BR.brief_digest(b, "brief-g")
        self.assertIn("CAPABILITY GAP (no qualified translation exists", text)
        self.assertIn("capability gap servlet-response-member: the handler calls getWriter", text)
        self.assertIn("servlet-redirect-response: ResponseEntity<Void> 302 Found with Location uriInfo.getBaseUriBuilder()", text)
        # a handler subject is labelled by its type and member, not by the last dot of a parameter type
        self.assertIn("  RootRestController#redirectToSwagger|response -- checks now", text)
        self.assertIn("  Dump#dump|out -- capability gap servlet-response-member", text)
        self.assertLess(text.index("REQUIRED SHAPE"), text.index("WRITE SET"))


class SmallBriefGuidance(unittest.TestCase):
    """v28 t_1cec0a74: an 8 KB brief printed as raw JSON, its previous_run and planned requirement mid-document;
    two runs read other cards' repositories (a `grep -B10 ... -B130` slow walk) instead of writing the owed file."""

    def test_a_changed_numeric_operand_does_not_prove_a_repeated_question(self):
        walk = ['cat src/a/OwnerRepository.java | grep -B%d "void delete"' % n for n in range(10, 140, 10)]
        ledger = []
        for i, c in enumerate(walk):
            ledger += [{"phase": "start", "run": "27", "tool_call_id": "w%d" % i, "command": c},
                       {"phase": "end", "run": "27", "tool_call_id": "w%d" % i, "exit_code": 0, "output_tail": "void delete(Owner owner);"}]
        pr = BR.previous_run_context([{"id": 27, "outcome": "crashed", "error": "STOP WORKER_TOOL_LOOP: read_family_no_new_content_halt"},
                                      {"id": 28, "outcome": None}], ledger, "28", [], task="t_x")
        self.assertIsNone(pr["repeated"])

    def test_the_guidance_leads_a_small_brief_and_names_the_owed_file(self):
        b = dict(BriefDigest.BRIEF)
        b["cluster"] = dict(b["cluster"], not_open={"head": "u:other"})
        b["previous_run"] = {"run": "27", "outcome": "crashed", "stop": "guard", "kind": "halted-investigation",
                             "repeated": None, "last_loop_step": None, "left_in_tree": []}
        head = BR.brief_digest(b, "brief-s").split("\ncluster ", 1)[0]
        self.assertTrue(head.startswith("BRIEF (digest:"))
        for want in ("write-set files that do not exist: a/PetRepositoryImpl.java",
                     "card's planned requirements remain", "REQUIRED SHAPE",
                     "PREVIOUS RUN of this card (run 27)"):
            self.assertIn(want, head)
        self.assertNotIn("\ncluster ", head)

    def test_an_empty_digest_still_names_its_cluster_and_scope(self):
        out = BR.brief_digest({"cluster": {"id": "c:1"}, "write_set": [], "items": []}, "brief-e")
        self.assertIn("cluster c:1", out)
        self.assertIn("WRITE SET (0 file(s)", out)


class WorkerInformation(unittest.TestCase):
    """Exercise worker-visible outputs, not a model imitation or a new guard."""

    def test_documented_actions_are_visible_without_another_catalog_search(self):
        b = dict(BriefDigest.BRIEF, unit={"first_action": "replace the qualified handler parameter using UriInfo"},
                 items=[{"path": "src/A.java", "line": 7, "advice": {"first_action": "retire @CrossOrigin"}}])
        out = BR.brief_digest(b, "brief-x")
        self.assertIn("coordinated unit: replace the qualified handler parameter using UriInfo", out)
        self.assertIn("src/A.java:7: retire @CrossOrigin", out)
        self.assertLess(out.index("DOCUMENTED FIRST ACTIONS"), out.index("WRITE SET"))

    def test_missing_reference_is_explicit_and_is_not_a_classpath_claim(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "A.java").write_text("import example.Missing;\nclass A {}\n")
            advice = BR.compile_advice({"path": "A.java", "message": "cannot find symbol\n symbol: class Missing"},
                                       root, [], {}, [])
            self.assertIn("No matching reference is provided", advice["do_not"])
            self.assertNotIn("Follow references[]", advice["do_not"])
            self.assertNotIn("type is not on the destination classpath", advice["do_not"])

    def test_stdout_is_the_digest_even_for_small_briefs_and_full_is_json(self):
        from planner.canonical import write_canonical
        from planner.paths import WORKLIST
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            c = {"id": "c:one", "path": "src/A.java", "kind": "compile", "gate": "compile",
                 "write_set": ["src/A.java"], "items": []}
            write_canonical(root / WORKLIST, {"head": c["id"], "clusters": [c], "items": [],
                                             "measure": {"tuple": [0, 0, 0], "known": True}, "not_counted": []})
            for flags in ([], ["--full"]):
                so, se = io.StringIO(), io.StringIO()
                with patch.dict(os.environ, {"HERMES_KANBAN_TASK": "", "HERMES_KANBAN_RUN_ID": ""}), \
                        patch.object(BR, "product_paths_changed", return_value=[]), \
                        patch.object(BR, "_previous_run", return_value=None), \
                        patch.object(BR, "issued_ownership", return_value=None), \
                        contextlib.redirect_stdout(so), contextlib.redirect_stderr(se):
                    self.assertEqual(BR.main(["--root", td] + flags), 0)
                self.assertEqual(se.getvalue(), "")
                if flags:
                    self.assertEqual(json.loads(so.getvalue())["cluster"]["id"], "c:one")
                else:
                    self.assertTrue(so.getvalue().startswith("BRIEF (digest:"))
                    self.assertIn("WRITE SET", so.getvalue())
                    self.assertIn("PROCEDURE", so.getvalue())

    def test_shared_path_does_not_confer_ownership_and_line_shift_keeps_it(self):
        doc = {"items": [{"id": "e:new", "identity": "diag:owned", "path": "src/A.java", "message": "Profile"},
                         {"id": "e:other", "path": "src/A.java", "message": "Transactional"}],
               "clusters": [{"id": "u:transactions", "items": ["e:other"]}]}
        seal = {"task_id": "t_here", "cluster": "u:profile", "items": ["e:old"],
                "item_identities": {"e:old": "diag:owned"}}
        with patch.dict(os.environ, {"HERMES_KANBAN_TASK": "t_here"}), patch.object(BR, "load_issued", return_value=seal), \
                patch.object(BR, "candidate_sha256", return_value="c" * 64):
            out = BR.select_facts(doc, Path("."), item="e:new")
            self.assertIn("issued to this card t_here", out)
            out = BR.select_facts(doc, Path("."), item="e:other")
            self.assertIn("not in this card's sealed", out)
            self.assertIn("u:transactions", out)
            self.assertIn("advance.py still judges newly introduced failures", out)
        with patch.dict(os.environ, {"HERMES_KANBAN_TASK": "t_other"}), patch.object(BR, "load_issued", return_value=seal), \
                patch.object(BR, "candidate_sha256", return_value="c" * 64):
            out = BR.select_facts(doc, Path("."), file="src/A.java")
            self.assertNotIn("issued to this card", out)
            self.assertIn("ownership unknown", out)

    def test_retry_does_not_call_changing_or_unknown_results_known(self):
        for kind in ("changed-prefix", "missing-fingerprint", "unknown-exit", "identical"):
            ledger = []
            for i in range(4):
                e = {"phase": "end", "run": "17", "tool_call_id": str(i), "exit_code": 0,
                     "output_tail": "same last 800 characters", "output_chars": 2000,
                     "output_sha256": (str(i) if kind == "changed-prefix" else "a") * 64}
                if kind == "missing-fingerprint":
                    e.pop("output_sha256")
                if kind == "unknown-exit":
                    e["exit_code"] = None
                ledger += [{"phase": "start", "run": "17", "tool_call_id": str(i), "command": "cat build.log"}, e]
            pr = BR.previous_run_context(PreviousRun.RUNS, ledger, "18", [])
            text = BR.brief_digest(dict(BriefDigest.BRIEF, previous_run=pr), "brief-r")
            self.assertNotIn("do not run it again", text)
            if kind != "identical":
                self.assertIn("result equality is unproven", text)
            else:
                self.assertIn("recorded complete results were identical", text)


class OwedPlannedRequirement(unittest.TestCase):
    """Architect review 2026-09-29, G2: a card whose compile items are gone while its planned requirement is still
    owed gets ONE next action -- what is owed, where, by which shape and checks -- in place of the generic
    not-open procedure, never beside it."""

    def test_one_next_action_names_the_requirement_write_set_and_checks(self):
        planned = [{"id": "req:1", "subject": "z.repository.PetTypeRepositoryImpl", "acceptance": ["structure:x", "parity:y"]}]
        with tempfile.TemporaryDirectory() as td:
            nxt = BR.planned_owed_next("objective:x:1", ["a/PetTypeRepositoryImpl.java"], planned,
                                       {"checks_now": ["structure:single-injectable-implementation"]}, Path(td))
        for want in ("still owes its planned requirement(s): PetTypeRepositoryImpl", "editing only these files: a/PetTypeRepositoryImpl.java",
                     "Write-set files that do not exist yet: a/PetTypeRepositoryImpl.java",
                     "judged by: structure:single-injectable-implementation", "--cluster objective:x:1",
                     "those two commands are the whole step"):
            self.assertIn(want, nxt)
        b = dict(BriefDigest.BRIEF, procedure=nxt, issued_not_open={"head": "u:other", "next": nxt})
        b["cluster"] = dict(b["cluster"], not_open={"head": "u:other", "next": nxt})
        text = BR.brief_digest(b, "brief-o")
        lines = text.splitlines()
        self.assertEqual(lines[1], "NEXT ACTION (this card):")
        self.assertNotIn("no longer on the open work list", text)  # the generic not-open procedure is gone
        self.assertNotIn("this card's planned requirement still owes the file(s) above", text)
        self.assertEqual(text.count("still owes its planned requirement(s)"), 2)  # NEXT ACTION and PROCEDURE: one text


class DiagnosticOwnership(unittest.TestCase):
    """Architect review 2026-09-29, ruling 5: each measured diagnostic says whose it is and whether it blocks THIS
    card, without widening the write set; an unknown owner is said to be unknown."""
    CTX = {"self": "objective:mine:1", "task": "t_me", "mine": {"err:a"},
           "owners": {"err:a": "objective:mine:1", "err:b": "objective:other:2"},
           "tasks": {"objective:other:2": {"id": "t_other", "status": "blocked"}}}

    def test_labels(self):
        mine = BR.ownership_of({"id": "err:a", "category": "mandatory"}, self.CTX)
        other = BR.ownership_of({"id": "err:b", "category": "mandatory"}, self.CTX)
        unknown = BR.ownership_of({"id": "err:c", "category": "mandatory"}, self.CTX)
        advisory = BR.ownership_of({"id": "err:d", "category": "optional"}, self.CTX)
        self.assertEqual([x["blocks_this_card"] for x in (mine, other, unknown, advisory)], [True, False, None, False])
        self.assertIn("this card owns it: blocks this card", mine["label"])
        self.assertIn("owned by objective:other:2 (card t_other, blocked): not this card to repair", other["label"])
        self.assertIn("owner unresolved", unknown["label"])
        line = BR._item_line({"id": "err:b", "line": 7, "rule_id": "compile", "message": "cannot find symbol", "ownership": other})
        self.assertIn("[owned by objective:other:2 (card t_other, blocked)", line)

    def test_the_selectors_carry_ownership(self):
        with tempfile.TemporaryDirectory() as td:
            doc = {"candidate_sha256": "", "items": [{"id": "err:b", "category": "mandatory", "path": "a/X.java", "line": 3,
                                                     "rule_id": "compile", "message": "cannot find symbol Foo"}]}
            out = BR.select_facts(doc, Path(td), symbol="Foo", owners=self.CTX)
            self.assertIn("[owned by objective:other:2 (card t_other, blocked)", out)
            one = BR.select_facts(doc, Path(td), item="err:b", owners=self.CTX)
            self.assertIn('"blocks_this_card": false', one)
            self.assertNotIn("owned by", BR.select_facts(doc, Path(td), symbol="Foo"))  # off the board nothing is claimed


class VerificationState(unittest.TestCase):
    """V26-6 item 2: a verification already completed on this tree is not repeated because its run crashed;
    one of an older tree is marked stale."""
    REC = {"schema": "rhoai3.last-verify/v2", "status": "finished", "card": "t_x", "run": "17", "rc": 0,
           "procedure": "completed", "mode": "acceptance", "compilation": "failed", "compilation_detail": "200 compile error(s)",
           "tests": "not-run", "tests_detail": "compilation is not clean", "candidate_sha256": "a" * 64}

    def test_current_stale_unknown(self):
        self.assertEqual(BR.verification_state(self.REC, "t_x", "a" * 64)["state"], "current")
        self.assertEqual(BR.verification_state(self.REC, "t_x", "b" * 64)["state"], "stale")
        self.assertEqual(BR.verification_state(self.REC, "t_other", "a" * 64)["state"], "unknown")
        self.assertEqual(BR.verification_state(dict(self.REC, status="started"), "t_x", "a" * 64)["state"], "unknown")
        self.assertEqual(BR.verification_state(dict(self.REC, candidate_sha256=""), "t_x", "a" * 64)["state"], "unknown")
        self.assertEqual(BR.verification_state(None, "t_x", "a" * 64)["state"], "unknown")

    def test_a_current_but_unusable_record_asks_for_acceptance_verification_not_an_edit(self):
        # architect review F2: freshness is not eligibility
        for rec, why in ((dict(self.REC, procedure="failed", rc=1, compilation="unknown"), "procedure did not complete"),
                         (dict(self.REC, mode="diagnostic"), "diagnostic verification"),
                         ({k: v for k, v in self.REC.items() if k not in ("procedure", "mode")}, "does not say")):
            vs = BR.verification_state(rec, "t_x", "a" * 64)
            self.assertEqual((vs["state"], vs["reusable"]), ("current", False))
            text = BR.brief_digest(dict(BriefDigest.BRIEF, last_verify=dict(rec, schema="rhoai3.last-verify/v2"),
                                        last_verify_state=vs), "brief-f2")
            self.assertNotIn("do not re-run run-verify.sh", text)
            self.assertIn("run run-verify.sh --mode acceptance on this tree now -- no product edit is needed", text)
            self.assertIn(why, text)

    def test_the_digest_keeps_procedure_compilation_and_tests_apart(self):
        b = dict(BriefDigest.BRIEF, last_verify=self.REC, last_verify_state=BR.verification_state(self.REC, "t_x", "a" * 64))
        text = BR.brief_digest(b, "brief-v2")
        self.assertIn("procedure completed (exit 0); compilation FAILED (200 compile error(s)); tests not run: compilation is not clean", text)
        self.assertIn("that result stands -- do not re-run run-verify.sh until you change the tree", text)
        b["last_verify_state"] = BR.verification_state(self.REC, "t_x", "b" * 64)
        self.assertIn("it is STALE: the tree changed since", BR.brief_digest(b, "brief-v3"))


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

    def test_the_required_architecture_is_printed_whole(self):
        long_arch = "the <Fragment>Impl in the fragment's package, @ApplicationScoped and @Typed to the fragment; " * 8
        req = dict(self.REQ, recipe={"id": "spring-data-fragment-impl", "architecture": long_arch})
        b = dict(BriefDigest.BRIEF, planned_requirements=[req],
                 issued_checks={"outcome": "req:X", "checks_now": ["unit:fragment-implementation"], "requirements": [req["id"]]})
        b["_retry_state"] = {}
        text = BR.brief_digest(b, "brief-a")
        self.assertIn(" ".join(long_arch.split()), text)

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
