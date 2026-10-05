#!/usr/bin/env python3
"""Token budgets and the no-accepted-checkpoint stop, enforced inside the workspace (v32).

Before this file the only shape-independent bound on a worker run was the runtime's
500-iteration budget (v32: 62.8M input tokens on one M1 run, ~46M on one repository card,
against 0.3M-6M for a healthy Qwen 3.8 card run), and the run-level stopping conditions in
run-defaults.json were applied by a lead watching from outside (v31: the lead's credential
expired for nine hours). Every loop guard recognises one loop shape; a token budget bounds
all of them.

Three named stops. Each reaches the board through the native primitive the runtime itself
uses for the comparable stop, so retry accounting and the board read them the same way:

  RUN_TOKEN_BUDGET_EXHAUSTED        one kanban worker run read more prompt tokens than the
                                    selected model profile's ``run_input_token_budget``
                                    (model-profiles.json, pinned per run in run control and
                                    copied verbatim to Managed Scope model-profile.json).
                                    Mode ``pre-tool``: a pre_tool_call entry (matcher ``.*``)
                                    of every worker. Recorded with EXACTLY the call the
                                    runtime makes for "Iteration budget exhausted"
                                    (agent/turn_finalizer.py _record_kanban_budget_exhausted):
                                    kanban_db._record_task_failure(outcome="timed_out",
                                    release_claim=True, end_run=True). The failure counts
                                    toward the task's max_retries / kanban.failure_limit
                                    circuit breaker; the dispatcher respawns or gives up
                                    exactly as after iteration exhaustion. The worker is then
                                    sent SIGTERM (the signal the dispatcher's own max-runtime
                                    stop sends; a kanban worker flushes its session and exits).
  MIGRATION_TOKEN_BUDGET_EXHAUSTED  the whole migration run (every worker session of every
                                    profile) read more than run-defaults.json
                                    ``budget.run_input_token_budget``.
  MIGRATION_NO_ACCEPTED_CHECKPOINT  no card was accepted (reached done) for
                                    ``budget.no_accepted_checkpoint_minutes``.
                                    Both migration stops: mode ``tick``, an
                                    on_kanban_dispatch_tick hook of the gateway-embedded
                                    dispatcher (every dispatch_interval_seconds). A stop is
                                    an append-only record in run-stops.jsonl beside the
                                    request ledger; while it is active every tick blocks each
                                    running or ready card natively (kanban_db.block_task, kind
                                    needs_input, the stop as the reason; a running card's block
                                    is bound to its run and its worker gets SIGTERM). Lifting
                                    is an Operator act (mode ``lift``, recorded): the token
                                    stop then stays lifted for the run (the Operator accepted
                                    the overspend); the stall stop re-arms from the lift.

Counting. Prompt tokens are sessions.input_tokens + cache_read_tokens + cache_write_tokens
of the profile state.db: Hermes splits the provider's prompt_tokens into those three
(agent/usage_pricing.py normalize_usage). A worker run is the session tree rooted at the
session the worker started in (compression children and delegated children are its
descendants), found from the hook payload's session id. The migration run is every
``source='kanban'`` session of every profile under this workspace's Hermes home (one run
per workspace). The migration limits are read from run-defaults.json as the destination's
initial commit declared them, never from the working tree.

Self-contained on purpose: the Stage 050 producer copies THIS FILE into Managed Scope and
runs it with the Hermes interpreter (the native writes import hermes_cli.kanban_db); it
imports nothing from the destination tree. The worker hook fails open: an enforcer that
cannot read its inputs allows the call and says why on stderr (the tick bound and the
iteration budget remain).

Usage:
  run_budget.py pre-tool                                   (hook JSON on stdin)
  run_budget.py tick --root <dest> --stops <run-stops.jsonl>  (hook JSON on stdin)
  run_budget.py lift --stops <run-stops.jsonl> --code <CODE> --by <name> [--note <text>]
"""
from __future__ import annotations

import argparse
import datetime
import glob
import json
import os
import signal
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Iterable

RUN_CODE = "RUN_TOKEN_BUDGET_EXHAUSTED"
MIGRATION_TOKEN_CODE = "MIGRATION_TOKEN_BUDGET_EXHAUSTED"
STALL_CODE = "MIGRATION_NO_ACCEPTED_CHECKPOINT"
MIGRATION_CODES = (MIGRATION_TOKEN_CODE, STALL_CODE)

PROFILE_KEY = "run_input_token_budget"        # model-profiles.json profiles.<model>
BUDGET_TOKEN_KEY = "run_input_token_budget"   # run-defaults.json budget
BUDGET_STALL_KEY = "no_accepted_checkpoint_minutes"

PROMPT_COLS = ("input_tokens", "cache_read_tokens", "cache_write_tokens")
# The run's terminators end it without another model request: never refused for budget.
TERMINATORS = frozenset(("kanban_complete", "complete_task", "kanban_block", "kanban_request_review",
                         "request_review"))
SESSION_SLACK = 5.0      # seconds: a run's first session starts after the dispatcher claimed it
LIVE = ("running", "ready")


# ------------------------------------------------------------------------- reading

def _rows(conn: sqlite3.Connection, sql: str, args: Iterable[Any] = ()) -> list[dict[str, Any]]:
    cur = conn.execute(sql, tuple(args))
    names = [d[0] for d in cur.description or ()]
    return [dict(zip(names, r)) for r in cur.fetchall()]


def _one(conn: sqlite3.Connection, sql: str, args: Iterable[Any] = ()) -> dict[str, Any] | None:
    got = _rows(conn, sql, args)
    return got[0] if got else None


def _int(v: Any) -> int | None:
    return v if isinstance(v, int) and not isinstance(v, bool) and v > 0 else None


def run_limit(profile_doc: Any) -> int | None:
    """The selected profile's per-worker-run prompt-token budget, or None when it pins none."""
    if not isinstance(profile_doc, dict):
        return None
    prof = (profile_doc.get("profiles") or {}).get(profile_doc.get("default_model")) or {}
    return _int(prof.get(PROFILE_KEY)) if isinstance(prof, dict) else None


def _ro(path: Path) -> sqlite3.Connection:
    return sqlite3.connect("file:%s?mode=ro" % path, uri=True, timeout=5)


def _session_cols(conn: sqlite3.Connection) -> list[str]:
    have = {str(r[1]) for r in conn.execute("PRAGMA table_info(sessions)")}
    if "input_tokens" not in have:
        raise ValueError("the sessions table has no input_tokens column")
    return [c for c in PROMPT_COLS if c in have]


def run_prompt_tokens(state_db: Path, session_id: str, run_started: float) -> int | None:
    """Prompt tokens of the worker run whose live session is ``session_id``: the session tree
    rooted at the earliest ancestor that started inside the run. None when the session is not
    (yet) recorded."""
    if not session_id or not Path(state_db).is_file():
        return None
    conn = _ro(Path(state_db))
    try:
        cols = _session_cols(conn)
        rows = _rows(conn, "SELECT id, parent_session_id, %s FROM sessions WHERE started_at >= ?" % ", ".join(cols),
                     (float(run_started) - SESSION_SLACK,))
    finally:
        conn.close()
    by_id = {str(r["id"]): r for r in rows}
    if session_id not in by_id:
        return None
    root = session_id
    seen = {root}
    while True:
        parent = str(by_id[root].get("parent_session_id") or "")
        if not parent or parent not in by_id or parent in seen:
            break
        root = parent
        seen.add(root)
    children: dict[str, list[str]] = {}
    for sid, r in by_id.items():
        children.setdefault(str(r.get("parent_session_id") or ""), []).append(sid)
    total, todo, done = 0, [root], set()
    while todo:
        sid = todo.pop()
        if sid in done:
            continue
        done.add(sid)
        total += sum(int(by_id[sid].get(c) or 0) for c in cols)
        todo.extend(children.get(sid, ()))
    return total


def kanban_root_home(home: str) -> str:
    """The base Hermes home (a profile home is <root>/profiles/<name>)."""
    home = (home or "").rstrip("/")
    parent, name = os.path.split(home)
    root, profiles = os.path.split(parent)
    return root if profiles == "profiles" and name and root else home


def state_dbs(home: str) -> list[Path]:
    root = kanban_root_home(home)
    if not root:
        return []
    found = [Path(root) / "state.db"] + [Path(p) for p in sorted(glob.glob(os.path.join(root, "profiles", "*", "state.db")))]
    return [p for p in found if p.is_file()]


def migration_prompt_tokens(dbs: Iterable[Path]) -> int:
    """Prompt tokens of every kanban worker session in these profile databases."""
    total = 0
    for p in dbs:
        conn = _ro(Path(p))
        try:
            cols = _session_cols(conn)
            row = conn.execute("SELECT %s FROM sessions WHERE source = 'kanban'"
                               % ", ".join("COALESCE(SUM(%s), 0)" % c for c in cols)).fetchone()
        finally:
            conn.close()
        total += sum(int(v or 0) for v in row)
    return total


def declared_limits(root: Path) -> tuple[dict[str, Any], str]:
    """run-defaults.json ``budget`` as the destination's initial commit declared it."""
    def git(*a: str) -> str:
        return subprocess.run(["git", "-c", "safe.directory=%s" % root, "-C", str(root), *a], capture_output=True,
                              text=True, timeout=15, check=True).stdout
    try:
        roots = git("rev-list", "--max-parents=0", "HEAD").split()
        if len(roots) != 1:
            return {}, "the destination history has %d root commits" % len(roots)
        doc = json.loads(git("show", "%s:run-defaults.json" % roots[0]))
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        return {}, "run-defaults.json is not readable from the initial commit (%s)" % type(exc).__name__
    budget = doc.get("budget") if isinstance(doc, dict) else None
    return (budget, "") if isinstance(budget, dict) else ({}, "run-defaults.json has no budget section")


# ------------------------------------------------------------------------- reasons

def run_reason(used: int, limit: int) -> str:
    return ("%s: %d of %d input tokens -- this worker run read more prompt tokens than the model profile's "
            "%s; the run was ended as a timed-out attempt (same retry accounting as an exhausted iteration budget)"
            % (RUN_CODE, used, limit, PROFILE_KEY))


def migration_token_reason(used: int, limit: int) -> str:
    return ("%s: %d of %d input tokens across every worker run of this migration run (run-defaults.json budget.%s); "
            "the run is stopped until an Operator lifts it (run_budget.py lift)" % (MIGRATION_TOKEN_CODE, used, limit,
                                                                                    BUDGET_TOKEN_KEY))


def _iso(ts: float | None) -> str:
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if ts else "never"


def stall_reason(minutes: int, limit: int, last_task: str, last_at: float | None) -> str:
    return ("%s: no card accepted for %d min (limit %d min, run-defaults.json budget.%s; last accepted %s at %s); "
            "the run is stopped until an Operator lifts it (run_budget.py lift)"
            % (STALL_CODE, minutes, limit, BUDGET_STALL_KEY, last_task or "none", _iso(last_at)))


# ------------------------------------------------------------------------- native writes

class HermesNative:
    """The board writes, through the pinned runtime's own kanban_db primitives."""

    def __init__(self, board: str | None = None, db_path: str | None = None):
        from hermes_cli import kanban_db as kb  # the Hermes interpreter runs this file
        self.kb = kb
        self.conn = kb.connect(Path(db_path)) if db_path else kb.connect(board=board)

    def record_run_failure(self, task: str, error: str) -> None:
        # EXACTLY agent/turn_finalizer._record_kanban_budget_exhausted's call for an exhausted iteration budget.
        self.kb._record_task_failure(self.conn, task, error=error, outcome="timed_out", release_claim=True,
                                     end_run=True)

    def block(self, task: str, reason: str, run_id: int | None = None) -> bool:
        return bool(self.kb.block_task(self.conn, task, reason=reason, kind="needs_input", expected_run_id=run_id))


class LazyNative:
    """Opens the Hermes board writer only when a stop is recorded: the worker hook runs before every
    tool call and reads through a read-only connection."""

    def __init__(self, factory: Callable[[], Any]):
        self._factory, self._native = factory, None

    def __getattr__(self, name: str) -> Any:
        if self._native is None:
            self._native = self._factory()
        return getattr(self._native, name)


def sigterm(pid: int) -> None:
    try:
        os.kill(int(pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError, ValueError, TypeError):
        pass


# ------------------------------------------------------------------------- per worker run

def check_tool_call(payload: dict, env: dict, conn: sqlite3.Connection, native: Any, kill: Callable[[int], None],
                    profile_doc: Any, parent_pid: int | None = None) -> dict | None:
    """The pre_tool_call decision for one worker tool call: None (allow) or a block decision.
    Records the stop natively and ends the worker when this run crossed its budget."""
    task = (env.get("HERMES_KANBAN_TASK") or "").strip()
    run = (env.get("HERMES_KANBAN_RUN_ID") or "").strip()
    limit = run_limit(profile_doc)
    if not task or not run.isdigit() or limit is None:
        return None
    row = _one(conn, "SELECT id, task_id, started_at, ended_at, error, worker_pid FROM task_runs WHERE id = ?", (int(run),))
    if row is None or str(row.get("task_id")) != task:
        return None
    if row.get("ended_at") is not None:
        # this run already ended on its budget and the worker is still calling tools: refuse again and re-signal
        if str(row.get("error") or "").startswith(RUN_CODE):
            if parent_pid:
                kill(parent_pid)
            return {"action": "block", "message": "%s; this worker run has ended" % str(row["error"])[:600]}
        return None
    if str(payload.get("tool_name") or "") in TERMINATORS:
        return None
    t = _one(conn, "SELECT status, current_run_id, worker_pid FROM tasks WHERE id = ?", (task,))
    if t is None or t.get("status") != "running" or str(t.get("current_run_id")) != run:
        return None                       # not this execution's live run: nothing to record
    sid = str(payload.get("session_id") or env.get("HERMES_SESSION_ID") or "")
    db = Path(env.get("HERMES_HOME") or "") / "state.db"
    used = run_prompt_tokens(db, sid, float(row.get("started_at") or 0))
    if used is None or used < limit:
        return None
    reason = run_reason(used, limit)
    pid = t.get("worker_pid") or row.get("worker_pid") or parent_pid
    native.record_run_failure(task, reason)
    if pid:
        kill(int(pid))
    return {"action": "block", "message": reason}


# ------------------------------------------------------------------------- migration run

def read_stops(path: Path) -> list[dict[str, Any]]:
    out = []
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return out
    for line in lines:
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if isinstance(ev, dict) and ev.get("event") in ("stop", "lift") and ev.get("code") in MIGRATION_CODES:
            out.append(ev)
    return out


def append_stop(path: Path, event: dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    line = (json.dumps(event, sort_keys=True) + "\n").encode("utf-8")
    fd = os.open(str(path), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        os.write(fd, line)
    finally:
        os.close(fd)


def active_stops(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """code -> its latest stop, for every code whose latest event is a stop (not lifted)."""
    last: dict[str, dict[str, Any]] = {}
    for ev in events:
        last[ev["code"]] = ev
    return {c: ev for c, ev in last.items() if ev["event"] == "stop"}


def live_tasks(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return _rows(conn, "SELECT id, status, current_run_id, worker_pid FROM tasks WHERE status IN (?, ?) ORDER BY id", LIVE)


def last_acceptance(conn: sqlite3.Connection) -> tuple[str, float | None]:
    row = _one(conn, "SELECT id, completed_at FROM tasks WHERE completed_at IS NOT NULL ORDER BY completed_at DESC LIMIT 1")
    return (str(row["id"]), float(row["completed_at"])) if row else ("", None)


def first_run_start(conn: sqlite3.Connection) -> float | None:
    row = _one(conn, "SELECT MIN(started_at) AS s FROM task_runs")
    return float(row["s"]) if row and row.get("s") is not None else None


def due_stop(conn: sqlite3.Connection, limits: dict[str, Any], used: int | None, now: float,
             events: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The migration stop that is due now, or None. A token stop fires once per run; the stall
    stop measures from the latest of the last accepted card, the first worker run and its last lift."""
    tok = _int(limits.get(BUDGET_TOKEN_KEY))
    if tok is not None and used is not None and used >= tok and not any(e["code"] == MIGRATION_TOKEN_CODE for e in events):
        return {"event": "stop", "code": MIGRATION_TOKEN_CODE, "at": now, "used": used, "limit": tok,
                "reason": migration_token_reason(used, tok)}
    mins = _int(limits.get(BUDGET_STALL_KEY))
    if mins is None:
        return None
    last_task, last_at = last_acceptance(conn)
    lifts = [float(e.get("at") or 0) for e in events if e["code"] == STALL_CODE and e["event"] == "lift"]
    base = max([x for x in (last_at, first_run_start(conn), max(lifts) if lifts else None) if x is not None], default=None)
    if base is None or now - base < mins * 60:
        return None
    waited = int((now - base) // 60)
    return {"event": "stop", "code": STALL_CODE, "at": now, "minutes": waited, "limit": mins,
            "last_accepted": last_task, "reason": stall_reason(waited, mins, last_task, last_at)}


def tick(conn: sqlite3.Connection, native: Any, kill: Callable[[int], None], limits: dict[str, Any],
         used: int | None, now: float, stops: Path) -> list[dict[str, Any]]:
    """One dispatcher tick: fire a due migration stop, then hold every active stop on the board."""
    events = read_stops(stops)
    active = active_stops(events)
    live = live_tasks(conn)
    out: list[dict[str, Any]] = []
    if not active and live:
        due = due_stop(conn, limits, used, now, events)
        if due is not None:
            append_stop(stops, due)
            active = {due["code"]: due}
            out.append({"fired": due["code"], "reason": due["reason"]})
    for code, ev in sorted(active.items()):
        for t in live:
            running = t.get("status") == "running"
            ok = native.block(str(t["id"]), str(ev.get("reason") or code),
                              int(t["current_run_id"]) if running and t.get("current_run_id") is not None else None)
            if ok and running and t.get("worker_pid"):
                kill(int(t["worker_pid"]))
            out.append({"stop": code, "task": t["id"], "blocked": bool(ok), "was": t.get("status")})
        break                                # one active stop holds the board
    return out


# ------------------------------------------------------------------------- entry points

def _payload() -> dict:
    try:
        doc = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        return {}
    return doc if isinstance(doc, dict) else {}


def _pre_tool() -> int:
    env = dict(os.environ)
    if not (env.get("HERMES_KANBAN_TASK") and env.get("HERMES_KANBAN_RUN_ID") and env.get("HERMES_KANBAN_DB")):
        return 0
    try:
        payload = _payload()
        managed = env.get("HERMES_MANAGED_DIR") or "/projects/.platform/hermes"
        profile = json.loads(Path(managed, "model-profile.json").read_text(encoding="utf-8"))
        if run_limit(profile) is None:
            print("run_budget: the selected profile pins no %s; not enforced" % PROFILE_KEY, file=sys.stderr)
            return 0
        conn = _ro(Path(env["HERMES_KANBAN_DB"]))
        try:
            decision = check_tool_call(payload, env, conn, LazyNative(HermesNative), sigterm, profile,
                                       parent_pid=os.getppid())
        finally:
            conn.close()
    except Exception as exc:  # fail open: a budget reader that cannot read never stops correct work
        print("run_budget: not enforced (%s: %s)" % (type(exc).__name__, exc), file=sys.stderr)
        return 0
    if decision:
        sys.stdout.write(json.dumps(decision))
        sys.stdout.flush()
    return 0


def _tick(args: argparse.Namespace) -> int:
    try:
        payload = _payload()
        extra = payload.get("extra") if isinstance(payload.get("extra"), dict) else {}
        limits, why = declared_limits(Path(args.root))
        if why:
            print("run_budget tick: %s; migration stops not enforced" % why, file=sys.stderr)
            return 0
        used = migration_prompt_tokens(state_dbs(os.environ.get("HERMES_HOME") or ""))
        native = HermesNative(board=extra.get("board") or None, db_path=args.kanban_db)
        for row in tick(native.conn, native, sigterm, limits, used, time.time(), Path(args.stops)):
            print("run_budget tick: %s" % json.dumps(row, sort_keys=True), file=sys.stderr)
    except Exception as exc:  # an observer of the dispatcher never fails its tick
        print("run_budget tick: not enforced (%s: %s)" % (type(exc).__name__, exc), file=sys.stderr)
    return 0


def _lift(args: argparse.Namespace) -> int:
    active = active_stops(read_stops(Path(args.stops)))
    if args.code not in active:
        print("REFUSE: %s is not an active stop in %s (active: %s)" % (args.code, args.stops, ", ".join(sorted(active)) or "none"),
              file=sys.stderr)
        return 1
    append_stop(Path(args.stops), {"event": "lift", "code": args.code, "at": time.time(), "by": args.by,
                                   "note": args.note or ""})
    print("lifted %s (by %s); unblock the cards natively to continue" % (args.code, args.by))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="mode", required=True)
    sub.add_parser("pre-tool")
    t = sub.add_parser("tick")
    t.add_argument("--root", required=True)
    t.add_argument("--stops", required=True)
    t.add_argument("--kanban-db", default=None)
    lf = sub.add_parser("lift")
    lf.add_argument("--stops", required=True)
    lf.add_argument("--code", required=True, choices=MIGRATION_CODES)
    lf.add_argument("--by", required=True)
    lf.add_argument("--note", default="")
    args = ap.parse_args(argv)
    if args.mode == "pre-tool":
        return _pre_tool()
    if args.mode == "tick":
        return _tick(args)
    return _lift(args)


if __name__ == "__main__":
    raise SystemExit(main())
