#!/usr/bin/env python3
"""Bind the decided datasource to THIS RUN's own database (dest-init, then M2).

Every migration run gets its own parity database, its own credentials secret
and its own fixture identities, created from `k8s-run/` in the destination
repository when the workspace is initiated. The golden therefore cannot name
a database: a hardcoded `instance` is the single object two runs would share,
and the first thing a second run's reset would destroy.

So the golden ships `instance: UNSTAMPED` and this script writes the real one,
from the only file that knows it -- `migration.yaml` `resources`, stamped by
the RHDH app-migration skeleton from the run's name, the same value the
`k8s-run/` manifests were stamped with. One producer, two consumers, no
inference.

What it does NOT change is the ADR-009 contract. The keys stay the keys, the
credentials stay environment references by NAME, and no value is read, printed
or written anywhere. `jdbc_url_env`, `username_env` and `password_env` are
compared rather than overwritten: if the manifests and the decision disagree
about which variable carries the URL, that is a defect in the run's own
resources and this refuses instead of papering over it.

Backward compatible by construction. A destination whose `migration.yaml` has
no `resources` block predates per-run resources (v9 and earlier), and its
decisions.yaml already names the shared instance it was bootstrapped against:
nothing is touched and the reason is printed.

`--verify` additionally measures what the workspace actually received. The
devfile names this run's two secrets, and DevWorkspace Operator 0.41 injects
them into this workspace only (`mount-to-devworkspace-include`). Three
outcomes, and they are not the same finding:

  * the variables are set and the URL names this run's instance -> OK;
  * the variables are absent -> WARN. Argo CD may not have finished creating
    the run's resources when the workspace started, or this is a pre-per-run
    destination. The run can still analyze; it cannot capture oracles;
  * the variables are set and the URL names a DIFFERENT instance -> REFUSE.
    That is another run's database, and every parity result taken against it
    would be evidence about the wrong data.

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
        if current == UNSTAMPED or not current:
            return 1, [
                "REFUSE: RUN_RESOURCES %s datasource.instance is %r and %s carries no "
                "resources.parity_database to stamp it from. This destination was scaffolded "
                "without per-run resources; re-create it from the app-migration template."
                % (DECISIONS, current or "", MIGRATION)
            ]
        out.append("NOTE: %s carries no resources block (pre-per-run destination); "
                   "datasource.instance stays %s" % (MIGRATION, current))
        return 0, out

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
    if current not in (UNSTAMPED, "") and not current.startswith(want.split(".", 1)[0]):
        # An already-stamped destination naming somebody else's instance is the
        # defect this whole design exists to prevent; say which, and stamp it.
        out.append("NOTE: %s datasource.instance named %s, which is not this run's database" % (DECISIONS, current))
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
    """What this workspace actually received, measured against this run's names."""
    out: list[str] = []
    resources = run_resources(root)
    db = parity_database(resources)
    if not db:
        return 0, ["WARN: no resources block in %s; nothing to verify" % MIGRATION]
    instance = str(db.get("instance") or "")
    host = instance.split(".", 1)[0]
    names = [str(db.get(f) or "") for f in ENV_FIELDS if db.get(f)]
    fixtures = resources.get("fixture_credentials")
    fixtures = dict(fixtures) if isinstance(fixtures, dict) else {}
    fixture_env = [str(x) for x in (fixtures.get("env") or [])]

    missing = [n for n in names if not os.environ.get(n)]
    url_var = str(db.get("jdbc_url_env") or "")
    url = os.environ.get(url_var, "") if url_var else ""
    if url and host and host not in url:
        # Never print the URL: it is not a secret, but it is one substitution
        # away from being read as one. Name the instance, not the string.
        return 1, ["REFUSE: RUN_RESOURCES %s is set but does not name this run's database (%s). "
                   "This workspace received another run's parity database; stop before capturing "
                   "anything against it." % (url_var, instance)]
    if missing:
        out.append("WARN: %s not set in this workspace (secret %s). The run's resources may not be "
                   "created yet (Argo CD Application run-%s-resources) or the workspace started "
                   "before they were; analysis can proceed, oracle capture cannot."
                   % (", ".join(missing), db.get("workspace_secret") or "<workspace secret>",
                      resources.get("run") or "<run>"))
    elif url:
        out.append("OK: the datasource variables are set and name this run's database (%s)" % instance)
    missing_fixtures = [n for n in fixture_env if not os.environ.get(n)]
    if missing_fixtures:
        out.append("WARN: %s not set (secret %s); ADR-014 fixture scenarios cannot authenticate."
                   % (", ".join(missing_fixtures), fixtures.get("secret") or "<fixture secret>"))
    elif fixture_env:
        out.append("OK: the fixture identity variables are set (%d, from %s)"
                   % (len(fixture_env), fixtures.get("secret")))
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

    rc, report = stamp(root, check_only=args.check_only)
    if args.verify and rc == 0:
        vrc, vreport = verify_environment(root)
        report += vreport
        rc = rc or vrc
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
