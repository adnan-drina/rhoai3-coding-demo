"""Kanban stuck-task watchdog (AD-H §13/§15.2) — the ONLY Hermes cron job.

no_agent cron script: exit 0 + empty stdout = silent tick; exit 0 + stdout =
local alert; non-zero exit = error alert (broken watchdog cannot be silent).

Primary: alert when a task stays `running` past STUCK_SECONDS *after* native
`max_runtime_seconds` recovery should have fired. Does not restart/kill/board-
mutate.

Also (AD-009 §3.2a / Deputy E-20260810T145838Z): for every `running` task, invoke
`check-stream-liveness.py --ttfc-sec 90 --stamp` so TTFC is not documentation-only.
Verdict stamp on breach is allowed; board block remains Lead/Monitor.

Default stuck budget comes from `.hermes/phase-dispatch.yaml` (must exceed max
phase max_runtime_seconds). A second cron job requires an Architect decision
stating why this one is insufficient.
"""

from __future__ import annotations

import os
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_TTFC_SEC = 90


def hermes_home() -> Path:
    raw = os.environ.get("HERMES_HOME", "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".hermes"


def phase_dispatch_path() -> Path | None:
    """Scaffold-authored budgets live beside HERMES_HOME (…/.hermes/phase-dispatch.yaml)."""
    home = hermes_home()
    candidate = home.parent / "phase-dispatch.yaml"
    if candidate.is_file():
        return candidate
    env = os.environ.get("PHASE_DISPATCH_YAML", "").strip()
    if env:
        p = Path(env).expanduser()
        if p.is_file():
            return p
    return None


def stuck_seconds_from_yaml(path: Path) -> int | None:
    """Minimal parse — avoid PyYAML dependency in the cron sandbox."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    m = re.search(
        r"(?m)^watchdog:\s*\n(?:[ \t]+.+\n)*?[ \t]+stuck_seconds:\s*(\d+)\s*$",
        text,
    )
    if not m:
        return None
    return max(60, int(m.group(1)))


def stuck_seconds() -> int:
    # Precedence: env override → phase-dispatch.yaml → §15 default ( > max budget 3600 ).
    if "STUCK_SECONDS" in os.environ:
        try:
            return max(60, int(os.environ["STUCK_SECONDS"]))
        except ValueError as exc:
            raise SystemExit(
                f"kanban-stuck-watchdog: bad STUCK_SECONDS: {exc}"
            ) from exc
    path = phase_dispatch_path()
    if path is not None:
        parsed = stuck_seconds_from_yaml(path)
        if parsed is not None:
            return parsed
    return 4200


def project_root() -> Path:
    """Workspace root that owns migration/ and .hermes/home/kanban/logs/."""
    home = hermes_home()
    if home.name == "home" and home.parent.name == ".hermes":
        return home.parent.parent
    env = os.environ.get("PROJECT_ROOT", "").strip()
    if env:
        return Path(env).expanduser()
    return home.parent


def ttfc_seconds() -> int:
    if "TTFC_SECONDS" in os.environ:
        try:
            return max(30, int(os.environ["TTFC_SECONDS"]))
        except ValueError as exc:
            raise SystemExit(f"kanban-stuck-watchdog: bad TTFC_SECONDS: {exc}") from exc
    return DEFAULT_TTFC_SEC


def check_fast_deny(task_id: str, root: Path) -> str | None:
    """Return alert if non-retryable vLLM validation 400 seen (Deputy E-163600Z)."""
    script = hermes_home() / "scripts" / "check-vllm-validation-fast-deny.py"
    if not script.is_file():
        return None
    try:
        cp = subprocess.run(
            [
                sys.executable,
                str(script),
                str(root),
                "--task-id",
                str(task_id),
                "--stamp",
            ],
            text=True,
            capture_output=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"WATCHDOG: fast-deny check failed for {task_id}: {exc}"
    if cp.returncode == 2:
        detail = (cp.stderr or cp.stdout or "").strip().splitlines()
        tail = detail[-1] if detail else "vllm_validation_error"
        return (
            f"WATCHDOG: fast-deny task {task_id} — {tail}. "
            f"Do not sleep-retry; compact/split or Lead block."
        )
    return None


def check_ttfc(task_id: str, root: Path, ttfc: int) -> str | None:
    """Return alert line if TTFC breached; None if OK/skip."""
    script = hermes_home() / "scripts" / "check-stream-liveness.py"
    if not script.is_file():
        return (
            f"WATCHDOG: TTFC checker missing at {script} "
            f"(task {task_id}) — detector not invocable"
        )
    try:
        cp = subprocess.run(
            [
                sys.executable,
                str(script),
                str(root),
                "--task-id",
                str(task_id),
                "--ttfc-sec",
                str(ttfc),
                "--stamp",
            ],
            text=True,
            capture_output=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"WATCHDOG: TTFC check failed for {task_id}: {exc}"
    if cp.returncode == 2:
        detail = (cp.stderr or cp.stdout or "").strip().splitlines()
        tail = detail[-1] if detail else "ttfc_breach"
        return (
            f"WATCHDOG: TTFC breach task {task_id} (ttfc={ttfc}s) — {tail}. "
            f"Verdict stamp attempted; board action is Lead/Monitor."
        )
    return None


def find_running_table(conn: sqlite3.Connection) -> tuple[str, str, str] | None:
    """Return (table, status_col, time_col) for a tasks-like table, or None."""
    tables = [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    ]
    preferred = ("tasks", "kanban_tasks", "task", "items")
    ordered = [t for t in preferred if t in tables] + [
        t for t in tables if t not in preferred
    ]
    for table in ordered:
        cols = {
            r[1].lower(): r[1]
            for r in conn.execute(f'PRAGMA table_info("{table}")')
        }
        status_col = next(
            (cols[c] for c in ("status", "state", "column", "lane") if c in cols),
            None,
        )
        if not status_col:
            continue
        time_col = next(
            (
                cols[c]
                for c in (
                    "updated_at",
                    "updated",
                    "started_at",
                    "started",
                    "running_since",
                    "modified_at",
                    "mtime",
                    "created_at",
                    "created",
                )
                if c in cols
            ),
            None,
        )
        if time_col:
            return table, status_col, time_col
    return None


def parse_epoch(value: object, now: float) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        ts = float(value)
        # ms vs s heuristic
        if ts > 1e12:
            ts /= 1000.0
        return ts
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        return parse_epoch(int(text), now)
    try:
        # ISO-ish
        from datetime import datetime

        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text).timestamp()
    except ValueError:
        return None


def stillborn_grace_seconds() -> int:
    """Age after which running+NULL heartbeat is stillborn (Operator E-184628Z)."""
    if "STILLBORN_GRACE_SECONDS" in os.environ:
        try:
            return max(30, int(os.environ["STILLBORN_GRACE_SECONDS"]))
        except ValueError as exc:
            raise SystemExit(
                f"kanban-stuck-watchdog: bad STILLBORN_GRACE_SECONDS: {exc}"
            ) from exc
    return 120


def check_stillborn_null_heartbeat(
    conn: sqlite3.Connection, *, now: float, grace: int
) -> list[str]:
    """Alert when status=running but last_heartbeat_at is NULL past grace.

    Heartbeat-age watchdogs miss stillborn workers (provider-resolution failure
    at spawn): they never heartbeat, so AGE checks never fire.
    """
    try:
        cols = {
            r[1].lower(): r[1]
            for r in conn.execute('PRAGMA table_info("task_runs")')
        }
    except sqlite3.Error:
        return []
    need = {"task_id", "status", "started_at", "last_heartbeat_at"}
    if not need.issubset(cols):
        return []
    q = (
        f'SELECT "{cols["task_id"]}", "{cols["started_at"]}", '
        f'"{cols["last_heartbeat_at"]}", "{cols["status"]}" '
        f'FROM task_runs WHERE lower(cast("{cols["status"]}" as text)) = ? '
        f'AND "{cols["last_heartbeat_at"]}" IS NULL'
    )
    alerts: list[str] = []
    try:
        rows = list(conn.execute(q, ("running",)))
    except sqlite3.Error:
        return []
    for task_id, started_at, _hb, status in rows:
        started = parse_epoch(started_at, now)
        if started is None:
            alerts.append(
                f"WATCHDOG: STILLBORN task {task_id!s} status={status!s} "
                f"last_heartbeat_at=NULL started_at={started_at!r} "
                f"(unparseable) — reclaim/redispatch after Managed Scope check."
            )
            continue
        age = now - started
        if age >= grace:
            alerts.append(
                f"WATCHDOG: STILLBORN task {task_id!s} running with "
                f"last_heartbeat_at=NULL for {int(age)}s "
                f"(grace {grace}s). Likely spawn env missing "
                f"HERMES_MANAGED_DIR / provider — reclaim + assert-managed-scope-active."
            )
    return alerts


def check_complete_cmd_enforce(root: Path) -> list[str]:
    """Architect E-20260811T200911Z — auto-wire COMPLETE-CMD reclaim on red/missing receipt."""
    script = Path(__file__).resolve().parent / "enforce-complete-exit-criteria.py"
    if not script.is_file():
        return [
            "WATCHDOG: COMPLETE-CMD enforce script missing "
            f"({script}) — cannot auto-reclaim red receipts"
        ]
    try:
        cp = subprocess.run(
            [sys.executable, str(script), str(root), "--sweep-done"],
            cwd=str(root),
            text=True,
            capture_output=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return [f"WATCHDOG: COMPLETE-CMD enforce failed to run: {exc}"]
    out = ((cp.stdout or "") + (cp.stderr or "")).strip()
    if cp.returncode == 0:
        return []
    # rc=1 means reclaim happened or dry mismatch; surface tails for Lead
    lines = [ln for ln in out.splitlines() if ln.strip()][-12:]
    if not lines:
        lines = [f"enforce rc={cp.returncode}"]
    return ["WATCHDOG: COMPLETE-CMD enforce — " + ln for ln in lines]


def check_conversation_liveness(task_id: str, root: Path) -> str | None:
    """BANK-CONV-LIVE-WD-1 — flat transcript + API idle while hb warm (post-tool stall)."""
    script = Path(__file__).resolve().parent / "check-conversation-liveness.py"
    if not script.is_file():
        return None
    flat = int(os.environ.get("CONV_LIVE_FLAT_SECONDS", "600"))
    try:
        cp = subprocess.run(
            [
                sys.executable,
                str(script),
                str(root),
                "--task-id",
                task_id,
                "--flat-sec",
                str(flat),
            ],
            cwd=str(root),
            text=True,
            capture_output=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"WATCHDOG: conversation-liveness failed to run for {task_id}: {exc}"
    if cp.returncode == 0:
        return None
    tail = ((cp.stderr or "") + "\n" + (cp.stdout or "")).strip().splitlines()
    msg = tail[-1] if tail else f"rc={cp.returncode}"
    # RW-1: stamp stream-layer classify receipt (bounded-retry policy input)
    classify = Path(__file__).resolve().parent / "classify-conv-live-stall.py"
    if classify.is_file():
        try:
            subprocess.run(
                [
                    sys.executable,
                    str(classify),
                    str(root),
                    "--task-id",
                    task_id,
                    "--stamp",
                    "--flat-sec",
                    str(flat),
                ],
                cwd=str(root),
                text=True,
                capture_output=True,
                timeout=90,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
    return f"WATCHDOG: BANK-CONV-LIVE-WD-1 {task_id}: {msg}"


def main() -> int:
    home = hermes_home()
    db_path = Path(os.environ.get("KANBAN_DB", str(home / "kanban.db")))
    threshold = stuck_seconds()
    now = time.time()

    if not db_path.is_file():
        # No board yet — nothing stuck. Silent tick.
        return 0

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        print(f"kanban-stuck-watchdog: cannot open {db_path}: {exc}", file=sys.stderr)
        return 1

    try:
        found = find_running_table(conn)
        if found is None:
            print(
                f"kanban-stuck-watchdog: no tasks table with status+time columns in {db_path}",
                file=sys.stderr,
            )
            return 1
        table, status_col, time_col = found
        # Identify a human-readable id column if present
        cols = {
            r[1].lower(): r[1]
            for r in conn.execute(f'PRAGMA table_info("{table}")')
        }
        id_col = next(
            (cols[c] for c in ("id", "task_id", "uuid", "key", "name", "title") if c in cols),
            None,
        )
        select_cols = [status_col, time_col] + ([id_col] if id_col else [])
        q = (
            f'SELECT {", ".join(f"{c}" for c in select_cols)} '
            f'FROM "{table}" WHERE lower(cast("{status_col}" as text)) = ?'
        )
        rows = list(conn.execute(q, ("running",)))
        stillborn_alerts = check_stillborn_null_heartbeat(
            conn, now=now, grace=stillborn_grace_seconds()
        )
    except sqlite3.Error as exc:
        print(f"kanban-stuck-watchdog: query failed: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()

    alerts: list[str] = list(stillborn_alerts)
    root = project_root()
    # Architect E-20260811T200911Z — red/missing complete-exit receipt must not stay done
    alerts.extend(check_complete_cmd_enforce(root))
    ttfc = ttfc_seconds()
    for row in rows:
        status_v, time_v = row[0], row[1]
        ident = row[2] if len(row) > 2 else "?"
        started = parse_epoch(time_v, now)
        if started is None:
            alerts.append(
                f"WATCHDOG: task {ident!s} status={status_v!s} has unparseable "
                f"{time_col}={time_v!r} (threshold {threshold}s)"
            )
            continue
        age = now - started
        if age >= threshold:
            alerts.append(
                f"WATCHDOG: Kanban task {ident!s} stuck in running for "
                f"{int(age)}s (threshold {threshold}s). Alert only — no action taken."
            )
        # AD-009 §3.2a — TTFC caller (Deputy E-20260810T145838Z)
        ttfc_alert = check_ttfc(str(ident), root, ttfc)
        if ttfc_alert:
            alerts.append(ttfc_alert)
        # Deputy E-20260810T163600Z — fast-deny non-retryable validation 400s
        fd_alert = check_fast_deny(str(ident), root)
        if fd_alert:
            alerts.append(fd_alert)
        # BANK-CONV-LIVE-WD-1 — post-tool / stream-stale class (warm hb mask)
        cl_alert = check_conversation_liveness(str(ident), root)
        if cl_alert:
            alerts.append(cl_alert)

    if alerts:
        print("\n".join(alerts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
