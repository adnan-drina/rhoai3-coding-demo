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


# The Operator's declaration of one variant of the source baseline, under
# names no specimen owns: the statements are the SPECIMEN's own SQL and this
# script never parses them.
VARIANT = "identity-disabled"
VARIANT_STATEMENT = "UPDATE accounts SET enabled = false WHERE name = 'an-identity'"
VARIANT_SECURITY_YAML = (
    "security:\n"
    "  adr: ADR-003\n"
    "  switch:\n"
    "    key: acme.security.enable\n"
    '    disabled_value: "off"\n'
    '    enabled_value: "on"\n'
    "  identities:\n"
    "    - name: an-identity\n"
    "      credential_ref: ACME_IDENTITY_CREDENTIAL\n"
    "  fixtures:\n"
    "    - name: %s\n"
    "      intent: refuse\n"
    "      scenarios: auth-allowed\n"
    "      dataset_config_key: acme.sql.init.data-locations\n"
    "      statements:\n"
    "        - %s\n" % (VARIANT, json.dumps(VARIANT_STATEMENT))
)


def _variant_case() -> int:
    """The variant reset: the verified baseline, then the declared statements
    -- and the restoration that follows is the baseline verified again.

    ADR-014 asks for a separately recorded variant of the source baseline AND
    for the baseline to be restored afterwards. Both halves are measured here
    the only way they can be without a database: the plan the script resolves.
    The order is the claim being checked -- the baseline is loaded and
    VERIFIED before the fixture's statements are applied, so what the variant
    varies is a baseline this run proved rather than whatever the database
    happened to hold -- and the restoration is this same script with no
    --variant, which loads the baseline and verifies it.
    """
    with tempfile.TemporaryDirectory(prefix="reset-variant-") as td:
        t = Path(td)
        root = _tree(t / "variant", with_baseline=True)
        (root / "decisions.yaml").write_text(
            (root / "decisions.yaml").read_text(encoding="utf-8") + VARIANT_SECURITY_YAML, encoding="utf-8")
        p = subprocess.run(["bash", str(RESET), "--root", str(root), "--variant", VARIANT, "--print-plan"],
                           text=True, capture_output=True)
        if p.returncode != 0:
            return _fail("a declared variant resolves without a database: rc=%s %s" % (p.returncode, p.stderr[-400:]))
        lines = [ln for ln in p.stdout.splitlines() if ln.startswith(("apply: ", "verify: ", "restore: "))]
        baseline = next((i for i, ln in enumerate(lines) if ln.endswith("baseline-data.sql")), -1)
        verify = next((i for i, ln in enumerate(lines) if ln.startswith("verify: row counts")), -1)
        fixture = next((i for i, ln in enumerate(lines) if ln.startswith("apply: fixture ")), -1)
        restore = next((i for i, ln in enumerate(lines) if ln.startswith("restore: ")), -1)
        if min(baseline, verify, fixture, restore) < 0:
            return _fail("the variant plan loads the baseline, verifies it, applies the fixture and names the restoration: %s" % lines)
        if not (baseline < verify < fixture < restore):
            return _fail("the baseline is loaded and VERIFIED before the fixture's statements: %s" % lines)
        if "1 statement(s)" not in lines[fixture] or VARIANT not in lines[fixture]:
            return _fail("the plan says which fixture and how many statements: %s" % lines[fixture])
        if "verifies it" not in lines[restore]:
            return _fail("the restoration is the baseline, verified: %s" % lines[restore])
        # the statements themselves are never parsed here, only passed on --
        # and they are the last thing applied
        p = subprocess.run(["bash", str(RESET), "--root", str(root), "--variant", VARIANT], text=True, capture_output=True,
                           env={**os.environ, "FIXTURE_DB_URL": "", "FIXTURE_DB_USER": "", "FIXTURE_DB_PASSWORD": ""})
        if p.returncode != 1 or "FIXTURE_DB_URL" not in p.stderr:
            return _fail("a variant reset still refuses without the credentials the decision names: rc=%s %s"
                         % (p.returncode, p.stderr[-300:]))
        # a variant nobody declared is refused, and the refusal says what IS
        # declared rather than resetting to something nobody asked for
        p = subprocess.run(["bash", str(RESET), "--root", str(root), "--variant", "no-such-fixture", "--print-plan"],
                           text=True, capture_output=True)
        if p.returncode != 1 or "no security fixture named" not in p.stderr:
            return _fail("an undeclared variant refuses by name: rc=%s %s" % (p.returncode, p.stderr[-300:]))
        # ... and a tree that declares no security section at all says so
        plain = _tree(t / "plain", with_baseline=True)
        p = subprocess.run(["bash", str(RESET), "--root", str(plain), "--variant", VARIANT, "--print-plan"],
                           text=True, capture_output=True)
        if p.returncode != 1 or "no usable security section" not in p.stderr:
            return _fail("a tree declaring no security section refuses the variant: rc=%s %s" % (p.returncode, p.stderr[-300:]))
        # the baseline reset is exactly what it was: no variant, no fixture line
        p = subprocess.run(["bash", str(RESET), "--root", str(root), "--print-plan"], text=True, capture_output=True)
        if p.returncode != 0 or "apply: fixture" in p.stdout or "restore:" in p.stdout:
            return _fail("the baseline reset is untouched by a declared fixture: rc=%s %s" % (p.returncode, p.stdout))
    return 0


def _revert_case() -> int:
    """--revert-variant: the other half of revert-then-read.

    It executes ONLY the revert the variant corpus records -- computed from
    the fixture's statements over the declared dataset -- and nothing else:
    no schema is dropped, no baseline is loaded. The revert first proves it
    finds the variant state and then proves it left the baseline value; the
    judgement is the same over canned observations (no database here), and
    the SQL it sends asserts the same facts. A plan computed from statements
    decisions.yaml no longer declares, a corpus with no plan, and both flags
    at once are refused by name."""
    sys.path.insert(0, str(HERE))
    import _variant_revert as vr
    from planner.canonical import write_canonical
    from _scenarios import corpus_path
    declared_rows = "INSERT INTO accounts VALUES ('an-identity', true);\nINSERT INTO accounts VALUES ('other', true);\n"
    schema = "CREATE TABLE accounts (name VARCHAR(20) PRIMARY KEY, enabled BOOLEAN NOT NULL);\n"
    plan = vr.compute_plan([VARIANT_STATEMENT], declared_rows, schema, {"path": "db/populateDB.sql", "sha256": "0" * 64})
    if plan["statements"] != ['UPDATE "accounts" SET "enabled" = true WHERE "name" = \'an-identity\'']:
        return _fail("the revert restores the seeded value: %s" % plan["statements"])
    # the judgement: the variant state found, exactly the rows updated, the
    # baseline value left -- anything else is REVERT_UNEXPECTED_STATE
    good_before, good_after = {0: {"table_rows": 2, "selected": 1, "variant": 1}}, {0: {"updated": 1, "baseline": 1}}
    if vr.observation_gaps(plan, good_before, good_after):
        return _fail("the variant state, reverted, is accepted")
    for before, after, what in (({0: {"table_rows": 1, "selected": 1, "variant": 1}}, good_after, "a row gone from the table"),
                                ({0: {"table_rows": 2, "selected": 1, "variant": 0}}, good_after, "the variant value not found"),
                                (good_before, {0: {"updated": 1, "baseline": 0}}, "the baseline value not left")):
        gaps = vr.observation_gaps(plan, before, after)
        if not gaps or "REVERT_UNEXPECTED_STATE" not in gaps[0]:
            return _fail("%s refuses: %s" % (what, gaps))
    sql = vr.revert_sql(plan)
    for fact in ('SELECT count(*) INTO n FROM "accounts";\n  IF n <> 2',
                 '"enabled" IS NOT DISTINCT FROM false;\n  IF n <> 1',
                 'GET DIAGNOSTICS n = ROW_COUNT;\n  IF n <> 1',
                 '"enabled" IS NOT DISTINCT FROM true;\n  IF n <> 1', "RAISE EXCEPTION", "DO $revert$"):
        if fact not in sql:
            return _fail("the revert SQL asserts %r: %s" % (fact, sql))
    if "DROP" in sql.upper() or "INSERT" in sql.upper():
        return _fail("the revert changes nothing but the reverted rows: %s" % sql)
    try:
        vr.compute_plan(["UPDATE accounts SET enabled = false, name = 'x' WHERE name = 'an-identity'"], declared_rows, schema, {})
        return _fail("a multi-column update has no computable revert")
    except vr.RevertRefusal:
        pass

    with tempfile.TemporaryDirectory(prefix="reset-revert-") as td:
        root = _tree(Path(td) / "revert", with_baseline=True)
        (root / "decisions.yaml").write_text(
            (root / "decisions.yaml").read_text(encoding="utf-8") + VARIANT_SECURITY_YAML, encoding="utf-8")
        corpus = {"schema": "rhoai3.scenario-corpus/v1", "approved_by": "operator:test", "security_mode": "enabled",
                  "security_variant": VARIANT, "initial_state": {"reset": "the reset script", "dataset": "declared"},
                  "fixture": {"name": VARIANT, "statements": [VARIANT_STATEMENT], "revert": plan}, "scenarios": []}
        write_canonical(root / corpus_path("enabled", VARIANT), corpus)

        def run(*extra: str) -> subprocess.CompletedProcess:
            return subprocess.run(["bash", str(RESET), "--root", str(root)] + list(extra), text=True, capture_output=True)

        p = run("--revert-variant", VARIANT, "--print-plan")
        if p.returncode != 0 or "nothing dropped, nothing loaded" not in p.stdout or "revert: fixture %s (1 " % VARIANT not in p.stdout:
            return _fail("the revert plan resolves without a database: rc=%s %s %s" % (p.returncode, p.stdout, p.stderr[-300:]))
        if "apply:" in p.stdout or "sql: " + plan["statements"][0] in p.stdout or 'sql:   UPDATE "accounts"' not in p.stdout:
            return _fail("the revert applies no asset and sends exactly the verified block: %s" % p.stdout)
        p = run("--revert-variant", VARIANT)
        if p.returncode != 1 or "FIXTURE_DB_URL" not in p.stderr:
            return _fail("a revert still needs the credentials the decision names: rc=%s %s" % (p.returncode, p.stderr[-300:]))
        p = run("--revert-variant", VARIANT, "--variant", VARIANT, "--print-plan")
        if p.returncode != 2:
            return _fail("setting and reverting a variant at once is a usage error: rc=%s" % p.returncode)
        # a plan computed from statements the decision no longer declares
        stale = dict(corpus, fixture=dict(corpus["fixture"], statements=["UPDATE accounts SET enabled = false WHERE name = 'other'"]))
        write_canonical(root / corpus_path("enabled", VARIANT), stale)
        p = run("--revert-variant", VARIANT, "--print-plan")
        if p.returncode != 1 or "REVERT_STALE_PLAN" not in p.stderr:
            return _fail("a revert computed from other statements refuses: rc=%s %s" % (p.returncode, p.stderr[-300:]))
        # a corpus with no plan names why (and what the derivation said)
        bare = dict(corpus, fixture={"name": VARIANT, "statements": [VARIANT_STATEMENT],
                                     "revert_refused": "REVERT_NOT_COMPUTABLE: a reason"})
        write_canonical(root / corpus_path("enabled", VARIANT), bare)
        p = run("--revert-variant", VARIANT, "--print-plan")
        if p.returncode != 1 or "REVERT_NO_PLAN" not in p.stderr or "REVERT_NOT_COMPUTABLE: a reason" not in p.stderr:
            return _fail("a corpus with no revert refuses and carries the derivation's reason: rc=%s %s" % (p.returncode, p.stderr[-300:]))
        # a plan edited into something that is not a translated literal
        edited = dict(corpus, fixture=dict(corpus["fixture"], revert=dict(plan, rows=[dict(plan["rows"][0], baseline_value="now()")])))
        write_canonical(root / corpus_path("enabled", VARIANT), edited)
        p = run("--revert-variant", VARIANT, "--print-plan")
        if p.returncode != 1 or "REVERT_NO_PLAN" not in p.stderr:
            return _fail("an edited revert plan is not executed: rc=%s %s" % (p.returncode, p.stderr[-300:]))
    return 0


def main() -> int:
    if _plan_case() or _verification_case() or _variant_case() or _revert_case():
        return 1
    print("OK: reset-parity-db (the plan loads the derived baseline and not the per-engine seed; an older tree keeps the "
          "previous behaviour and says the baseline is unverified; every existing flag still holds; a declared fixture "
          "VARIANT loads the baseline, VERIFIES it, and only then applies the Operator's own statements, names the "
          "restoration that follows, still refuses without the credentials the decision names, and refuses an undeclared "
          "variant and a tree with no security section by name while the baseline reset stays what it was; the reset contract "
          "refuses a drifted row count, a sequence left at RESTART WITH, and a missing sequence, and the SQL it sends "
          "asserts the same facts; --revert-variant executes only the revert the variant corpus records, drops and loads nothing, "
          "proves it finds the variant state and leaves the baseline value -- REVERT_UNEXPECTED_STATE otherwise -- and refuses a "
          "stale plan, a missing or edited plan and both flags at once by name)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
