#!/usr/bin/env python3
"""run_declaration selftest: real git histories, one per way a run could
inherit or rewrite a budget that is not its own.

  * a factory declaration in the initial commit is this run's, with the
    defaults' limits and the initial commit's time -- for a versioned name and
    for a name with no version suffix alike
  * later commits, a restart and a fresh clone (a reopened workspace) all read
    the SAME declaration: nothing renews it
  * missing declaration, missing defaults, unrendered template markup, a wrong
    schema and incomplete provenance are refused
  * another run's declaration is refused, against migration.yaml and against
    MIGRATION_RUN_NAME
  * an earlier golden's per-run files are refused on the launch path (a v1
    declaration, a run-configuration.json beside a v2 one); a v1 declaration
    is readable for history only
  * a declaration added after the initial commit, or changed after it (by a
    commit or in the working tree), or defaults changed after it, is refused
  * a history that does not begin at the platform's scaffolding commit is
    refused; shallow and non-repositories are unverifiable
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))

from planner import run_declaration as rd  # noqa: E402

DEFAULTS = {"schema": "rhoai3.run-defaults/v1",
            "budget": {"max_wall_hours": 24, "clock": "earlier of destination first commit and M1 dispatch",
                       "stopping_conditions": ["wall budget exhausted"]},
            "configuration": {"model": {"id": "m"}}}
GIT = ["git", "-c", "user.name=factory", "-c", "user.email=factory@example.invalid",
       "-c", "init.defaultBranch=main", "-c", "commit.gpgsign=false"]


def declaration(run: str, task: str = "0b7c9a52-4f0e-4d1e-9d5e-2f6c1f1f9a10") -> str:
    """What the app-migration skeleton renders for `run` (same keys, same order)."""
    return json.dumps({"schema": "rhoai3.run-budget/v2", "run_id": run,
                       "limits": "run-defaults.json#/budget", "declared_at_source": "initial-commit",
                       "declared_by": {"factory": "rhdh-scaffolder", "template": "app-migration",
                                       "scaffolder_task": task},
                       "note": "factory declaration"}, indent=2) + "\n"


def migration(run: str) -> str:
    return "migration:\n  target: quarkus\nresources:\n  run: %s\n  namespace: wksp-ai-developer\n" % run


def git(root: Path, *args: str, when: str = "2026-09-24T09:00:00+00:00") -> str:
    env = dict(os.environ, GIT_AUTHOR_DATE=when, GIT_COMMITTER_DATE=when)
    return subprocess.run([*GIT, "-C", str(root), *args], check=True, capture_output=True,
                          text=True, env=env).stdout.strip()


def repo(tmp: Path, name: str, files: dict[str, str], later: list[dict[str, str | None]] = ()) -> Path:
    """A destination whose initial commit holds `files`; each of `later` is one more commit."""
    root = tmp / name
    root.mkdir()
    git(root, "init", "-q")
    for step, commit in enumerate([files, *later]):
        for rel, text in commit.items():
            path = root / rel
            if text is None:
                path.unlink()
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "commit %d" % step, when="2026-09-24T09:%02d:00+00:00" % step)
    return root


def factory(run: str) -> dict[str, str]:
    return {"run-budget.json": declaration(run), "run-defaults.json": json.dumps(DEFAULTS, indent=2),
            "migration.yaml": migration(run), "README.md": "destination\n"}


def main() -> int:
    failures: list[str] = []

    def ok(cond: bool, what: str) -> None:
        if not cond:
            failures.append(what)

    def expect(root: Path, code: str, why: str, **kw) -> rd.Declaration:
        d = rd.load(root, **kw)
        ok(d.code == code, "%s: expected %s, got %s (%s)" % (why, code, d.code, d.detail))
        if code not in (rd.OK, rd.LEGACY):
            ok(not d.ok and not d.budget, "%s: a refusal still carried a budget" % why)
        return d

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        # 1. The factory declaration, for a versioned name and an unversioned one.
        for run in ("spring-petclinic-rest-legacy-v12", "orders-modernization"):
            root = repo(tmp, run, factory(run))
            first = git(root, "rev-list", "--max-parents=0", "HEAD")
            d = expect(root, rd.OK, "factory declaration for %s" % run, expected_run=run)
            ok(d.run_id == run and d.budget.get("run_id") == run, "%s: run identity not the full name" % run)
            ok(d.budget.get("max_wall_hours") == 24 and d.budget.get("clock") == DEFAULTS["budget"]["clock"],
               "%s: limits are not the shared defaults" % run)
            ok(d.declared_at == "2026-09-24T09:00:00Z" and d.budget.get("declared_at") == d.declared_at,
               "%s: declared_at is not the initial commit time (%s)" % (run, d.declared_at))
            ok(d.initial_commit == first, "%s: initial commit not recorded" % run)
            ok("deadline" not in d.budget and "clock_start" not in d.budget and "source_commit" not in d.budget,
               "%s: a time or commit was invented before its defining event" % run)

        # 2. Later commits, repeated loads and a fresh clone never renew it.
        run = "retry-probe"
        root = repo(tmp, run, factory(run), later=[{"src/Main.java": "class Main {}\n"},
                                                   {".hermes/AUTOSTART-STATUS": "{}\n"}])
        a = expect(root, rd.OK, "after two more commits", expected_run=run)
        b = expect(root, rd.OK, "restart (second load)", expected_run=run)
        clone = tmp / "reopened"
        subprocess.run(["git", "clone", "-q", str(root), str(clone)], check=True)
        c = expect(clone, rd.OK, "reopened workspace (fresh clone)", expected_run=run)
        ok(a.declared_at == b.declared_at == c.declared_at and a.budget == b.budget == c.budget,
           "restart or reopen changed the declared budget")
        ok(a.declared_at == "2026-09-24T09:00:00Z", "a later commit moved the declaration time")

        # 3. Missing, incomplete and unrendered declarations.
        files = factory("r-missing")
        del files["run-budget.json"]
        expect(repo(tmp, "missing", files), rd.MISSING, "no declaration", expected_run="r-missing")
        files = factory("r-nodefaults")
        del files["run-defaults.json"]
        expect(repo(tmp, "nodefaults", files), rd.DEFAULTS_MISSING, "no defaults", expected_run="r-nodefaults")
        files = factory("r-raw")
        files["run-budget.json"] = declaration("${{ values.name }}")
        expect(repo(tmp, "unrendered", files), rd.INVALID, "unrendered run_id")
        files = factory("r-rawtask")
        files["run-budget.json"] = declaration("r-rawtask", task="${{ values.scaffolderTaskId }}")
        expect(repo(tmp, "unrendered-task", files), rd.INVALID, "unrendered task id", expected_run="r-rawtask")
        files = factory("r-schema")
        files["run-budget.json"] = files["run-budget.json"].replace("run-budget/v2", "run-budget/v9")
        expect(repo(tmp, "schema", files), rd.INVALID, "unknown schema", expected_run="r-schema")
        files = factory("r-noprov")
        doc = json.loads(files["run-budget.json"])
        del doc["declared_by"]
        files["run-budget.json"] = json.dumps(doc)
        expect(repo(tmp, "noprov", files), rd.INVALID, "no provenance", expected_run="r-noprov")
        files = factory("r-badlimits")
        files["run-defaults.json"] = json.dumps({**DEFAULTS, "budget": {"clock": "x"}})
        expect(repo(tmp, "badlimits", files), rd.INVALID, "defaults without max_wall_hours",
               expected_run="r-badlimits")

        # 4. Another run's declaration.
        root = repo(tmp, "foreign", factory("run-a"))
        expect(root, rd.FOREIGN, "workspace expects another run", expected_run="run-b")
        expect(root, rd.FOREIGN, "MIGRATION_RUN_NAME names another run",
               environ={rd.RUN_NAME_ENV: "run-b"})
        files = factory("run-a")
        files["migration.yaml"] = migration("run-b")
        expect(repo(tmp, "foreign-assignment", files), rd.FOREIGN, "assignment names another run")
        expect(root, rd.FOREIGN, "run-a-retry must not pass as run-a", expected_run="run-a-retry")

        # 5. An earlier golden's per-run files: refused to launch, readable as history.
        legacy = json.dumps({"schema": "rhoai3.run-budget/v1", "run_id": "v11",
                             "declared_at": "2026-09-23T17:10:00Z", "max_wall_hours": 24})
        files = factory("v12-new")
        files["run-budget.json"] = legacy
        root = repo(tmp, "stale-legacy", files)
        expect(root, rd.STALE, "a v11 declaration copied into a new run", expected_run="v12-new")
        h = expect(root, rd.LEGACY, "the same file read for history", allow_legacy=True)
        ok(h.run_id == "v11" and h.declared_at == "2026-09-23T17:10:00Z", "history lost the legacy record")
        files = factory("r-stalecfg")
        files["run-configuration.json"] = json.dumps({"run_id": "v11"})
        expect(repo(tmp, "stale-config", files), rd.STALE, "run-configuration.json beside a v2 declaration",
               expected_run="r-stalecfg")

        # 6. Declared late, or rewritten.
        files = factory("r-late")
        late = files.pop("run-budget.json")
        expect(repo(tmp, "late", files, later=[{"run-budget.json": late}]), rd.NOT_INITIAL,
               "declaration added after the initial commit", expected_run="r-late")
        grown = json.loads(declaration("r-grown"))
        grown["max_wall_hours"] = 48
        expect(repo(tmp, "renewed", factory("r-grown"), later=[{"run-budget.json": json.dumps(grown)}]),
               rd.ALTERED, "declaration rewritten by a later commit", expected_run="r-grown")
        more = dict(DEFAULTS, budget=dict(DEFAULTS["budget"], max_wall_hours=48))
        expect(repo(tmp, "defaults-grown", factory("r-dg"), later=[{"run-defaults.json": json.dumps(more)}]),
               rd.ALTERED, "defaults extended by a later commit", expected_run="r-dg")
        root = repo(tmp, "worktree", factory("r-wt"))
        (root / "run-budget.json").write_text(json.dumps(dict(json.loads(declaration("r-wt")), max_wall_hours=48)))
        expect(root, rd.ALTERED, "declaration edited in the working tree", expected_run="r-wt")
        root = repo(tmp, "removed", factory("r-rm"), later=[{"run-budget.json": None}])
        expect(root, rd.MISSING, "declaration deleted by a later commit", expected_run="r-rm")

        # 7. Histories the platform did not provision, and histories that cannot be read.
        root = repo(tmp, "receipt", factory("r-rc"))
        first = git(root, "rev-list", "--max-parents=0", "HEAD")
        expect(root, rd.OK, "receipt names this scaffolding commit",
               environ={rd.RUN_NAME_ENV: "r-rc", rd.RECEIPT_ENV: "run=r-rc;scaffold=%s" % first})
        expect(root, rd.ALTERED, "receipt names another scaffolding commit",
               environ={rd.RUN_NAME_ENV: "r-rc", rd.RECEIPT_ENV: "run=r-rc;scaffold=%s" % ("f" * 40)})
        plain = tmp / "plain"
        plain.mkdir()
        for rel, text in factory("r-plain").items():
            (plain / rel).write_text(text)
        expect(plain, rd.UNVERIFIABLE, "not a repository", expected_run="r-plain")
        deep = repo(tmp, "deep", factory("r-deep"), later=[{"a.txt": "1\n"}, {"b.txt": "2\n"}])
        shallow = tmp / "shallow"
        subprocess.run(["git", "clone", "-q", "--depth", "1", deep.as_uri(), str(shallow)], check=True)
        expect(shallow, rd.UNVERIFIABLE, "shallow clone", expected_run="r-deep")

        # 8. The CLI carries the typed code to dest-init and preflight logs.
        cli_env = {k: v for k, v in os.environ.items() if k not in (rd.RUN_NAME_ENV, rd.RECEIPT_ENV)}
        cli_env["PYTHONPATH"] = str(HERE.parent)
        for root, expect_rc, token in ((tmp / "missing", 1, rd.MISSING),
                                       (tmp / "retry-probe", 0, "OK: run retry-probe")):
            cli = subprocess.run([sys.executable, "-m", "planner.run_declaration", "--root", str(root)],
                                 env=cli_env, capture_output=True, text=True)
            ok(cli.returncode == expect_rc and token in (cli.stdout + cli.stderr),
               "CLI on %s: rc %d, output %r" % (root.name, cli.returncode, (cli.stdout + cli.stderr)[-200:]))

    if failures:
        for f in failures:
            print("FAIL: %s" % f, file=sys.stderr)
        return 1
    print("OK: run_declaration selftest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
