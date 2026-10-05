#!/usr/bin/env python3
"""Card text (H-11 slice 1, v30 Kanban readability review 2026-10-01).

Every repair card of the frozen v30 plan (r3) is rendered with planner.card_text and judged against the
review's content contract: no JSON, no "0 owned obligations", no "Make implement", immediate and later checks
named apart, a follow-up says why it exists, a handoff reports each check's result (never "passing" from a
class or from done). The presentation is pinned: a v1 plan renders exactly what v30 published, a v2 body is
stored once and never rewritten by a later revision."""
from __future__ import annotations

import copy
import gzip
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from planner import card_text as CT  # noqa: E402
from planner import native_control as NC  # noqa: E402

FX = json.loads(gzip.decompress((HERE / "fixtures" / "v30-plan-r3-cards.json.gz").read_bytes()))
PLAN = FX["plan"]
NODES = {n["outcome_id"]: n for n in PLAN["nodes"]}


def node(prefix: str) -> dict:
    return next(n for oid, n in NODES.items() if oid.startswith(prefix))


class Descriptions(unittest.TestCase):
    def test_every_v30_repair_card_reads_without_json_or_zero_obligation_wording(self):
        for oid, n in NODES.items():
            if n.get("role") != "repair":
                continue
            body = CT.description(PLAN, n)
            title = CT.title(PLAN, n)
            for bad in ("{", "0 owned obligation", "Make implement", "obligation(s)", "requirement requirement"):
                self.assertNotIn(bad, body + title, (oid, bad))
            self.assertIn("Done when:", body, oid)
            self.assertIn("the reviewer approves", body, oid)
            self.assertTrue(title.startswith("M3 ") and len(title) <= 130, title)
            self.assertLessEqual(len(body.split()), 260, (oid, len(body.split())))

    def test_the_generator_card_names_its_check_and_the_later_checks_it_does_not_discharge(self):
        body = CT.description(PLAN, node("requirement:generator-configuration:"))
        self.assertIn("1 check passes on the current candidate: clean generation", body)
        self.assertIn("Checked later, not by this card: 28 checks", body)
        self.assertIn("does not discharge them", body)
        self.assertIn("pom.xml", body)

    def test_a_follow_up_says_what_failed_and_why_it_exists(self):
        f = node("followup:requirement:generator-configuration:")
        title, body = CT.title(PLAN, f), CT.description(PLAN, f)
        self.assertIn("create-refused-pets", title)
        self.assertIn("Why this card exists", body)
        self.assertIn("HTTP behavior of OwnerRestController", body)
        self.assertIn("stays accepted", body)
        r = node("followup:objective:selected-repository-implementation:")
        self.assertIn("repository effects of OwnerRepository", CT.title(PLAN, r))
        self.assertNotIn("measured finding", CT.description(PLAN, r))     # an owed check is not a finding

    def test_findings_are_named_by_kind(self):
        self.assertIn("97 compiler errors", CT.description(PLAN, node("objective:spring-dao-exceptions:")))
        dao_free = [n for n in NODES.values() if n.get("role") == "repair" and not n.get("obligations")
                    and (n.get("acceptance") or {}).get("requirement_checks")]
        self.assertTrue(dao_free)
        for n in dao_free:
            self.assertNotIn("finding", CT.description(PLAN, n).split("Checked later")[0].split("Details:")[0]
                             .replace("check, requirement", ""), n["outcome_id"])

    def test_the_assessment_names_the_checks_deferred_to_it(self):
        a = next(n for n in NODES.values() if n.get("role") == "assess")
        deferred = (a.get("acceptance") or {}).get("deferred_requirement_checks") or []
        body = CT.assess_description(PLAN, a)
        if deferred:
            self.assertIn("Also measured here: %d check" % len(deferred), body)


class Handoff(unittest.TestCase):
    def test_each_check_is_reported_by_its_result_never_passing_by_class(self):
        n = copy.deepcopy(node("objective:selected-repository-implementation:"))
        kept = n["acceptance"]["requirement_checks"]
        last = {"commit": "cc04f9e7c2942abc", "measurement": {
            "execution": {"build": {"state": "pass"}, "compile": {"state": "pass"}, "tests": {"state": "not-run"}},
            "checks": [kept[0]], "classes": ["build", "compile"],
            "unmet_checks": {"req:x|" + kept[1]: {"status": "fail", "detail": "does not carry @ApplicationScoped"},
                             "req:x|" + kept[2]: {"status": "unknown", "detail": "not measured"}},
            "open_owned": []}}
        s = CT.handoff_summary("M3 COMPILE — x", n, last, accepted_now=False, rejects=1, budget={"spent": 1, "limit": 12})
        self.assertIn("NOT accepted on the current tree", s)
        self.assertIn("Execution: build pass, compile pass, tests not-run.", s)
        self.assertIn("Checks judged here (3): 1 pass, 1 fail, 1 unknown", s)
        self.assertIn("Checked later, not discharged by this review", s)
        self.assertNotIn("checks build, compile", s)
        ok = dict(last, measurement=dict(last["measurement"], checks=kept, unmet_checks={}))
        s = CT.handoff_summary("M3 COMPILE — x", n, ok, accepted_now=True, rejects=0, budget={"spent": 0, "limit": 12})
        self.assertIn("implementation ready for review", s)
        self.assertIn("Checks judged here (3): 3 pass.", s)


class Pinning(unittest.TestCase):
    def test_a_v1_plan_renders_exactly_what_v30_published(self):
        published = FX["published_bodies"]
        seen = 0
        for n in PLAN["nodes"]:
            t = n.get("title")
            if n.get("role") == "repair" and t in published:
                self.assertEqual(NC.native_body(n), published[t], t)
                seen += 1
        self.assertGreater(seen, 25)
        self.assertIsNone(PLAN.get("presentation"))
        self.assertIs(NC.card_bodies(PLAN), PLAN)                     # a v1 plan is never re-rendered

    def test_a_v2_body_is_stored_once_and_never_rewritten_by_a_revision(self):
        plan = copy.deepcopy(PLAN)
        for n in plan["nodes"]:
            n.pop("card_body", None)
        plan["presentation"] = CT.PRESENTATION_V2
        r1 = NC.card_bodies(plan)
        gen = next(n for n in r1["nodes"] if n["outcome_id"].startswith("requirement:generator-configuration:"))
        self.assertEqual(NC.native_body(gen), gen["card_body"])
        self.assertIn("clean generation", gen["card_body"])
        # a later revision changes the facts of a published node: its published body does not move
        later = copy.deepcopy(r1)
        for n in later["nodes"]:
            if n["outcome_id"] == gen["outcome_id"]:
                n["acceptance"]["later_checks"] = []
        r2 = NC.native_revision(later)
        again = next(n for n in r2["nodes"] if n["outcome_id"] == gen["outcome_id"])
        self.assertEqual(again["card_body"], gen["card_body"])
        self.assertEqual(r2["presentation"], CT.PRESENTATION_V2)

    def test_fresh_v2_titles_are_readable_and_published_titles_are_kept(self):
        plan = copy.deepcopy(PLAN)
        plan["presentation"] = CT.PRESENTATION_V2
        f = next(n for n in plan["nodes"] if n["outcome_id"].startswith("followup:requirement:"))
        f["title"] = "Follow-up: x"                                   # not yet published
        out = {n["outcome_id"]: n["title"] for n in NC.native_titles(plan)["nodes"]}
        self.assertIn("create-refused-pets", out[f["outcome_id"]])
        kept = next(n for n in PLAN["nodes"] if n["outcome_id"].startswith("behavior:http:"))
        self.assertEqual(out[kept["outcome_id"]], kept["title"])     # an "M3 " title is never rewritten

    def test_the_run_decision_selects_the_presentation(self):
        from planner.decisions import card_presentation
        self.assertEqual(card_presentation({}), "v1")
        self.assertEqual(card_presentation({"loop": {"card_presentation": "v2"}}), "v2")
        self.assertEqual(card_presentation({"loop": {"card_presentation": "v9"}}), "v1")


class SpecimenAgnostic(unittest.TestCase):
    """The renderer is specimen-agnostic: every identifier of the frozen v30 plan is renamed (package, types,
    members, scenario ids, artifacts, files) and the rendered titles and bodies are the same text up to the same
    renaming -- nothing in card_text keys on a PetClinic name -- and no original name survives."""

    RENAMES = [("org.springframework.samples.petclinic", "io.acme.depot.app"), ("springframework/samples/petclinic", "acme/depot/app"),
               ("OwnerRestController", "CustomerApiResource"), ("PetRestController", "ParcelApiResource"),
               ("PetTypeRestController", "ParcelKindApiResource"), ("SpecialtyRestController", "SkillApiResource"),
               ("VetRestController", "CourierApiResource"), ("VisitRestController", "DeliveryApiResource"),
               ("RootRestController", "IndexApiResource"), ("UserRestController", "AccountApiResource"),
               ("ClinicService", "DepotService"), ("Owner", "Customer"), ("owner", "customer"), ("PetType", "ParcelKind"),
               ("Specialt", "Skil"), ("specialt", "skil"), ("Visit", "Delivery"), ("visit", "delivery"),
               ("Vet", "Courier"), ("vet", "courier"), ("Pet", "Parcel"), ("pet", "parcel"), ("petclinic", "depot"),
               ("openapi-generator-maven-plugin", "contract-codegen-plugin"), ("openapitools", "acmetools")]

    @staticmethod
    def mask(text: str) -> str:
        import re
        prev = None
        while prev != text:
            prev, text = text, re.sub(r"\([^()]*\)", "<list>", text)
        return re.sub(r"the behavior cards? for [^;.]*", "the behavior cards for <names>", text)

    def rename(self, text: str) -> str:
        for a, b in self.RENAMES:
            text = text.replace(a, b)
        return text

    def test_titles_and_bodies_are_invariant_under_renaming(self):
        twin = json.loads(self.rename(json.dumps(PLAN)))
        compared = 0
        for a, b in zip(PLAN["nodes"], twin["nodes"]):
            if a.get("role") != "repair":
                continue
            # the subject is rename-invariant; the title caps its length, so the cut point may move with name length
            self.assertEqual(self.rename(CT.subject_of(PLAN, a)), CT.subject_of(twin, b), a["outcome_id"])
            self.assertLessEqual(len(CT.title(twin, b)), 130)
            # same sentences, groups and counts; the name lists inside parentheses are sorted by name, so a renaming
            # may legitimately reorder which names are shown before "+n more"
            self.assertEqual(self.mask(self.rename(CT.description(PLAN, a))), self.mask(CT.description(twin, b)), a["outcome_id"])
            text = CT.title(twin, b) + CT.description(twin, b)
            for original in ("petclinic", "Owner", "Clinic", "openapi-generator"):
                self.assertNotIn(original, text, (b["outcome_id"], original))
            compared += 1
        self.assertGreater(compared, 30)


class LiveRevision(unittest.TestCase):
    """Through the real publication path (schedule_lifecycle's desk, golden decisions: card_presentation v2)."""

    def test_a_revision_inherits_v2_and_the_plan_card_reports_each_revision_once(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("sl_for_cards", HERE / "schedule_lifecycle.test.py")
        SL = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(SL)
        d = SL.Desk()
        r = d.r
        try:
            self.assertEqual(r.plan().get("presentation"), CT.PRESENTATION_V2)
            m2 = r.board.m2_task()
            d.complete(SL.B_ITEM)                       # an accepted card's read regresses: unowned evidence (H13-R1)
            d.measured(record_fail=("sc:read-items-1",))
            tid, run, lock = r.claim(SL.B_ORDER)
            with self.assertRaises(SL.Refusal):
                NC.issue(r.root, r.board, task_id=tid, run_id=run, claim_lock=lock)
            plan = r.plan()
            self.assertEqual(plan.get("presentation"), CT.PRESENTATION_V2)          # inherited by the revision
            f = next(n for n in plan["nodes"] if n["outcome_id"].startswith("followup:"))
            self.assertIn("repository effects of", f["title"])
            self.assertIn("Why this card exists", f["card_body"])
            notes = [c["body"] for c in r.native.comment_rows(m2)]
            self.assertEqual(sum(1 for b in notes if b.startswith("Plan revision 1 published:")), 1, notes)
            rev2 = [b for b in notes if b.startswith("Plan revision 2:")]
            self.assertEqual(len(rev2), 1, notes)
            self.assertIn("1 card added", rev2[0])
            self.assertIn("(10 planned + 1 added)", rev2[0])
            self.assertNotIn("{", "".join(notes))
            # a replayed publication posts nothing twice
            from planner.native_publish import progress_update
            progress_update(r.root, r.board, plan, [f["outcome_id"]], tid)
            self.assertEqual(sum(1 for c in r.native.comment_rows(m2) if c["body"].startswith("Plan revision 2:")), 1)
        finally:
            d.close()


if __name__ == "__main__":
    unittest.main()
