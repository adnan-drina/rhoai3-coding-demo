"""Which run is this, and what budget did it declare? Read, never assumed.

The golden scaffold is reusable: it is fetched unchanged for every run. Until
2026-09-24 it also carried run-budget.json and run-configuration.json naming
run v11 with fixed timestamps, and Developer Hub copied both into every new
destination, so creating v12 would have meant editing and republishing the
golden -- or, worse, a v12 destination silently carrying v11's declaration.

Two files now say two different things, and come from two different places:

  run-defaults.json   GOLDEN. What every run inherits: budget limits, the
                      clock definition, M5 limits, model/image/runtime pins.
                      Configured values, identical for every run, never a
                      claim that anything is ready.
  run-budget.json     FACTORY. Written by the app-migration template into the
                      destination's initial commit: this run's name, the
                      scaffolder task that declared it, and a pointer to the
                      defaults it binds.

WHEN WAS THE BUDGET DECLARED? The installed scaffolder has no clock: its
templating offers four filters (parseRepoUrl, parseEntityRef, pick,
projectSlug), no globals, and a task context holding only the task id. So the
factory writes no timestamp. The declaration's defining event is the commit
that introduces it -- the destination's initial commit, created by the same
scaffolder task -- and its time is that commit's time. Nothing here invents a
time, a deadline, a source commit or a readiness result before the event that
defines it: the deadline needs the clock start (the earlier of that commit and
M1 dispatch), and the legacy source commit is recorded when it is cloned.

A declaration is only a declaration if the run cannot rewrite it, so:

  * it must be present in the repository's ONE root commit (added later, it
    was declared after the run began -- that is not a budget, it is a wish);
  * the declaration AND the defaults it binds must be byte-identical at HEAD
    and in the working tree to what that root commit introduced (reopening,
    restarting or retrying a workspace re-reads the same bytes, so it can
    never renew a budget);
  * when the platform's provisioning receipt is present, the root commit must
    be the scaffolding commit the platform itself recorded (a rewritten
    history with a fresh root is not the run the platform provisioned);
  * its run must be the run the migration.yaml assignment names and, inside a
    workspace, MIGRATION_RUN_NAME -- which admission policy holds equal to the
    DevWorkspace name.

TYPED OUTCOMES. Each names what to do; none falls back to another run:

  OK                            factory declaration for this run, intact
  LEGACY                        a pre-2026-09-24 self-contained declaration
                                (schema v1), read only for history
                                (allow_legacy): the v10/v11 records
  RUN_DECLARATION_MISSING       no run-budget.json
  RUN_DECLARATION_DEFAULTS_MISSING  no run-defaults.json to bind
  RUN_DECLARATION_INVALID       unreadable, wrong schema, unrendered, or
                                missing a required field
  RUN_DECLARATION_FOREIGN       names a run other than this one
  RUN_DECLARATION_STALE         an earlier generation's per-run file: a v1
                                declaration on a launch path, or a
                                run-configuration.json riding beside a v2 one
  RUN_DECLARATION_NOT_INITIAL   not introduced by the destination's initial
                                commit
  RUN_DECLARATION_ALTERED       declaration or defaults changed since then
  RUN_DECLARATION_UNVERIFIABLE  no usable history (not a repository, shallow,
                                several roots, or git unavailable)
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from planner.paths import MIGRATION
from planner.yamlite import load_yaml

DECLARATION = Path("run-budget.json")
DEFAULTS = Path("run-defaults.json")
# Per-run files an earlier scaffold generation shipped from the golden.
STALE_FILES = (Path("run-configuration.json"),)

SCHEMA = "rhoai3.run-budget/v2"
LEGACY_SCHEMA = "rhoai3.run-budget/v1"
DEFAULTS_SCHEMA = "rhoai3.run-defaults/v1"
LIMITS_REF = "run-defaults.json#/budget"
DECLARED_AT_SOURCE = "initial-commit"

RUN_NAME_ENV = "MIGRATION_RUN_NAME"
RECEIPT_ENV = "PARITY_RUN_RECEIPT"

OK = "OK"
LEGACY = "LEGACY"
MISSING = "RUN_DECLARATION_MISSING"
DEFAULTS_MISSING = "RUN_DECLARATION_DEFAULTS_MISSING"
INVALID = "RUN_DECLARATION_INVALID"
FOREIGN = "RUN_DECLARATION_FOREIGN"
STALE = "RUN_DECLARATION_STALE"
NOT_INITIAL = "RUN_DECLARATION_NOT_INITIAL"
ALTERED = "RUN_DECLARATION_ALTERED"
UNVERIFIABLE = "RUN_DECLARATION_UNVERIFIABLE"

RECREATE = ("Recreate the run from the Developer Hub app-migration template; never copy "
            "another run's declaration.")
# A factory value that reached the file unrendered: the template did not stamp it.
_UNRENDERED = re.compile(r"\$\{\{|\{\{|\{%")


class Declaration:
    def __init__(self, code: str, detail: str, run_id: str = "", budget: dict | None = None,
                 declared_at: str = "", initial_commit: str = ""):
        self.code = code
        self.detail = detail
        self.run_id = run_id
        self.budget = budget or {}
        self.declared_at = declared_at
        self.initial_commit = initial_commit

    @property
    def ok(self) -> bool:
        return self.code in (OK, LEGACY)

    def __str__(self) -> str:
        return "%s: %s" % (self.code, self.detail)


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-c", "safe.directory=" + str(root), "-C", str(root), *args],
                          capture_output=True, timeout=15)


def _history(root: Path) -> tuple[str, str] | Declaration:
    """(root commit, its UTC time as ...Z), or the reason there is no single honest answer."""
    try:
        shallow = _git(root, "rev-parse", "--is-shallow-repository")
        if shallow.returncode != 0:
            return Declaration(UNVERIFIABLE, "%s is not a git repository, so the commit that declared "
                                             "the budget cannot be found" % root)
        if shallow.stdout.decode().strip() == "true":
            return Declaration(UNVERIFIABLE, "the clone is shallow, so its first commit is not visible; "
                                             "run `git fetch --unshallow` and check again")
        roots = _git(root, "rev-list", "--max-parents=0", "HEAD").stdout.decode().split()
        if len(roots) != 1:
            return Declaration(UNVERIFIABLE, "the history has %d root commits; a destination has exactly "
                                             "one, the scaffolding commit" % len(roots))
        epoch = int(_git(root, "show", "-s", "--format=%ct", roots[0]).stdout.decode().strip())
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        return Declaration(UNVERIFIABLE, "git is unavailable or the initial commit has no time (%s)" % exc)
    when = datetime.datetime.fromtimestamp(epoch, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return roots[0], when


def _blob(root: Path, rev: str, rel: Path) -> bytes | None:
    got = _git(root, "show", "%s:%s" % (rev, rel.as_posix()))
    return got.stdout if got.returncode == 0 else None


def _unchanged(root: Path, first: str, rel: Path) -> str:
    """Why `rel` is not what the initial commit introduced; '' when it is."""
    original = _blob(root, first, rel)
    if original is None:
        return "%s is not in the initial commit %s" % (rel, first[:12])
    if _blob(root, "HEAD", rel) != original:
        return "%s was changed by a later commit" % rel
    path = root / rel
    if not path.is_file() or path.read_bytes() != original:
        return "%s differs in the working tree" % rel
    return ""


def _assigned_run(root: Path) -> str:
    doc = load_yaml(root / MIGRATION) if (root / MIGRATION).is_file() else {}
    res = doc.get("resources") if isinstance(doc, dict) else None
    return str(res.get("run") or "") if isinstance(res, dict) else ""


def _receipt_scaffold(environ: dict) -> str:
    text = environ.get(RECEIPT_ENV, "")
    fields = dict(p.split("=", 1) for p in text.split(";") if "=" in p)
    return fields.get("scaffold", "").strip()


def _identity(run_id: str, root: Path, expected: str) -> str:
    """Why `run_id` is not this run; '' when every available witness agrees."""
    assigned = _assigned_run(root)
    for witness, name in (("migration.yaml resources.run", assigned),
                          ("this workspace (%s / the expected run)" % RUN_NAME_ENV, expected)):
        if name and name != run_id:
            return "the declaration names run %r and %s names %r" % (run_id, witness, name)
    return ""


def _load_json(path: Path) -> tuple[Any, str]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), ""
    except (OSError, ValueError) as exc:
        return None, "%s is not readable JSON (%s)" % (path.name, exc)


def load(root: Path, expected_run: str | None = None, environ: dict | None = None,
         allow_legacy: bool = False) -> Declaration:
    """This destination's run declaration, or the typed reason it has none.

    `allow_legacy` is for reading HISTORY (run-report on v10/v11) and nothing
    else. A legacy file labels its run (`"v11"`) rather than naming it, so its
    identity cannot be checked by equality -- and it is exactly what a stale
    golden would leave in a new destination. Launch paths never pass it.
    """
    root = Path(root)
    env = dict(os.environ if environ is None else environ)
    expected = (expected_run if expected_run is not None else env.get(RUN_NAME_ENV, "")).strip()

    path = root / DECLARATION
    if not path.is_file():
        return Declaration(MISSING, "%s is absent. The app-migration template writes it into the "
                                    "destination's initial commit; its absence means this repository was "
                                    "not created by the current factory, or the golden and the template "
                                    "are out of step. %s" % (DECLARATION, RECREATE))
    doc, why = _load_json(path)
    if not isinstance(doc, dict):
        return Declaration(INVALID, why or "%s is not a JSON object" % DECLARATION)
    schema = doc.get("schema")
    run_id = doc.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip() or _UNRENDERED.search(run_id):
        return Declaration(INVALID, "%s carries no rendered run_id; the factory did not stamp it. %s"
                           % (DECLARATION, RECREATE))
    if schema == LEGACY_SCHEMA and not allow_legacy:
        return Declaration(STALE, "%s is a pre-2026-09-24 declaration labelled run %r, copied from an "
                                  "earlier golden. It cannot declare this run. %s"
                           % (DECLARATION, run_id, RECREATE), run_id)
    if schema not in (SCHEMA, LEGACY_SCHEMA):
        return Declaration(INVALID, "%s has schema %r; expected %r" % (DECLARATION, schema, SCHEMA), run_id)
    if schema == SCHEMA:
        mismatch = _identity(run_id, root, expected)
        if mismatch:
            return Declaration(FOREIGN, "%s. This is another run's budget; nothing may run against it. %s"
                               % (mismatch, RECREATE), run_id)

    history = _history(root)
    if isinstance(history, Declaration):
        history.run_id = run_id
        return history
    first, first_at = history

    if schema == LEGACY_SCHEMA:
        return _legacy(root, doc, run_id, first, first_at)
    if _UNRENDERED.search(path.read_text(encoding="utf-8")):
        return Declaration(INVALID, "%s still contains template markup; the factory did not render it. %s"
                           % (DECLARATION, RECREATE), run_id)
    declared_by = doc.get("declared_by")
    if (doc.get("limits") != LIMITS_REF or doc.get("declared_at_source") != DECLARED_AT_SOURCE
            or not isinstance(declared_by, dict) or not declared_by.get("template")
            or not declared_by.get("scaffolder_task")):
        return Declaration(INVALID, "%s must name limits %r, declared_at_source %r and the template and "
                                    "scaffolder task that declared it" % (DECLARATION, LIMITS_REF,
                                                                          DECLARED_AT_SOURCE), run_id)
    for stale in STALE_FILES:
        if (root / stale).exists():
            other, _ = _load_json(root / stale)
            named = other.get("run_id") if isinstance(other, dict) else None
            return Declaration(STALE, "%s from an earlier scaffold generation (run %r) is present beside "
                                      "this run's declaration: the golden and the template are out of "
                                      "step. %s" % (stale, named, RECREATE), run_id)

    if not (root / DEFAULTS).is_file():
        return Declaration(DEFAULTS_MISSING, "%s binds %s, which is absent: the golden this destination "
                                             "was created from predates run declarations. %s"
                           % (DECLARATION, DEFAULTS, RECREATE), run_id)
    defaults, why = _load_json(root / DEFAULTS)
    limits = defaults.get("budget") if isinstance(defaults, dict) else None
    if (not isinstance(defaults, dict) or defaults.get("schema") != DEFAULTS_SCHEMA
            or not isinstance(limits, dict)):
        return Declaration(INVALID, why or "%s is not a %s document with a budget section"
                           % (DEFAULTS, DEFAULTS_SCHEMA), run_id)
    hours = limits.get("max_wall_hours")
    if (not isinstance(hours, (int, float)) or isinstance(hours, bool) or hours <= 0
            or not isinstance(limits.get("clock"), str) or not limits["clock"].strip()):
        return Declaration(INVALID, "%s budget needs a positive max_wall_hours and a clock definition"
                           % DEFAULTS, run_id)

    for rel in (DECLARATION, DEFAULTS):
        changed = _unchanged(root, first, rel)
        if changed and _blob(root, first, rel) is None:
            return Declaration(NOT_INITIAL, "%s. A budget added after the destination was created was not "
                                            "declared before the run began. %s" % (changed, RECREATE), run_id)
        if changed:
            return Declaration(ALTERED, "%s since the initial commit %s. A declared budget is never renewed "
                                        "or rewritten; restore it (`git checkout %s -- %s`) or record the "
                                        "change as an assisted continuation" % (changed, first[:12],
                                                                                first[:12], rel), run_id)

    scaffold = _receipt_scaffold(env)
    if scaffold and scaffold != first:
        return Declaration(ALTERED, "the platform provisioned this run from scaffolding commit %s, and this "
                                    "history begins at %s: it is not the history the platform recorded"
                           % (scaffold[:12], first[:12]), run_id)

    budget = dict(limits)
    budget.update({
        "run_id": run_id,
        "declared_at": first_at,
        "declared_at_source": DECLARED_AT_SOURCE,
        "initial_commit": first,
        "declared_by": declared_by,
        "defaults_sha256": hashlib.sha256((root / DEFAULTS).read_bytes()).hexdigest(),
    })
    return Declaration(OK, "run %s declared its budget in initial commit %s at %s (limits %s)"
                       % (run_id, first[:12], first_at, LIMITS_REF), run_id, budget, first_at, first)


def _legacy(root: Path, doc: dict, run_id: str, first: str, first_at: str) -> Declaration:
    """A v10/v11 self-contained declaration, read for the record of THAT run only."""
    at = str(doc.get("declared_at") or "")
    hours = doc.get("max_wall_hours")
    if not at or not isinstance(hours, (int, float)) or isinstance(hours, bool) or hours <= 0:
        return Declaration(INVALID, "legacy %s needs declared_at and a positive max_wall_hours" % DECLARATION,
                           run_id)
    changed = _unchanged(root, first, DECLARATION)
    if changed:
        return Declaration(ALTERED, "legacy declaration: %s since the initial commit %s" % (changed, first[:12]),
                           run_id)
    budget = {k: v for k, v in doc.items() if k != "schema"}
    budget["initial_commit"] = first
    return Declaration(LEGACY, "run %s carries a pre-2026-09-24 self-contained declaration made at %s "
                               "(initial commit %s at %s)" % (run_id, at, first[:12], first_at),
                       run_id, budget, at, first)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Check this destination's run declaration.")
    ap.add_argument("--root", default=".")
    ap.add_argument("--expect", default=None,
                    help="the run this must be (default: $%s when set)" % RUN_NAME_ENV)
    ap.add_argument("--json", action="store_true", help="print the effective budget on success")
    ap.add_argument("--history", action="store_true",
                    help="also read a pre-2026-09-24 declaration, for the record only")
    args = ap.parse_args(argv)
    d = load(Path(args.root), args.expect, allow_legacy=args.history)
    if not d.ok:
        print("REFUSE: %s" % d, file=sys.stderr)
        return 1
    print(json.dumps(d.budget, indent=2, sort_keys=True) if args.json else "%s: %s" % (d.code, d.detail))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
