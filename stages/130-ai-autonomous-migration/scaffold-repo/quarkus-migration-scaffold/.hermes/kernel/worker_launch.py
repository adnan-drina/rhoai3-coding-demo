#!/usr/bin/env python3
"""Worker launch shim: a retry after a loop stop starts escalated (v32 item 2, harness half).

The gateway-embedded kanban dispatcher spawns every worker as ``$HERMES_BIN -p <profile> ...
chat -q "work kanban task <id>"`` (hermes_cli/kanban_db.py _default_spawn /
_resolve_hermes_argv: an explicit HERMES_BIN wins over PATH). The Stage 050 producer copies
THIS FILE into Managed Scope (``bin/hermes-worker-launch``) and pins HERMES_BIN to it in the
managed .env, so it is the one place that sees each worker process start, with the task and
the run id the dispatcher assigned. Every other invocation (a harness script calling
``$HERMES_BIN kanban ...``) is passed through unchanged.

For a dispatcher-spawned worker it sets ``HERMES_START_ESCALATED_TURNS=<n>`` (read by the
runtime's loop escalation, which starts that many turns on the profile's thinking bundle)
when, and only when:

  * the selected model profile (Managed Scope model-profile.json, the run's pinned copy) has
    ``loop_escalation.enabled`` true and a positive ``loop_escalation.retry_start_turns``; and
  * the card's PREVIOUS run (the latest ended run of the same task before this one) ended in
      a loop halt               "STOP WORKER_TOOL_LOOP" (every runtime guardrail halt),
      iteration exhaustion      "Iteration budget exhausted",
      the run token budget      "RUN_TOKEN_BUDGET_EXHAUSTED" (kernel/run_budget.py).

A first run, a retry after any other end, and a profile without loop escalation (Qwen 3.6)
start normally; an inherited value is removed so it can never leak into such a start. Any
failure to decide starts the worker normally and says why on stderr (the worker log).
Self-contained: imports nothing from the destination tree.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

ENV_OUT = "HERMES_START_ESCALATED_TURNS"
REAL_DEFAULT = "/usr/local/bin/hermes"
# (kind, the text the runtime / harness writes into the ended run's error)
LOOP_ENDS = (
    ("loop-halt", "STOP WORKER_TOOL_LOOP"),
    ("iteration-budget", "Iteration budget exhausted"),
    ("token-budget", "RUN_TOKEN_BUDGET_EXHAUSTED"),
)


def worker_spawn(argv: list[str], env: dict) -> bool:
    """True for the dispatcher's worker invocation of this task (and nothing else)."""
    task = (env.get("HERMES_KANBAN_TASK") or "").strip()
    if not task or "chat" not in argv or "-q" not in argv:
        return False
    i = argv.index("-q")
    return i + 1 < len(argv) and argv[i + 1] == "work kanban task %s" % task


def retry_start_turns(profile_doc: Any) -> int:
    """The selected profile's retry_start_turns when its loop escalation is enabled; else 0."""
    if not isinstance(profile_doc, dict):
        return 0
    prof = (profile_doc.get("profiles") or {}).get(profile_doc.get("default_model"))
    le = prof.get("loop_escalation") if isinstance(prof, dict) else None
    if not isinstance(le, dict) or le.get("enabled") is not True:
        return 0
    n = le.get("retry_start_turns")
    return n if isinstance(n, int) and not isinstance(n, bool) and n > 0 else 0


def previous_end(db: Path, task: str, run_id: int) -> tuple[str, int] | None:
    """(kind, run) when the latest ended run of ``task`` before ``run_id`` ended in a loop stop."""
    conn = sqlite3.connect("file:%s?mode=ro" % db, uri=True, timeout=5)
    try:
        row = conn.execute("SELECT id, error FROM task_runs WHERE task_id = ? AND id < ? AND ended_at IS NOT NULL "
                           "ORDER BY id DESC LIMIT 1", (task, int(run_id))).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    text = str(row[1] or "")              # the stop reason the runtime / run_budget.py recorded
    for kind, needle in LOOP_ENDS:
        if needle in text:
            return kind, int(row[0])
    return None


def launch_env(argv: list[str], env: dict, profile_path: Path) -> tuple[dict, str]:
    """The environment the worker starts with, and a one-line note ('' when nothing changed)."""
    out = dict(env)
    if not worker_spawn(argv, env):
        return out, ""
    inherited = out.pop(ENV_OUT, None)
    note = "" if inherited is None else "worker-launch: removed an inherited %s" % ENV_OUT
    run = (env.get("HERMES_KANBAN_RUN_ID") or "").strip()
    db = (env.get("HERMES_KANBAN_DB") or "").strip()
    if not run.isdigit() or not db:
        return out, note
    n = retry_start_turns(json.loads(Path(profile_path).read_text(encoding="utf-8")))
    if not n:
        return out, note
    prev = previous_end(Path(db), env["HERMES_KANBAN_TASK"].strip(), int(run))
    if prev is None:
        return out, note
    out[ENV_OUT] = str(n)
    return out, ("worker-launch: run %s retries run %d of %s after a %s; %s=%d"
                 % (run, prev[1], env["HERMES_KANBAN_TASK"].strip(), prev[0], ENV_OUT, n))


def real_binary(env: dict) -> str:
    real = (env.get("HERMES_REAL_BIN") or "").strip() or REAL_DEFAULT
    if os.path.realpath(real) == os.path.realpath(__file__):
        real = REAL_DEFAULT                  # never exec ourselves
    return real


def main(argv: list[str]) -> int:
    env = dict(os.environ)
    try:
        managed = env.get("HERMES_MANAGED_DIR") or "/projects/.platform/hermes"
        new_env, note = launch_env(argv, env, Path(managed) / "model-profile.json")
    except Exception as exc:  # never break a spawn: start normally and say why
        new_env, note = dict(env), "worker-launch: started without a retry decision (%s: %s)" % (type(exc).__name__, exc)
        if worker_spawn(argv, env):
            new_env.pop(ENV_OUT, None)
    if note:
        print(note, file=sys.stderr, flush=True)
    real = real_binary(env)
    os.execve(real, [real, *argv], new_env)
    return 127                               # not reached


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
