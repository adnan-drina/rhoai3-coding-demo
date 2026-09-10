#!/usr/bin/env python3
"""coverage-account selftest: every retirement gets a row; a claimed
replacement must be a measured PASS; a gap is recorded, not fatal; the lint
refuses an absent, an edited, and an unmentioned account, and never authors."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
COMPOSER = HERE / "compose-coverage-account.py"
LINT = HERE.parents[1] / "check-release-readiness" / "scripts" / "assert-coverage-account.py"

DECISIONS = """schema: rhoai3.decisions/v2

adrs:
  - id: ADR-001
    status: accepted
    title: Destination platform
  - id: ADR-009
    status: accepted
    title: Retire the thing
  - id: ADR-010
    status: proposed
    title: Not decided yet

destination_platform:
  id: quarkus-rhbq-3.27
  adr: ADR-001

thresholds:
  max_attempts: 3
  adr: ADR-001

not_applicable: []

datasource:
  adr: ADR-001
  db_kind: postgresql
  db_version: "16"
  jdbc_extension: io.quarkus:quarkus-jdbc-postgresql
  profile: prod
  instance: fixture-isolated-postgres
  jdbc_url_env: FIXTURE_DB_URL
  username_env: FIXTURE_DB_USER
  password_env: FIXTURE_DB_PASSWORD
  reset_procedure: drop and recreate, then apply schema and seed
  schema_owner: destination-orm
  schema_sql: ""
  seed_sql: ""
  hibernate_generation: none
  source_baseline_db_kind: hsqldb

retired_sources:
  - path: src/main/java/a/Replaced.java
    adr: ADR-009
    reason: superseded by the platform
    replaced_by: [ep-passes]
  - path: src/main/java/a/Unreplaced.java
    adr: ADR-009
    reason: nothing covers it
  - path: src/test/java/a/RetiredTest.java
    adr: ADR-009
    reason: the implementation it tested is gone
    replaced_by: [ep-passes]
  - path: src/main/java/a/ClaimedButFailing.java
    adr: ADR-009
    reason: claims a scenario that did not pass
    replaced_by: [ep-fails]
  - path: src/main/java/a/NotDecided.java
    adr: ADR-010
    reason: the ADR is only proposed
    replaced_by: [ep-passes]
"""


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def _root(td: Path, *, surefire_rc: int | None) -> Path:
    root = td / "dest"
    root.mkdir(parents=True)
    # the golden .hermes as-is: lib, and the schemas the decisions loader reads
    (root / ".hermes").symlink_to(HERE.parents[3], target_is_directory=True)
    (root / "decisions.yaml").write_text(DECISIONS, encoding="utf-8")
    parity = root / "verification" / "parity"
    parity.mkdir(parents=True)
    (parity / "receipt.json").write_text(json.dumps({
        "schema": "rhoai3.parity-receipt/v1", "verdict": "FAIL",
        "entry_points": [{"entry_point": "ep-passes", "verdict": "PASS", "reason": ""},
                         {"entry_point": "ep-fails", "verdict": "FAIL", "reason": "body differs"}],
    }), encoding="utf-8")
    if surefire_rc is not None:
        d = root / "evidence" / "receipts" / "gates"
        d.mkdir(parents=True)
        (d / "assert-surefire-results.json").write_text(json.dumps({"rc": surefire_rc}), encoding="utf-8")
    return root


def _rows(root: Path) -> dict[str, dict]:
    doc = json.loads((root / "evidence" / "verdicts" / "coverage-account.json").read_text())
    return {r["path"]: r for r in doc["rows"]}, doc


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="cov-") as td:
        root = _root(Path(td), surefire_rc=0)
        p = subprocess.run([sys.executable, str(COMPOSER), str(root)], text=True, capture_output=True)
        if p.returncode != 0:
            return _fail("composer: %s%s" % (p.stdout, p.stderr))
        rows, doc = _rows(root)
        if sorted(rows) != ["src/main/java/a/ClaimedButFailing.java", "src/main/java/a/NotDecided.java",
                            "src/main/java/a/Replaced.java", "src/main/java/a/Unreplaced.java",
                            "src/test/java/a/RetiredTest.java"]:
            return _fail("every retired source needs a row: %s" % sorted(rows))
        if rows["src/main/java/a/Replaced.java"]["remaining_gap"]:
            return _fail("a replacement measured PASS is not a gap: %s" % rows["src/main/java/a/Replaced.java"])
        if not rows["src/main/java/a/Unreplaced.java"]["remaining_gap"] or "replaced_by" not in " ".join(rows["src/main/java/a/Unreplaced.java"]["gap_reasons"]):
            return _fail("a retirement naming no scenario is a recorded gap: %s" % rows["src/main/java/a/Unreplaced.java"])
        if not rows["src/main/java/a/ClaimedButFailing.java"]["remaining_gap"]:
            return _fail("a claimed scenario that measured FAIL must be a gap")
        if not rows["src/main/java/a/NotDecided.java"]["remaining_gap"]:
            return _fail("a retirement whose ADR is only proposed must be a gap")
        if rows["src/test/java/a/RetiredTest.java"]["kind"] != "test" or rows["src/test/java/a/RetiredTest.java"]["remaining_gap"]:
            return _fail("a retired test beside passing scenarios and executed tests is replaced: %s" % rows["src/test/java/a/RetiredTest.java"])
        if doc["summary"] != {"retired": 5, "tests": 1, "implementations": 4, "replaced": 2, "remaining_gaps": 3}:
            return _fail("summary: %s" % doc["summary"])

        # a retired test without fresh executed test evidence is a gap
        root2 = _root(Path(td) / "b", surefire_rc=None)
        subprocess.run([sys.executable, str(COMPOSER), str(root2)], text=True, capture_output=True, check=True)
        rows2, _ = _rows(root2)
        if not rows2["src/test/java/a/RetiredTest.java"]["remaining_gap"]:
            return _fail("a retired test with no executed-test evidence must be a gap")
        if rows2["src/main/java/a/Replaced.java"]["remaining_gap"]:
            return _fail("test evidence must not be required of an implementation row")

        # the lint: a gap is not a refusal, but hiding one is
        verdict_p = root / "evidence" / "verdicts" / "m4-verdict.json"
        verdict_p.write_text(json.dumps({"gate": "M4_VERDICT", "phase": "M4", "ran": True, "verdict": "REFUSE",
                                         "ship": False, "failed_floors": ["check-product-tests"], "floors": [{"name": "check-product-tests", "rc": 1, "idle": False}],
                                         "coverage_account": {"retired": 5, "remaining_gaps": 3}}), encoding="utf-8")
        p = subprocess.run([sys.executable, str(LINT), str(root)], text=True, capture_output=True)
        if p.returncode != 0:
            return _fail("a complete account with three recorded gaps must PASS: %s%s" % (p.stdout, p.stderr))
        before = (root / "evidence" / "verdicts" / "coverage-account.json").read_bytes()

        verdict_p.write_text(json.dumps({"gate": "M4_VERDICT", "phase": "M4", "ran": True, "verdict": "REFUSE",
                                         "ship": False, "failed_floors": ["check-product-tests"], "floors": [{"name": "check-product-tests", "rc": 1, "idle": False}],
                                         "coverage_account": {"retired": 5, "remaining_gaps": 0}}), encoding="utf-8")
        p = subprocess.run([sys.executable, str(LINT), str(root)], text=True, capture_output=True)
        if p.returncode != 1 or "carries coverage_account" not in p.stderr:
            return _fail("a verdict that under-reports the gaps must refuse: rc=%s %s" % (p.returncode, p.stderr[:300]))

        account_p = root / "evidence" / "verdicts" / "coverage-account.json"
        edited = json.loads(account_p.read_text())
        for r in edited["rows"]:
            r["remaining_gap"] = False
        edited["summary"]["remaining_gaps"] = 0
        edited["remaining_gaps"] = []
        account_p.write_text(json.dumps(edited), encoding="utf-8")
        p = subprocess.run([sys.executable, str(LINT), str(root)], text=True, capture_output=True)
        if p.returncode != 1 or "not what decisions.yaml" not in p.stderr:
            return _fail("an edited account must refuse: rc=%s %s" % (p.returncode, p.stderr[:300]))
        if account_p.read_bytes() != json.dumps(edited).encode():
            return _fail("the checker must not author the account it is checking")

        account_p.write_text(before.decode(), encoding="utf-8")
        account_p.unlink()
        p = subprocess.run([sys.executable, str(LINT), str(root)], text=True, capture_output=True)
        if p.returncode != 1 or "unaccounted" not in p.stderr:
            return _fail("an absent account must refuse naming the unaccounted retirements: rc=%s %s" % (p.returncode, p.stderr[:300]))
    print("OK: coverage-account selftest (every retirement rowed; PASS scenario replaces, no scenario / failed scenario / proposed ADR / missing test evidence are recorded gaps; lint PASSes on disclosed gaps and refuses an under-reporting verdict, an edited account and an absent one, without authoring)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
