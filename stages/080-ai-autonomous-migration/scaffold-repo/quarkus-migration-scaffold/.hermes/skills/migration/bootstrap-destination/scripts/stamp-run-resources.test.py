#!/usr/bin/env python3
"""stamp-run-resources selftest, on synthetic trees that are not the specimen.

Exits proven here:
  - a run whose migration.yaml declares resources gets decisions.yaml
    datasource.instance rewritten to ITS OWN database, with the file's prose,
    comments and every other key byte-identical; a second run changes nothing
  - the ADR-009 contract survives: jdbc_url_env / username_env / password_env
    are compared, not rewritten, and a disagreement between the run's
    resources and the decision REFUSES and writes nothing
  - a destination that predates per-run resources (no resources block, an
    instance already named) is left alone and says so -- the backward
    compatibility the running v9 depends on
  - a destination with neither a resources block nor a named instance refuses
    rather than planning against nothing
  - --check-only never writes
  - --verify: absent variables WARN, variables naming ANOTHER run's database
    REFUSE, variables naming this run's database pass; no credential value is
    ever read or printed
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
  manifests: k8s-run
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


def _tree(tmp: Path, migration: str, instance: str, url_env: str = "DEMO_DB_URL") -> Path:
    root = Path(tempfile.mkdtemp(dir=tmp))
    (root / "decisions.yaml").write_text(DECISIONS_TEMPLATE % (instance, url_env), encoding="utf-8")
    (root / "migration.yaml").write_text(migration, encoding="utf-8")
    return root


def _run(root: Path, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    e = dict(os.environ)
    for k in ("DEMO_DB_URL", "DEMO_DB_USER", "DEMO_DB_PASSWORD",
              "DEMO_ADMIN_CREDENTIAL", "DEMO_INVALID_CREDENTIAL"):
        e.pop(k, None)
    e.update(env or {})
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
        ok(r.returncode == 0, "a pre-per-run destination was refused: %s" % r.stderr)
        ok("no resources block" in r.stdout, "pre-per-run destination not explained: %s" % r.stdout)
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
        ok("oracle capture cannot" in r.stdout, "the WARN did not say what it costs")

        root = _tree(tmp, MIGRATION_WITH_RESOURCES % "DEMO_DB_URL", "UNSTAMPED")
        r = _run(root, "--verify", env={
            "DEMO_DB_URL": "jdbc:postgresql://some-other-run-parity-postgres.wksp-ai-developer.svc:5432/parity",
            "DEMO_DB_USER": "parity", "DEMO_DB_PASSWORD": "not-read"})
        ok(r.returncode == 1, "another run's database was accepted")
        ok("another run's parity database" in r.stderr, "cross-run refusal not named: %s" % r.stderr)
        ok("not-read" not in (r.stdout + r.stderr), "a credential value reached the output")

        root = _tree(tmp, MIGRATION_WITH_RESOURCES % "DEMO_DB_URL", "UNSTAMPED")
        r = _run(root, "--verify", env={
            "DEMO_DB_URL": "jdbc:postgresql://demo-run-v2-parity-postgres.wksp-ai-developer.svc:5432/parity",
            "DEMO_DB_USER": "parity", "DEMO_DB_PASSWORD": "not-read",
            "DEMO_ADMIN_CREDENTIAL": "a:b", "DEMO_INVALID_CREDENTIAL": "c:d"})
        ok(r.returncode == 0, "this run's own database was refused: %s" % r.stderr)
        ok("name this run's database" in r.stdout, "verify did not confirm the binding: %s" % r.stdout)
        ok("fixture identity variables are set" in r.stdout, "fixture identities not verified")
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
