#!/usr/bin/env python3
"""run-report selftest: every field comes from a recorded file or is null with a reason.

The destination is a real planner fixture (planner.specimens: bundle, git
baseline, bootstrap, simulated verification, baseline step, admission), with
a hand-written run laid over it: accepted steps with runtime gates and verify
records, attempt rows, operator steps, rewinds, dispositions, an M4 close row,
parity receipts, runs and scenario records in two security modes, a corpus and
capture receipts, release blockers, a generated-test manifest with surefire
XML, harness install manifests in both formats, a unit seal, K4 mint receipts,
a bootstrap transformation receipt, a board export, worker logs, a copy of the
live Hermes configuration and a declared budget.

Covered: each report section; the clock that starts before bootstrap; first
PASSING parity/M4 apart from first composition/verdict ("unreached" only when
the records are there); the four classifications, prior assistance never
reported as zero without a bootstrap receipt; a bare directory (every value
null with a reason, nothing guessed, nothing "unreached"); real `git log`
versus --git-log; secrets never copied from the configuration; the comparison
on the common unchanged contract subset; and a renamed specimen (another base
package, other card and cluster ids) producing the same shape and counts.
"""
from __future__ import annotations

import ast
import datetime
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "run-report.py"
GOLDEN = HERE.parents[4]
sys.path.insert(0, str(GOLDEN / ".hermes" / "lib"))

from planner import specimens  # noqa: E402
from planner.canonical import load_json  # noqa: E402

# Most cases drive the script as a subprocess over a built tree. compare() is a
# pure function over two finished reports, so it is exercised directly.
_spec = importlib.util.spec_from_file_location("run_report_module", SCRIPT)
rr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rr)

T0 = 1_800_000_000  # the bootstrap baseline commit time in the fixture history
START = T0 - 1000   # the destination's first commit: the clock start


def ISO(epoch: int) -> str:
    return datetime.datetime.fromtimestamp(epoch, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _w(root: Path, rel: str, doc) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=1), encoding="utf-8")


def _run(root: Path, *extra: str) -> tuple:
    out = root.parent / ("%s-report.json" % root.name)
    proc = subprocess.run([sys.executable, str(SCRIPT), "--root", str(root), "--out", str(out), *extra], text=True, capture_output=True)
    rep = json.loads(out.read_text(encoding="utf-8")) if out.is_file() else None
    return proc, rep, out


def _measure(t):
    return {"known": True, "tuple": list(t), "compile_errors": t[1], "mandatory_incidents": t[0], "failing_tests": t[2], "parity_mismatches": None, "blocked": []}


def _rt(pkg=None, boot=None):
    return {"package": {"ran": pkg is not None, "rc": pkg}, "boot": {"ran": boot is not None, "rc": 0 if boot else (1 if boot is False else None), "ready": bool(boot)},
            "ready": bool(boot), "blockers": [], "reasons": []}


def _verify(total_ms, warmup_ms):
    return {"mode": "acceptance", "total_ms": total_ms, "stages_ms": {"warmup": warmup_ms, "rescan": total_ms - warmup_ms}}


class Ids:
    """Card, cluster and commit identities, so a renamed specimen can use others."""

    def __init__(self, tag: str) -> None:
        self.tag = tag
        self.c = ["c:%s%010d" % (tag, i) for i in range(6)]
        self.t = ["t_%s%06d" % (tag, i) for i in range(12)]
        self.sha = ["%s%039d" % (tag[0], i) for i in range(21)]


def history(root: Path, ids: Ids, *, operator_steps, rewinds, dispositions):
    """Lay the loop record over the prepared destination; return git-log lines."""
    base = dict(load_json(root / "verification/loop/steps.json")["steps"][0], commit=ids.sha[0])
    c, t, s = ids.c, ids.t, ids.sha
    steps = [base,
             {"verdict": "accepted", "cluster": c[0], "card": t[0], "attempt": 1, "commit": s[1], "measure": _measure((1, 5, 0)), "runtime": _rt(), "gate": "",
              "amendments": [{"path": "src/main/java/X.java", "reason": "needs a field"}], "revisions": [], "changed": ["src/main/java/X.java", "pom.xml"],
              "verify": _verify(80000, 12000)},
             {"verdict": "accepted", "cluster": c[1], "card": t[2], "attempt": 2, "commit": s[3], "measure": _measure((0, 0, 0)), "runtime": _rt(pkg=1), "gate": "",
              "amendments": [], "revisions": [{"n": 1, "path": "src/main/java/Y.java", "evidence": "javac:diag:1"}], "unit": {"unit_id": "u1", "rule": "unit/diagnostic-family/v1"},
              "changed": ["src/main/java/Y.java"], "verify": _verify(20000, 10)},
             {"verdict": "accepted", "cluster": c[2], "card": t[3], "attempt": 1, "commit": s[4], "measure": _measure((0, 0, 0)), "runtime": _rt(pkg=0, boot=False), "gate": "package"},
             {"verdict": "accepted", "cluster": c[2], "card": t[4], "attempt": 1, "commit": s[6], "measure": _measure((0, 0, 0)), "runtime": _rt(pkg=0, boot=True), "gate": "boot"}]
    lines = ["%s %d initial commit" % (s[20], START),
             "%s %d fix-until-green: baseline [1, 9, 0]" % (s[0], T0),
             "%s %d fix-until-green: %s attempt 1 [1, 5, 0]" % (s[1], T0 + 600, c[0]),
             "%s %d fix-until-green: %s attempt 2 [0, 0, 0]" % (s[3], T0 + 3600, c[1]),
             "%s %d fix-until-green: %s attempt 1 [0, 0, 0]" % (s[4], T0 + 7200, c[2]),
             "%s %d fix-until-green: %s attempt 1 [0, 0, 0]" % (s[6], T0 + 10800, c[2]),
             "%s %d harness: install golden abcdef12 (project 1234abcd) over 99990000" % (s[7], T0 + 5000),
             "%s %d harness: install the catalogue of golden abcdef12" % (s[8], T0 + 5100),
             "%s %d m4: generated product tests (corpus x, generator 1.0)" % (s[9], T0 + 12000)]
    for n, op in enumerate(operator_steps):
        at = T0 + 4000 + n
        steps.insert(3, dict({"verdict": "operator", "cluster": "operator", "card": "", "attempt": 0, "commit": s[10 + n], "at": ISO(at),
                              "operator": "operator:x", "author": "author-seat", "measure": _measure((0, 0, 0)), "changed": ["pom.xml"],
                              "reason": "Apply the ruling. Second sentence."}, **op))
        lines.append("%s %d fix-until-green: operator step by operator:x (%s): Apply the ruling." % (s[10 + n], at, op.get("adr", "")))
    rejected = [
        {"cluster": c[1], "card": t[1], "measure": _measure((0, 3, 0)), "changed": ["a"], "budget": {"spent": 1}, "reason": "measure did not decrease", "rewound": True},
        {"cluster": c[3], "card": t[5], "measure": None, "changed": [], "rewound": True, "reason": "closed by operator operator:x without a verdict: stale card"},
        {"kind": "close", "cluster": "M4_VERIFY", "card": t[6], "verdict": "REFUSE", "at": ISO(T0 + 13000), "failed_floors": ["floor-a"], "operator": "operator:x",
         "resumed": True, "measure": None, "changed": [], "contract_reseal": {"changed": [".hermes/planning/schemas/x.json"]}},
        {"cluster": c[4], "card": t[7], "measure": _measure((0, 0, 0)), "changed": ["b"], "budget": {"spent": 1}, "reason": "measure did not decrease", "verify": _verify(5000, 10)},
        {"cluster": c[4], "card": t[8], "measure": _measure((0, 0, 0)), "changed": ["b"], "budget": {"spent": 2}, "reason": "measure did not decrease"},
    ]
    pending = [{"cluster": c[1], "card": t[1], "cause": "harness", "cleared": "accepted", "issued": {"cluster": c[1], "kind": "compile", "task_id": t[1], "amendments": [{"path": "p"}]}},
               {"cluster": c[5], "card": t[9], "cause": "unproven-repair", "issued": {"cluster": c[5], "kind": "boot", "task_id": t[9]},
                "run_mode": "acceptance", "total_ms": 1000, "stages_ms": {"warmup": 20}}]
    _w(root, "verification/loop/steps.json", {"schema": "rhoai3.loop-steps/v1", "steps": steps, "rejected": rejected, "pending": pending, "attempts": {c[4]: 2},
                                              "rewinds": rewinds, "deferral_clearances": dispositions})
    _w(root, "verification/loop/deferred.json", {"schema": "rhoai3.loop-deferred/v1", "clusters": [c[4]], "reasons": {c[4]: "2 of 2"}})
    _w(root, "verification/loop/state.json", {"schema": "rhoai3.loop-state/v1", "measure": dict(_measure((0, 0, 0)), parity_mismatches=2), "head": c[4], "open_clusters": 1, "deferred": [c[4]]})
    return lines


def bundle_eps(root: Path) -> list:
    ids = [str(e["id"]) for e in load_json(root / "evidence/planning/evidence-bundle.json")["entry_points"]]
    return (ids + ["ep:padding#p%d():http" % i for i in range(4)])[:4]


def evidence(root: Path, ids: Ids, *, transformations=True, m4_verdict="REFUSE") -> None:
    """Receipts, verdicts, manifests, seals: the files the report reads besides the loop record."""
    ep = bundle_eps(root)
    _w(root, "verification/scenarios/corpus.json", {"schema": "rhoai3.scenario-corpus/v1", "approved_by": "operator:x", "scenarios": [
        {"id": "sc:x", "entry_point": ep[0], "method": "GET", "path": "/x"},
        {"id": "sc:y", "entry_point": ep[1], "method": "GET", "path": "/y"}]})
    corpus_sha = "c" * 64
    _w(root, "verification/source-oracles/scenarios/_capture.json", {"security_mode": "disabled", "corpus_sha256": corpus_sha, "at": ISO(START + 10)})
    _w(root, "verification/source-oracles/scenarios-enabled/_capture.json", {"security_mode": "enabled", "corpus_sha256": corpus_sha})
    _w(root, "verification/parity/receipt.json", {"schema": "rhoai3.parity-receipt/v1", "verdict": "FAIL", "security_mode": "disabled", "total": 4,
                                                  "producer": "compose-parity-receipt.py", "corpus_sha256": corpus_sha,
                                                  "binding": {"mode": "sealed"}, "coverage_gaps": [{"scenario": "sc:x"}],
                                                  "entry_points": [{"entry_point": ep[0], "verdict": "PASS", "reason": ""},
                                                                   {"entry_point": ep[1], "verdict": "FAIL", "reason": "status 403 vs 200; body a vs b"},
                                                                   {"entry_point": ep[2], "verdict": "INCONCLUSIVE", "reason": "no parity record"},
                                                                   {"entry_point": ep[3], "verdict": "SKIPPED", "reason": ""}]})
    _w(root, "verification/parity/_run.json", {"schema": "rhoai3.parity-run/v1", "at": ISO(T0 + 11000), "ok": True, "receipt_verdict": "FAIL",
                                               "scenario_filter": [], "binding": {"mode": "sealed"}, "security_mode": "disabled", "failures": [],
                                               "reset_cmd": "bash reset-parity-db.sh", "producer": "run-parity.py", "corpus_sha256": corpus_sha,
                                               "scenarios": {"declared": 3, "selected": 3, "run": 3, "passed": 1, "failed": 1, "inconclusive": 1},
                                               "entry_points": {"admitted": 4, "compared": 3, "passed": 1, "failed": 1, "inconclusive": 1, "skipped": 1}})
    _w(root, "verification/parity/scenarios/sc_x.json", {"schema": "rhoai3.scenario-parity/v1", "scenario": "sc:x", "verdict": "PASS"})
    _w(root, "verification/parity/scenarios/sc_y.json", {"schema": "rhoai3.scenario-parity/v1", "scenario": "sc:y", "verdict": "FAIL"})
    _w(root, "verification/parity/scenarios/y.json", {"schema": "rhoai3.scenario-parity/v1", "scenario": "y", "verdict": "INCONCLUSIVE"})
    _w(root, "verification/parity/receipt-enabled.json", {"schema": "rhoai3.parity-receipt/v1", "verdict": "PASS", "security_mode": "enabled", "total": 1,
                                                          "entry_points": [{"entry_point": ep[0], "verdict": "PASS", "reason": ""}]})
    _w(root, "verification/parity/_run-enabled.json", {"at": ISO(T0 + 11500), "ok": True, "receipt_verdict": "PASS", "scenario_filter": ["sc:only"], "security_mode": "enabled"})
    _w(root, "evidence/verdicts/m4-verdict.json", {"card_id": ids.t[10], "verdict": m4_verdict, "ship": False, "failed_floors": ["floor-b"] if m4_verdict == "REFUSE" else [],
                                                   "floors": [{"name": "floor-b", "rc": 1 if m4_verdict == "REFUSE" else 0}], "coverage_account": {"retired": 3, "remaining_gaps": 1}})
    _w(root, "verification/loop/release-blockers.json", {"schema": "rhoai3.release-blockers/v1", "verdict": "REFUSE", "verdict_card": ids.t[6], "at": ISO(T0 + 13000),
                                                         "owners": ["ADR-003"], "floors": [{"floor": "floor-a", "adr": "ADR-003", "owner": "Operator step", "explained_by": 1}],
                                                         "entry_points": [{"entry_point": ep[1], "verdict": "FAIL", "adr": "ADR-003", "owner": "Operator step", "reason": "status 403 vs 200"}],
                                                         "withheld_obligations": ["parity:1"], "parity_obligations": ["parity:2", "parity:3"]})
    _w(root, "evidence/verdicts/coverage-account.json", {"summary": {"retired": 3, "replaced": 2, "remaining_gaps": 1, "uncovered_capabilities": 1},
                                                         "uncovered_capabilities": [{"scenario": "sc:x", "kind": "fixture-failed", "reason": "fixture failed. more"}],
                                                         "parity_receipt_verdict": "FAIL"})
    gen_class = "%s.generated.ApiParityTest" % ids.tag
    _w(root, "evidence/tests/generated-manifest.json", {"generator": "generate-product-tests.py", "generator_version": "1.2.0", "corpus_sha256": corpus_sha,
                                                        "cases": [{"class": gen_class, "method": "m%d" % i} for i in range(3)],
                                                        "files": [{"path": "src/parity-test/java/X.java"}], "gaps": [{"scenario": "sc:x", "kind": "unqualified", "reason": "after effect"}]})
    rep = root / "target" / "surefire-reports"
    rep.mkdir(parents=True, exist_ok=True)
    (rep / ("TEST-%s.xml" % gen_class)).write_text(
        '<testsuite name="%s" tests="3"><testcase classname="%s" name="m0"/><testcase classname="%s" name="m1"><failure message="x"/></testcase>'
        '<testcase classname="%s" name="m2"><skipped/></testcase></testsuite>' % (gen_class, gen_class, gen_class, gen_class), encoding="utf-8")
    (rep / "TEST-other.RetainedTests.xml").write_text('<testsuite><testcase classname="other.RetainedTests" name="v"/></testsuite>', encoding="utf-8")
    compact = lambda e: ISO(e).replace("-", "").replace(":", "")  # noqa: E731
    _w(root, "evidence/harness/install-manifest-abcdef12.json", {"schema": "rhoai3.harness-install/v1", "golden": "abcdef12" + "0" * 32, "previous_golden": "99990000" + "0" * 32,
                                                                 "project_commit": "1234abcd", "installed_at": compact(T0 + 4990)})
    _w(root, "evidence/harness/install-manifest-00001111.json", {"golden_sha": "00001111" + "0" * 32, "prev_sha": "ffff" * 10, "project": "5678ef00", "generated_at": ISO(START - 5000)})
    _w(root, "evidence/planning/batch-scope/u-1/%s.json" % ("d" * 32), {"schema": "rhoai3.batch-scope/v4", "kind": "unit", "cluster": "u:1", "unit_id": "u1",
                                                                        "rule": "unit/diagnostic-family/v1", "writable_paths": ["a", "b"], "symbols": [{}],
                                                                        "bounds": {"files": 2, "sites": 7, "symbols": 1, "max_files": 20}})
    _w(root, "evidence/planning/batch-scope/c-2/%s.json" % ("e" * 32), {"schema": "rhoai3.batch-scope/v3", "cluster": "c:2"})
    _w(root, "evidence/receipts/k4/mints.json", {"schema": "rhoai3.k4-mint-receipts/v1", "mints": [
        {"created": [{"task_id": t, "logical_id": "x", "idempotency_key": "k"}]} for t in ids.t[:11]]})
    specimens.runtime(root, package_rc=0, boot_ready=True)
    if transformations:
        _w(root, "evidence/producers/decided-repairs.json", {
            "schema": "rhoai3.decided-repairs-receipt/v1", "status": "ok", "decision": {"manifest_sha256": "m" * 64},
            "rows": [{"id": "port-retained-test", "adr": "ADR-003", "status": "applied", "files": ["src/test/java/a/RetainedTest.java"],
                      "implementation_version": "1.0.0"},
                     {"id": "adapter", "adr": "ADR-003", "status": "already-applied"},
                     {"id": "retire-check", "adr": "ADR-002", "status": "refused", "refusal": {"class": "MISMATCH", "detail": "unexpected configuration"}}],
            "inventory": [{"id": "port-retained-test", "path": "src/test/java/a/RetainedTest.java", "symbol": "a.RetainedTest#validate"},
                          {"transformation": "adapter", "path": "src/main/java/a/Adapter.java", "symbol": "a.Adapter"}]})
        bs = load_json(root / "evidence/producers/bootstrap.json")
        bs["decided_repairs"] = {"receipt_sha256": specimens.stable_hash(root / "evidence/producers/decided-repairs.json")}
        _w(root, "evidence/producers/bootstrap.json", bs)


def board(dirp: Path, ids: Ids) -> tuple:
    def k1(cluster, kind):
        return "## card\n\n```json\n%s\n```\n" % json.dumps({"increment_id": cluster, "increment_kind": kind, "attempt": 1})
    rows = [{"id": "t_m1", "title": "M1 ANALYZE", "status": "done", "created_at": T0 - 900, "started_at": T0 - 800, "completed_at": T0 - 400, "body": "no k1"},
            {"id": ids.t[0], "title": "M3 compile A", "status": "done", "created_at": T0, "started_at": T0 + 10, "completed_at": T0 + 310, "body": k1(ids.c[0], "compile")},
            {"id": ids.t[2], "title": "M3 compile B", "status": "done", "created_at": T0, "started_at": T0 + 10, "completed_at": T0 + 110, "body": k1(ids.c[1], "compile")},
            {"id": ids.t[3], "title": "M3 compile C", "status": "done", "created_at": T0, "started_at": T0 + 10, "completed_at": T0 + 210, "body": k1(ids.c[2], "compile")},
            {"id": ids.t[4], "title": "M3 boot C", "status": "done", "created_at": T0, "started_at": T0 + 10, "completed_at": T0 + 20, "body": k1(ids.c[2], "boot"),
             "model_override": "other-model"},
            {"id": ids.t[10], "title": "M4 VERIFY", "status": "blocked", "created_at": T0 + 13500, "started_at": T0 + 13600, "completed_at": T0 + 14000,
             "body": k1("M4_VERIFY", "close"), "result": "composed REFUSE"},
            {"id": "t_orphan", "title": "M4 VERIFY", "status": "done", "created_at": T0 + 9000, "started_at": None, "completed_at": T0 + 9500, "body": "", "result": "closed by rewind"}]
    kj = dirp / "kanban.json"
    kj.write_text(json.dumps(rows), encoding="utf-8")
    logs = dirp / "logs"
    logs.mkdir()
    (logs / ("%s.log" % ids.t[0])).write_text("Query: work kanban task\n  ┊ 💻 $ python3 advance.py  7.4s [exit 1]\nREFUSE: LOOP_WRONG_CARD\n  ┊ ⚡ kanban_block   0.0s\n", encoding="utf-8")
    (logs / ("%s.log" % ids.t[2])).write_text("Query: work kanban task\n  ┊ ⚡ kanban_complete   0.5s\n", encoding="utf-8")
    (logs / "t_m1.log").write_text("Query: work kanban task\nprotocol_violation\nQuery: work kanban task\n", encoding="utf-8")
    cfg = dirp / "hermes-config.json"
    cfg.write_text(json.dumps({"model": {"provider": "custom", "default": "some-model"},
                               "providers": {"custom": {"api_key": "SECRET-VALUE", "stale_timeout_seconds": 600, "context_length": 98304}},
                               "kanban": {"max_in_progress": 1}}), encoding="utf-8")
    bud = dirp / "budget.json"
    bud.write_text(json.dumps({"declared_at": ISO(START - 60), "max_wall_hours": 12, "stop_when": ["a cluster defers", "M4 verdict composed"]}), encoding="utf-8")
    return kj, logs, cfg, bud


PREPARED: dict = {}


def prepared(name: str, base: str) -> Path:
    """One planner-prepared destination per specimen, copied per test."""
    key = (name, base)
    if key not in PREPARED:
        td = Path(tempfile.mkdtemp(prefix="run-report-base-"))
        root = specimens.build_dest(td / "dest", specimens.specimen(name, base=base), decisions=specimens.admitted_decisions())
        specimens.prepare_loop(root)
        PREPARED[key] = root
    td = Path(tempfile.mkdtemp(prefix="run-report-"))
    dest = td / "dest"
    shutil.copytree(PREPARED[key], dest, symlinks=True)
    return dest


ACCEPTED_OP = {"adr": "ADR-003", "reviewer": "architect"}


class Fixture:
    def __init__(self, ids: Ids, base: str = "org.acme.clinic", *, ops=None, rewinds=None, dispositions=None, **ev) -> None:
        root = prepared("http", base)
        ops = [dict(ACCEPTED_OP, beside_pending={"card": ids.t[2], "cluster": ids.c[1]})] if ops is None else ops
        rewinds = [{"at": ISO(T0 + 9000), "operator": "operator:x", "closed_cards": [ids.t[5]], "moved_steps": [], "to_step": 2,
                    "to_commit": ids.sha[3], "reason": "Close the stale card. Then re-admit."}] if rewinds is None else rewinds
        dispositions = [{"at": ISO(T0 + 9100), "cluster": ids.c[1], "kind": "metadata-only", "operator": "operator:x", "attempts": 3, "cards": [ids.t[1]],
                         "commit": "", "reason": "Harness defect, since corrected.", "was_deferred_because": "3 of 3 attempt(s) spent"}] if dispositions is None else dispositions
        lines = history(root, ids, operator_steps=ops, rewinds=rewinds, dispositions=dispositions)
        evidence(root, ids, **ev)
        self.root = root
        self.git_log = root.parent / "git-log.txt"
        self.git_log.write_text("\n".join(sorted(lines, key=lambda l: -int(l.split()[1]))) + "\n", encoding="utf-8")
        self.kanban, self.logs, self.config, self.budget = board(root.parent, ids)

    def all_inputs(self) -> list:
        return ["--git-log", str(self.git_log), "--kanban-json", str(self.kanban), "--kanban-logs", str(self.logs),
                "--hermes-config", str(self.config), "--budget", str(self.budget)]


class RunReportTest(unittest.TestCase):
    maxDiff = None

    def test_full_fixture_every_section(self):
        ids = Ids("a")
        fx = Fixture(ids)
        root = fx.root
        proc, rep, _ = _run(root, *fx.all_inputs())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(rep["schema"], "rhoai3.run-report/v1")
        self.assertIn("# Run report", proc.stdout)
        self.assertNotIn("SECRET-VALUE", json.dumps(rep))                                    # a secret is never copied
        p = rep["pinned_inputs"]
        freeze = load_json(root / "evidence/producers/freeze.json")["source_digest"]
        self.assertEqual((p["frozen_source_digest"]["value"], p["frozen_source_digest"]["source"]), (freeze, "evidence/producers/freeze.json"))
        self.assertIn("evidence/frozen/source-manifest.json", p["frozen_source_digest"]["agrees"])
        adm = load_json(root / "evidence/planning/admission-receipt.json")
        self.assertEqual(p["bundle_digest"]["value"], adm["seals"]["evidence_bundle"])
        self.assertTrue(p["bundle_digest"]["worklist_agrees"])
        self.assertEqual(p["decisions_digest"]["value"], specimens.stable_hash(root / "decisions.yaml"))
        self.assertTrue(p["decisions_digest"]["matches_admission_seal"])
        self.assertEqual((p["unit_formation"]["value"], p["runtime_feedback"]["value"]), ("off", "off"))
        self.assertIn("absent means off", p["unit_formation"]["note"])
        self.assertEqual(p["accepted_adrs"]["value"], ["ADR-001", "ADR-002", "ADR-003"])
        goldens = p["installed_goldens"]["value"]
        self.assertEqual([g["golden"][:8] for g in goldens], ["00001111", "abcdef12"])       # in install order
        self.assertEqual(goldens[1]["commit"], ids.sha[7])                                   # matched to its install commit
        self.assertEqual([g["before_start"] for g in goldens], [True, False])
        self.assertEqual(p["created_from_golden"]["value"], "ffff" * 10)
        self.assertEqual(p["project_commits"]["value"], ["5678ef00", "1234abcd"])

        env = rep["pinned_environment"]
        self.assertEqual(env["hermes_agent"]["value"]["version"], load_json(root / ".hermes/pins.json")["pins"]["hermes_agent"]["version"])
        self.assertIn("mta_cli", env["tool_pins"]["value"])
        self.assertEqual(env["model_provider"]["value"], {"hermes-config:hermes-config.json#model.provider": "custom",
                                                          "hermes-config:hermes-config.json#model.default": "some-model"})
        self.assertEqual(env["inference"]["value"], {"hermes-config:hermes-config.json#providers.custom.stale_timeout_seconds": 600,
                                                     "hermes-config:hermes-config.json#providers.custom.context_length": 98304})
        self.assertEqual(env["concurrency"]["value"], {"hermes-config:hermes-config.json#kanban.max_in_progress": 1})
        self.assertEqual(env["card_model_overrides"]["value"], ["-/other-model"])
        self.assertEqual(env["database"]["datasource"]["value"]["db_kind"], "postgresql")
        self.assertIn("src/main/resources/db/postgresql/initDB.sql", env["database"]["assets"]["value"])
        self.assertEqual(env["database"]["reset_cmd"]["value"], {"verification/parity/_run.json": "bash reset-parity-db.sh"})
        cc = env["corpus_and_captures"]
        self.assertEqual((cc["corpus"]["scenarios"], cc["corpus"]["distinct_digests"]), (2, ["c" * 64]))
        self.assertEqual(sorted(cc["captures"]["value"]), ["verification/source-oracles/scenarios", "verification/source-oracles/scenarios-enabled"])
        self.assertEqual(cc["captures"]["value"]["verification/source-oracles/scenarios-enabled"]["security_mode"], "enabled")
        comp = env["comparators"]
        self.assertIn(".hermes/skills/gates/capture-source-oracles/scripts/compose-parity-receipt.py", comp["value"])
        self.assertEqual(comp["producers"]["evidence/tests/generated-manifest.json"], "generate-product-tests.py 1.2.0")

        t = rep["timeline"]
        self.assertEqual((t["clock_start"]["value"], t["clock_start"]["from"]), (ISO(START), "destination_created"))
        comps = t["clock_start"]["components"]
        self.assertEqual(comps["m1_dispatched"]["at"], ISO(T0 - 900))
        self.assertEqual(comps["bootstrap_baseline"]["since_start"], "+0h16m")               # bootstrap is inside the clock
        self.assertEqual(t["baseline"]["value"], ISO(T0))
        self.assertEqual((t["first_accepted_step"]["value"], t["first_accepted_step"]["card"]), (ISO(T0 + 600), ids.t[0]))
        self.assertEqual((t["first_accepted_step"]["since_baseline"], t["first_accepted_step"]["since_start"]), ("+0h10m", "+0h26m"))
        self.assertEqual(t["first_zero_measure"]["card"], ids.t[2])
        self.assertEqual(t["first_package_pass"]["card"], ids.t[3])                          # rc 1 at t[2] is not a pass
        self.assertEqual(t["first_boot_pass"]["card"], ids.t[4])                             # ready False at t[3] is not a pass
        self.assertEqual(t["first_boot_pass"]["seconds_since_start"], 11800)
        self.assertEqual((t["first_full_parity"]["value"], t["first_full_parity"]["mode"]), (ISO(T0 + 11000), "disabled"))  # the enabled run is scoped
        self.assertEqual(t["first_full_parity"]["run_receipt_verdict"], "FAIL")
        self.assertIn("latest full run", t["first_full_parity"]["note"])
        fpp = t["first_passing_parity"]
        self.assertEqual(fpp["disabled"]["value"], "unreached")                             # composed, not passing
        self.assertIsNone(fpp["enabled"]["value"])                                          # passing receipt, but no composition time
        self.assertIn("no composition time", fpp["enabled"]["reason"])
        m4 = {v["card"]: v for v in t["m4_verdicts"]}
        self.assertEqual((m4[ids.t[6]]["verdict"], m4[ids.t[6]]["at"]), ("REFUSE", ISO(T0 + 13000)))
        self.assertEqual(m4[ids.t[10]]["at"], ISO(T0 + 14000))                              # board completion, said so
        self.assertTrue(m4[ids.t[10]]["time_source"].startswith("kanban-json"))
        self.assertIsNone(m4["t_orphan"]["verdict"])                                         # never parsed from prose
        self.assertEqual([v["card"] for v in t["m4_verdicts"]], ["t_orphan", ids.t[6], ids.t[10]])
        self.assertEqual(t["first_m4_verdict"]["card"], "t_orphan")
        self.assertEqual(t["first_passing_m4"]["value"], "unreached")
        self.assertEqual(t["m4_commits"][0]["commit"], ids.sha[9])
        self.assertEqual(t["last_event"]["value"], ISO(T0 + 14000))

        bs = rep["bootstrap_repairs"]
        dec = bs["decided"]
        self.assertEqual((dec["applied"], dec["refused"], dec["adrs"]), (2, 1, ["ADR-003"]))   # applied + already-applied
        self.assertEqual((dec["schema_ok"], dec["bound_by_bootstrap"], dec["inventory_rows"], dec["manifest_sha256"]), (True, True, 2, "m" * 64))
        rows = {r["id"]: r for r in dec["value"]}
        self.assertEqual((rows["port-retained-test"]["files"], rows["port-retained-test"]["symbols"], rows["port-retained-test"]["implementation_version"]),
                         (["src/test/java/a/RetainedTest.java"], ["a.RetainedTest#validate"], "1.0.0"))
        self.assertEqual((rows["adapter"]["files"], rows["adapter"]["symbols"]), (["src/main/java/a/Adapter.java"], ["a.Adapter"]))
        self.assertFalse(rows["retire-check"]["applied"])
        self.assertEqual(rows["retire-check"]["refusal"]["class"], "MISMATCH")
        self.assertIsNone(bs["decision"]["value"])                                          # this fixture's decisions.yaml decides none
        self.assertIn("import", bs["mechanical_changes"]["value"])

        w = rep["loop_work"]
        c = w["cards"]
        self.assertEqual((c["minted"]["value"], c["minted"]["source"]), (11, "evidence/receipts/k4/mints.json"))
        self.assertEqual((c["accepted"]["value"], c["reverted"]["value"], c["reverted_then_rewound"]["value"], c["m4_closed"]["value"]), (4, 3, 1, 1))
        self.assertEqual(c["closed_without_verdict"]["value"], [{"card": ids.t[5], "cluster": ids.c[3]}])
        self.assertEqual(c["pending"]["value"]["open"], [{"card": ids.t[9], "cluster": ids.c[5], "cause": "unproven-repair"}])
        self.assertEqual(c["pending"]["value"]["cleared"], {"accepted": 1})
        self.assertEqual(c["deferred"]["value"]["open"], [ids.c[4]])
        self.assertEqual(len(c["deferred"]["value"]["deferred_then_cleared"]), 1)
        self.assertIsNone(c["issued_now"]["value"])
        per = w["attempts_per_cluster"]["value"]
        self.assertEqual(per[ids.c[1]], {"accepted": 1, "reverted": 1, "max_attempt": 2, "cards": [ids.t[2], ids.t[1]]})
        self.assertEqual(per[ids.c[4]]["reverted"], 2)
        self.assertEqual(w["attempt_counters_now"]["value"], {ids.c[4]: 2})
        self.assertEqual(w["retries"]["value"], 1)                                           # 3 reverted − 2 deferrals
        self.assertEqual(w["scope_amendments"]["value"], 2)                                  # one accepted + one pending issued
        self.assertEqual(w["scope_revisions"]["value"], [{"card": ids.t[2], "path": "src/main/java/Y.java", "evidence": "javac:diag:1"}])
        self.assertEqual((w["unit_sizes"]["value"][0]["files"], w["unit_sizes"]["value"][0]["sites"]), (2, 7))
        self.assertEqual(w["batch_scopes"]["value"], {"rhoai3.batch-scope/v3": 1, "rhoai3.batch-scope/v4": 1})
        self.assertEqual(w["unit_steps_accepted"]["value"], 1)
        k = w["clusters_by_kind"]
        self.assertEqual(k["clusters"]["compile"], sorted(ids.c[:3]))
        self.assertEqual(k["clusters"]["boot"], sorted([ids.c[2], ids.c[5]]))
        self.assertEqual(k["clusters_with_several_kinds"], [ids.c[2]])                       # a re-issued id keeps both kinds
        self.assertEqual(k["cards_by_kind"], {"boot": 2, "close": 1, "compile": 4})           # board K1 + the pending issued card
        self.assertEqual(w["accepted_by_gate"]["value"], {"compile/incident/test (no gate)": 2, "package": 1, "boot": 1})

        i = rep["interventions"]
        op = i["operator_steps"][0]
        self.assertEqual((op["adr"], op["author"], op["reviewer"], op["applies_accepted_adr"]), (["ADR-003"], "author-seat", "architect", True))
        self.assertEqual((op["reason_head"], op["beside_pending"]["card"], op["seconds_since_start"]), ("Apply the ruling.", ids.t[2], 5000))
        self.assertEqual(i["rewinds"][0]["closed_cards"], [ids.t[5]])
        self.assertEqual(i["dispositions"][0]["kind"], "metadata-only")
        self.assertEqual(i["m4_resumes"]["value"][0]["contract_reseal"], [".hermes/planning/schemas/x.json"])
        self.assertEqual(i["repair_inventory"]["value"], {"worker_files": ["pom.xml", "src/main/java/X.java", "src/main/java/Y.java"],
                                                          "operator_files": ["pom.xml"], "both": ["pom.xml"]})
        h = rep["harness_changes"]
        self.assertEqual([x["golden"][:8] for x in h["prior_preparation"]], ["00001111"])
        self.assertEqual([x["golden"][:8] for x in h["installs_after_start"]], ["abcdef12"])
        self.assertEqual(h["other_harness_commits"]["value"][0]["commit"], ids.sha[8])

        cost = rep["cost"]
        v = cost["verifications"]["value"]
        self.assertEqual((v["count"], v["total_s"], v["by_mode"]), (4, 106, {"acceptance": 4}))
        self.assertEqual(cost["verifications"]["warmup_seconds"]["n"], 4)
        self.assertEqual(cost["cache"]["maven_config"], (root / ".mvn/maven.config").read_text().split() if (root / ".mvn/maven.config").is_file() else None)
        tt = cost["time"]
        self.assertEqual(tt["wall_seconds"]["value"], 15000)
        self.assertEqual(tt["card_run_seconds"]["value"], {"sum": 1410, "union": 1100, "cards": 6})
        self.assertEqual(tt["queue_seconds"]["value"], {"sum": 240, "cards": 6})
        self.assertEqual(tt["outside_card_runs_seconds"]["value"], 13900)
        self.assertEqual(tt["tool_seconds"]["value"], 7)
        self.assertIsNone(tt["provider_seconds"]["value"])
        self.assertEqual(tt["unattributed_in_card_runs_seconds"]["value"], 1402)
        self.assertEqual(tt["verification_seconds"]["value"], 106)

        f = rep["final_state"]
        self.assertEqual((f["measure"]["value"], f["measure"]["parity_mismatches"]), ([0, 0, 0], 2))
        self.assertEqual(f["admission"]["value"], adm["status"])
        d = f["parity"]["default"]
        self.assertEqual(d["value"], "FAIL")
        self.assertEqual(d["entry_points"], {"denominator": 4, "PASS": 1, "FAIL": 1, "INCONCLUSIVE": 1, "other": {"SKIPPED": 1}})
        self.assertEqual(d["scenarios"]["run"]["declared"], 3)
        self.assertEqual((d["scenarios"]["run"]["PASS"], d["scenarios"]["run"]["FAIL"], d["scenarios"]["run"]["INCONCLUSIVE"]), (1, 1, 1))
        self.assertEqual(d["scenarios"]["records"], {"source": "verification/parity/scenarios/*.json", "denominator": 2, "PASS": 1, "FAIL": 1,
                                                     "INCONCLUSIVE": 0, "legacy_records_ignored": 1})
        self.assertEqual([x["verdict"] for x in d["not_passed"]], ["FAIL", "INCONCLUSIVE"])
        self.assertEqual(d["not_passed"][0]["reason_head"], "status 403 vs 200")
        self.assertEqual(f["parity"]["enabled"]["value"], "PASS")
        self.assertTrue(f["parity"]["enabled"]["run"]["scoped"])
        self.assertEqual(f["m4_verdict"]["failed_floors"], ["floor-b"])
        rb = f["release_blockers"]
        self.assertEqual(rb["floors"], [{"floor": "floor-a", "adr": "ADR-003", "owner": "Operator step", "explained_by": 1}])
        self.assertEqual((rb["withheld_obligations"], rb["parity_obligations_resumed"]), (1, 2))
        ex = f["generated_tests"]["execution"]
        self.assertEqual(ex["value"], {"executed": 2, "passed": 1, "failed": 1, "errors": 0, "skipped": 1})
        self.assertEqual(ex["all_tests"]["passed"], 2)                                      # the retained test counts only in all_tests
        self.assertEqual(f["generated_tests"]["manifest"]["value"]["cases"], 3)
        self.assertEqual(f["coverage_account"]["value"], {"retired": 3, "replaced": 2, "remaining_gaps": 1, "uncovered_capabilities": 1})
        self.assertEqual(f["package_gate"]["value"], "pass")

        ct = rep["contract"]
        self.assertEqual(sorted(ct["scenarios"]["value"]), ["sc:x", "sc:y"])
        self.assertIn(bundle_eps(root)[0], ct["entry_points"]["value"])
        bd = rep["budget"]
        self.assertEqual(bd["declared"]["value"]["max_wall_hours"], 12)
        self.assertTrue(bd["declared"]["declared_before_launch"])
        self.assertEqual(bd["loop_stopping_rule"]["value"]["max_attempts"], 2)

        b = rep["board"]
        self.assertEqual(b["cards"]["value"]["by_phase"]["M3"]["run_seconds"], {"n": 4, "total_s": 610, "median_s": 150, "max_s": 300})
        self.assertEqual(b["cards"]["never_started"], ["t_orphan"])
        self.assertIn("t_orphan", b["cards"]["loop_cards_not_in_record"])
        lg = b["logs"]["value"]
        self.assertEqual((lg["blocked"], lg["protocol_violation"], lg["refuse"], lg["nonzero_exits"], lg["complete"], lg["runs"]), (1, 1, 1, 1, 1, 4))
        self.assertEqual(sorted(b["logs"]["cards_with_events"]), sorted([ids.t[0], "t_m1"]))

        cl = rep["classification"]
        self.assertEqual(cl["value"], "assisted")
        self.assertEqual(cl["counts"], {"operator_steps": 1, "rewinds": 1, "dispositions": 1, "bootstrap_repairs": 2})
        self.assertEqual(cl["prior_assistance"]["value"], 2)
        self.assertTrue(any(r.startswith("rewind by operator:x") for r in cl["reasons"]))
        self.assertTrue(any(r.startswith("prior assistance: 2 decided bootstrap repair") for r in cl["reasons"]))

    def test_a_comparison_names_the_pinned_inputs_that_differ(self):
        """ADR-019 section 4: name changed inputs without inferring their causal effects. The Operator ran v10 on a different worker model than v9, so
        the comparison must say so and must not let the delta read as a harness
        result."""
        def rep(model, golden, run_id):
            return {"pinned_inputs": {"pilot_run_id": rr.V(run_id, "x"), "installed_goldens": rr.V([{"golden": golden}], "x"),
                                      "unit_formation": rr.V("v1", "x"), "bootstrap_repairs": rr.U("no receipt")},
                    "pinned_environment": {"model_provider": rr.V({"cfg#model.default": model}, "x"),
                                           "toolchain": rr.V({"jdk": "21"}, "x")},
                    "contract": {"entry_points": rr.V({"ep:a": "d1", "ep:b": "d2"}, "x"),
                                 "scenarios": rr.V({"sc:1": "s1"}, "x")},
                    "final_state": {"parity": {"disabled": {"verdicts": {"ep:a": "PASS", "ep:b": "FAIL"}}}},
                    "classification": {"value": "assisted", "reasons": []},
                    "timeline": {}, "cost": {}, "loop_work": {"cards": {}, "retries": {}}}
        out = rr.compare(rep("qwen3-6-27b", "g1", "v9"), [("v10", rep("qwen3-8-27b-int4", "g2", "v10"))])
        d = out["differing_pins"]
        self.assertIn("model_provider", d["differs"])
        self.assertEqual(d["differs"]["model_provider"]["v9"], {"cfg#model.default": "qwen3-6-27b"})
        self.assertEqual(d["differs"]["model_provider"]["v10"], {"cfg#model.default": "qwen3-8-27b-int4"})
        self.assertIn("installed_goldens", d["differs"])
        # a pin that is the SAME is not reported as differing, or the caveat means nothing
        self.assertNotIn("toolchain", d["differs"])
        self.assertNotIn("unit_formation", d["differs"])
        # a pin no run could read is neither same nor different
        self.assertEqual(d["unknown"].get("bootstrap_repairs.decided"), ["v10", "v9"])
        # and two runs on identical pins produce no caveat at all
        same = rr.compare(rep("qwen3-6-27b", "g1", "v9"), [("v10", rep("qwen3-6-27b", "g1", "v10"))])
        self.assertEqual(same["differing_pins"]["differs"], {})

    def test_comparison_uses_emitted_nested_pins(self):
        import copy
        fx = Fixture(Ids("pins"))
        proc, baseline, _ = _run(fx.root, *fx.all_inputs())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        candidate = copy.deepcopy(baseline)
        candidate["pinned_environment"]["toolchain"]["legacy_build"] = rr.V({"jdk": "changed"}, "test")
        candidate["pinned_environment"]["database"]["datasource"]["value"]["db_version"] = "changed"
        candidate["pinned_environment"]["corpus_and_captures"]["corpus"]["value"] = {"digest": "changed"}
        candidate["pinned_environment"].pop("model_provider")
        pins = rr.differing_pins([("v9", baseline), ("v10", candidate)])
        for key in ("toolchain.legacy_build", "database.datasource", "corpus_and_captures.corpus"):
            self.assertIn(key, pins["differs"])
        self.assertEqual(pins["unknown"]["model_provider"], ["v10"])
        self.assertEqual(rr.differing_pins([("a", baseline), ("b", baseline)])["differs"], {})

    def test_classifications(self):
        ids = Ids("b")
        cases = [
            ("autonomous", dict(ops=[], rewinds=[], dispositions=[], transformations=False)),
            ("autonomous_execution_with_predecided_repairs", dict(ops=[], rewinds=[], dispositions=[], m4_verdict="PROVISIONAL_ACCEPT")),
            ("assisted-by-decision", dict(ops=[dict(ACCEPTED_OP), dict(ACCEPTED_OP, adr="ADR-001,ADR-002")], rewinds=[], dispositions=[])),
            ("assisted", dict(ops=[{"adr": "ADR-003", "reviewer": ""}], rewinds=[], dispositions=[])),           # no reviewer
            ("assisted", dict(ops=[{"adr": "ADR-099", "reviewer": "architect"}], rewinds=[], dispositions=[])),  # not accepted
            ("assisted", dict(ops=[{"adr": "", "reviewer": "architect"}], rewinds=[], dispositions=[])),         # no ADR
            ("assisted", dict(ops=[dict(ACCEPTED_OP)], dispositions=[])),                                         # a rewind
            ("assisted", dict(ops=[], rewinds=[])),                                                               # a disposition only
        ]
        for want, kw in cases:
            with self.subTest(want=want, kw=kw):
                fx = Fixture(ids, **kw)
                proc, rep, _ = _run(fx.root, "--git-log", str(fx.git_log))
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertEqual(rep["classification"]["value"], want, rep["classification"])
                self.assertIn("Classification: **%s**" % want, proc.stdout)
                if want != "autonomous":
                    self.assertTrue(rep["classification"]["reasons"])
                self.assertEqual(len(rep["harness_changes"]["installs_after_start"]), 1)   # installs never change the class
                if want == "autonomous":
                    self.assertEqual(rep["classification"]["prior_assistance"]["value"], 0)  # the receipt was read and says none
                if kw.get("m4_verdict") == "PROVISIONAL_ACCEPT":
                    fpm = rep["timeline"]["first_passing_m4"]
                    self.assertEqual((fpm["card"], fpm["verdict"]), (ids.t[10], "PROVISIONAL_ACCEPT"))
                    self.assertIsNone(fpm["at"])                                            # no board: its time is not guessed
                    self.assertEqual(rep["timeline"]["first_m4_verdict"]["card"], ids.t[6])  # the first verdict is another row

    def test_no_bootstrap_receipt_is_not_zero_prior_assistance(self):
        fx = Fixture(Ids("n"), ops=[], rewinds=[], dispositions=[], transformations=False)
        (fx.root / "evidence/producers/bootstrap.json").unlink()
        _, rep, _ = _run(fx.root, "--git-log", str(fx.git_log))
        cl = rep["classification"]
        self.assertEqual(cl["value"], "autonomous")
        self.assertIsNone(cl["prior_assistance"]["value"])
        self.assertIn("no bootstrap receipt", cl["prior_assistance"]["reason"])
        self.assertTrue(any(r.startswith("prior assistance unrecorded") for r in cl["reasons"]))
        self.assertIsNone(rep["bootstrap_repairs"]["decided"]["value"])

    def test_decided_but_unrecorded_is_not_zero(self):
        """decisions.yaml decides bootstrap repairs; the tree was bootstrapped without them."""
        fx = Fixture(Ids("d"), ops=[], rewinds=[], dispositions=[], transformations=False)
        doc = specimens.admitted_decisions()
        doc["decided_repairs"] = {"adr": "ADR-003", "applies": ["ADR-003"], "manifest": "operator-patches/x/manifest.json", "manifest_sha256": "m" * 64}
        (fx.root / "decisions.yaml").write_text(specimens.decisions_yaml(doc), encoding="utf-8")
        _, rep, _ = _run(fx.root, "--git-log", str(fx.git_log))
        bs = rep["bootstrap_repairs"]
        self.assertEqual(bs["decision"]["value"]["manifest"], "operator-patches/x/manifest.json")
        self.assertIsNone(bs["decided"]["value"])
        self.assertIn("bootstrapped before decided repairs existed", bs["decided"]["reason"])
        self.assertIsNone(rep["classification"]["prior_assistance"]["value"])
        self.assertEqual(rep["classification"]["value"], "autonomous")
        self.assertTrue(any(r.startswith("prior assistance unrecorded") for r in rep["classification"]["reasons"]))
        self.assertFalse(rep["pinned_inputs"]["decisions_digest"]["matches_admission_seal"])

    def test_unreadable_decisions_cannot_be_by_decision(self):
        fx = Fixture(Ids("c"), ops=[dict(ACCEPTED_OP)], rewinds=[], dispositions=[])
        (fx.root / "decisions.yaml").write_text("- a list, not a mapping\n", encoding="utf-8")
        _, rep, _ = _run(fx.root, "--git-log", str(fx.git_log))
        self.assertEqual(rep["classification"]["value"], "assisted")
        self.assertIsNone(rep["interventions"]["operator_steps"][0]["applies_accepted_adr"])
        self.assertIn("unverifiable", rep["classification"]["reasons"][0])
        self.assertIsNone(rep["pinned_inputs"]["unit_formation"]["value"])
        self.assertIn("not a mapping", rep["pinned_inputs"]["unit_formation"]["reason"])
        self.assertEqual(rep["budget"]["declared"]["value"], "undeclared")                  # no file given, none in the tree

    def test_real_git_history_and_absent_inputs(self):
        """No hand-written history: the prepared destination's own git log and baseline step."""
        root = prepared("http", "org.acme.clinic")
        proc, rep, _ = _run(root)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        base = load_json(root / "verification/loop/steps.json")["steps"][0]
        epoch = subprocess.run(["git", "-C", str(root), "log", "-1", "--format=%ct", base["commit"]], text=True, capture_output=True, check=True).stdout.strip()
        first = subprocess.run(["git", "-C", str(root), "log", "--reverse", "--format=%ct"], text=True, capture_output=True, check=True).stdout.split()[0]
        t = rep["timeline"]
        self.assertEqual((t["baseline"]["value"], t["baseline"]["source"]), (ISO(int(epoch)), "git log"))
        self.assertEqual(t["clock_start"]["value"], ISO(int(first)))
        self.assertEqual(rep["classification"]["value"], "autonomous")
        self.assertEqual(rep["classification"]["prior_assistance"]["value"], 0)
        self.assertEqual(t["first_accepted_step"]["value"], "unreached")                    # the record is there and has none
        self.assertEqual(t["first_m4_verdict"]["value"], "unreached")
        self.assertEqual(t["first_passing_m4"]["value"], "unreached")
        for sect, key in (("final_state", "m4_verdict"), ("final_state", "release_blockers"), ("final_state", "coverage_account"),
                          ("pinned_inputs", "installed_goldens"), ("loop_work", "unit_sizes"), ("timeline", "first_full_parity"),
                          ("timeline", "first_passing_parity"), ("pinned_environment", "model_provider")):
            e = rep[sect][key]
            self.assertIsNone(e["value"], (sect, key))
            self.assertTrue(e["reason"], (sect, key))
        self.assertIn("Managed Scope", rep["pinned_environment"]["model_provider"]["reason"])
        self.assertIsNone(rep["final_state"]["parity"]["default"]["value"])
        self.assertIn("absent", rep["final_state"]["parity"]["default"]["reason"])
        self.assertIsNone(rep["final_state"]["generated_tests"]["execution"]["value"])
        self.assertIn("not provided", rep["board"]["cards"]["reason"])
        self.assertIn("not provided", rep["board"]["logs"]["reason"])
        self.assertIsNone(rep["loop_work"]["cards"]["minted"]["value"])
        self.assertIsNone(rep["loop_work"]["clusters_by_kind"]["value"])
        self.assertIsNone(rep["cost"]["time"]["tool_seconds"]["value"])
        self.assertFalse((root / "evidence/reports").exists())                             # --out elsewhere: nothing written in the tree

    def test_enclosing_repository_is_not_this_history(self):
        root = prepared("http", "org.acme.clinic")
        sub = root / "nested"
        sub.mkdir()
        _, rep, _ = _run(sub)
        self.assertIsNone(rep["inputs"]["git_history"])
        self.assertIn("not the top", rep["inputs"]["git_history_reason"])

    def test_default_out_is_the_destination_report(self):
        root = prepared("http", "org.acme.clinic")
        proc = subprocess.run([sys.executable, str(SCRIPT), "--root", str(root)], text=True, capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(load_json(root / "evidence/reports/run-report.json")["schema"], "rhoai3.run-report/v1")

    def test_bare_directory_every_value_null_with_reason(self):
        root = Path(tempfile.mkdtemp(prefix="run-report-bare-")) / "dest"
        root.mkdir()
        proc, rep, _ = _run(root)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIsNone(rep["classification"]["value"])
        self.assertIn("steps.json is absent", rep["classification"]["reason"])
        self.assertIsNone(rep["classification"]["prior_assistance"]["value"])
        self.assertIsNone(rep["inputs"]["git_history"])
        self.assertTrue(rep["inputs"]["git_history_reason"])
        self.assertNotIn('"unreached"', json.dumps(rep))                                     # nothing claimed without its records

        def walk(node, path):
            if isinstance(node, dict):
                if "value" in node and "source" in node and node["value"] is None:
                    self.assertTrue(node.get("reason"), path)
                for k, v in node.items():
                    walk(v, path + "." + k)
            elif isinstance(node, list):
                for n, v in enumerate(node):
                    walk(v, "%s[%d]" % (path, n))
        walk(rep, "report")
        for k, e in rep["pinned_inputs"].items():
            self.assertIsNone(e["value"], k)
        self.assertEqual(rep["timeline"]["m4_verdicts"], [])
        self.assertIsNone(rep["loop_work"]["record"]["value"])
        self.assertEqual(rep["budget"]["declared"]["value"], "undeclared")

    def test_usage(self):
        proc = subprocess.run([sys.executable, str(SCRIPT), "--root", "/nonexistent/run-report"], text=True, capture_output=True)
        self.assertEqual(proc.returncode, 2)
        root = Path(tempfile.mkdtemp(prefix="run-report-usage-"))
        bogus = root / "bogus.json"
        bogus.write_text("{}", encoding="utf-8")
        proc = subprocess.run([sys.executable, str(SCRIPT), "--root", str(root), "--compare", str(bogus)], text=True, capture_output=True)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("is not a rhoai3.run-report/v1 report", proc.stderr)

    def test_comparison_on_the_common_unchanged_contract(self):
        a = Fixture(Ids("a"))
        b = Fixture(Ids("b"))
        corpus = load_json(b.root / "verification/scenarios/corpus.json")
        corpus["scenarios"][1]["path"] = "/y-changed"
        corpus["scenarios"].append({"id": "sc:z", "entry_point": "ep:z", "method": "GET", "path": "/z"})
        _w(b.root, "verification/scenarios/corpus.json", corpus)
        _, _, b_out = _run(b.root, "--git-log", str(b.git_log))
        proc, rep, _ = _run(a.root, *a.all_inputs(), "--compare", "B=%s" % b_out)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        cmp_ = rep["comparison"]
        self.assertEqual(cmp_["runs"], ["this", "B"])
        sc = cmp_["scenarios"]["value"]
        self.assertEqual((sc["common_unchanged"], sc["common_changed"], sc["extra"]), (["sc:x"], ["sc:y"], {"this": [], "B": ["sc:z"]}))
        eps = cmp_["entry_points"]["value"]
        n = len(eps["common_unchanged"])
        self.assertEqual((eps["common_changed"], eps["extra"]), ([], {"this": [], "B": []}))
        par = cmp_["parity_on_common_entry_points"]["this"]["default"]
        self.assertEqual(par, {"denominator": n, "PASS": 1, "FAIL": 1, "INCONCLUSIVE": 1, "absent": n - 4})
        self.assertEqual(cmp_["headline"]["this"]["classification"], "assisted")
        self.assertEqual(cmp_["headline"]["B"]["seconds_since_start"]["first_boot_pass"], 11800)
        self.assertEqual(cmp_["headline"]["this"]["seconds_since_start"]["first_passing_m4"], "unreached")
        self.assertIn("## Comparison", proc.stdout)

    def test_renamed_specimen_same_shape(self):
        """Another base package and other identities: the same counts, nothing keyed on names."""
        a = Fixture(Ids("a"), "org.acme.clinic")
        z = Fixture(Ids("z"), "net.renamed.storefront")
        _, ra, _ = _run(a.root, *a.all_inputs())
        _, rz, _ = _run(z.root, *z.all_inputs())

        def shape(rep):
            w = rep["loop_work"]
            return {
                "cards": {k: (len(v["value"]) if isinstance(v.get("value"), list) else v.get("value")) for k, v in w["cards"].items() if k not in ("pending", "deferred")},
                "per": sorted((v["accepted"], v["reverted"], v["max_attempt"]) for v in w["attempts_per_cluster"]["value"].values()),
                "kinds": w["clusters_by_kind"]["value"], "retries": w["retries"]["value"],
                "timeline": {k: rep["timeline"][k].get("since_start") for k in ("first_accepted_step", "first_package_pass", "first_boot_pass", "first_full_parity")},
                "parity": rep["final_state"]["parity"]["default"]["entry_points"], "tests": rep["final_state"]["generated_tests"]["execution"]["value"],
                "class": rep["classification"]["value"], "counts": rep["classification"]["counts"], "cost": rep["cost"]["time"]["wall_seconds"]["value"],
                "contract": (len(rep["contract"]["entry_points"]["value"]), len(rep["contract"]["scenarios"]["value"])),
            }
        self.assertEqual(shape(ra), shape(rz))
        self.assertNotEqual(ra["pinned_inputs"]["frozen_source_digest"]["value"], rz["pinned_inputs"]["frozen_source_digest"]["value"])
        self.assertNotIn("org.acme", json.dumps(rz))

    def test_source_is_specimen_agnostic_and_py39(self):
        text = SCRIPT.read_text(encoding="utf-8")
        for literal in ("petclinic", "Petclinic", "spring", "Owner", "org.acme", "ValidatorTests", "jacoco"):
            self.assertNotIn(literal, text, literal)
        ast.parse(text, feature_version=(3, 9))
        ast.parse(Path(__file__).read_text(encoding="utf-8"), feature_version=(3, 9))


if __name__ == "__main__":
    unittest.main(verbosity=1)
