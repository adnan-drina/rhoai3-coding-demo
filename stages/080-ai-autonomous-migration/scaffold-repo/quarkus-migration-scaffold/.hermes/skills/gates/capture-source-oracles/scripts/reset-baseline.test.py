#!/usr/bin/env python3
"""reset-parity-db.sh selftest: the reset loads the DERIVED baseline and verifies it.

There is no PostgreSQL here, and a test that needed one would not run where the
harness is landed, so the reset is measured in the two places it can be:

- ``--print-plan`` resolves the decision, the assets and the baseline facts and
  prints what it WOULD apply, touching no database. That is what proves the
  reset loads ``baseline-data.sql`` rather than the source's own per-engine
  seed, and that an older tree without the derived asset keeps the previous
  behaviour and says the baseline is unverified.
- the verification itself is a pure judgement over query results
  (``verify_observations``), so it is exercised with canned numbers -- a
  matching baseline, a row count that drifted, a sequence still sitting where a
  ``RESTART WITH`` left it, and a sequence the engine does not have. The SQL the
  script actually sends is generated from the same plan by the same module, and
  is checked to assert the same facts.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOLDEN = HERE.parents[4]
RESET = HERE / "reset-parity-db.sh"
BASELINE_TOOL = GOLDEN / ".hermes" / "skills" / "migration" / "bootstrap-destination" / "scripts" / "_baseline_data.py"
sys.path.insert(0, str(GOLDEN / ".hermes" / "lib"))
from planner import pipeline, specimens  # noqa: E402

_spec = importlib.util.spec_from_file_location("baseline_data", BASELINE_TOOL)
bd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bd)  # type: ignore[union-attr]

SCHEMA = """CREATE TABLE IF NOT EXISTS owners (
  id SERIAL,
  first_name VARCHAR(30),
  CONSTRAINT pk_owners PRIMARY KEY (id)
);
ALTER SEQUENCE owners_id_seq RESTART WITH 100;

CREATE TABLE IF NOT EXISTS pets (
  id SERIAL,
  name VARCHAR(30),
  birth_date DATE,
  CONSTRAINT pk_pets PRIMARY KEY (id)
);
ALTER SEQUENCE pets_id_seq RESTART WITH 100;
"""
DECLARED = """INSERT INTO owners VALUES (1, 'George');
INSERT INTO owners VALUES (2, 'O''Brien');
INSERT INTO pets VALUES (1, 'Leo', '2010-09-07');
"""
ENGINE_SEED = "INSERT INTO pets VALUES (1, 'Leo', '2000-09-07') ON CONFLICT DO NOTHING;\n"


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def _tree(root: Path, *, with_baseline: bool) -> Path:
    root = specimens.build_dest(root, specimens.specimen("http"), decisions=specimens.admitted_decisions())
    db = root / "src" / "main" / "resources" / "db"
    (db / "postgresql").mkdir(parents=True, exist_ok=True)
    (db / "postgresql" / "initDB.sql").write_text(SCHEMA, encoding="utf-8")
    (db / "postgresql" / "populateDB.sql").write_text(ENGINE_SEED, encoding="utf-8")
    pipeline.assemble_bundle(root)
    if with_baseline:
        contract = {
            "translator": bd.TRANSLATOR, "translator_version": bd.TRANSLATOR_VERSION,
            "destination_engine": "postgresql",
            "declared_dataset": {"path": "src/main/resources/db/hsqldb/populateDB.sql", "sha256": "0" * 64,
                                 "named_by": "corpus initial_state.dataset"},
            "schema_asset": {"path": "src/main/resources/db/postgresql/initDB.sql", "sha256": "1" * 64},
        }
        built = bd.build_baseline(DECLARED, SCHEMA, "postgresql")
        (db / "postgresql" / bd.BASELINE_FILENAME).write_text(bd.render_asset(built, contract), encoding="utf-8")
    return root


def _plan_case() -> int:
    with tempfile.TemporaryDirectory(prefix="reset-") as td:
        t = Path(td)
        root = _tree(t / "derived", with_baseline=True)
        p = subprocess.run(["bash", str(RESET), "--root", str(root), "--print-plan"], text=True, capture_output=True)
        if p.returncode != 0:
            return _fail("--print-plan must resolve without a database: rc=%s %s" % (p.returncode, p.stderr[-400:]))
        out = p.stdout
        if "apply: src/main/resources/db/postgresql/initDB.sql" not in out:
            return _fail("the plan must recreate the schema from the installed schema asset: %s" % out)
        if "apply: src/main/resources/db/postgresql/baseline-data.sql" not in out:
            return _fail("the plan must load the DERIVED baseline: %s" % out)
        if any(ln.startswith("apply: ") and ln.endswith("populateDB.sql") for ln in out.splitlines()):
            return _fail("the source's own per-engine seed is no longer what the reset loads: %s" % out)
        if "dataset: src/main/resources/db/hsqldb/populateDB.sql" not in out:
            return _fail("the plan must name the declared dataset the baseline came from: %s" % out)
        if "rows: owners=2 pets=1" not in out:
            return _fail("the plan must print the row counts it will verify: %s" % out)
        if "sequences: owners.id pets.id" not in out:
            return _fail("the plan must print the sequences it will align: %s" % out)
        if "verify: row counts" not in out:
            return _fail("the plan must say what it verifies: %s" % out)

        # an older tree: the previous behaviour, and it SAYS the baseline is unverified
        old = _tree(t / "older", with_baseline=False)
        p = subprocess.run(["bash", str(RESET), "--root", str(old), "--print-plan"], text=True, capture_output=True)
        if p.returncode != 0:
            return _fail("a tree without the derived asset must still plan a reset: rc=%s %s" % (p.returncode, p.stderr[-300:]))
        if "apply: src/main/resources/db/postgresql/populateDB.sql" not in p.stdout:
            return _fail("without a derived asset the reset keeps loading the decided seed: %s" % p.stdout)
        if "unverified" not in (p.stdout + p.stderr):
            return _fail("an unverified baseline must be printed as a fact of the run: %s" % p.stdout)

        # every existing flag still means what it meant
        p = subprocess.run(["bash", str(RESET), "--root", str(root)], text=True, capture_output=True,
                           env={**os.environ, "FIXTURE_DB_URL": "", "FIXTURE_DB_USER": "", "FIXTURE_DB_PASSWORD": ""})
        if p.returncode != 1 or "FIXTURE_DB_URL" not in p.stderr:
            return _fail("a real reset still refuses without the credentials the decision names: rc=%s %s" % (p.returncode, p.stderr[-300:]))
        p = subprocess.run(["bash", str(RESET), "--root", str(root), "--nonsense"], text=True, capture_output=True)
        if p.returncode != 2 or "--driver" not in p.stderr:
            return _fail("usage must still exit 2 and name every flag: rc=%s %s" % (p.returncode, p.stderr[-200:]))
    return 0


def _verification_case() -> int:
    """The reset contract, judged over canned query results."""
    built = bd.build_baseline(DECLARED, SCHEMA, "postgresql")
    contract = {"translator": bd.TRANSLATOR, "translator_version": bd.TRANSLATOR_VERSION,
                "destination_engine": "postgresql",
                "declared_dataset": {"path": "db/hsqldb/populateDB.sql", "sha256": "0" * 64, "named_by": "corpus"},
                "schema_asset": {"path": "db/postgresql/initDB.sql", "sha256": "1" * 64}}
    plan = bd.plan_from_asset(bd.render_asset(built, contract))
    if plan["row_counts"] != {"owners": 2, "pets": 1}:
        return _fail("the plan is re-measured from the asset body: %s" % plan["row_counts"])
    if [(s["table"], s["column"]) for s in plan["sequences"]] != [("owners", "id"), ("pets", "id")]:
        return _fail("the plan must name every sequence the asset aligns: %s" % plan["sequences"])

    good = {"row_counts": {"owners": 2, "pets": 1},
            "sequences": {"owners.id": {"next": 3, "max": 2}, "pets.id": {"next": 2, "max": 1}}}
    if bd.verify_observations(plan, good) != []:
        return _fail("a database that holds the declared baseline verifies: %s" % bd.verify_observations(plan, good))

    # the two failures ADR-009 is about, each named where it is
    drifted = json.loads(json.dumps(good))
    drifted["row_counts"]["owners"] = 3
    msgs = bd.verify_observations(plan, drifted)
    if msgs != ["BASELINE owners: 3 row(s) after the reset, the derived baseline declares 2"]:
        return _fail("a row count that drifted must refuse by table: %s" % msgs)
    restarted = json.loads(json.dumps(good))
    restarted["sequences"]["owners.id"]["next"] = 100
    msgs = bd.verify_observations(plan, restarted)
    if msgs != ["BASELINE owners.id: the sequence next value is 100 but the seeded maximum + 1 is 3"]:
        return _fail("a sequence still sitting where RESTART WITH left it must refuse: %s" % msgs)
    missing = {"row_counts": {"owners": 2, "pets": 1}, "sequences": {"owners.id": {"next": 3, "max": 2}}}
    msgs = bd.verify_observations(plan, missing)
    if len(msgs) != 1 or "no sequence for it" not in msgs[0] or "pets.id" not in msgs[0]:
        return _fail("a generated identity with no sequence must refuse: %s" % msgs)
    empty = {"row_counts": {}, "sequences": {}}
    if len(bd.verify_observations(plan, empty)) != 4:
        return _fail("a database that lost the baseline entirely refuses on every fact")

    # the SQL the script sends asserts the same facts, in the same words
    sql = bd.verification_sql(plan)
    for needle in ('SELECT count(*) INTO n FROM "owners"', "IF n <> 2 THEN",
                   "pg_get_serial_sequence('pets', 'id')", "want := COALESCE(mx, 0) + 1",
                   # RAISE substitutes on %, not on %s: a message that said %s would print "3s"
                   "BASELINE owners: % row(s)",
                   "the derived baseline declares 2", "the seeded maximum + 1 is %'"):
        if needle not in sql:
            return _fail("the generated verification must assert %r: %s" % (needle, sql[:400]))
    if sql.count("RAISE EXCEPTION") != 2 + 2 * len(plan["sequences"]):
        return _fail("every check must raise on its own mismatch: %s" % sql)

    # an asset nobody generated is not a baseline
    try:
        bd.plan_from_asset("INSERT INTO owners VALUES (1, 'George');\n")
    except bd.BaselineRefusal as exc:
        if "marker" not in exc.detail:
            return _fail("an unmarked file must be refused for the marker it lacks: %s" % exc.detail)
    else:
        return _fail("a file with no generated marker must not be read as a baseline")
    return 0


def main() -> int:
    if _plan_case() or _verification_case():
        return 1
    print("OK: reset-parity-db (the plan loads the derived baseline and not the per-engine seed; an older tree keeps the "
          "previous behaviour and says the baseline is unverified; every existing flag still holds; the reset contract "
          "refuses a drifted row count, a sequence left at RESTART WITH, and a missing sequence, and the SQL it sends "
          "asserts the same facts)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
