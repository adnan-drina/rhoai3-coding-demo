#!/usr/bin/env python3
"""run_identity selftest: the counterexamples, on synthetic runs.

Every case here is one the architect's 2026-09-22 review demonstrated PASSING
against the substring check this module replaces. They are written as
counterexamples, not as confirmations: a check is only worth its name if
something fails it.

  1. the right service in the WRONG NAMESPACE
  2. the right server, the WRONG DATABASE
  3. a DIFFERENT HOST whose name starts with the expected one
  4. ANOTHER HOST carrying the expected name only in a query parameter

and the surrounding obligations:

  * every accepted DNS spelling of the SAME Service is accepted, and only those
  * a wrong PORT on the right host is a different endpoint
  * the platform receipt is required, and a receipt for another run refuses
  * a workspace whose own identity is a DIFFERENT run refuses (the name
    collision case: demo-v10-retry must not pass as demo-v10)
  * absent variables are RUN_RESOURCES_MISSING -- blocking for reset, fixture,
    startup and parity, permitted for analysis, and never confused with a wrong
    target
  * a destination with no assignment and no decided instance is refused
  * a pre-per-run destination (v9's shape) keeps working under the legacy
    exception, and a fresh destination cannot reach it
  * no credential value is read, returned or printed
"""
from __future__ import annotations

import sys
import subprocess
import json
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))

from planner import run_identity as ri  # noqa: E402

NS = "wksp-ai-developer"
RUN = "demo-v10"
OTHER = "demo-v10-retry"
HOST = "%s-parity-postgres" % RUN
INSTANCE = "%s.%s" % (HOST, NS)
GOOD_URL = "jdbc:postgresql://%s.%s.svc:5432/parity" % (HOST, NS)
RECEIPT = ("run=%s;namespace=%s;workspace=%s;host=%s;port=5432;database=parity;engine=postgresql;scaffold=abc123"
           % (RUN, NS, RUN, HOST))
SECRET = "never-printed-password"

DECISIONS = """adrs:
  - id: ADR-009
    status: accepted
    title: the effective database is a decision

datasource:
  adr: ADR-009
  db_kind: postgresql
  db_version: "16"
  profile: prod
  instance: %s
  jdbc_url_env: PETCLINIC_DB_URL
  username_env: PETCLINIC_DB_USER
  password_env: PETCLINIC_DB_PASSWORD
"""

MIGRATION = """migration:
  target: quarkus
resources:
  run: %s
  namespace: %s
  receipt_env: PARITY_RUN_RECEIPT
  parity_database:
    instance: %s
    database: parity
    port: 5432
    server_secret: %s-parity-postgres
    workspace_secret: %s-parity-db
    jdbc_url_env: PETCLINIC_DB_URL
    username_env: PETCLINIC_DB_USER
    password_env: PETCLINIC_DB_PASSWORD
  fixture_credentials:
    secret: %s-parity-credentials
    env:
      - PETCLINIC_ADMIN_CREDENTIAL
      - PETCLINIC_INVALID_CREDENTIAL
"""

MIGRATION_NO_RESOURCES = "migration:\n  target: quarkus\n"


def _tree(tmp: Path, migration: str, instance: str) -> Path:
    root = Path(tempfile.mkdtemp(dir=tmp))
    (root / "decisions.yaml").write_text(DECISIONS % instance, encoding="utf-8")
    (root / "migration.yaml").write_text(migration, encoding="utf-8")
    subprocess.run(['git', 'init', '-q', str(root)], check=True)
    subprocess.run(['git', '-C', str(root), 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(root), '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.test', 'commit', '-qm', 'scaffold'], check=True)
    global RECEIPT
    sha = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    RECEIPT = RECEIPT.rsplit('scaffold=', 1)[0] + 'scaffold=' + sha
    return root


def _env(url: str, receipt: str | None = None, **extra: str) -> dict:
    receipt = RECEIPT if receipt is None else receipt
    env = {"DEVWORKSPACE_NAMESPACE": NS, "DEVWORKSPACE_NAME": RUN, "MIGRATION_RUN_NAME": RUN, "PETCLINIC_DB_URL": url, "PETCLINIC_DB_USER": "parity",
           "PETCLINIC_DB_PASSWORD": SECRET}
    if receipt:
        env["PARITY_RUN_RECEIPT"] = receipt
    env.update(extra)
    return env


def main() -> int:
    failures: list[str] = []

    def ok(cond: bool, what: str) -> None:
        if not cond:
            failures.append(what)

    def refuses(root: Path, url: str, why: str, code: str = ri.MISMATCH, **kw) -> None:
        v = ri.check(root, _env(url, **kw))
        ok(v.code == code, "%s: expected %s, got %s (%s)" % (why, code, v.code, v.detail))
        ok(v.blocking_for("reset") and v.blocking_for("parity") and v.blocking_for("startup"),
           "%s: did not block the operations that connect" % why)
        ok(SECRET not in str(v), "%s: a credential value reached the verdict" % why)

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        mig = MIGRATION % (RUN, NS, INSTANCE, RUN, RUN, RUN)
        root = _tree(tmp, mig, "UNSTAMPED")

        # --- the four counterexamples ------------------------------------
        refuses(root, "jdbc:postgresql://%s.other-namespace.svc:5432/parity" % HOST,
                "counterexample 1: the right service in the wrong namespace")
        refuses(root, "jdbc:postgresql://%s.%s.svc:5432/somebody-else" % (HOST, NS),
                "counterexample 2: the right server, the wrong database")
        refuses(root, "jdbc:postgresql://%s-old.%s.svc:5432/parity" % (HOST, NS),
                "counterexample 3: a different host whose name starts with the expected one")
        refuses(root, "jdbc:postgresql://elsewhere.%s.svc:5432/parity?ApplicationName=%s" % (NS, HOST),
                "counterexample 4: the expected name only in a query parameter")
        # the same trick with a semicolon property list
        refuses(root, "jdbc:postgresql://elsewhere.%s.svc:5432/parity;host=%s" % (NS, HOST),
                "counterexample 4b: the expected name only in a semicolon property")

        # a wrong port on the right host is a different endpoint
        refuses(root, "jdbc:postgresql://%s.%s.svc:15432/parity" % (HOST, NS),
                "a wrong port on the right host")

        # --- the accepted spellings, and only those -----------------------
        for spelling in ("%s.%s" % (HOST, NS), "%s.%s.svc" % (HOST, NS),
                         "%s.%s.svc.cluster.local" % (HOST, NS), HOST):
            v = ri.check(root, _env("jdbc:postgresql://%s:5432/parity" % spelling))
            ok(v.code == ri.OK, "%s is the same Service and was refused (%s)" % (spelling, v.detail))
            ok(SECRET not in str(v), "a credential value reached the verdict for %s" % spelling)
        # the bare name only resolves where the server runs: a receipt naming
        # another namespace makes the short form somebody else's service
        v = ri.check(root, _env("jdbc:postgresql://%s:5432/parity" % HOST,
                                receipt=RECEIPT.replace("namespace=%s" % NS, "namespace=elsewhere")))
        ok(v.code == ri.RECEIPT_MISMATCH,
           "a receipt from another namespace was accepted (%s)" % v.code)

        # --- the receipt --------------------------------------------------
        v = ri.check(root, _env(GOOD_URL, receipt=""))
        ok(v.code == ri.RECEIPT_MISSING, "a run with no platform receipt was accepted (%s)" % v.code)
        v = ri.check(root, _env(GOOD_URL, receipt=RECEIPT.replace("run=%s" % RUN, "run=%s" % OTHER)))
        ok(v.code == ri.RECEIPT_MISMATCH, "another run's receipt was accepted (%s)" % v.code)

        # --- the name collision: demo-v10-retry is not demo-v10 -----------
        v = ri.check(root, _env(GOOD_URL, MIGRATION_RUN_NAME=OTHER))
        ok(v.code == ri.RECEIPT_MISMATCH,
           "a workspace identifying itself as %s accepted %s's database (%s)" % (OTHER, RUN, v.code))
        # and the reverse: the retry run's own assignment does not accept the
        # shorter run's database, which the "<name>,<name>-*" targeting gave it
        retry_root = _tree(tmp, MIGRATION % (OTHER, NS, "%s-parity-postgres.%s" % (OTHER, NS), OTHER, OTHER, OTHER),
                           "UNSTAMPED")
        v = ri.check(retry_root, _env(GOOD_URL, receipt=RECEIPT))
        ok(v.code == ri.RECEIPT_MISMATCH,
           "%s accepted %s's database and receipt (%s)" % (OTHER, RUN, v.code))

        # --- absence is a different finding from wrongness ----------------
        v = ri.check(root, {})
        ok(v.code == ri.MISSING, "absent variables were not RUN_RESOURCES_MISSING (%s)" % v.code)
        for operation in ("reset", "revert", "fixture", "startup", "parity"):
            ok(v.blocking_for(operation), "absence did not block %s" % operation)
        ok(not v.blocking_for("analysis"), "absence blocked static analysis, which the architect permits")
        # a WRONG target blocks analysis too
        wrong = ri.check(root, _env("jdbc:postgresql://%s.other-namespace.svc:5432/parity" % HOST))
        ok(wrong.blocking_for("analysis"), "a wrong target did not block analysis")

        # --- unassigned, and unparseable ----------------------------------
        bare = _tree(tmp, MIGRATION_NO_RESOURCES, "UNSTAMPED")
        v = ri.check(bare, _env(GOOD_URL))
        ok(v.code == ri.UNASSIGNED, "a destination assigned nothing was accepted (%s)" % v.code)
        ok(v.blocking_for("analysis"), "an unassigned destination did not block")
        v = ri.check(root, _env("postgres://%s.%s:5432/parity" % (HOST, NS)))
        ok(v.code == ri.UNPARSEABLE, "a non-JDBC endpoint was accepted (%s)" % v.code)
        v = ri.check(root, _env("jdbc:mysql://%s.%s.svc:5432/parity" % (HOST, NS)))
        ok(v.code == ri.MISMATCH, "an endpoint of another engine was accepted (%s)" % v.code)
        # credentials smuggled into the authority are never an accepted form
        v = ri.check(root, _env("jdbc:postgresql://user:pw@%s.%s.svc:5432/parity" % (HOST, NS)))
        ok(v.code == ri.UNPARSEABLE, "an authority carrying credentials was parsed (%s)" % v.code)

        # --- the legacy exception, bounded --------------------------------
        legacy = _tree(tmp, MIGRATION_NO_RESOURCES, "shared-parity-postgres.%s" % NS)
        ri.LEGACY_ASSIGNMENTS = tmp / 'platform-legacy.json'
        ri.LEGACY_ASSIGNMENTS.write_text(json.dumps({'existing-v9': {
            'instance': 'shared-parity-postgres.' + NS, 'database': 'petclinic',
            'port': 5432, 'engine': 'postgresql'}}))
        v = ri.check(legacy, {"DEVWORKSPACE_NAMESPACE": NS, "DEVWORKSPACE_NAME": "existing-v9", "PETCLINIC_DB_URL": "jdbc:postgresql://shared-parity-postgres.%s.svc:5432/petclinic" % NS,
                              "PETCLINIC_DB_USER": "u", "PETCLINIC_DB_PASSWORD": SECRET})
        ok(v.code == ri.LEGACY, "a pre-per-run destination was refused (%s %s)" % (v.code, v.detail))
        ok(not v.blocking_for("reset"), "the legacy exception blocked the run it exists for")
        # and it is still an ownership check, not a bypass
        v = ri.check(legacy, {"DEVWORKSPACE_NAMESPACE": NS, "DEVWORKSPACE_NAME": "existing-v9", "PETCLINIC_DB_URL": "jdbc:postgresql://somebody-else.%s.svc:5432/petclinic" % NS,
                              "PETCLINIC_DB_USER": "u", "PETCLINIC_DB_PASSWORD": SECRET})
        ok(v.code == ri.MISMATCH, "the legacy exception accepted another instance (%s)" % v.code)
        # a FRESH destination cannot reach it: the golden ships UNSTAMPED
        fresh = _tree(tmp, MIGRATION_NO_RESOURCES, "UNSTAMPED")
        ok(ri.check(fresh, _env(GOOD_URL)).code == ri.UNASSIGNED,
           "a fresh destination reached the legacy exception")

        # A stamped NEW run must not downgrade by deleting its assignment.
        stamped = _tree(tmp, MIGRATION % (RUN, NS, INSTANCE, RUN, RUN, RUN), INSTANCE)
        (stamped / 'migration.yaml').write_text(MIGRATION_NO_RESOURCES)
        v = ri.check(stamped, _env(GOOD_URL.replace('/parity', '/another_database'), receipt=''))
        ok(v.code == ri.UNASSIGNED and v.blocking_for('reset'), 'stamped run downgraded to legacy')
        root = _tree(tmp, MIGRATION % (RUN, NS, INSTANCE, RUN, RUN, RUN), INSTANCE)
        for receipt in (RECEIPT.replace('port=5432', 'port=5544'),
                        RECEIPT.replace('workspace=' + RUN, 'workspace=other'),
                        RECEIPT.replace('engine=postgresql', 'engine=mysql'),
                        RECEIPT.split(';scaffold=')[0],
                        RECEIPT.rsplit('scaffold=', 1)[0] + 'scaffold=' + 'f' * 40):
            ok(ri.check(root, _env(GOOD_URL, receipt)).code == ri.RECEIPT_MISMATCH,
               'invalid receipt binding accepted')
        ok(ri.check(root, _env(GOOD_URL, DEVWORKSPACE_NAME='other')).code == ri.RECEIPT_MISMATCH,
           'actual workspace mismatch accepted')
        ok(ri.check(root, _env(GOOD_URL, DEVWORKSPACE_NAMESPACE='other')).code == ri.RECEIPT_MISMATCH,
           'actual workspace namespace mismatch accepted')
        (root / 'migration.yaml').write_text((root / 'migration.yaml').read_text().replace('server_secret:', 'unassigned_secret:'))
        ok(ri.check(root, _env(GOOD_URL)).code == ri.RECEIPT_MISMATCH,
           'assignment changed since scaffolding accepted')

        # --- require() raises with the typed code -------------------------
        try:
            ri.require(root, "reset", _env("jdbc:postgresql://%s.other-namespace.svc:5432/parity" % HOST))
            failures.append("require() did not raise on a wrong target")
        except SystemExit as exc:
            ok(ri.MISMATCH in str(exc), "require() raised without the typed code: %s" % exc)
            ok(SECRET not in str(exc), "require() printed a credential value")

        (root / "migration.yaml").write_text(MIGRATION % (RUN, NS, INSTANCE, RUN, RUN, RUN))
        # --- the good case ------------------------------------------------
        v = ri.check(root, _env(GOOD_URL, MIGRATION_RUN_NAME=RUN))
        ok(v.code == ri.OK, "this run's own database was refused: %s" % v.detail)
        ok(not any(v.blocking_for(op) for op in ("reset", "fixture", "startup", "parity", "analysis")),
           "this run's own database blocked its own operations")
        ok(SECRET not in str(v), "a credential value reached the verdict")
        ok(ri.fixture_gaps(root, _env(GOOD_URL)) == ["PETCLINIC_ADMIN_CREDENTIAL",
                                                     "PETCLINIC_INVALID_CREDENTIAL"],
           "absent fixture identities were not reported")
        ok(ri.fixture_gaps(root, _env(GOOD_URL, PETCLINIC_ADMIN_CREDENTIAL="a:b",
                                      PETCLINIC_INVALID_CREDENTIAL="c:d")) == [],
           "present fixture identities were reported as gaps")

    if failures:
        for f in failures:
            print("FAIL: %s" % f, file=sys.stderr)
        return 1
    print("OK: run_identity selftest (%d counterexamples refused)" % 7)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
