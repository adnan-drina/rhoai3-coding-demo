#!/usr/bin/env python3
"""Land-time tests for paved_road (M1/M2 index). Not dest."""
from __future__ import annotations

import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from paved_road import (
    GOLDEN_ROOT,
    HERMES_DIR,
    SPECIFY_RUN,
    audit_bytes,
    coverage,
    evaluate_audit,
    generate_audit,
    load_steps,
    matching_terminal_lines,
    sync_audit,
    validate_steps_doc,
)

M1 = HERMES_DIR / "skills" / "paved-road" / "paved-road-m1"
M2 = HERMES_DIR / "skills" / "paved-road" / "paved-road-m2"
AUTOSTART = (
    HERMES_DIR
    / "skills"
    / "harness"
    / "dispatch-phase"
    / "scripts"
    / "autostart-migration.sh"
)
LIB = Path(__file__).resolve().parent

M2_SKILLS = (
    "  ┊ 📚 skill  speckit-specify\n"
    "  ┊ 📚 skill  speckit-plan\n"
    "  ┊ 📚 skill  speckit-tasks\n"
    "  ┊ 📚 skill  plan-migration-partition\n"
    "  ┊ 📚 skill  check-spec-readiness\n"
)
M2_NATIVES_OK = (
    "  ┊ 💻 $         python3 .hermes/skills/sdd/check-spec-readiness/"
    "scripts/check-partition-coverage.py . --write-receipt "
    "evidence/receipts/partition-coverage/latest.json  0.2s\n"
    "  ┊ 💻 $         python3 .hermes/skills/sdd/check-spec-readiness/"
    "scripts/assert-m2-speckit-conformance.py .  0.2s\n"
)
M2_KERNELS_OK = (
    "  ┊ 💻 $         python3 .hermes/kernel/k4_convert.py --partition p  0.1s\n"
    "  ┊ 💻 $         python3 .hermes/kernel/k4_mint.py --exec  0.1s\n"
)


def _eval_msg(text: str, doc: dict, root: Path) -> tuple[int, str]:
    buf = io.StringIO()
    with redirect_stderr(buf):
        rc = evaluate_audit(text, doc, root)
    return rc, buf.getvalue()


class TestStepsContract(unittest.TestCase):
    def test_m1_one_producer_scan_with_mta(self):
        doc = load_steps(M1 / "steps.json")
        self.assertEqual(doc["artifact"], "m1-analyze")
        producers = [s for s in doc["steps"] if s.get("producer") is True]
        self.assertEqual(len(producers), 1)
        self.assertEqual(producers[0]["skill"], "scan-with-mta")
        names = [s.get("skill") for s in doc["steps"] if s["backing"] == "skill"]
        self.assertEqual(
            names,
            [
                "derive-legacy-boot3",
                "inventory-legacy-surface",
                "scan-with-mta",
            ],
        )
        native = [s for s in doc["steps"] if s["backing"] == "native"]
        self.assertEqual(len(native), 1)
        self.assertEqual(native[0]["native"], "kanban_attach.py")

    def test_m1_scan_before_inventory_is_refused(self):
        swapped = load_steps(M1 / "steps.json")
        steps = list(swapped["steps"])
        inv = next(i for i, s in enumerate(steps) if s.get("skill") == "inventory-legacy-surface")
        scan = next(i for i, s in enumerate(steps) if s.get("skill") == "scan-with-mta")
        steps[inv], steps[scan] = steps[scan], steps[inv]
        swapped["steps"] = steps
        errors = validate_steps_doc(swapped)
        self.assertTrue(
            any("inventory-legacy-surface must precede scan-with-mta" in e for e in errors),
            errors,
        )

    def test_m1_split_handoff_step_is_refused(self):
        doc = load_steps(M1 / "steps.json")
        extra = {
            "id": "emit-findings-handoff",
            "backing": "native",
            "native": "emit-findings-handoff.py",
        }
        doc["steps"] = list(doc["steps"]) + [extra]
        errors = validate_steps_doc(doc)
        self.assertTrue(
            any("emit-findings-handoff.py runs inside mta-analyze-legacy.sh" in e for e in errors),
            errors,
        )

    def test_m2_one_producer_plan_migration_partition(self):
        doc = load_steps(M2 / "steps.json")
        self.assertEqual(doc["artifact"], "m2-partition")
        producers = [s for s in doc["steps"] if s.get("producer") is True]
        self.assertEqual(len(producers), 1)
        self.assertEqual(producers[0]["skill"], "plan-migration-partition")
        skills = [s.get("skill") for s in doc["steps"] if s["backing"] == "skill"]
        self.assertEqual(
            skills,
            [
                "speckit-specify",
                "speckit-plan",
                "speckit-tasks",
                "plan-migration-partition",
                "check-spec-readiness",
            ],
        )
        kernels = [s["kernel"] for s in doc["steps"] if s["backing"] == "kernel"]
        self.assertEqual(kernels, ["k4_convert.py", "k4_mint.py"])
        native = [s["native"] for s in doc["steps"] if s["backing"] == "native"]
        self.assertEqual(
            native,
            ["check-partition-coverage.py", "assert-m2-speckit-conformance.py"],
        )

    def test_audit_json_generated_from_steps(self):
        for skill in (M1, M2):
            rc, msg = sync_audit(skill)
            self.assertEqual(rc, 0, msg)
            doc = load_steps(skill / "steps.json")
            self.assertEqual(
                (skill / "audit.json").read_text(encoding="utf-8"),
                audit_bytes(doc),
            )
            generated = generate_audit(doc)
            self.assertFalse(generated["last_wins_across_needles"])
            self.assertTrue(generated["last_wins_within_needle"])
            self.assertTrue(generated["unmatched_exit_1_fails"])
            self.assertTrue(generated["silence_fails"])
            self.assertIn("workflow-run.json", generated["forgeable_receipts"])


class TestAuditSemantics(unittest.TestCase):
    def setUp(self):
        self.doc = load_steps(M2 / "steps.json")
        self.keep = M2 / "fixtures" / "green-m2"

    def test_dest14_fixture_refuses(self):
        dest14 = M2 / "fixtures" / "dest-14-m2-four-exit1"
        text = (dest14 / "official.log").read_text(encoding="utf-8")
        self.assertGreaterEqual(text.count("[exit 1]"), 4)
        self.assertIn("preparing kanban_complete", text)
        self.assertNotIn("preparing kanban_block", text)
        rc, blob = _eval_msg(text, self.doc, dest14)
        self.assertEqual(rc, 1)
        self.assertIn("check-partition-coverage.py", blob)
        self.assertIn("assert-m2-speckit-conformance.py", blob)
        self.assertNotIn("mandated needle 'plan-migration-partition'", blob)

    def test_skill_dir_red_with_skill_view_passes(self):
        fx = M2 / "fixtures" / "skill-dir-red-skill-view-green"
        text = (fx / "official.log").read_text(encoding="utf-8")
        self.assertIn("assert-m2-story-headings.py", text)
        self.assertIn("[exit 1]", text)
        rc, blob = _eval_msg(text, self.doc, fx)
        self.assertEqual(rc, 0, blob)

    def test_basename_boundary_ignores_parent_directory(self):
        text = (
            "  ┊ 💻 $         python3 .hermes/skills/sdd/"
            "plan-migration-partition/scripts/assert-m2-story-headings.py "
            ".  0.1s [exit 1]\n"
        )
        self.assertEqual(matching_terminal_lines(text, "k4_convert.py"), [])
        self.assertEqual(
            matching_terminal_lines(text, "check-partition-coverage.py"), []
        )
        got = matching_terminal_lines(text, "assert-m2-story-headings.py")
        self.assertEqual(len(got), 1)
        self.assertIn("assert-m2-story-headings.py", got[0])

    def test_green_passes(self):
        text = (self.keep / "official.log").read_text(encoding="utf-8")
        rc = evaluate_audit(text, self.doc, self.keep)
        self.assertEqual(rc, 0)

    def test_green_fixtures_match_dispatcher_success_format(self):
        """Success lines omit [exit 0] (dest-9 t_af875a24). [exit 1] is failure."""
        logs = (
            M1 / "fixtures" / "green-m1" / "official.log",
            M2 / "fixtures" / "green-m2" / "official.log",
        )
        for path in logs:
            text = path.read_text(encoding="utf-8")
            self.assertNotIn(
                "[exit 0]",
                text,
                "%s must not invent [exit 0]; dispatcher omits it on success"
                % path,
            )

    def test_omitted_exit_marker_is_success(self):
        text = M2_SKILLS + M2_NATIVES_OK + M2_KERNELS_OK
        rc = evaluate_audit(text, self.doc, self.keep)
        self.assertEqual(rc, 0)

    def test_explicit_exit_2_refuses(self):
        text = (
            M2_SKILLS
            + M2_NATIVES_OK
            + "  ┊ 💻 $         python3 .hermes/kernel/k4_convert.py --partition p  0.1s [exit 2]\n"
            "  ┊ 💻 $         python3 .hermes/kernel/k4_mint.py --exec  0.1s\n"
        )
        rc = evaluate_audit(text, self.doc, self.keep)
        self.assertEqual(rc, 1)

    def test_silence_refuses(self):
        rc = evaluate_audit("no mandated needles\n", self.doc, self.keep)
        self.assertEqual(rc, 1)

    def test_exit1_not_cleared_by_other_needle(self):
        text = (
            M2_SKILLS
            + M2_NATIVES_OK
            + "  ┊ 💻 $         python3 .hermes/kernel/k4_convert.py --partition p  0.1s [exit 1]\n"
            "  ┊ 💻 $         python3 .hermes/kernel/k4_mint.py --exec  0.1s [exit 0]\n"
        )
        rc = evaluate_audit(text, self.doc, self.keep)
        self.assertEqual(rc, 1)

    def test_same_needle_later_success_clears_exit1(self):
        text = (
            M2_SKILLS
            + M2_NATIVES_OK
            + "  ┊ 💻 $         python3 .hermes/kernel/k4_convert.py --partition p  0.1s [exit 1]\n"
            "  ┊ 💻 $         python3 .hermes/kernel/k4_convert.py --partition p  0.1s\n"
            "  ┊ 💻 $         python3 .hermes/kernel/k4_mint.py --exec  0.1s\n"
        )
        rc, blob = _eval_msg(text, self.doc, self.keep)
        self.assertEqual(rc, 0, blob)

    def test_same_needle_exit1_without_later_clean_refuses(self):
        text = (
            M2_SKILLS
            + M2_NATIVES_OK
            + "  ┊ 💻 $         python3 .hermes/kernel/k4_convert.py --partition p  0.1s [exit 1]\n"
            "  ┊ 💻 $         python3 .hermes/kernel/k4_mint.py --exec  0.1s\n"
        )
        rc, blob = _eval_msg(text, self.doc, self.keep)
        self.assertEqual(rc, 1)
        self.assertIn("unmatched [exit 1]", blob)
        self.assertIn("k4_convert.py", blob)

    def test_two_run_prior_red_then_clean_passes(self):
        fx = M2 / "fixtures" / "two-run-prior-red-then-clean"
        text = (fx / "official.log").read_text(encoding="utf-8")
        self.assertGreaterEqual(text.count("Query: work kanban task"), 2)
        self.assertIn("[exit 1]", text)
        rc, blob = _eval_msg(text, self.doc, fx)
        self.assertEqual(rc, 0, blob)

    def test_two_run_prior_red_no_rerun_refuses(self):
        fx = M2 / "fixtures" / "two-run-prior-red-no-rerun"
        text = (fx / "official.log").read_text(encoding="utf-8")
        self.assertGreaterEqual(text.count("Query: work kanban task"), 2)
        rc, blob = _eval_msg(text, self.doc, fx)
        self.assertEqual(rc, 1)
        self.assertIn("unmatched [exit 1]", blob)
        self.assertIn("check-partition-coverage.py", blob)

    def test_workflow_run_json_is_not_proof(self):
        with tempfile.TemporaryDirectory(prefix="paved-forge-") as tmp:
            root = Path(tmp)
            receipt = root / "evidence" / "receipts" / "speckit"
            receipt.mkdir(parents=True)
            (receipt / "workflow-run.json").write_text("{}", encoding="utf-8")
            text = "stamped workflow-run.json; no skill_view\n"
            rc = evaluate_audit(text, self.doc, root)
            self.assertEqual(rc, 1)

    def test_specify_workflow_run_is_not_dispatch(self):
        text = (
            "  ┊ 📚 skill  speckit-specify\n"
            "  ┊ 💻 $         %s -i spec=x  1.0s [exit 0]\n" % SPECIFY_RUN
        )
        rc = evaluate_audit(text, self.doc, self.keep)
        self.assertEqual(rc, 1)

    def test_path_mention_is_not_skill_view(self):
        text = (
            "load .hermes/skills/speckit-specify/SKILL.md\n"
            "  ┊ 📚 skill  speckit-plan\n"
            "  ┊ 📚 skill  speckit-tasks\n"
            "  ┊ 📚 skill  plan-migration-partition\n"
            "  ┊ 📚 skill  check-spec-readiness\n"
            + M2_NATIVES_OK
            + "  ┊ 💻 $         python3 .hermes/kernel/k4_convert.py p  0.1s [exit 0]\n"
            "  ┊ 💻 $         python3 .hermes/kernel/k4_mint.py --exec  0.1s [exit 0]\n"
        )
        rc = evaluate_audit(text, self.doc, self.keep)
        self.assertEqual(rc, 1)


class TestAutostartAndCoverage(unittest.TestCase):
    def test_autostart_pins_one_skill_per_card(self):
        src = AUTOSTART.read_text(encoding="utf-8")
        self.assertIn("--skill paved-road-m1", src)
        self.assertIn("--skill paved-road-m2", src)
        self.assertEqual(src.count("--skill "), 2)
        self.assertNotIn("--skill derive-legacy-boot3", src)
        self.assertNotIn("--skill scan-with-mta", src)
        self.assertNotIn("--skill inventory-legacy-surface", src)
        self.assertNotIn("--skill plan-migration-partition", src)
        self.assertNotIn("--skill check-spec-readiness", src)
        self.assertIn("--max-retries 1", src)
        self.assertIn("kanban_request_review", src)
        self.assertIn("kanban_block", src)
        self.assertIn("skill_view", src)
        self.assertIn("type-inventory.json", src)
        self.assertNotIn("workflow run speckit", src.lower())

    def test_coverage_golden(self):
        self.assertEqual(coverage(GOLDEN_ROOT), 0)

    def test_cli_coverage(self):
        proc = subprocess.run(
            [sys.executable, str(LIB / "paved_road.py"), "coverage", "--root", str(GOLDEN_ROOT)],
            text=True,
            capture_output=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


class TestResolveLogProfileHome(unittest.TestCase):
    def test_profile_home_resolves_to_root_log(self):
        import os

        from paved_road import resolve_log

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "kanban" / "logs").mkdir(parents=True)
            log = root / "kanban" / "logs" / "t_ok.log"
            log.write_text("ok\n", encoding="utf-8")
            profile = root / "profiles" / "reviewer"
            profile.mkdir(parents=True)
            prev = os.environ.get("HERMES_HOME")
            os.environ["HERMES_HOME"] = str(profile)
            try:
                got = resolve_log("t_ok", None)
            finally:
                if prev is None:
                    os.environ.pop("HERMES_HOME", None)
                else:
                    os.environ["HERMES_HOME"] = prev
            self.assertEqual(got, log)

    def test_base_home_unchanged(self):
        import os

        from paved_road import resolve_log

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "kanban" / "logs").mkdir(parents=True)
            log = root / "kanban" / "logs" / "t_def.log"
            log.write_text("ok\n", encoding="utf-8")
            prev = os.environ.get("HERMES_HOME")
            os.environ["HERMES_HOME"] = str(root)
            try:
                got = resolve_log("t_def", None)
            finally:
                if prev is None:
                    os.environ.pop("HERMES_HOME", None)
                else:
                    os.environ["HERMES_HOME"] = prev
            self.assertEqual(got, log)

    def test_absent_log_path_still_points_at_root(self):
        import os

        from paved_road import resolve_log

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "kanban" / "logs").mkdir(parents=True)
            profile = root / "profiles" / "implementer"
            profile.mkdir(parents=True)
            prev = os.environ.get("HERMES_HOME")
            os.environ["HERMES_HOME"] = str(profile)
            try:
                got = resolve_log("t_missing", None)
            finally:
                if prev is None:
                    os.environ.pop("HERMES_HOME", None)
                else:
                    os.environ["HERMES_HOME"] = prev
            self.assertEqual(
                got, root / "kanban" / "logs" / "t_missing.log"
            )
            self.assertFalse(got.is_file())


class TestM1Green(unittest.TestCase):
    def test_m1_green_passes(self):
        from paved_road import evaluate_audit as ev

        doc = load_steps(M1 / "steps.json")
        root = M1 / "fixtures" / "green-m1"
        text = (root / "official.log").read_text(encoding="utf-8")
        self.assertEqual(ev(text, doc, root), 0)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
