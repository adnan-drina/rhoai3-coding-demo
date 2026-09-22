#!/usr/bin/env python3
"""stamp-run-resources selftest, on synthetic trees that are not the specimen.

Exits proven here:
  - a run whose migration.yaml declares resources gets decisions.yaml
    datasource.instance rewritten to ITS OWN database, with the file's prose,
    comments and every other key byte-identical; a second run changes nothing
  - the ADR-009 contract survives: jdbc_url_env / username_env / password_env
    are compared, not rewritten, and a disagreement between the run's
    resources and the decision REFUSES and writes nothing
  - a destination without resources cannot gain a legacy exemption merely
    because its decisions already name an instance
  - a destination with neither a resources block nor a named instance refuses
    rather than planning against nothing
  - --check-only never writes
  - --verify: absent variables WARN, variables naming ANOTHER run's database
    REFUSE, variables naming this run's database pass; no credential value is
    ever read or printed
  - a REFUSED verification writes NOTHING -- not decisions.yaml, and therefore
    not a stamped instance a later step would read as settled. This is the
    architect's 2026-09-22 finding: the reviewed version stamped first and
    verified second, so a workspace holding another run's database ended
    dest-init with a stamped decision and a subsequent M2 stamp returned 0
  - a run whose endpoint is right but whose platform receipt is absent or
    describes another run is refused: a name is not a receipt
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "stamp-run-resources.py"

DECISIONS_TEMPLATE = """# A decisions file with prose, because the real one is mostly prose and a
# stamp that reformats it is a stamp that loses the reasoning.
adrs:
  - id: ADR-009
    status: accepted
    title: the effective database is a decision

datasource:
  adr: ADR-009
  db_kind: postgresql
  db_version: "16"
  jdbc_extension: io.quarkus:quarkus-jdbc-postgresql
  profile: prod
  instance: %s
  jdbc_url_env: %s
  username_env: DEMO_DB_USER
  password_env: DEMO_DB_PASSWORD
  reset_procedure: drops and recreates the public schema
  schema_owner: source-assets
  hibernate_generation: none

security:
  adr: ADR-009
"""

MIGRATION_WITH_RESOURCES = """migration:
  target: quarkus
resources:
  run: demo-run-v2
  namespace: wksp-ai-developer
  receipt_env: PARITY_RUN_RECEIPT
  parity_database:
    instance: demo-run-v2-parity-postgres.wksp-ai-developer
    database: parity
    server_secret: demo-run-v2-parity-postgres
    workspace_secret: demo-run-v2-parity-db
    jdbc_url_env: %s
    username_env: DEMO_DB_USER
    password_env: DEMO_DB_PASSWORD
  fixture_credentials:
    secret: demo-run-v2-parity-credentials
    env:
      - DEMO_ADMIN_CREDENTIAL
      - DEMO_INVALID_CREDENTIAL
"""

MIGRATION_NO_RESOURCES = """migration:
  target: quarkus
"""

GOOD_URL = "jdbc:postgresql://demo-run-v2-parity-postgres.wksp-ai-developer.svc:5432/parity"
RECEIPT = ("run=demo-run-v2;namespace=wksp-ai-developer;workspace=demo-run-v2;"
           "host=demo-run-v2-parity-postgres;port=5432;database=parity;engine=postgresql;scaffold=abc123")


def _tree(tmp: Path, migration: str, instance: str, url_env: str = "DEMO_DB_URL") -> Path:
    root = Path(tempfile.mkdtemp(dir=tmp))
    (root / "decisions.yaml").write_text(DECISIONS_TEMPLATE % (instance, url_env), encoding="utf-8")
    (root / "migration.yaml").write_text(migration, encoding="utf-8")
    subprocess.run(['git', 'init', '-q', str(root)], check=True)
    subprocess.run(['git', '-C', str(root), 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(root), '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.test', 'commit', '-qm', 'scaffold'], check=True)
    return root


def _run(root: Path, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    e = dict(os.environ)
    for k in ("DEMO_DB_URL", "DEMO_DB_USER", "DEMO_DB_PASSWORD",
              "DEMO_ADMIN_CREDENTIAL", "DEMO_INVALID_CREDENTIAL", "PARITY_RUN_RECEIPT"):
        e.pop(k, None)
    e.update(env or {})
    e['DEVWORKSPACE_NAME'] = e['MIGRATION_RUN_NAME'] = 'demo-run-v2'
    e['DEVWORKSPACE_NAMESPACE'] = 'wksp-ai-developer'
    if e.get('PARITY_RUN_RECEIPT') == RECEIPT:
        sha = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
        e['PARITY_RUN_RECEIPT'] = RECEIPT.replace('scaffold=abc123', 'scaffold=' + sha)
    return subprocess.run([sys.executable, str(SCRIPT), "--root", str(root), *args],
                          capture_output=True, text=True, env=e)


def main() -> int:
    failures: list[str] = []

    def ok(cond: bool, what: str) -> None:
        if not cond:
            failures.append(what)

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        # 1. stamps this run's own database, keeps everything else byte-identical
        root = _tree(tmp, MIGRATION_WITH_RESOURCES % "DEMO_DB_URL", "UNSTAMPED")
        before = (root / "decisions.yaml").read_text(encoding="utf-8")
        r = _run(root)
        after = (root / "decisions.yaml").read_text(encoding="utf-8")
        ok(r.returncode == 0, "stamp exited %d: %s" % (r.returncode, r.stderr))
        ok("instance: demo-run-v2-parity-postgres.wksp-ai-developer" in after, "instance not stamped")
        ok("STAMPED" in r.stdout, "stamp did not report STAMPED")
        diff = [(a, b) for a, b in zip(before.splitlines(), after.splitlines()) if a != b]
        ok(len(diff) == 1 and diff[0][0].strip() == "instance: UNSTAMPED",
           "stamp changed more than the instance line: %r" % (diff,))
        ok(len(before.splitlines()) == len(after.splitlines()), "stamp changed the line count")

        # 2. idempotent
        r2 = _run(root)
        ok(r2.returncode == 0 and "already names this run" in r2.stdout,
           "second stamp did not report unchanged: %s%s" % (r2.stdout, r2.stderr))
        ok((root / "decisions.yaml").read_text(encoding="utf-8") == after, "second stamp rewrote the file")

        # 3. the env-var contract is compared, never rewritten
        root = _tree(tmp, MIGRATION_WITH_RESOURCES % "OTHER_DB_URL", "UNSTAMPED")
        before = (root / "decisions.yaml").read_text(encoding="utf-8")
        r = _run(root)
        ok(r.returncode == 1, "an env-var disagreement did not refuse")
        ok("different environment variables" in r.stderr, "refusal did not name the disagreement: %s" % r.stderr)
        ok((root / "decisions.yaml").read_text(encoding="utf-8") == before,
           "a refused stamp still wrote decisions.yaml")

        # 4. pre-per-run destination: left alone, and says so
        root = _tree(tmp, MIGRATION_NO_RESOURCES, "shared-parity-postgres.wksp-ai-developer")
        before = (root / "decisions.yaml").read_text(encoding="utf-8")
        r = _run(root)
        ok(r.returncode == 1, "unmarked legacy shape was accepted")
        ok("UNASSIGNED" in r.stderr, "missing legacy authorization not explained")
        ok((root / "decisions.yaml").read_text(encoding="utf-8") == before,
           "a pre-per-run destination was rewritten")

        # 5. neither a resources block nor a named instance -> refuse
        root = _tree(tmp, MIGRATION_NO_RESOURCES, "UNSTAMPED")
        r = _run(root)
        ok(r.returncode == 1 and "carries no resources.parity_database" in r.stderr,
           "an unstampable destination did not refuse: %s%s" % (r.stdout, r.stderr))

        # 6. --check-only never writes
        root = _tree(tmp, MIGRATION_WITH_RESOURCES % "DEMO_DB_URL", "UNSTAMPED")
        before = (root / "decisions.yaml").read_text(encoding="utf-8")
        r = _run(root, "--check-only")
        ok(r.returncode == 1, "--check-only accepted an unstamped decision")
        ok((root / "decisions.yaml").read_text(encoding="utf-8") == before, "--check-only wrote the file")

        # 7. --verify, three outcomes
        root = _tree(tmp, MIGRATION_WITH_RESOURCES % "DEMO_DB_URL", "UNSTAMPED")
        r = _run(root, "--verify")
        ok(r.returncode == 0 and "WARN" in r.stdout, "absent variables were not a WARN: %s%s" % (r.stdout, r.stderr))
        ok("static analysis may continue" in r.stdout, "the WARN did not say what it costs")

        root = _tree(tmp, MIGRATION_WITH_RESOURCES % "DEMO_DB_URL", "UNSTAMPED")
        before = (root / "decisions.yaml").read_text(encoding="utf-8")
        r = _run(root, "--verify", env={
            "DEMO_DB_URL": "jdbc:postgresql://some-other-run-parity-postgres.wksp-ai-developer.svc:5432/parity",
            "DEMO_DB_USER": "parity", "DEMO_DB_PASSWORD": "not-read",
            "PARITY_RUN_RECEIPT": RECEIPT})
        ok(r.returncode == 1, "another run's database was accepted")
        ok("RUN_RESOURCES_MISMATCH" in r.stderr, "cross-run refusal not typed: %s" % r.stderr)
        ok("not-read" not in (r.stdout + r.stderr), "a credential value reached the output")
        # THE DEFECT: a refused verification must leave the decision unstamped,
        # or the next stamp -- M2's, without --verify -- finds it already
        # settled and agrees.
        ok((root / "decisions.yaml").read_text(encoding="utf-8") == before,
           "a REFUSED verification still stamped decisions.yaml")
        ok((root / ".hermes" / "RUN-RESOURCES-STATUS").read_text(encoding="utf-8").startswith("result=refused"),
           "the status file did not record the refusal")
        # ... and the M2-style call, which passes no --verify, must not be the
        # way around it: the ownership question is asked whether or not the
        # answer is reported.
        r2 = _run(root, env={
            "DEMO_DB_URL": "jdbc:postgresql://some-other-run-parity-postgres.wksp-ai-developer.svc:5432/parity",
            "DEMO_DB_USER": "parity", "DEMO_DB_PASSWORD": "not-read",
            "PARITY_RUN_RECEIPT": RECEIPT})
        ok(r2.returncode == 1 and "RUN_RESOURCES_MISMATCH" in r2.stderr,
           "a stamp without --verify accepted another run's database: %s%s" % (r2.stdout, r2.stderr))
        ok((root / "decisions.yaml").read_text(encoding="utf-8") == before,
           "a stamp without --verify wrote the wrong instance")

        # a right endpoint with no platform receipt: a name is not a receipt
        root = _tree(tmp, MIGRATION_WITH_RESOURCES % "DEMO_DB_URL", "UNSTAMPED")
        before = (root / "decisions.yaml").read_text(encoding="utf-8")
        r = _run(root, "--verify", env={
            "DEMO_DB_URL": GOOD_URL, "DEMO_DB_USER": "parity", "DEMO_DB_PASSWORD": "not-read"})
        ok(r.returncode == 1 and "RUN_RESOURCES_RECEIPT_MISSING" in r.stderr,
           "an unprovable endpoint was accepted: %s%s" % (r.stdout, r.stderr))
        ok((root / "decisions.yaml").read_text(encoding="utf-8") == before,
           "an unprovable endpoint still stamped decisions.yaml")

        root = _tree(tmp, MIGRATION_WITH_RESOURCES % "DEMO_DB_URL", "UNSTAMPED")
        r = _run(root, "--verify", env={
            "DEMO_DB_URL": GOOD_URL, "DEMO_DB_USER": "parity", "DEMO_DB_PASSWORD": "not-read",
            "PARITY_RUN_RECEIPT": RECEIPT,
            "DEMO_ADMIN_CREDENTIAL": "a:b", "DEMO_INVALID_CREDENTIAL": "c:d"})
        ok(r.returncode == 0, "this run's own database was refused: %s%s" % (r.stdout, r.stderr))
        ok("names this run's own database" in r.stdout, "verify did not confirm the binding: %s" % r.stdout)
        ok("fixture identity variables are set" in r.stdout, "fixture identities not verified")
        ok("STAMPED" in r.stdout, "a verified run did not stamp its decision")
        ok("not-read" not in (r.stdout + r.stderr) and "a:b" not in (r.stdout + r.stderr),
           "a credential value reached the output")
        ok((root / ".hermes" / "RUN-RESOURCES-STATUS").is_file(), "no status file written")

    if failures:
        for f in failures:
            print("FAIL: %s" % f, file=sys.stderr)
        return 1
    print("OK: stamp-run-resources selftest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
