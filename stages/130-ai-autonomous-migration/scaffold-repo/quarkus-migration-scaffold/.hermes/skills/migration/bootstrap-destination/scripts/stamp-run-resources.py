#!/usr/bin/env python3
"""Bind the decided datasource to THIS RUN's own database (dest-init, then M2).

Every migration run gets its own parity database, its own credentials secret
and its own fixture identities, created by trusted platform code when the
workspace is initiated. The golden therefore cannot name a database: a
hardcoded `instance` is the single object two runs would share, and the first
thing a second run's reset would destroy.

So the golden ships `instance: UNSTAMPED` and this script writes the real one,
from the only file that knows it -- `migration.yaml` `resources`, stamped by
the RHDH app-migration skeleton from the run's name: the assignment the
platform issued for this run. One producer, two consumers, no inference.

What it does NOT change is the ADR-009 contract. The keys stay the keys, the
credentials stay environment references by NAME, and no value is read, printed
or written anywhere. `jdbc_url_env`, `username_env` and `password_env` are
compared rather than overwritten: if the manifests and the decision disagree
about which variable carries the URL, that is a defect in the run's own
resources and this refuses instead of papering over it.

A missing resource block refuses unless the platform explicitly assigned this
existing workspace a legacy endpoint in /etc/hermes/migration-legacy-assignments.json.
A stamped instance alone never authorizes legacy access. Fresh runs cannot
remove their resource block to bypass receipt verification.

`--verify` additionally measures what the workspace actually received, through
the one ownership check every destructive entry point uses
(`.hermes/lib/planner/run_identity.py`): the endpoint is PARSED into host, port
and database and compared field by field with the assignment and the platform
receipt. It is never a substring test — the architect demonstrated on
2026-09-22 that a substring test passes a wrong namespace, a wrong database, a
different host with the expected prefix, and another host entirely carrying the
expected name only in a query parameter.

VERIFICATION RUNS FIRST, and a refusal writes nothing. The reviewed version
stamped the decision and then verified, so a workspace holding another run's
database ended the step with a stamped decision that a later M2 stamp happily
confirmed. Ownership is established before the decision records an instance.

Outcomes, and they are not the same finding: the run's own database -> stamp
and proceed; the variables absent -> WARN, static analysis may continue and
oracle capture may not; anything else (another run's database, an unparseable
endpoint, a missing or disagreeing platform receipt) -> REFUSE, nothing is
written, and the workspace's postStart does not start the migration.

The verdict is written to `.hermes/RUN-RESOURCES-STATUS` so the Operator reads
it without re-running anything.

  stamp-run-resources.py --root /projects/modernized [--verify] [--check-only]

Exit 0 stamped (or nothing to stamp), 1 refused, 2 usage."""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

UNSTAMPED = "UNSTAMPED"
STATUS_REL = Path(".hermes") / "RUN-RESOURCES-STATUS"
ENV_FIELDS = ("jdbc_url_env", "username_env", "password_env")


def _ensure_hermes_lib() -> None:
    p = Path(__file__).resolve()
    for parent in p.parents:
        lib = parent / "lib"
        if (lib / ".hermes-lib").is_file():
            s = str(lib)
            if s not in sys.path:
                sys.path.insert(0, s)
            return
    raise SystemExit("FAIL: RUN_RESOURCES .hermes/lib marker missing")


_ensure_hermes_lib()
from planner import run_identity  # noqa: E402
from planner.paths import DECISIONS, MIGRATION  # noqa: E402
from planner.yamlite import load_yaml  # noqa: E402


def run_resources(root: Path) -> dict:
    """migration.yaml `resources`, or {} when this destination predates it."""
    path = root / MIGRATION
    if not path.is_file():
        return {}
    doc = load_yaml(path)
    res = doc.get("resources") if isinstance(doc, dict) else None
    return dict(res) if isinstance(res, dict) else {}


def parity_database(resources: dict) -> dict:
    db = resources.get("parity_database")
    return dict(db) if isinstance(db, dict) else {}


def _datasource_span(lines: list[str]) -> tuple[int, int]:
    """[start, end) of the top-level `datasource:` block, or (-1, -1)."""
    start = -1
    for i, line in enumerate(lines):
        if line.rstrip() == "datasource:":
            start = i
            break
    if start < 0:
        return -1, -1
    for j in range(start + 1, len(lines)):
        s = lines[j]
        if s.strip() and not s.startswith((" ", "\t", "#")):
            return start, j
    return start, len(lines)


def _read_field(lines: list[str], start: int, end: int, key: str) -> tuple[int, str]:
    """(line index, value) of `  <key>: <value>` inside the block, or (-1, "")."""
    pat = re.compile(r"^(\s+)%s:\s*(.*?)\s*$" % re.escape(key))
    for i in range(start + 1, end):
        m = pat.match(lines[i])
        if m and len(m.group(1)) == 2:
            value = m.group(2)
            if value and value[0] in "\"'" and value[-1] == value[0] and len(value) > 1:
                value = value[1:-1]
            return i, value
    return -1, ""


def stamp(root: Path, check_only: bool = False) -> tuple[int, list[str]]:
    """(exit code, report lines). Writes decisions.yaml only when it must."""
    out: list[str] = []
    dec_path = root / DECISIONS
    if not dec_path.is_file():
        return 1, ["REFUSE: RUN_RESOURCES %s is not in this tree" % DECISIONS]
    db = parity_database(run_resources(root))
    lines = dec_path.read_text(encoding="utf-8").splitlines()
    start, end = _datasource_span(lines)
    if start < 0:
        return 1, ["REFUSE: RUN_RESOURCES %s has no top-level datasource block" % DECISIONS]
    idx, current = _read_field(lines, start, end, "instance")
    if idx < 0:
        return 1, ["REFUSE: RUN_RESOURCES %s datasource names no instance key" % DECISIONS]

    if not db:
        if not run_identity.assignment(root).get("legacy"):
            return 1, ["REFUSE: RUN_RESOURCES_UNASSIGNED migration.yaml carries no resources.parity_database "
                       "and this workspace has no platform-authorized legacy assignment"]
        return 0, ["NOTE: explicit platform legacy assignment; datasource.instance stays %s" % current]

    want = str(db.get("instance") or "")
    if not want:
        return 1, ["REFUSE: RUN_RESOURCES %s resources.parity_database names no instance" % MIGRATION]

    # The variables are a CONTRACT, not a value to be rewritten: the run's
    # manifests write the secret under these names and the decision reads them
    # under these names. A disagreement is a defect in the run's resources.
    mismatched = []
    for field in ENV_FIELDS:
        declared = str(db.get(field) or "")
        i, decided = _read_field(lines, start, end, field)
        if not declared or i < 0:
            continue
        if declared != decided:
            mismatched.append("%s: %s says %r, %s says %r"
                              % (field, MIGRATION, declared, DECISIONS, decided))
    if mismatched:
        return 1, ["REFUSE: RUN_RESOURCES the run's resources and the decision name different "
                   "environment variables (%s)" % "; ".join(mismatched)]

    if current == want:
        out.append("OK: %s datasource.instance already names this run's database (%s)" % (DECISIONS, want))
        return 0, out
    if current not in (UNSTAMPED, ""):
        # An already-stamped destination naming somebody else's instance is the
        # defect this whole design exists to prevent. Equality, not a prefix:
        # `<run>-parity-postgres.ns` and `<run>-parity-postgres-old.ns` share a
        # prefix and are two different servers.
        out.append("NOTE: %s datasource.instance named %s, which is not this run's database (%s)"
                   % (DECISIONS, current, want))
    if check_only:
        return 1, out + ["REFUSE: RUN_RESOURCES %s datasource.instance is %r; this run's database is %s"
                         % (DECISIONS, current, want)]
    indent = re.match(r"^(\s*)", lines[idx]).group(1)
    lines[idx] = "%sinstance: %s" % (indent, want)
    dec_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    out.append("STAMPED: %s datasource.instance = %s (from %s resources.parity_database)"
               % (DECISIONS, want, MIGRATION))
    return 0, out


def verify_environment(root: Path) -> tuple[int, list[str]]:
    """Whose database is this workspace holding? Parsed, not matched.

    One decision, made by the module every reset, fixture mutation, startup and
    parity run also calls, so the answer cannot differ between the step that
    checks and the step that connects."""
    out: list[str] = []
    resources = run_resources(root)
    verdict = run_identity.check(root)
    if not resources:
        # A pre-per-run destination has no assignment to verify against, but it
        # still has an instance the decision names, and pointing it at somebody
        # else's server is the same defect. The reduced check applies. A
        # destination that names nothing at all is stamp()'s refusal, which
        # says what to do about it, so it is not pre-empted here; and absent
        # variables are a WARN at dest-init, not a stop.
        if verdict.code == run_identity.UNASSIGNED:
            return 0, []
        if verdict.blocking_for("analysis"):
            return 1, ["REFUSE: %s %s" % (verdict.code, verdict.detail)]
        return 0, ["NOTE: no resources block in %s; %s" % (MIGRATION, verdict.detail)]
    if verdict.code == run_identity.MISSING:
        out.append("WARN: %s The run's resources may not exist yet (the platform "
                   "provision-migration-run Pipeline) or this workspace started before they did."
                   % verdict.detail)
    elif verdict.blocking_for("reset"):
        # Never print the URL: it is not a secret, but it is one substitution
        # away from being read as one. Name the finding, not the string.
        return 1, ["REFUSE: %s %s Stop before capturing anything against it."
                   % (verdict.code, verdict.detail)]
    else:
        out.append("OK: %s" % verdict.detail)
    missing_fixtures = run_identity.fixture_gaps(root)
    fixtures = dict(resources.get("fixture_credentials") or {}) \
        if isinstance(resources.get("fixture_credentials"), dict) else {}
    if missing_fixtures:
        out.append("WARN: %s not set (secret %s); ADR-014 fixture scenarios cannot authenticate."
                   % (", ".join(missing_fixtures), fixtures.get("secret") or "<fixture secret>"))
    elif fixtures.get("env"):
        out.append("OK: the fixture identity variables are set (%d, from %s)"
                   % (len(fixtures.get("env") or []), fixtures.get("secret")))
    return 0, out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True)
    ap.add_argument("--verify", action="store_true",
                    help="also measure the environment this workspace received")
    ap.add_argument("--check-only", action="store_true",
                    help="refuse an unstamped decision instead of writing it (gate use)")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    if not root.is_dir():
        print("FAIL: --root must be an existing directory", file=sys.stderr)
        return 2

    # Ownership FIRST, and ALWAYS -- `--verify` decides how much is REPORTED,
    # never whether the question is asked. A refused verification leaves
    # decisions.yaml exactly as it was, because a stamped decision is what a
    # later step reads as settled: the reviewed version stamped first, so the
    # M2 call (which passes no --verify) found the wrong instance already
    # written and agreed with it.
    rc, report = verify_environment(root)
    if not args.verify and rc == 0:
        report = []
    if rc == 0:
        src, sreport = stamp(root, check_only=args.check_only)
        report += sreport
        rc = src
    for line in report:
        print(line, file=sys.stderr if line.startswith("REFUSE") else sys.stdout)
    status = root / STATUS_REL
    try:
        status.parent.mkdir(parents=True, exist_ok=True)
        status.write_text("result=%s\n%s\n" % ("ok" if rc == 0 else "refused", "\n".join(report)),
                          encoding="utf-8")
    except OSError:
        pass
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
