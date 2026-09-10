#!/usr/bin/env python3
"""Land-time tests for paved_road (M1/M2 index). Not dest."""
from __future__ import annotations

import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from paved_road import (
    GOLDEN_ROOT,
    HERMES_DIR,
    audit_bytes,
    audit_paths,
    coverage,
    evaluate_audit,
    generate_audit,
    is_allowed_audit_log,
    load_steps,
    matching_terminal_lines,
    resolve_log,
    sync_audit,
    validate_steps_doc,
)

M1 = HERMES_DIR / "skills" / "paved-road" / "paved-road-m1"
M2 = HERMES_DIR / "skills" / "paved-road" / "paved-road-m2"
AUTOSTART = HERMES_DIR / "skills" / "harness" / "dispatch-phase" / "scripts" / "autostart-migration.sh"
LIB = Path(__file__).resolve().parent

GATE = "  ┊ 💻 $         python3 .hermes/skills/planning/admit-migration-plan/scripts/assert-planner-activated.py --root /projects/modernized  0.1s\n"
M2_SKILLS = "  ┊ 📚 skill  bootstrap-destination\n  ┊ 📚 skill  build-worklist\n  ┊ 📚 skill  admit-migration-plan\n  ┊ 📚 skill  verify-live-kanban-loop\n"
M2_MINT = "  ┊ 💻 $         python3 .hermes/kernel/k4_mint.py --root /projects/modernized --exec --verify-board  1.2s\n"


def _eval_msg(text: str, doc: dict, root: Path) -> tuple[int, str]:
    buf = io.StringIO()
    with redirect_stderr(buf):
        rc = evaluate_audit(text, doc, root)
    return rc, buf.getvalue()


class TestStepsContract(unittest.TestCase):
    def test_m1_freeze_first_assemble_producer(self):
        doc = load_steps(M1 / "steps.json")
        self.assertEqual(doc["artifact"], "m1-analyze")
        producers = [s for s in doc["steps"] if s.get("producer") is True]
        self.assertEqual(len(producers), 1)
        self.assertEqual(producers[0]["skill"], "assemble-evidence-bundle")
        names = [s.get("skill") for s in doc["steps"] if s["backing"] == "skill"]
        self.assertEqual(names[0], "freeze-migration-input")
        self.assertNotIn("derive-legacy-boot3", names)
        self.assertLess(names.index("inventory-legacy-surface"), names.index("scan-with-mta"))
        native = [s for s in doc["steps"] if s["backing"] == "native"]
        # M1 ends by dispatching the next phase: it binds the platform-recorded
        # pilot authorization to the bundle it just produced and mints M2.
        self.assertEqual([n["native"] for n in native], ["kanban_attach.py", "autostart-migration.sh"])

    def test_m1_scan_before_inventory_is_refused(self):
        swapped = load_steps(M1 / "steps.json")
        steps = list(swapped["steps"])
        inv = next(i for i, s in enumerate(steps) if s.get("skill") == "inventory-legacy-surface")
        scan = next(i for i, s in enumerate(steps) if s.get("skill") == "scan-with-mta")
        steps[inv], steps[scan] = steps[scan], steps[inv]
        swapped["steps"] = steps
        self.assertTrue(any("order" in e for e in validate_steps_doc(swapped)))

    def test_m1_split_handoff_step_is_refused(self):
        doc = load_steps(M1 / "steps.json")
        doc["steps"] = list(doc["steps"]) + [{"id": "emit-findings-handoff", "backing": "native", "native": "emit-findings-handoff.py"}]
        self.assertTrue(any("emit-findings-handoff.py runs inside" in e for e in validate_steps_doc(doc)))

    def test_m2_gate_first_admit_producer(self):
        doc = load_steps(M2 / "steps.json")
        self.assertEqual(doc["artifact"], "m2-admission")
        self.assertEqual(doc["steps"][0]["native"], "assert-planner-activated.py")
        producers = [s for s in doc["steps"] if s.get("producer") is True]
        self.assertEqual(producers[0]["skill"], "admit-migration-plan")
        self.assertEqual([s["kernel"] for s in doc["steps"] if s["backing"] == "kernel"], ["k4_mint.py"])
        self.assertNotIn("k4_convert.py", [s.get("kernel") for s in doc["steps"]])

    def test_m2_speckit_step_refused(self):
        doc = load_steps(M2 / "steps.json")
        doc["steps"] = [{"id": "speckit-specify", "backing": "skill", "skill": "speckit-specify"}] + list(doc["steps"])
        errors = validate_steps_doc(doc)
        self.assertTrue(any("retired" in e or "activation" in e for e in errors), errors)

    def test_audit_json_generated_from_steps(self):
        for skill in (M1, M2):
            rc, msg = sync_audit(skill)
            self.assertEqual(rc, 0, msg)
            doc = load_steps(skill / "steps.json")
            self.assertEqual((skill / "audit.json").read_text(encoding="utf-8"), audit_bytes(doc))
            generated = generate_audit(doc)
            self.assertFalse(generated["last_wins_across_needles"])
            self.assertTrue(generated["last_wins_within_needle"])
            self.assertTrue(generated["unmatched_exit_1_fails"])
            self.assertTrue(generated["silence_fails"])
            self.assertTrue(generated["worker_receipts_are_not_proof"])
            self.assertNotIn("forgeable_receipts", generated)


class TestAuditSemantics(unittest.TestCase):
    def setUp(self):
        self.doc = load_steps(M2 / "steps.json")
        self.keep = M2 / "fixtures" / "green-m2"

    def test_green_passes(self):
        text = (self.keep / "official.log").read_text(encoding="utf-8")
        self.assertEqual(evaluate_audit(text, self.doc, self.keep), 0)

    def test_green_fixtures_match_dispatcher_success_format(self):
        for path in (M1 / "fixtures" / "green-m1" / "official.log", M2 / "fixtures" / "green-m2" / "official.log"):
            self.assertNotIn("[exit 0]", path.read_text(encoding="utf-8"))

    def test_omitted_exit_marker_is_success(self):
        self.assertEqual(evaluate_audit(GATE + M2_SKILLS + M2_MINT, self.doc, self.keep), 0)

    def test_explicit_exit_2_refuses(self):
        text = GATE + M2_SKILLS + M2_MINT.replace("  1.2s\n", "  1.2s [exit 2]\n")
        self.assertEqual(evaluate_audit(text, self.doc, self.keep), 1)

    def test_silence_refuses(self):
        self.assertEqual(evaluate_audit("no mandated needles\n", self.doc, self.keep), 1)

    def test_gate_refusal_is_a_refusal(self):
        text = GATE.replace("  0.1s\n", "  0.1s [exit 1]\n") + M2_SKILLS + M2_MINT
        rc, blob = _eval_msg(text, self.doc, self.keep)
        self.assertEqual(rc, 1)
        self.assertIn("assert-planner-activated.py", blob)

    def test_exit1_not_cleared_by_other_needle(self):
        text = GATE.replace("  0.1s\n", "  0.1s [exit 1]\n") + M2_SKILLS + M2_MINT
        self.assertEqual(evaluate_audit(text, self.doc, self.keep), 1)

    def test_same_needle_later_success_clears_exit1(self):
        text = GATE + M2_SKILLS + M2_MINT.replace("  1.2s\n", "  1.2s [exit 1]\n") + M2_MINT
        rc, blob = _eval_msg(text, self.doc, self.keep)
        self.assertEqual(rc, 0, blob)

    def test_basename_boundary_ignores_parent_directory(self):
        text = "  ┊ 💻 $         python3 .hermes/skills/planning/build-worklist/scripts/build-worklist.test.py  0.1s [exit 1]\n"
        self.assertEqual(matching_terminal_lines(text, "k4_mint.py"), [])
        self.assertEqual(matching_terminal_lines(text, "assert-planner-activated.py"), [])
        self.assertEqual(len(matching_terminal_lines(text, "build-worklist.test.py")), 1)

    def test_path_mention_is_not_skill_view(self):
        text = GATE + "load .hermes/skills/migration/bootstrap-destination/SKILL.md\n  ┊ 📚 skill  build-worklist\n  ┊ 📚 skill  admit-migration-plan\n  ┊ 📚 skill  verify-live-kanban-loop\n" + M2_MINT
        self.assertEqual(evaluate_audit(text, self.doc, self.keep), 1)

    def test_worker_receipt_is_not_proof(self):
        with tempfile.TemporaryDirectory(prefix="paved-forge-") as tmp:
            root = Path(tmp)
            (root / "evidence" / "planning").mkdir(parents=True)
            (root / "evidence" / "planning" / "admission-receipt.json").write_text('{"status":"ADMITTED"}', encoding="utf-8")
            self.assertEqual(evaluate_audit("stamped a receipt; no skill_view\n", self.doc, root), 1)


class TestAutostartAndCoverage(unittest.TestCase):
    def test_autostart_pins_index_only(self):
        src = AUTOSTART.read_text(encoding="utf-8")
        self.assertIn("--skill paved-road-m1", src)
        self.assertIn("--skill paved-road-m2", src)
        for leaf in ("freeze-migration-input", "scan-with-mta", "inventory-legacy-surface", "bootstrap-destination", "build-worklist", "admit-migration-plan", "derive-legacy-boot3"):
            self.assertNotIn("--skill %s" % leaf, src)
        self.assertIn("--max-retries 1", src)
        self.assertIn("kanban_request_review", src)
        self.assertIn("kanban_block", src)
        self.assertIn("skill_view", src)
        self.assertIn("planner_activation", src)
        self.assertNotIn("speckit", src.lower())

    def test_coverage_golden(self):
        self.assertEqual(coverage(GOLDEN_ROOT), 0)

    def test_cli_coverage(self):
        proc = subprocess.run([sys.executable, str(LIB / "paved_road.py"), "coverage", "--root", str(GOLDEN_ROOT)], text=True, capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


class TestResolveLogProfileHome(unittest.TestCase):
    def _with_home(self, home: Path, task: str) -> Path | None:
        prev = os.environ.get("HERMES_HOME")
        os.environ["HERMES_HOME"] = str(home)
        try:
            return resolve_log(task, None)
        finally:
            if prev is None:
                os.environ.pop("HERMES_HOME", None)
            else:
                os.environ["HERMES_HOME"] = prev

    def test_profile_home_resolves_to_root_log(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "kanban" / "logs").mkdir(parents=True)
            (root / "kanban" / "logs" / "t_ok.log").write_text("ok\n", encoding="utf-8")
            profile = root / "profiles" / "reviewer"
            profile.mkdir(parents=True)
            self.assertEqual(self._with_home(profile, "t_ok"), root / "kanban" / "logs" / "t_ok.log")

    def test_base_home_unchanged(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "kanban" / "logs").mkdir(parents=True)
            self.assertEqual(self._with_home(root, "t_def"), root / "kanban" / "logs" / "t_def.log")


class TestAuditLogMustBeOfficial(unittest.TestCase):
    def test_fixture_official_log_allowed(self):
        path = M2 / "fixtures" / "green-m2" / "official.log"
        self.assertTrue(is_allowed_audit_log(path))
        self.assertEqual(audit_paths(path, M2 / "fixtures" / "green-m2", M2 / "steps.json"), 0)

    def test_kanban_logs_task_file_allowed(self):
        self.assertTrue(is_allowed_audit_log(Path("/projects/modernized/.hermes/home/kanban/logs/t_28a9dee4.log")))

    def test_implementer_cache_terminal_output_refused(self):
        cache = Path("/projects/modernized/.hermes/home/profiles/implementer/cache/terminal-output/out-1.log")
        self.assertFalse(is_allowed_audit_log(cache))
        buf = io.StringIO()
        with redirect_stderr(buf):
            rc = audit_paths(cache, M2 / "fixtures" / "green-m2", M2 / "steps.json")
        self.assertEqual(rc, 1)
        self.assertIn("not an official kanban log", buf.getvalue())

    def test_random_tmp_log_refused(self):
        self.assertFalse(is_allowed_audit_log(Path("/tmp/worker.log")))


class TestM1Green(unittest.TestCase):
    def test_m1_green_passes(self):
        doc = load_steps(M1 / "steps.json")
        root = M1 / "fixtures" / "green-m1"
        self.assertEqual(evaluate_audit((root / "official.log").read_text(encoding="utf-8"), doc, root), 0)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
