"""The mechanics of the one-pair M3 pilot (PARALLEL-M3-PILOT.md): worktree roots, seeding, the one
integration writer, attempt namespaces and the gates that keep an unintegrated candidate from counting.

A pilot pair task works in a native git worktree (``<dest>/.worktrees/<slug>``, branch ``wt/<slug>``).
A worktree holds only tracked files; the run's state (``verification/``, the untracked ``evidence/``,
the frozen source under ``.derived/``) is seeded from the canonical tree, under the integration lock,
when the worker first issues. From then on the worktree's candidate, index, build outputs, issuance,
verification records and rollback are its own; the board, deadline, request allowance and budgets are
the run's (shared through HERMES_HOME and the platform run control), never copied.

The ONLY path from a worktree candidate to the canonical tree is ``integrate``: one writer at a time,
the ordinary acceptance transaction (run-verify.sh + advance.py) on the COMBINED canonical tree,
idempotent across interruption.
"""
from __future__ import annotations

import fcntl
import json
import os
import shutil
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from planner.execution_policy import WORKTREES_DIR

SEED = Path("verification") / "pilot" / "seed.json"
SEED_SCHEMA = "rhoai3.pilot-seed/v1"
LOCK_NAME = ".integration.lock"
INTEGRATION_ENV = "RHOAI3_PILOT_INTEGRATION"
# untracked run state a worktree needs, copied once from the canonical tree (never .hermes/home: the
# board and the sessions are the run's, read through HERMES_HOME)
SEED_DIRS = ("verification", "evidence", ".derived")
SEED_FILES = (".hermes/AUTOSTART-STATUS", ".hermes/RUN-RESOURCES-STATUS")
# per-execution state that must NOT carry over: another execution's receipts, locks and build work
SEED_SKIP = ("verification/build/.work", "verification/loop/issued.json", "verification/loop/last-advance.json",
             "verification/loop/last-verify.json", "verification/pilot", "verification/native-board/refusals")


def git(root: Path, *args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True, check=check)


def canonical_root(root: Path) -> Path | None:
    """The canonical destination of a linked worktree (the repository's main working tree), or None
    when ``root`` is not a linked worktree."""
    root = Path(root)
    gd = git(root, "rev-parse", "--absolute-git-dir").stdout.strip()
    cd = git(root, "rev-parse", "--path-format=absolute", "--git-common-dir").stdout.strip()
    if not gd or not cd or os.path.realpath(gd) == os.path.realpath(cd):
        return None
    return Path(os.path.realpath(cd)).parent


def is_pilot_worktree(root: Path) -> bool:
    """A linked worktree inside its canonical destination's .worktrees/ directory."""
    canon = canonical_root(root)
    if canon is None:
        return False
    return Path(os.path.realpath(root)).parent == Path(os.path.realpath(canon)) / WORKTREES_DIR


def seeded(root: Path) -> dict[str, Any] | None:
    try:
        doc = json.loads((Path(root) / SEED).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) and doc.get("schema") == SEED_SCHEMA else None


def _head(root: Path) -> str:
    return git(root, "rev-parse", "HEAD").stdout.strip()


def _clean(root: Path) -> list[str]:
    """Uncommitted PRODUCT paths (tracked changes and untracked non-ignored files; run state is not product)."""
    from planner.paths import is_product_path
    out = []
    for line in git(root, "status", "--porcelain", "--untracked-files=all").stdout.splitlines():
        path = line[3:].strip().strip('"')
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if path and is_product_path(path):
            out.append(path)
    return out


@contextmanager
def integration_lock(canon: Path, timeout: float = 1800.0) -> Iterator[None]:
    """One writer of the canonical tree at a time (seeding reads under it too). Waiting costs nothing."""
    d = Path(canon) / WORKTREES_DIR
    d.mkdir(parents=True, exist_ok=True)
    fh = open(d / LOCK_NAME, "a+")
    deadline = time.monotonic() + timeout
    try:
        while True:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() > deadline:
                    raise TimeoutError("the integration lock of %s was not free within %ds" % (canon, int(timeout)))
                time.sleep(2)
        yield
    finally:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        finally:
            fh.close()


def _skip(rel: str) -> bool:
    return any(rel == s or rel.startswith(s + "/") for s in SEED_SKIP)


def seed(root: Path, *, task: str, run: int) -> dict[str, Any]:
    """Copy the canonical run state into this worktree, once, from the canonical HEAD this worktree is
    at. A worktree created before a sibling integrated is fast-forwarded first when it holds no edits.
    Refuses a dirty canonical tree (an integration is in progress) or a diverged worktree."""
    root = Path(root)
    have = seeded(root)
    if have is not None and have.get("task") == task:
        return have
    canon = canonical_root(root)
    if canon is None or not is_pilot_worktree(root):
        raise ValueError("PILOT_NOT_WORKTREE %s is not a pilot worktree of a canonical destination" % root)
    with integration_lock(canon):
        dirty = _clean(canon)
        if dirty:
            raise ValueError("PILOT_CANONICAL_DIRTY the canonical tree has uncommitted product changes (%s): an "
                             "integration is in progress or was interrupted; issue again after it" % ", ".join(dirty[:3]))
        chead, whead = _head(canon), _head(root)
        if whead != chead:
            if _clean(root):
                raise ValueError("PILOT_WORKTREE_DIVERGED the worktree has edits on %s while the canonical HEAD is %s"
                                 % (whead[:12], chead[:12]))
            if git(root, "merge-base", "--is-ancestor", whead, chead).returncode != 0:
                raise ValueError("PILOT_WORKTREE_DIVERGED worktree HEAD %s is not an ancestor of the canonical HEAD %s"
                                 % (whead[:12], chead[:12]))
            git(root, "merge", "--ff-only", "-q", chead, check=True)
        copied = 0
        for d in SEED_DIRS:
            src = canon / d
            if not src.is_dir():
                continue
            for dirpath, dirnames, filenames in os.walk(src):
                rel_dir = os.path.relpath(dirpath, canon).replace(os.sep, "/")
                dirnames[:] = [x for x in dirnames if not _skip("%s/%s" % (rel_dir, x))]
                for f in filenames:
                    rel = "%s/%s" % (rel_dir, f)
                    if _skip(rel):
                        continue
                    dst = root / rel
                    if dst.exists():
                        continue          # a tracked file: the worktree has it at the same commit
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(canon / rel, dst)
                    copied += 1
        for rel in SEED_FILES:
            if (canon / rel).is_file() and not (root / rel).exists():
                (root / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(canon / rel, root / rel)
                copied += 1
        doc = {"schema": SEED_SCHEMA, "task": task, "run": int(run), "canonical": str(canon),
               "canonical_head": chead, "files": copied, "seeded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        (root / SEED).parent.mkdir(parents=True, exist_ok=True)
        (root / SEED).write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return doc


def attempt_key(root: Path, candidate: str) -> str:
    """The board attempt namespace of a verdict: a worktree's candidates and the canonical integration
    of the same change never share a key (their accept records are different facts)."""
    if os.environ.get(INTEGRATION_ENV) == "1":
        return "int-" + candidate[:12]
    if seeded(root) is not None:
        return "wt-" + candidate[:13]
    return candidate[:16]


def mode(root: Path) -> str:
    """'integration' (the canonical advance an integrate runs), 'worktree' (a seeded pilot worktree) or ''."""
    if os.environ.get(INTEGRATION_ENV) == "1":
        return "integration"
    return "worktree" if seeded(root) is not None else ""


def integration_gap(root: Path, board: Any, task_id: str, node: dict[str, Any]) -> str:
    """'' unless ``node`` is a pilot pair outcome whose latest acceptance was not made by an integration
    into the canonical tree (``root``) that is still in its history."""
    if not node.get("pilot_pair"):
        return ""
    recs = [r for r in board.records(task_id, "integrated")]
    if not recs:
        return ("%s is a pilot pair outcome: its candidate is not the application's until native_gate.py integrate "
                "has applied and verified it on the main tree" % node["outcome_id"])
    commit = str(recs[-1].get("integrated_commit") or "")
    if not commit or git(Path(root), "merge-base", "--is-ancestor", commit, "HEAD").returncode != 0:
        return "the integrated commit %s of %s is not in the main tree's history" % (commit[:12], node["outcome_id"])
    return ""


def sibling_tolerant(root: Path, board: Any, task_id: str, node: dict[str, Any], accepted_tree: str) -> str:
    """'' when a pilot pair outcome accepted by integration on an earlier canonical tree still stands on the
    current one: every commit since its integrated commit leaves the paths it changed untouched (the
    sibling's integration). Else why not."""
    if not node.get("pilot_pair"):
        return "not a pilot pair outcome"
    recs = [r for r in board.records(task_id, "integrated")]
    if not recs:
        return "no integration is recorded"
    rec = recs[-1]
    if str(rec.get("canonical_tree") or "") != accepted_tree:
        return "the latest acceptance is not the recorded integration"
    commit = str(rec.get("integrated_commit") or "")
    r = Path(root)
    if git(r, "merge-base", "--is-ancestor", commit, "HEAD").returncode != 0:
        return "the integrated commit is not in the main tree's history"
    mine = set(git(r, "diff", "--name-only", "%s^" % commit, commit).stdout.split())
    since = set(git(r, "diff", "--name-only", commit, "HEAD").stdout.split())
    if mine & since:
        return "later commits changed %s, which this outcome changed" % sorted(mine & since)[0]
    if _clean(r):
        return "the main tree has uncommitted changes"
    return ""


# ---------------------------------------------------------------------------
# integration: the one path from a worktree candidate to the canonical tree
# ---------------------------------------------------------------------------

LOOP_SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "migration" / "fix-until-green" / "scripts"
WT_COMMIT_ENV = "RHOAI3_PILOT_WT_COMMIT"


def _run(argv: list[str], env: dict[str, str], log: Path) -> int:
    with open(log, "a", encoding="utf-8") as fh:
        fh.write("\n$ %s\n" % " ".join(argv))
        fh.flush()
        return subprocess.run(argv, env=env, stdout=fh, stderr=subprocess.STDOUT).returncode


def _read(p: Path) -> dict[str, Any]:
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _restore(canon: Path, paths: list[str]) -> None:
    """Put the named product paths of the canonical tree back to HEAD (an interrupted or failed
    integration of exactly these paths); nothing else is touched."""
    tracked = set(git(canon, "ls-files", "--", *paths).stdout.split()) if paths else set()
    if tracked:
        git(canon, "reset", "-q", "HEAD", "--", *sorted(tracked))
        git(canon, "checkout", "-q", "HEAD", "--", *sorted(tracked))
    for rel in paths:
        if rel not in tracked and (canon / rel).is_file():
            (canon / rel).unlink()


def integrate(root: Path, board: Any, *, task_id: str, run_id: int, runner=None) -> dict[str, Any]:
    """Apply this pair task's accepted worktree candidate to the canonical tree and judge the COMBINED
    tree with the ordinary acceptance transaction. One writer; replayable; nothing counts until the
    canonical advance.py accepts. A textual conflict spends no attempt; a canonical REVERTED is a genuine
    rejection under the existing budget rules (advance.py records it and restores the canonical tree)."""
    from planner import native_control as NC
    root = Path(os.path.realpath(root))
    runner = runner or _run
    seed_doc = seeded(root)
    canon = canonical_root(root)
    if seed_doc is None or canon is None:
        raise NC.Refusal("PILOT_NOT_SEEDED", "integrate runs in a seeded pilot worktree (native_gate.py issue seeds it)")
    NC.live_run(board, task_id, run_id)
    _role, _run_key, oid, _plan, node = NC.node_context(board, task_id)
    if not node.get("pilot_pair"):
        raise NC.Refusal("PILOT_NOT_PAIR", "%s is not a pilot pair outcome" % oid)
    left = _clean(root)
    if left:
        raise NC.Refusal("PILOT_CANDIDATE_UNCOMMITTED", "the worktree has product edits advance.py has not accepted (%s): "
                         "run run-verify.sh and advance.py here first" % ", ".join(left[:3]))
    whead, base = _head(root), str(seed_doc.get("canonical_head") or "")
    steps = _read(root / "verification" / "loop" / "steps.json").get("steps") or []
    accepted = [s for s in steps if isinstance(s, dict) and s.get("card") == task_id and s.get("verdict") == "accepted"]
    if not accepted or str(accepted[-1].get("commit") or "") != whead:
        raise NC.Refusal("PILOT_NOT_ACCEPTED", "advance.py has not accepted the worktree HEAD %s for %s" % (whead[:12], task_id))
    from planner.paths import is_product_path
    changed = sorted(p for p in git(root, "diff", "--name-only", base, whead).stdout.split() if is_product_path(p))
    issues = [r for r in board.records(task_id, "issue") if int(r.get("run") or 0) == int(run_id)]
    allowed = set(issues[-1].get("allowed_paths") or []) if issues else set()
    outside = [p for p in changed if p not in allowed]
    if outside:
        raise NC.Refusal("PILOT_OUT_OF_SCOPE", "the candidate changes %s outside the issued write set" % ", ".join(outside[:3]))
    with integration_lock(canon):
        done = [r for r in board.records(task_id, "integrated") if r.get("wt_commit") == whead]
        if done:
            return {"status": "INTEGRATED", "replayed": True, **{k: done[-1].get(k) for k in ("integrated_commit", "canonical_tree")}}
        csteps = _read(canon / "verification" / "loop" / "steps.json").get("steps") or []
        prior = [s for s in csteps if isinstance(s, dict) and s.get("card") == task_id and s.get("verdict") == "accepted"
                 and s.get("pilot_wt_commit") == whead]
        if prior:        # interrupted after the canonical acceptance, before the record
            return _record_integrated(board, canon, task_id, run_id, whead, base, str(prior[-1].get("commit") or ""), recovered=True)
        dirty = _clean(canon)
        begun = [r for r in board.records(task_id, "integrate-begin") if r.get("wt_commit") == whead]
        if dirty:
            if begun and set(dirty) <= set(changed):
                _restore(canon, dirty)       # an interrupted apply of exactly this candidate
            else:
                raise NC.Refusal("PILOT_CANONICAL_DIRTY", "the main tree has uncommitted product changes (%s) that are not "
                                 "this candidate's" % ", ".join(dirty[:3]))
        chead = _head(canon)
        board.record(task_id, "integrate-begin", "integrate-begin:%d:%s:%d" % (int(run_id), whead[:12], len(begun) + 1),
                     run=int(run_id), wt_commit=whead, base=base, canonical_head=chead, paths=changed)
        iss = NC.issue(canon, board, task_id=task_id, run_id=run_id)
        from native_gate import write_issued_projection
        write_issued_projection(canon, iss)
        if not iss.get("cluster"):
            board.record(task_id, "integration-rejected", "integration-rejected:%d:%s:noscope" % (int(run_id), whead[:12]),
                         run=int(run_id), wt_commit=whead, verdict="NOTHING_ISSUED", reason=str(iss.get("next") or "")[:300])
            return {"status": "NOTHING_ISSUED", "next": iss.get("next")}
        log = canon / "verification" / "pilot" / ("integrate-%s-%s.log" % (task_id, whead[:12]))
        log.parent.mkdir(parents=True, exist_ok=True)
        if changed:
            patch = git(canon, "diff", "--binary", base, whead, "--", *changed).stdout
            chk = subprocess.run(["git", "-C", str(canon), "apply", "--check", "--index"], input=patch, text=True, capture_output=True)
            if chk.returncode != 0:
                board.record(task_id, "integration-conflict", "integration-conflict:%d:%s:%s" % (int(run_id), whead[:12], chead[:12]),
                             run=int(run_id), wt_commit=whead, canonical_head=chead, detail=chk.stderr[-300:])
                return {"status": "CONFLICT", "detail": chk.stderr[-300:]}
            subprocess.run(["git", "-C", str(canon), "apply", "--index"], input=patch, text=True, capture_output=True, check=True)
        env = dict(os.environ, **{INTEGRATION_ENV: "1", WT_COMMIT_ENV: whead})
        rv = runner(["bash", str(LOOP_SCRIPTS / "run-verify.sh"), "--root", str(canon), "--mode", "acceptance"], env, log)
        if rv != 0:
            _restore(canon, changed)
            board.record(task_id, "integration-rejected", "integration-rejected:%d:%s:verify" % (int(run_id), whead[:12]),
                         run=int(run_id), wt_commit=whead, verdict="VERIFY_FAILED", reason="run-verify.sh exited %d" % rv)
            return {"status": "VERIFY_FAILED", "rc": rv, "log": str(log)}
        runner(["python3", str(LOOP_SCRIPTS / "advance.py"), "--root", str(canon), "--cluster", str(iss["cluster"]),
                "--card", task_id], env, log)
        la = _read(canon / "verification" / "loop" / "last-advance.json")
        verdict = str(la.get("verdict") or "")
        if verdict == "ACCEPTED" and _head(canon) != chead:
            return _record_integrated(board, canon, task_id, run_id, whead, base, _head(canon))
        if verdict not in ("VERIFICATION_PENDING",) and _clean(canon):
            _restore(canon, [p for p in _clean(canon) if p in set(changed)])
        board.record(task_id, "integration-rejected", "integration-rejected:%d:%s:%s" % (int(run_id), whead[:12], verdict or "none"),
                     run=int(run_id), wt_commit=whead, verdict=verdict or "UNJUDGED", reason=str(la.get("reason") or "")[:300])
        return {"status": "REJECTED", "verdict": verdict, "log": str(log)}


def _record_integrated(board: Any, canon: Path, task_id: str, run_id: int, whead: str, base: str, commit: str,
                       recovered: bool = False) -> dict[str, Any]:
    from planner import native_control as NC
    lv = _read(canon / "verification" / "loop" / "last-verify.json")
    rec = board.record(task_id, "integrated", "integrated:%d:%s" % (int(run_id), whead[:12]), run=int(run_id),
                       wt_commit=whead, base=base, integrated_commit=commit, canonical_tree=NC._product_tree(canon),
                       verification={k: lv.get(k) for k in ("procedure", "rc", "compilation", "compile_errors", "tests",
                                                             "mode", "candidate_sha256")},
                       recovered=recovered)
    return {"status": "INTEGRATED", "integrated_commit": commit, "canonical_tree": rec.get("canonical_tree"),
            "recovered": recovered}


def rebase(root: Path, board: Any, *, task_id: str, run_id: int) -> dict[str, Any]:
    """Same-card rework after a rejected or conflicting integration: the worktree moves onto the current
    canonical HEAD (its candidate commits replayed, or -- on a conflict -- kept under refs/pilot/ for the
    worker to redo by hand) and its run state is seeded again from the canonical tree. Spends nothing."""
    from planner import native_control as NC
    root = Path(os.path.realpath(root))
    canon = canonical_root(root)
    seed_doc = seeded(root)
    if canon is None or seed_doc is None:
        raise NC.Refusal("PILOT_NOT_SEEDED", "rebase runs in a seeded pilot worktree")
    NC.live_run(board, task_id, run_id)
    left = _clean(root)
    if left:
        raise NC.Refusal("PILOT_CANDIDATE_UNCOMMITTED", "the worktree has unaccepted product edits (%s)" % ", ".join(left[:3]))
    with integration_lock(canon):
        chead, whead, base = _head(canon), _head(root), str(seed_doc.get("canonical_head") or "")
        n = len(git(root, "for-each-ref", "refs/pilot/%s/" % task_id).stdout.splitlines()) + 1
        keep = "refs/pilot/%s/%d" % (task_id, n)
        git(root, "update-ref", keep, whead, check=True)
        replayed = git(root, "rebase", "-q", "--onto", chead, base)        # the current (wt/) branch
        if replayed.returncode != 0:
            git(root, "rebase", "--abort")
            git(root, "reset", "-q", "--keep", chead, check=True)
            outcome = "conflict: the previous candidate is kept at %s (git diff %s %s); redo it on the new baseline" % (keep, base[:12], keep)
        else:
            outcome = "replayed onto %s" % chead[:12]
        for d in ("verification", ".derived"):
            if (root / d).exists():
                shutil.rmtree(root / d)
        for rel in git(root, "ls-files", "-o", "--exclude-standard", "--ignored", "evidence").stdout.splitlines():
            if (root / rel).is_file():
                (root / rel).unlink()
    doc = seed(root, task=task_id, run=int(run_id))
    return {"status": "REBASED", "canonical_head": chead, "kept": keep, "outcome": outcome, "seed": doc}
