#!/usr/bin/env python3
"""Land-time tests for paved_road (M1/M2 index). Not dest."""
from __future__ import annotations

import io
import json
import contextlib
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch
from pathlib import Path

from paved_road import (
    GOLDEN_ROOT,
    HERMES_DIR,
    audit_bytes,
    audit_paths,
    load_exec_ledger,
    coverage,
    evaluate_audit,
    generate_audit,
    is_allowed_audit_log,
    load_steps,
    matching_terminal_lines,
    m1_handoff_gaps,
    resolve_log,
    run_executables,
    sync_audit,
    validate_steps_doc,
)

M1 = HERMES_DIR / "skills" / "paved-road" / "paved-road-m1"
M2 = HERMES_DIR / "skills" / "paved-road" / "paved-road-m2"
FAKE_HERMES = M1 / "fixtures" / "fake-hermes"


def native_env(phase: str, show_dir: Path | None = None, store: Path | None = None) -> dict:
    """The fake native CLI a reviewer audit reads (kanban show / attachments)."""
    fx = (M1 if phase == "m1" else M2) / "fixtures"
    return {"HERMES_BIN": str(FAKE_HERMES), "FAKE_SHOW_DIR": str(show_dir or fx / "native"),
            "FAKE_ATTACHMENT_STORE": str(store or fx / "native-attachments")}
AUTOSTART = HERMES_DIR / "skills" / "harness" / "dispatch-phase" / "scripts" / "autostart-migration.sh"
LIB = Path(__file__).resolve().parent

GATE = "  ┊ 💻 $         python3 .hermes/skills/planning/admit-migration-plan/scripts/assert-planner-activated.py --root /projects/modernized  0.1s\n"
M2_SKILLS = "  ┊ 📚 skill  bootstrap-destination\n  ┊ 📚 skill  build-worklist\n  ┊ 📚 skill  admit-migration-plan\n  ┊ 📚 skill  verify-live-kanban-loop\n"
# the mint and the handoff facts it is followed by (a green M2 runs both; tests
# that mark or drop the mint touch only its "1.2s" line)
M2_MINT = ("  ┊ 💻 $         python3 .hermes/kernel/k4_mint.py --root /projects/modernized --exec --verify-board  1.2s\n"
           "  ┊ 💻 $         python3 .hermes/kernel/handoff_facts.py --root /projects/modernized --phase m2 --task t_m2 --write  0.3s\n")


def intent_ledger(text: str, run: str = "1") -> list[dict]:
    """The execution ledger a log line's AUTHOR intended: one start/end pair
    per invocation, the end carrying the marker's code (else 0), for tests of
    OTHER audit semantics. V17-6b tests edit these pairs explicitly: in
    production an unmarked line proves nothing."""
    import re as _re
    rows = []
    for i, ln in enumerate(text.splitlines()):
        m = _re.search(r"\$\s+(?P<cmd>.*?)\s+\d+(?:\.\d+)?s(?:\s+\[(?P<tag>[^\]]*)\])?\s*$", ln)
        if "$" not in ln or not m:
            continue
        em = _re.fullmatch(r"exit (\d+)", m.group("tag") or "")
        base = {"task": "t", "run": run, "tool_call_id": "c%d" % i, "command": m.group("cmd")}
        rows.append(dict(base, phase="start"))
        rows.append(dict(base, phase="end", exit_code=int(em.group(1)) if em else (0 if m.group("tag") is None else 1)))
    return rows


def _eval_msg(text: str, doc: dict, root: Path) -> tuple[int, str]:
    buf = io.StringIO()
    with redirect_stderr(buf):
        rc = evaluate_audit(text, doc, root, intent_ledger(text))
    return rc, buf.getvalue()


class TestM1Handoff(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / ".hermes").mkdir()
        (self.root / "evidence/planning").mkdir(parents=True)
        (self.root / "evidence/planning/evidence-bundle.json").write_text("{}")
        self.status = {"state": "minted", "m1_id": "t_m1", "after_m1": "t_m1",
                       "m2_id": "t_m2", "planner_activation": "activated"}
        self.pins = {"pins": {"planner": {"activation": "activated"}}}
        self.card = {"task": {"id": "t_m2", "title": "M2 PLAN", "workspace_kind": "dir", "workspace_path": str(self.root)},
                     "parents": [{"id": "t_m1"}]}

    def check_handoff(self):
        (self.root / ".hermes/AUTOSTART-STATUS").write_text(json.dumps(self.status))
        (self.root / ".hermes/pins.json").write_text(json.dumps(self.pins))
        result = subprocess.CompletedProcess([], 0, json.dumps(self.card), "")
        real_run = subprocess.run
        # `paved_road.subprocess` is the shared module: pass git (run control
        # reading the run's initial commit) through, fake only the kanban CLI
        fake = lambda argv, *a, **k: real_run(argv, *a, **k) if argv[:1] == ["git"] else result  # noqa: E731
        with patch("paved_road.subprocess.run", side_effect=fake) as run:
            gaps = m1_handoff_gaps(self.root, "t_m1")
        return gaps, run

    def test_governed_pilot_m2_passes_m1_audit(self):
        # v14 (2026-09-25): a governed run's activation is the platform record
        # plus the M1 binding; pins.json stays not-activated. The audit read
        # pins.json directly and refused "M2 recorded without planner
        # activation" although autostart had minted M2 as pilot.
        from planner import run_control
        from planner.canonical import digest
        run = "orders-service-v3"
        control, state = self.root / "control", self.root / "state"
        control.mkdir()
        (self.root / "run-budget.json").write_text(json.dumps({"schema": "rhoai3.run-budget/v2", "run_id": run,
            "run_control": {"contract": run_control.CONTRACT_SCHEMA, "root": str(control), "state": str(state)}}))
        git = lambda *a: subprocess.run(["git", "-C", str(self.root), "-c", "user.email=t@t", "-c", "user.name=t", *a],  # noqa: E731
                                        check=True, capture_output=True, text=True).stdout.strip()
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        git("add", "-A")
        git("commit", "-q", "-m", "scaffold")
        (control / "contract.json").write_text(json.dumps({"schema": run_control.CONTRACT_SCHEMA, "run_id": run,
            "scaffold_commit": git("rev-parse", "HEAD"), "activation": "pilot", "authorized_by": "provision-migration-run:tr-1",
            "authorization": {"event": "scaffolding push"}}))
        ok, msg = run_control.bind(self.root, digest(json.loads("{}")), "M1")
        self.assertTrue(ok, msg)
        self.pins = {"pins": {"planner": {"activation": "not-activated"}}}
        self.status["planner_activation"] = "pilot"
        gaps, _ = self.check_handoff()
        self.assertEqual(gaps, [])

    def test_skipped_exit_zero_does_not_pass_m1_audit(self):
        self.status = {"state": "skipped", "reason": "AUTO_START_MIGRATION off"}
        self.check_handoff()
        # Reproduce v10: the mandated command ran and returned zero.
        doc = {"kind": "m1-analyze", "steps": [{"id": "dispatch-next-phase", "backing": "native",
                                                    "native": "autostart-migration.sh"}]}
        text = "Query: work kanban task t_m1\n  ┊ 💻 $ bash .hermes/autostart-migration.sh --root .  0.1s\n"
        rc, msg = _eval_msg(text, doc, self.root)
        self.assertEqual(rc, 1)
        self.assertIn("PHASE_HANDOFF", msg)

    def test_native_parent_beside_task_passes(self):
        gaps, run = self.check_handoff()
        self.assertEqual(gaps, [])
        self.assertEqual(run.call_args.args[0], ["hermes", "kanban", "show", "t_m2", "--json"])

    def test_wrong_parent_or_workspace_refuses(self):
        for field in ("parent", "workspace"):
            with self.subTest(field=field):
                if field == "parent":
                    self.card["parents"] = [{"id": "t_other"}]
                else:
                    self.card["parents"] = [{"id": "t_m1"}]
                    self.card["task"]["workspace_path"] = "/another-run"
                self.assertTrue(self.check_handoff()[0])

    def test_stale_continuation_refuses(self):
        self.status["after_m1"] = "t_old"
        self.assertTrue(self.check_handoff()[0])

    def test_missing_child_refuses(self):
        self.status["m2_id"] = ""
        self.assertTrue(self.check_handoff()[0])

    def test_explicit_analysis_only_does_not_require_m2(self):
        self.pins["pins"]["planner"]["activation"] = "not-activated"
        self.status.update(m2_id="", planner_activation="not-activated")
        gaps, run = self.check_handoff()
        self.assertEqual(gaps, [])
        self.assertFalse([c for c in run.call_args_list if c.args[0][:1] != ["git"]], "no M2 card lookup")

    def test_unbound_pilot_cannot_claim_analysis_only(self):
        self.pins["pins"]["planner"]["activation"] = "pilot"
        self.status.update(m2_id="", planner_activation="not-activated")
        self.assertTrue(self.check_handoff()[0])


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
        self.assertEqual([n["native"] for n in native], ["handoff_facts.py", "kanban_attach.py", "autostart-migration.sh"])

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
        self.assertEqual(evaluate_audit(text, self.doc, self.keep, load_exec_ledger(self.keep / "official.log")), 0)

    def test_green_fixtures_match_dispatcher_success_format(self):
        for path in (M1 / "fixtures" / "green-m1" / "official.log", M2 / "fixtures" / "green-m2" / "official.log"):
            self.assertNotIn("[exit 0]", path.read_text(encoding="utf-8"))

    def test_omitted_exit_marker_is_unknown_without_a_ledger(self):
        # V17-6b: the runtime omits the marker whenever a result is not JSON
        # with a non-zero exit_code; an unmarked line alone proves nothing
        text = GATE + M2_SKILLS + M2_MINT
        self.assertEqual(evaluate_audit(text, self.doc, self.keep), 1)
        self.assertEqual(evaluate_audit(text, self.doc, self.keep, intent_ledger(text)), 0)

    def test_unmarked_failed_command_refuses(self):
        # V17-6b, the v17 shape: the log line is unmarked, the command exited 1
        text = GATE + M2_SKILLS + M2_MINT
        ledger = intent_ledger(text)
        ledger[-1]["exit_code"] = 1
        self.assertEqual(evaluate_audit(text, self.doc, self.keep, ledger), 1)

    def test_unknown_exit_code_refuses(self):
        text = GATE + M2_SKILLS + M2_MINT
        ledger = intent_ledger(text)
        ledger[-1]["exit_code"] = None
        self.assertEqual(evaluate_audit(text, self.doc, self.keep, ledger), 1)

    def test_red_then_recorded_clean_passes(self):
        text = GATE + M2_SKILLS + M2_MINT + M2_MINT
        ledger = intent_ledger(text)
        ledger[-7]["exit_code"] = 1  # the first mint's end (each M2_MINT is mint + facts): red, then the second is clean
        self.assertEqual(evaluate_audit(text, self.doc, self.keep, ledger), 0)

    def test_m2_without_handoff_facts_refuses(self):
        # v23 M2 handed off "29 outcomes" and "unresolved: []": the counts are computed, not written
        text = GATE + M2_SKILLS + M2_MINT.splitlines(keepends=True)[0]
        rc, msg = _eval_msg(text, self.doc, self.keep)
        self.assertEqual(rc, 1)
        self.assertIn("handoff_facts.py", msg)

    def test_a_plan_only_mint_is_not_the_step(self):
        # the mint without --exec plans and exits 0: the step requires the flag that makes it act
        bare = M2_MINT.replace(" --exec", "")
        text = GATE + M2_SKILLS + bare
        rc, msg = _eval_msg(text, self.doc, self.keep)
        self.assertEqual(rc, 1)
        self.assertIn("lacks --exec", msg)
        # a later invocation WITH --exec is the step
        self.assertEqual(evaluate_audit(GATE + M2_SKILLS + bare + M2_MINT, self.doc, self.keep,
                                        intent_ledger(GATE + M2_SKILLS + bare + M2_MINT)), 0)

    def test_m1_attach_without_exec_is_refused(self):
        # v23 M1: `kanban_attach.py` with no arguments printed OK and attached nothing
        doc = load_steps(M1 / "steps.json")
        keep = M1 / "fixtures" / "green-m1"
        text = (keep / "official.log").read_text(encoding="utf-8")
        bare = text.replace("kanban_attach.py --task t_m1 --exec", "kanban_attach.py")
        self.assertNotEqual(bare, text)
        buf = io.StringIO()
        with redirect_stderr(buf):
            rc = evaluate_audit(bare, doc, keep, intent_ledger(bare, run="1"))
        self.assertEqual(rc, 1)
        self.assertIn("kanban_attach.py", buf.getvalue())
        self.assertIn("lacks --exec", buf.getvalue())

    def test_required_flag_in_a_compound_command_counts(self):
        # v24 validation run (…-v25) M1: the flag was glued to the separator and the audit refused a correct run
        from paved_road import args_of_run
        cmd = 'cd /projects/modernized && python3 .hermes/kernel/handoff_facts.py --root /projects/modernized --phase m1 --write; echo "EXIT=$?"'
        self.assertIn("--write", args_of_run(cmd, "handoff_facts.py"))
        cmd = 'cd /x && python3 .hermes/kernel/kanban_attach.py --task "$HERMES_KANBAN_TASK" --exec | tee out; echo done'
        self.assertIn("--exec", args_of_run(cmd, "kanban_attach.py"))
        self.assertIn("--exec", args_of_run("bash -c 'python3 .hermes/kernel/kanban_attach.py --exec; echo ok'", "kanban_attach.py"))
        # the flag must belong to the script's own command, not a neighbour's
        self.assertNotIn("--exec", args_of_run("python3 .hermes/kernel/kanban_attach.py; echo --exec", "kanban_attach.py"))
        self.assertEqual(args_of_run("cat .hermes/kernel/kanban_attach.py", "kanban_attach.py"), [])
        doc = load_steps(M1 / "steps.json")
        keep = M1 / "fixtures" / "green-m1"
        text = (keep / "official.log").read_text(encoding="utf-8")
        wrapped = text.replace("kanban_attach.py --task t_m1 --exec", 'kanban_attach.py --task t_m1 --exec; echo "EXIT=$?"')
        self.assertNotEqual(wrapped, text)
        ledger = intent_ledger(wrapped, run="1")
        with patch.dict(os.environ, {"HERMES_BIN": str(FAKE_HERMES), "FAKE_ATTACHMENT_STORE": str(M1 / "fixtures" / "native-attachments")}):
            buf = io.StringIO()
            with redirect_stderr(buf):
                rc = evaluate_audit(wrapped, doc, keep, ledger)
        self.assertNotIn("lacks --exec", buf.getvalue())
        self.assertEqual(rc, 0, buf.getvalue())

    def test_require_args_is_validated(self):
        doc = load_steps(M2 / "steps.json")
        bad = json.loads(json.dumps(doc))
        next(s for s in bad["steps"] if s["backing"] == "skill")["require_args"] = ["--exec"]
        self.assertTrue(any("require_args" in e for e in validate_steps_doc(bad, path=Path("x"))))

    def test_read_of_the_script_is_not_an_execution(self):
        text = GATE + M2_SKILLS + M2_MINT
        ledger = intent_ledger(text)
        for row in ledger[-2:]:
            row["command"] = "cat .hermes/kernel/k4_mint.py"
        self.assertEqual(evaluate_audit(text, self.doc, self.keep, ledger), 1)

    def test_review_repro_latest_invocation_unrecorded_refuses(self):
        # review of 660c1c03: log shows two invocations, ledger records only
        # the first (exit 0) -- the older success must not stand for the latest
        text = GATE + M2_SKILLS + M2_MINT + M2_MINT
        ledger = intent_ledger(text)[:-2]
        self.assertEqual(evaluate_audit(text, self.doc, self.keep, ledger), 1)

    def test_lost_observer_result_refuses(self):
        text = GATE + M2_SKILLS + M2_MINT + M2_MINT
        ledger = intent_ledger(text)[:-1]  # second mint started, its end never recorded
        self.assertEqual(evaluate_audit(text, self.doc, self.keep, ledger), 1)

    def test_unfinished_invocation_refuses(self):
        text = GATE + M2_SKILLS + M2_MINT
        ledger = intent_ledger(text)
        ledger.append(dict(ledger[-2], tool_call_id="c-unfinished"))  # a later start, still running
        self.assertEqual(evaluate_audit(text + M2_MINT, self.doc, self.keep, ledger), 1)

    def test_earlier_run_success_does_not_stand_for_a_later_run(self):
        text = GATE + M2_SKILLS + M2_MINT + M2_MINT
        first = intent_ledger(GATE + M2_SKILLS + M2_MINT, run="28")
        later = [dict(r, run="30", tool_call_id="late") for r in intent_ledger(M2_MINT, run="30") if r["phase"] == "start"]
        self.assertEqual(evaluate_audit(text, self.doc, self.keep, first + later), 1)

    def test_end_from_another_run_does_not_complete(self):
        text = GATE + M2_SKILLS + M2_MINT
        ledger = intent_ledger(text)
        ledger[-1]["run"] = "other"
        self.assertEqual(evaluate_audit(text, self.doc, self.keep, ledger), 1)

    def test_explicit_exit_2_refuses(self):
        text = GATE + M2_SKILLS + M2_MINT.replace("  1.2s\n", "  1.2s [exit 2]\n")
        self.assertEqual(evaluate_audit(text, self.doc, self.keep, intent_ledger(text)), 1)

    def test_silence_refuses(self):
        self.assertEqual(evaluate_audit("no mandated needles\n", self.doc, self.keep), 1)

    def test_gate_refusal_is_a_refusal(self):
        text = GATE.replace("  0.1s\n", "  0.1s [exit 1]\n") + M2_SKILLS + M2_MINT
        rc, blob = _eval_msg(text, self.doc, self.keep)
        self.assertEqual(rc, 1)
        self.assertIn("assert-planner-activated.py", blob)

    def test_exit1_not_cleared_by_other_needle(self):
        text = GATE.replace("  0.1s\n", "  0.1s [exit 1]\n") + M2_SKILLS + M2_MINT
        self.assertEqual(evaluate_audit(text, self.doc, self.keep, intent_ledger(text)), 1)

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
        self.assertEqual(evaluate_audit(text, self.doc, self.keep, intent_ledger(text)), 1)

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
        # the terminators and step order live in the pinned skills the card bodies name
        for leaf in ("paved-road-m1", "paved-road-m2"):
            self.assertIn("Procedure: %s" % leaf, src)
            skill = (HERMES_DIR / "skills" / "paved-road" / leaf / "SKILL.md").read_text(encoding="utf-8")
            for needed in ("kanban_request_review", "kanban_block", "skill_view"):
                self.assertIn(needed, skill, (leaf, needed))
        self.assertIn("planner_activation", src)
        self.assertIn("reused", src)
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

    def test_missing_log_flag_falls_back_to_official(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            official = root / "kanban" / "logs" / "t_ok.log"
            official.parent.mkdir(parents=True)
            official.write_text("ok\n", encoding="utf-8")
            missing = Path(td) / "projects" / "modernized" / "kanban" / "logs" / "t_ok.log"
            prev = os.environ.get("HERMES_HOME")
            os.environ["HERMES_HOME"] = str(root)
            try:
                self.assertEqual(resolve_log("t_ok", missing), official)
            finally:
                if prev is None:
                    os.environ.pop("HERMES_HOME", None)
                else:
                    os.environ["HERMES_HOME"] = prev

    def test_task_env_fills_missing_id(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            official = root / "kanban" / "logs" / "t_env.log"
            official.parent.mkdir(parents=True)
            official.write_text("ok\n", encoding="utf-8")
            prev_home = os.environ.get("HERMES_HOME")
            prev_task = os.environ.get("HERMES_KANBAN_TASK")
            os.environ["HERMES_HOME"] = str(root)
            os.environ["HERMES_KANBAN_TASK"] = "t_env"
            try:
                self.assertEqual(resolve_log(None, None), official)
            finally:
                if prev_home is None:
                    os.environ.pop("HERMES_HOME", None)
                else:
                    os.environ["HERMES_HOME"] = prev_home
                if prev_task is None:
                    os.environ.pop("HERMES_KANBAN_TASK", None)
                else:
                    os.environ["HERMES_KANBAN_TASK"] = prev_task


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


class TestAuditReceipt(unittest.TestCase):
    """V17-6: the audit writes its own result, bound to the native run and
    profile, beside the official log; K2 reads that, never an absent marker."""

    def _audit_into(self, logs: Path, fixture: str, env: dict) -> tuple[int, dict]:
        log = logs / "t_rcpt0001.log"
        log.write_text((M2 / "fixtures" / fixture / "official.log").read_text(encoding="utf-8"), encoding="utf-8")
        (logs / "t_rcpt0001.exec.jsonl").write_text(
            (M2 / "fixtures" / fixture / "official.exec.jsonl").read_text(encoding="utf-8"), encoding="utf-8")
        with patch.dict(os.environ, dict(native_env("m2"), **env), clear=False):
            with redirect_stderr(io.StringIO()):
                rc = audit_paths(log, M2 / "fixtures" / fixture, M2 / "steps.json")
        return rc, json.loads((logs / "t_rcpt0001.audit.json").read_text(encoding="utf-8"))

    def test_green_audit_receipt_names_run_and_profile(self):
        with tempfile.TemporaryDirectory() as td:
            logs = Path(td) / "kanban" / "logs"
            logs.mkdir(parents=True)
            rc, doc = self._audit_into(logs, "green-m2", {"HERMES_KANBAN_RUN_ID": "32", "HERMES_PROFILE": "Reviewer"})
            self.assertEqual(rc, 0)
            self.assertEqual((doc["task"], doc["rc"], doc["run"], doc["profile"]), ("t_rcpt0001", 0, "32", "reviewer"))

    def test_red_audit_receipt_records_the_red(self):
        red = [p.name for p in sorted((M2 / "fixtures").iterdir()) if p.is_dir() and p.name != "green-m2"
               and (p / "official.log").is_file()]
        self.assertTrue(red, "paved-road-m2 has no red fixture to audit")
        with tempfile.TemporaryDirectory() as td:
            logs = Path(td) / "kanban" / "logs"
            logs.mkdir(parents=True)
            rc, doc = self._audit_into(logs, red[0], {"HERMES_KANBAN_RUN_ID": "30", "HERMES_PROFILE": "reviewer"})
            self.assertNotEqual(rc, 0)
            self.assertEqual(doc["rc"], rc)

    def _receipt(self, logs: Path) -> dict:
        return json.loads((logs / "t_rcpt0001.audit.json").read_text(encoding="utf-8"))

    def _cli(self, env: dict, *extra) -> int:
        cli = M2 / "scripts" / "assert-paved-road-audit.py"
        return subprocess.run([sys.executable, str(cli), "t_rcpt0001", "--root", str(M2 / "fixtures" / "green-m2"), *extra],
                              env=dict(os.environ, **native_env("m2"), **env), capture_output=True, text=True).returncode

    def test_green_then_red_replaces_the_receipt(self):
        with tempfile.TemporaryDirectory() as td:
            logs = Path(td) / "kanban" / "logs"
            logs.mkdir(parents=True)
            env = {"HERMES_KANBAN_RUN_ID": "32", "HERMES_PROFILE": "reviewer", "HERMES_HOME": td}
            self.assertEqual(self._audit_into(logs, "green-m2", env)[0], 0)
            rc, doc = self._audit_into(logs, "red-no-rerun", env)
            self.assertNotEqual(rc, 0)
            self.assertEqual((doc["rc"], doc["state"]), (rc, "done"))

    def test_green_then_missing_log_is_not_green(self):
        # the user's counterexample: first audit 0, second audit (log gone) 1,
        # the stored same-run receipt must not still say 0
        with tempfile.TemporaryDirectory() as td:
            logs = Path(td) / "kanban" / "logs"
            logs.mkdir(parents=True)
            env = {"HERMES_KANBAN_RUN_ID": "7", "HERMES_PROFILE": "reviewer", "HERMES_HOME": td}
            self.assertEqual(self._audit_into(logs, "green-m2", env)[0], 0)
            (logs / "t_rcpt0001.log").unlink()
            self.assertNotEqual(self._cli(env), 0)
            self.assertNotEqual(self._receipt(logs)["rc"], 0)

    def test_green_then_missing_ledger_is_not_green(self):
        with tempfile.TemporaryDirectory() as td:
            logs = Path(td) / "kanban" / "logs"
            logs.mkdir(parents=True)
            env = {"HERMES_KANBAN_RUN_ID": "7", "HERMES_PROFILE": "reviewer", "HERMES_HOME": td}
            self.assertEqual(self._audit_into(logs, "green-m2", env)[0], 0)
            (logs / "t_rcpt0001.exec.jsonl").unlink()
            self.assertNotEqual(self._cli(env), 0)
            self.assertNotEqual(self._receipt(logs)["rc"], 0)

    def test_green_then_malformed_steps_is_not_green(self):
        with tempfile.TemporaryDirectory() as td:
            logs = Path(td) / "kanban" / "logs"
            logs.mkdir(parents=True)
            env = {"HERMES_KANBAN_RUN_ID": "7", "HERMES_PROFILE": "reviewer", "HERMES_HOME": td}
            self.assertEqual(self._audit_into(logs, "green-m2", env)[0], 0)
            bad = Path(td) / "steps.json"
            bad.write_text("{not json", encoding="utf-8")
            with patch.dict(os.environ, env, clear=False), redirect_stderr(io.StringIO()):
                self.assertNotEqual(audit_paths(logs / "t_rcpt0001.log", M2 / "fixtures" / "green-m2", bad), 0)
            self.assertNotEqual(self._receipt(logs)["rc"], 0)

    def test_interrupted_audit_leaves_running_not_green(self):
        from paved_road import write_audit_receipt
        with tempfile.TemporaryDirectory() as td:
            logs = Path(td) / "kanban" / "logs"
            logs.mkdir(parents=True)
            env = {"HERMES_KANBAN_RUN_ID": "7", "HERMES_PROFILE": "reviewer", "HERMES_HOME": td}
            self.assertEqual(self._audit_into(logs, "green-m2", env)[0], 0)
            with patch.dict(os.environ, env, clear=False):
                write_audit_receipt(logs / "t_rcpt0001.log", None)  # the first thing a new audit does
            doc = self._receipt(logs)
            self.assertEqual((doc["rc"], doc["state"]), (None, "running"))

    def test_receipt_binds_the_audited_inputs(self):
        with tempfile.TemporaryDirectory() as td:
            logs = Path(td) / "kanban" / "logs"
            logs.mkdir(parents=True)
            _, doc = self._audit_into(logs, "green-m2", {"HERMES_KANBAN_RUN_ID": "7", "HERMES_PROFILE": "reviewer"})
            log_bytes = (logs / "t_rcpt0001.log").read_bytes()
            import hashlib
            self.assertEqual(doc["log"], {"bytes": len(log_bytes), "sha256": hashlib.sha256(log_bytes).hexdigest()})
            self.assertTrue(doc["ledger"]["sha256"] and doc["steps_sha256"])

    def test_fixture_log_gets_no_receipt(self):
        audit_paths(M2 / "fixtures" / "green-m2" / "official.log", M2 / "fixtures" / "green-m2", M2 / "steps.json")
        self.assertFalse((M2 / "fixtures" / "green-m2" / "official.audit.json").exists())


M4 = HERMES_DIR / "skills" / "paved-road" / "paved-road-m4"
RUNNER_REL = ".hermes/skills/gates/check-release-readiness/scripts/run-m4-pre-verdict.sh"
RUNNER_LINE = "  ┊ 💻 $         bash %s /projects/modernized  44.8s\n" % RUNNER_REL
GREP_LINE = "  ┊ 💻 $         grep -n \"m4-floor\\|receipts\" %s  0.1s [exit 1]\n" % RUNNER_REL


class TestRunDetection(unittest.TestCase):
    """A mandated-step run is a command whose EXECUTABLE is the step's script.

    v9 t_caf2ad51 (2026-09-22): the pre-verdict runner ran once (64 s, passed)
    and a later ``grep … run-m4-pre-verdict.sh`` the worker ran while reading
    the script exited 1; a substring match over the whole line counted the
    grep as a failed run and refused a card that had walked the road."""

    def setUp(self):
        self.doc = load_steps(M4 / "steps.json")
        self.root = M4 / "fixtures" / "green-m4"
        self.green = (self.root / "official.log").read_text(encoding="utf-8")
        self.assertIn(RUNNER_LINE, self.green)

    def test_v9_shape_read_after_runner_passes(self):
        text = self.green.replace(RUNNER_LINE, RUNNER_LINE + GREP_LINE)
        rc, blob = _eval_msg(text, self.doc, self.root)
        self.assertEqual(rc, 0, blob)

    def test_runner_exit1_still_refuses(self):
        text = self.green.replace(RUNNER_LINE, RUNNER_LINE.replace("  44.8s\n", "  44.8s [exit 1]\n"))
        rc, blob = _eval_msg(text, self.doc, self.root)
        self.assertEqual(rc, 1)
        self.assertIn("unmatched [exit 1] on mandated needle 'run-m4-pre-verdict.sh'", blob)

    def test_reads_alone_are_not_a_run(self):
        reads = ("  ┊ 💻 $         cat %s  0.1s\n" % RUNNER_REL
                 + "  ┊ 💻 $         sed -n 1,40p %s  0.1s\n" % RUNNER_REL
                 + GREP_LINE.replace(" [exit 1]", ""))
        text = self.green.replace(RUNNER_LINE, reads)
        rc, blob = _eval_msg(text, self.doc, self.root)
        self.assertEqual(rc, 1)
        self.assertIn("silence: step pre-verdict needle 'run-m4-pre-verdict.sh' has no terminal argv", blob)

    def test_run_forms_count(self):
        for cmd in ("bash %s /projects/modernized" % RUNNER_REL,
                    "python3 %s /projects/modernized" % RUNNER_REL,
                    "timeout 600 python3 %s /projects/modernized" % RUNNER_REL,
                    "timeout -k 5 600s bash -x %s ." % RUNNER_REL,
                    "cd /projects/modernized && bash %s . 2>&1 | tee /tmp/runner.log" % RUNNER_REL,
                    "HERMES_KANBAN_TASK=t_x bash %s ." % RUNNER_REL,
                    "%s /projects/modernized" % RUNNER_REL):
            line = "  ┊ 💻 $         %s  64.0s [exit 1]\n" % cmd
            self.assertEqual(len(matching_terminal_lines(line, "run-m4-pre-verdict.sh")), 1, cmd)
            self.assertIn("run-m4-pre-verdict.sh", run_executables(cmd))

    def test_mentions_do_not_count(self):
        for cmd in ("grep -n \"m4-floor\\|receipts\" %s" % RUNNER_REL,
                    "cat %s" % RUNNER_REL,
                    "sed -n 60,120p %s" % RUNNER_REL,
                    "head -40 %s" % RUNNER_REL,
                    "ls -la %s" % RUNNER_REL,
                    "python3 -m py_compile %s" % RUNNER_REL,
                    "echo skipping %s" % RUNNER_REL):
            line = "  ┊ 💻 $         %s  0.1s [exit 1]\n" % cmd
            self.assertEqual(matching_terminal_lines(line, "run-m4-pre-verdict.sh"), [], cmd)
            self.assertNotIn("run-m4-pre-verdict.sh", run_executables(cmd))

    def test_quoted_operator_does_not_split_a_read(self):
        # the ``\|`` inside the grep pattern is not a pipe: one command, not a run
        self.assertEqual(run_executables("grep -n \"a\\|b\" %s" % RUNNER_REL), ["grep"])

    def test_bash_c_is_looked_through(self):
        self.assertIn("run-m4-pre-verdict.sh", run_executables("bash -c 'cd /projects/modernized && bash %s .'" % RUNNER_REL))
        self.assertNotIn("run-m4-pre-verdict.sh", run_executables("bash -c 'grep -c x %s'" % RUNNER_REL))


class TestM1Green(unittest.TestCase):
    def test_m1_green_passes(self):
        doc = load_steps(M1 / "steps.json")
        root = M1 / "fixtures" / "green-m1"
        with patch.dict(os.environ, {"HERMES_BIN": str(M1 / "fixtures" / "fake-hermes"),
                                     "FAKE_ATTACHMENT_STORE": str(M1 / "fixtures" / "native-attachments")}):
            self.assertEqual(evaluate_audit((root / "official.log").read_text(encoding="utf-8"), doc, root,
                                            load_exec_ledger(root / "official.log")), 0)


class TestHandoffReviewAudit(unittest.TestCase):
    """v24 WP1: the reviewer's audit compares the current structured handoff
    with the facts recomputed from the sealed artifacts before it can be green
    (review of 2c2264e1 F1/F2). The implementer's self-audit skips it."""

    def _audit(self, phase: str, show: dict | None = None, profile: str = "reviewer") -> tuple[int, str]:
        root = (M1 / "fixtures" / "green-m1") if phase == "m1" else (M2 / "fixtures" / "green-m2")
        doc = load_steps((M1 if phase == "m1" else M2) / "steps.json")
        text = (root / "official.log").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as td:
            show_dir = None
            if show is not None:
                show_dir = Path(td)
                (show_dir / ("t_%s.json" % phase)).write_text(json.dumps(show))
            env = dict(native_env(phase, show_dir), HERMES_PROFILE=profile)
            if phase == "m1":
                env["FAKE_ATTACHMENT_STORE"] = str(M1 / "fixtures" / "native-attachments")
            buf = io.StringIO()
            with patch.dict(os.environ, env), redirect_stderr(buf):
                rc = evaluate_audit(text, doc, root, load_exec_ledger(root / "official.log"))
        return rc, buf.getvalue()

    def _show(self, phase: str) -> dict:
        return json.loads(((M1 if phase == "m1" else M2) / "fixtures" / "native" / ("t_%s.json" % phase)).read_text())

    def test_accurate_handoffs_pass(self):
        for phase in ("m1", "m2"):
            rc, msg = self._audit(phase)
            self.assertEqual(rc, 0, "%s: %s" % (phase, msg))

    def test_truthful_zero_non_http_narrative_is_not_refused(self):
        show = self._show("m1")
        self.assertIn("0 non-HTTP; no operator observations", show["runs"][0]["summary"])
        self.assertEqual(self._audit("m1", show)[0], 0)

    def test_missing_facts_refuse_even_after_the_producer_ran(self):
        # the handoff_facts.py --write step ran (exit 0, KEEP present); the handoff carries no facts
        show = self._show("m2")
        show["runs"][0]["metadata"] = {"created_cards": ["t_a"], "summary": "Plan published."}
        rc, msg = self._audit("m2", show)
        self.assertEqual(rc, 1)
        self.assertIn("metadata.facts is missing", msg)

    def test_wrong_unresolved_ids_refuse(self):
        for ids, why in ((["unrelated-id"], "names 1 id(s) the plan does not"), ([], "omits 1 plan id"),
                         (["unresolved:verification:http:acme.Api"] * 2, "repeats")):
            show = self._show("m2")
            show["runs"][0]["metadata"]["unresolved"] = ids
            rc, msg = self._audit("m2", show)
            self.assertEqual(rc, 1, ids)
            self.assertIn(why, msg)

    def test_wrong_count_refuses(self):
        show = self._show("m2")
        show["runs"][0]["metadata"]["facts"]["cards"]["repair"] = 2
        rc, msg = self._audit("m2", show)
        self.assertEqual(rc, 1)
        self.assertIn("metadata.facts.cards differs", msg)

    def test_earlier_passing_run_does_not_cover_the_current_run(self):
        show = self._show("m2")
        good = show["runs"][0]
        show["runs"] = [good, {"id": 8, "profile": "reviewer", "outcome": "changes_requested"},
                        dict(good, id=9, metadata={"created_cards": ["t_a"]}),
                        {"id": 10, "profile": "reviewer", "outcome": None}]
        rc, msg = self._audit("m2", show)
        self.assertEqual(rc, 1)
        self.assertIn("run 9", msg)
        # and the old facts bound to run 7 do not pass for run 9 either
        show["runs"][2]["metadata"] = good["metadata"]
        rc, msg = self._audit("m2", show)
        self.assertEqual(rc, 1)
        self.assertIn("metadata.facts.binding differs", msg)

    def test_implementer_self_audit_needs_no_review_request(self):
        show = self._show("m2")
        show["runs"] = [{"id": 7, "profile": "implementer", "outcome": None}]
        self.assertEqual(self._audit("m2", show, profile="implementer")[0], 0)
        self.assertEqual(self._audit("m2", show, profile="reviewer")[0], 1)

    def test_attachments_still_refuse_when_missing(self):
        # the native attachment proof is kept (1bc989c0): an empty store refuses before any handoff check
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "t_m1").mkdir()
            env = dict(native_env("m1"), HERMES_PROFILE="reviewer", FAKE_ATTACHMENT_STORE=td)
            root = M1 / "fixtures" / "green-m1"
            buf = io.StringIO()
            with patch.dict(os.environ, env), redirect_stderr(buf):
                rc = evaluate_audit((root / "official.log").read_text(encoding="utf-8"), load_steps(M1 / "steps.json"),
                                    root, load_exec_ledger(root / "official.log"))
            self.assertEqual(rc, 1)
            self.assertIn("NATIVE_ATTACHMENTS", buf.getvalue())


class TestNativeAttachments(unittest.TestCase):
    """v23 M1 t_56d38285: six names in completion metadata, an empty native
    listing, a green audit. The audit now reads the native records."""

    ROOT = M1 / "fixtures" / "green-m1"
    STORE = M1 / "fixtures" / "native-attachments" / "t_m1"

    def _records(self, store: Path) -> list[dict]:
        return [{"id": i + 1, "filename": f.name, "size": f.stat().st_size, "stored_path": str(f)}
                for i, f in enumerate(sorted(store.iterdir()))]

    def _audit(self, records: list[dict]) -> tuple[int, str]:
        doc = load_steps(M1 / "steps.json")
        text = (self.ROOT / "official.log").read_text(encoding="utf-8")
        seen: list[list[str]] = []
        real_run = subprocess.run

        def fake(argv, *a, **k):
            if argv[:1] != ["hermes"]:
                return real_run(argv, *a, **k)  # git (run control) is real; only the kanban CLI is faked
            seen.append(list(argv))
            if argv[1:3] == ["kanban", "attachments"]:
                return subprocess.CompletedProcess(argv, 0, json.dumps(records), "")
            raise AssertionError("unexpected call %s" % argv)

        buf = io.StringIO()
        with patch("paved_road.subprocess.run", side_effect=fake), redirect_stderr(buf):
            rc = evaluate_audit(text, doc, self.ROOT, load_exec_ledger(self.ROOT / "official.log"))
        self.assertIn(["hermes", "kanban", "attachments", "t_m1", "--json"], seen)
        return rc, buf.getvalue()

    def test_valid_set_passes(self):
        self.assertEqual(self._audit(self._records(self.STORE))[0], 0)

    def test_no_native_record_refuses(self):
        rc, msg = self._audit([])
        self.assertEqual(rc, 1)
        self.assertIn("NATIVE_ATTACHMENTS", msg)
        self.assertIn("6 of 6", msg)

    def test_missing_one_refuses_naming_it(self):
        rc, msg = self._audit([r for r in self._records(self.STORE) if r["filename"] != "mta-findings.json"])
        self.assertEqual(rc, 1)
        self.assertIn("evidence/mta-findings.json: missing", msg)
        self.assertIn("1 of 6", msg)

    def test_incomplete_record_refuses(self):
        with tempfile.TemporaryDirectory() as td:
            store = Path(td)
            for f in self.STORE.iterdir():
                (store / f.name).write_bytes(f.read_bytes())
            short = store / "type-inventory.json"
            short.write_bytes(short.read_bytes()[:-1])
            rc, msg = self._audit(self._records(store))
            self.assertEqual(rc, 1)
            self.assertIn("evidence/type-inventory.json: incomplete", msg)
            # same size, different bytes: a record must hold the workspace evidence, not a name
            short.write_bytes(b"x" * (self.ROOT / "evidence/type-inventory.json").stat().st_size)
            rc, msg = self._audit(self._records(store))
            self.assertEqual(rc, 1)
            self.assertIn("stored bytes differ", msg)
            # a record whose stored file is gone
            recs = self._records(store)
            short.unlink()
            rc, msg = self._audit(recs)
            self.assertEqual(rc, 1)
            self.assertIn("stored file", msg)

    def test_metadata_names_are_not_records(self):
        # the completion metadata's names, without native records, are a claim
        rc, msg = self._audit([{"filename": Path(k).name} for k in
                               next(s for s in load_steps(M1 / "steps.json")["steps"] if s["id"] == "kanban-attach")["keep"]])
        self.assertEqual(rc, 1)
        self.assertIn("incomplete", msg)

    def test_step_field_is_validated(self):
        doc = load_steps(M1 / "steps.json")
        bad = json.loads(json.dumps(doc))
        next(s for s in bad["steps"] if s["backing"] == "skill")["native_attachments"] = True
        self.assertTrue(any("native_attachments" in e for e in validate_steps_doc(bad, path=Path("x"))))
        self.assertTrue(next(s for s in doc["steps"] if s["id"] == "kanban-attach").get("native_attachments"))


class PreloadedSkill(unittest.TestCase):
    """v24 (architect review 2026-09-29): three accepted outcomes were sent back because a retry run did not
    repeat skill_view fix-until-green. The dispatcher now preloads the task skills on every run and the K2 hook
    records that preload per run; the audit accepts it only for the LATEST implementer run, only for the
    SKILL.md that is on disk now."""
    FX = Path(__file__).resolve().parent.parent / "skills" / "paved-road" / "paved-road-m3" / "fixtures" / "no-skill-view"

    def _grade(self, preload, *, runs=("7",), edit_skill=False):
        import hashlib
        import shutil
        import tempfile
        from paved_road import evaluate_audit, load_exec_ledger, load_steps
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "fx"
            shutil.copytree(self.FX, root)
            md = root / ".hermes" / "skills" / "migration" / "fix-until-green" / "SKILL.md"
            md.parent.mkdir(parents=True)
            md.write_text("# fix-until-green\nthe loop procedure\n", encoding="utf-8")
            sha = hashlib.sha256(md.read_bytes()).hexdigest()
            if edit_skill:
                md.write_text("# fix-until-green\nchanged since the run\n", encoding="utf-8")
            text = (root / "official.log").read_text(encoding="utf-8")
            ledger = list(load_exec_ledger(root / "official.log") or [])
            for r in runs:
                ledger.append({"phase": "start", "task": "t_noskill", "run": r, "profile": "implementer", "command": "ls",
                               "tool_call_id": "c" + r})
            if preload is not None:
                row = {"phase": "preload", "task": "t_noskill", "profile": "implementer", "skill_sha256": {"fix-until-green": sha}}
                row.update(preload)
                ledger.append(row)
            steps = self.FX.parents[1] / "steps.json"
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
                rc = evaluate_audit(text, load_steps(steps), root, ledger)
            return rc, err.getvalue()

    def test_without_a_preload_the_missing_skill_view_still_refuses(self):
        rc, err = self._grade(None)
        self.assertEqual(rc, 1)
        self.assertIn("fix-until-green", err)

    def test_the_latest_runs_preload_of_the_current_skill_satisfies_the_step(self):
        rc, err = self._grade({"run": "7", "skills": ["paved-road-m3", "fix-until-green"]})
        self.assertEqual((rc, err), (0, ""))            # the fixture's only failure was the missing skill_view

    def test_an_older_runs_preload_does_not(self):
        rc, err = self._grade({"run": "6", "skills": ["fix-until-green"]}, runs=("6", "7"))
        self.assertIn("mandated skill_view absent for fix-until-green", err)

    def test_a_preload_of_another_text_does_not(self):
        rc, err = self._grade({"run": "7", "skills": ["fix-until-green"]}, edit_skill=True)
        self.assertIn("mandated skill_view absent for fix-until-green", err)

    def test_a_preload_without_the_skill_does_not(self):
        rc, err = self._grade({"run": "7", "skills": ["paved-road-m3"]})
        self.assertIn("mandated skill_view absent for fix-until-green", err)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
