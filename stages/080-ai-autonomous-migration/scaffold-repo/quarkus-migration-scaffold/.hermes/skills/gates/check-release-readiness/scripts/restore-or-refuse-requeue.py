#!/usr/bin/env python3
"""AD-H §5.1 / ER#2 F4 — restore-or-refuse before requeue after crash terminals.

Hermes requeue restores the task record, not the workspace. On terminals
crashed / gave_up / kill, Lead/Monitor MUST run this before unblock/requeue:

  check  (default) — dirty → exit 1 (refuse requeue); clean → exit 0
  restore          — git reset --hard BASELINE + clean -fd, then re-check

Does not claim release_qualified (no durable journal / full chaos inject).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

TERMINALS = frozenset(
    {"crashed", "gave_up", "kill", "killed", "timeout_kill", "timed_out"}
)


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)


def porcelain(root: Path) -> list[str]:
    cp = run(["git", "status", "--porcelain", "-uall"], root)
    if cp.returncode != 0:
        return ["__git_status_failed__"]
    paths: list[str] = []
    for line in cp.stdout.splitlines():
        if len(line) < 4:
            continue
        rest = line[3:]
        if " -> " in rest:
            rest = rest.split(" -> ", 1)[1]
        rest = rest.strip().strip('"')
        if rest:
            paths.append(rest)
    return paths


def is_git_repo(root: Path) -> bool:
    return run(["git", "rev-parse", "--is-inside-work-tree"], root).returncode == 0


def resolve_baseline(root: Path, baseline: str | None) -> str:
    if baseline:
        return baseline
    marker = root / "evidence" / "recovery" / "baseline-sha"
    if marker.is_file():
        return marker.read_text(encoding="utf-8").strip()
    # Prefer origin/HEAD when present; else HEAD
    for ref in ("origin/HEAD", "HEAD"):
        cp = run(["git", "rev-parse", "--verify", ref], root)
        if cp.returncode == 0:
            return cp.stdout.strip()
    return "HEAD"


def write_decision(root: Path, payload: dict) -> None:
    """Persist decision under HERMES_HOME/recovery/ (preferred) or /tmp.

    Never create untracked files inside the git worktree — that would defeat
    the post-restore workspace_clean check.
    """
    import os
    import tempfile

    hermes = os.environ.get("HERMES_HOME", "").strip()
    if hermes:
        out = Path(hermes) / "recovery"
    else:
        out = Path(tempfile.gettempdir()) / "rhoai3-f4-recovery"
    out.mkdir(parents=True, exist_ok=True)
    path = out / "last-restore-or-refuse.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"F4 decision logged: {path}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument(
        "--terminal",
        required=True,
        help="crashed | gave_up | kill (required proving-min gate)",
    )
    ap.add_argument(
        "--action",
        choices=("check", "restore"),
        default="check",
        help="check=refuse if dirty; restore=reset to baseline then check",
    )
    ap.add_argument(
        "--baseline",
        default=None,
        help="git ref/SHA to restore (default: evidence/recovery/baseline-sha or HEAD)",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="With --action restore: print plan only",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()
    terminal = args.terminal.strip().lower()

    if terminal not in TERMINALS:
        print(
            f"FAIL: unknown terminal={terminal!r}; "
            f"expected one of {sorted(TERMINALS)}",
            file=sys.stderr,
        )
        return 2

    if not is_git_repo(root):
        print("FAIL: not a git worktree — refuse requeue", file=sys.stderr)
        write_decision(
            root,
            {
                "ok": False,
                "terminal": terminal,
                "action": args.action,
                "decision": "refuse",
                "reason": "not_git_worktree",
            },
        )
        return 1

    dirty = porcelain(root)
    if dirty == ["__git_status_failed__"]:
        print("FAIL: git status failed — refuse requeue", file=sys.stderr)
        return 1

    if args.action == "check":
        if dirty:
            print(
                f"FAIL: F4 refuse requeue after {terminal}: "
                f"workspace dirty ({len(dirty)} path(s)) — requeue≠restore",
                file=sys.stderr,
            )
            for p in dirty[:30]:
                print(f"  dirty: {p}", file=sys.stderr)
            write_decision(
                root,
                {
                    "ok": False,
                    "terminal": terminal,
                    "action": "check",
                    "decision": "refuse",
                    "reason": "workspace_dirty",
                    "dirty_count": len(dirty),
                    "dirty_sample": dirty[:30],
                },
            )
            return 1
        print(f"OK: workspace_clean after {terminal} — requeue permitted")
        write_decision(
            root,
            {
                "ok": True,
                "terminal": terminal,
                "action": "check",
                "decision": "allow",
                "reason": "workspace_clean",
            },
        )
        return 0

    # restore
    baseline = resolve_baseline(root, args.baseline)
    if args.dry_run:
        print(f"DRY-RUN: would git reset --hard {baseline} && git clean -fd in {root}")
        print(f"DRY-RUN: dirty_now={len(dirty)}")
        return 0 if not dirty else 1

    print(f"F4 restore: baseline={baseline} terminal={terminal}")
    reset = run(["git", "reset", "--hard", baseline], root)
    if reset.returncode != 0:
        print(f"FAIL: git reset --hard failed: {reset.stderr.strip()}", file=sys.stderr)
        write_decision(
            root,
            {
                "ok": False,
                "terminal": terminal,
                "action": "restore",
                "decision": "refuse",
                "reason": "reset_failed",
                "baseline": baseline,
            },
        )
        return 1
    clean = run(["git", "clean", "-fd"], root)
    if clean.returncode != 0:
        print(f"FAIL: git clean -fd failed: {clean.stderr.strip()}", file=sys.stderr)
        return 1

    dirty_after = porcelain(root)
    if dirty_after:
        print(
            f"FAIL: still dirty after restore ({len(dirty_after)} path(s))",
            file=sys.stderr,
        )
        write_decision(
            root,
            {
                "ok": False,
                "terminal": terminal,
                "action": "restore",
                "decision": "refuse",
                "reason": "still_dirty",
                "baseline": baseline,
                "dirty_sample": dirty_after[:30],
            },
        )
        return 1

    sha = run(["git", "rev-parse", "HEAD"], root).stdout.strip()
    print(f"OK: restored workspace_clean sha={sha} — requeue permitted")
    write_decision(
        root,
        {
            "ok": True,
            "terminal": terminal,
            "action": "restore",
            "decision": "allow",
            "reason": "restored_clean",
            "baseline": baseline,
            "head": sha,
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
