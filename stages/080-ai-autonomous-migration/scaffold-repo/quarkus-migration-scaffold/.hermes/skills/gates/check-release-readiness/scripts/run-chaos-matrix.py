#!/usr/bin/env python3
"""Plan #7 chaos matrix — timeout, process death, dup dispatch, digest mismatch,
gate refusal exercised together; each leaves a named Kanban/verdict terminal.

Uses Hermes-native recovery (enforce_max_runtime / detect_crashed_workers /
idempotency) plus our domain consumers (BODY_REF_DIGEST, gate REFUSE). Does
**not** spawn LLM workers (AD-004: no orchestration rebuild).

Usage:
  HERMES_AGENT_ROOT=/home/user/.hermes/hermes-agent \\
    /path/to/hermes/venv/bin/python run-chaos-matrix.py <repo-root> \\
    [--out DIR] [--board SLUG]

Exit 0 only when all five scenarios record a named terminal state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


SCENARIOS = (
    "timeout",
    "process_death",
    "dup_dispatch",
    "digest_mismatch",
    "gate_refusal",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def load_hermes_db():
    root = Path(os.environ.get("HERMES_AGENT_ROOT", "")).expanduser()
    if not root.is_dir():
        # Common Dev Spaces layout
        cand = Path.home() / ".hermes" / "hermes-agent"
        if cand.is_dir():
            root = cand
    if not root.is_dir():
        raise SystemExit(
            "FAIL: set HERMES_AGENT_ROOT to hermes-agent checkout "
            "(needs hermes_cli.kanban_db)"
        )
    sys.path.insert(0, str(root))
    from hermes_cli import kanban_db as kb  # type: ignore

    return kb


def ensure_board(kb, slug: str) -> None:
    if not kb.board_exists(slug):
        kb.create_board(slug, name=f"Chaos matrix ({slug})")
    # Prefer not to switch global current board permanently; pass board= to APIs.


def task_events(conn, tid: str) -> list[dict]:
    rows = conn.execute(
        "SELECT kind, payload, created_at FROM task_events WHERE task_id = ? "
        "ORDER BY id",
        (tid,),
    ).fetchall()
    out = []
    for r in rows:
        payload = r["payload"]
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:
                pass
        out.append({"kind": r["kind"], "payload": payload, "created_at": r["created_at"]})
    return out


def task_runs(conn, tid: str) -> list[dict]:
    rows = conn.execute(
        "SELECT id, status, outcome, error, worker_pid, started_at, ended_at "
        "FROM task_runs WHERE task_id = ? ORDER BY id",
        (tid,),
    ).fetchall()
    return [dict(r) for r in rows]


def task_status(conn, tid: str) -> str:
    row = conn.execute("SELECT status FROM tasks WHERE id = ?", (tid,)).fetchone()
    return str(row["status"]) if row else "missing"


def scenario_timeout(kb, conn, board: str) -> dict:
    """max_runtime exceeded → outcome/event timed_out."""
    del board  # conn already scoped to the chaos board
    tid = kb.create_task(
        conn,
        title="CHAOS-7 timeout probe",
        body="Chaos matrix: sleep past max_runtime_seconds.",
        created_by="Lead",
        workspace_kind="scratch",
        max_runtime_seconds=2,
        max_retries=1,
        # Hermes VALID_INITIAL_STATUSES = {blocked, running}; "running" → ready.
        initial_status="running",
        idempotency_key=f"chaos7-timeout-{int(time.time())}",
    )
    claimed = kb.claim_task(conn, tid)
    if claimed is None:
        return {"scenario": "timeout", "ok": False, "error": "claim_failed", "task_id": tid}
    # Start a long-lived child and bind as worker (no LLM).
    proc = subprocess.Popen(["sleep", "120"])
    kb._set_worker_pid(conn, tid, proc.pid)
    # Backdate started_at so enforce_max_runtime sees elapsed > limit.
    with kb.write_txn(conn):
        conn.execute(
            "UPDATE tasks SET started_at = ? WHERE id = ?",
            (int(time.time()) - 10, tid),
        )
        run_id = kb._current_run_id(conn, tid)
        if run_id is not None:
            conn.execute(
                "UPDATE task_runs SET started_at = ? WHERE id = ?",
                (int(time.time()) - 10, run_id),
            )
    timed = kb.enforce_max_runtime(conn)
    # Child may already be dead from SIGTERM/SIGKILL; reap.
    try:
        proc.wait(timeout=8)
    except Exception:
        try:
            os.kill(proc.pid, signal.SIGKILL)
        except Exception:
            pass
    events = task_events(conn, tid)
    runs = task_runs(conn, tid)
    kinds = {e["kind"] for e in events}
    outcomes = {r.get("outcome") for r in runs}
    terminal = "timed_out" if ("timed_out" in kinds or "timed_out" in outcomes or tid in timed) else None
    return {
        "scenario": "timeout",
        "ok": terminal == "timed_out",
        "task_id": tid,
        "terminal_state": terminal or f"status={task_status(conn, tid)}",
        "kanban_status": task_status(conn, tid),
        "event_kinds": sorted(kinds),
        "run_outcomes": sorted(o for o in outcomes if o),
        "enforce_returned": timed,
        "evidence": {"events": events[-6:], "runs": runs},
    }


def scenario_process_death(kb, conn, board: str) -> dict:
    """Worker PID vanishes → outcome/event crashed."""
    del board
    tid = kb.create_task(
        conn,
        title="CHAOS-7 process-death probe",
        body="Chaos matrix: kill worker PID; detect_crashed_workers.",
        created_by="Lead",
        workspace_kind="scratch",
        max_runtime_seconds=300,
        max_retries=1,
        initial_status="running",
        idempotency_key=f"chaos7-death-{int(time.time())}",
    )
    claimed = kb.claim_task(conn, tid)
    if claimed is None:
        return {"scenario": "process_death", "ok": False, "error": "claim_failed", "task_id": tid}
    proc = subprocess.Popen(["sleep", "120"])
    kb._set_worker_pid(conn, tid, proc.pid)
    # Bypass launch-window grace by backdating started_at.
    with kb.write_txn(conn):
        conn.execute(
            "UPDATE tasks SET started_at = ? WHERE id = ?",
            (int(time.time()) - 60, tid),
        )
    os.kill(proc.pid, signal.SIGKILL)
    try:
        proc.wait(timeout=5)
    except Exception:
        pass
    time.sleep(0.3)
    crashed = kb.detect_crashed_workers(conn)
    events = task_events(conn, tid)
    runs = task_runs(conn, tid)
    kinds = {e["kind"] for e in events}
    outcomes = {r.get("outcome") for r in runs}
    terminal = "crashed" if ("crashed" in kinds or "crashed" in outcomes or tid in crashed) else None
    return {
        "scenario": "process_death",
        "ok": terminal == "crashed",
        "task_id": tid,
        "terminal_state": terminal or f"status={task_status(conn, tid)}",
        "kanban_status": task_status(conn, tid),
        "event_kinds": sorted(kinds),
        "run_outcomes": sorted(o for o in outcomes if o),
        "detect_returned": crashed,
        "evidence": {"events": events[-6:], "runs": runs},
    }


def scenario_dup_dispatch(kb, conn, board: str) -> dict:
    """Idempotency key + second claim refuse → named dup terminal."""
    del board
    key = f"chaos7-dup-{int(time.time())}"
    tid1 = kb.create_task(
        conn,
        title="CHAOS-7 dup-dispatch probe",
        body="Chaos matrix: idempotent create + duplicate claim refuse.",
        created_by="Lead",
        workspace_kind="scratch",
        max_runtime_seconds=60,
        max_retries=1,
        initial_status="running",
        idempotency_key=key,
    )
    tid2 = kb.create_task(
        conn,
        title="CHAOS-7 dup-dispatch probe (retry)",
        body="should dedup",
        created_by="Lead",
        workspace_kind="scratch",
        max_runtime_seconds=60,
        initial_status="running",
        idempotency_key=key,
    )
    claimed = kb.claim_task(conn, tid1)
    dup_claim = kb.claim_task(conn, tid1)
    events = task_events(conn, tid1)
    kinds = {e["kind"] for e in events}
    # Named terminal: idempotent_same_id + claim_rejected_or_none
    same_id = tid1 == tid2
    claim_refused = claimed is not None and dup_claim is None
    terminal = None
    if same_id and claim_refused:
        terminal = "dup_dispatch_refused"
    elif same_id:
        terminal = "idempotent_same_task_id"
    return {
        "scenario": "dup_dispatch",
        "ok": same_id and claim_refused,
        "task_id": tid1,
        "terminal_state": terminal or "dup_dispatch_incomplete",
        "kanban_status": task_status(conn, tid1),
        "idempotency_key": key,
        "create_ids": [tid1, tid2],
        "second_create_same_id": same_id,
        "second_claim_refused": claim_refused,
        "event_kinds": sorted(kinds),
        "evidence": {"events": events[-8:]},
    }


def scenario_digest_mismatch(kb, conn, board: str, root: Path, out: Path) -> dict:
    """Wrong sha256 on typed body ref → BODY_REF_DIGEST + Kanban blocked."""
    anchor = root / "governance" / "contracts" / "check-release-readiness.md"
    if not anchor.is_file():
        anchor = root / "pom.xml"
    actual = sha256_file(anchor) if anchor.is_file() else "0" * 64
    wrong = ("f" if actual[0] != "f" else "0") + actual[1:]
    body = {
        "task_id": "t_chaos7_digest",
        "role": "implementer",
        "phase": "M4",
        "refs": [
            {
                "key": "story_tip",
                "path": (
                    str(anchor.relative_to(root))
                    if str(anchor).startswith(str(root))
                    else str(anchor)
                ),
                "sha256": wrong,
            }
        ],
    }
    bodies_dir = root / "evidence" / "bodies"
    bodies_dir.mkdir(parents=True, exist_ok=True)
    body_path = bodies_dir / "chaos7-digest-mismatch.json"
    body_path.write_text(json.dumps({"body": body}, indent=2) + "\n", encoding="utf-8")

    script = (
        root
        / ".hermes"
        / "skills"
        / "check-spec-readiness"
        / "scripts"
        / "check-kanban-body.py"
    )
    proc = subprocess.run(
        [sys.executable, str(script), str(root)],
        capture_output=True,
        text=True,
    )
    stderr = proc.stderr or ""
    stdout = proc.stdout or ""
    digest_hit = "BODY_REF_DIGEST" in stderr or "BODY_REF_DIGEST" in stdout

    tid = kb.create_task(
        conn,
        title="CHAOS-7 digest-mismatch probe",
        body="Chaos matrix: BODY_REF_DIGEST → blocked.",
        created_by="Lead",
        workspace_kind="dir",
        workspace_path=str(root),
        max_retries=1,
        initial_status="running",
        idempotency_key=f"chaos7-digest-{int(time.time())}",
    )
    del board
    kb.block_task(
        conn,
        tid,
        reason="BODY_REF_DIGEST: typed body digest mismatch (chaos matrix)",
        kind="needs_input",
    )
    status = task_status(conn, tid)
    events = task_events(conn, tid)
    kinds = {e["kind"] for e in events}
    terminal = "blocked:BODY_REF_DIGEST" if digest_hit and status == "blocked" else None

    # Clean ephemeral body so validate-contracts is not permanently red.
    body_path.unlink(missing_ok=True)
    (out / "digest-mismatch-stderr.txt").write_text(stderr + stdout, encoding="utf-8")

    return {
        "scenario": "digest_mismatch",
        "ok": terminal is not None,
        "task_id": tid,
        "terminal_state": terminal or f"digest_hit={digest_hit};status={status}",
        "kanban_status": status,
        "consumer_code": "BODY_REF_DIGEST" if digest_hit else None,
        "check_rc": proc.returncode,
        "event_kinds": sorted(kinds),
        "evidence": {"events": events[-6:], "wrong_sha256": wrong, "path": str(anchor)},
    }


def scenario_gate_refusal(kb, conn, board: str, root: Path, out: Path) -> dict:
    """Known-bad admission → REFUSE verdict + Kanban blocked."""
    g1 = (
        root
        / ".hermes"
        / "skills"
        / "check-domain-parity"
        / "scripts"
        / "g1-characterization.py"
    )
    proc = subprocess.run(
        [sys.executable, str(g1), str(root)],
        capture_output=True,
        text=True,
    )
    combined = (proc.stdout or "") + (proc.stderr or "")
    (out / "gate-refusal-g1.log").write_text(combined, encoding="utf-8")

    refuse_path = (
        root / "governance" / "fixtures"
        / "admission"
        / "out"
        / "g1-characterization"
        / "known-bad.json"
    )
    if not refuse_path.is_file():
        refuse_path = (
            root / "governance" / "fixtures"
            / "admission"
            / "out"
            / "g1"
            / "known-bad.json"
        )
    verdict_doc = None
    if refuse_path.is_file():
        verdict_doc = json.loads(refuse_path.read_text(encoding="utf-8"))
    gate_verdict = str((verdict_doc or {}).get("verdict") or "").upper()
    refuse_ok = gate_verdict == "REFUSE"

    # Persist chaos verdict snapshot (not story M5).
    chaos_verdict = {
        "phase": "CHAOS",
        "gate": "g1_characterization",
        "fixture": "known-bad",
        "verdict": "REFUSE" if refuse_ok else gate_verdict or "MISSING",
        "routing": "blocked",
        "ship": False,
        "story_id": "CHAOS-7",
        "reason": "Plan #7 gate refusal exercise (known-bad admission)",
    }
    vdir = root / "evidence" / "verdicts"
    vdir.mkdir(parents=True, exist_ok=True)
    vpath = vdir / "chaos7-gate-refusal.json"
    vpath.write_text(json.dumps(chaos_verdict, indent=2) + "\n", encoding="utf-8")

    tid = kb.create_task(
        conn,
        title="CHAOS-7 gate-refusal probe",
        body="Chaos matrix: known-bad G-1 REFUSE → blocked.",
        created_by="Lead",
        workspace_kind="dir",
        workspace_path=str(root),
        max_retries=1,
        initial_status="running",
        idempotency_key=f"chaos7-gate-{int(time.time())}",
    )
    del board
    kb.block_task(
        conn,
        tid,
        reason="gate_refusal:G-1 known-bad REFUSE (chaos matrix)",
        kind="needs_input",
    )
    status = task_status(conn, tid)
    terminal = "blocked:gate_REFUSE" if refuse_ok and status == "blocked" else None
    return {
        "scenario": "gate_refusal",
        "ok": terminal is not None,
        "task_id": tid,
        "terminal_state": terminal or f"verdict={gate_verdict};status={status}",
        "kanban_status": status,
        "gate_verdict": gate_verdict,
        "verdict_path": str(vpath.relative_to(root)),
        "g1_rc": proc.returncode,
        "evidence": {"verdict": chaos_verdict, "fixture": str(refuse_path)},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".", help="migration repo root")
    ap.add_argument("--out", default=None, help="evidence output directory")
    ap.add_argument("--board", default="chaos-matrix-7", help="isolated Kanban board slug")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    out = Path(args.out).resolve() if args.out else root / "evidence" / "chaos" / "live-7"
    out.mkdir(parents=True, exist_ok=True)

    kb = load_hermes_db()
    ensure_board(kb, args.board)
    conn = kb.connect(board=args.board)

    results = []
    results.append(scenario_timeout(kb, conn, args.board))
    results.append(scenario_process_death(kb, conn, args.board))
    results.append(scenario_dup_dispatch(kb, conn, args.board))
    results.append(scenario_digest_mismatch(kb, conn, args.board, root, out))
    results.append(scenario_gate_refusal(kb, conn, args.board, root, out))

    matrix = {
        "plan_item": 7,
        "name": "chaos_matrix",
        "ts": utc_now(),
        "board": args.board,
        "repo": str(root),
        "scenarios": results,
        "all_ok": all(r.get("ok") for r in results),
        "terminal_states": {
            r["scenario"]: r.get("terminal_state") for r in results
        },
    }
    (out / "matrix.json").write_text(json.dumps(matrix, indent=2) + "\n", encoding="utf-8")
    summary_lines = [
        f"# Chaos matrix — {'PASS' if matrix['all_ok'] else 'FAIL'}",
        "",
        f"Board: `{args.board}` · {matrix['ts']}",
        "",
        "| Scenario | OK | Terminal | Task |",
        "|----------|----|----------|------|",
    ]
    for r in results:
        summary_lines.append(
            f"| {r['scenario']} | {r.get('ok')} | `{r.get('terminal_state')}` | `{r.get('task_id')}` |"
        )
    (out / "RESULT.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    print(json.dumps(matrix["terminal_states"], indent=2))
    if not matrix["all_ok"]:
        print("FAIL: chaos matrix incomplete — see", out / "matrix.json", file=sys.stderr)
        return 1
    print(f"OK: chaos matrix DEMONSTRATED — evidence {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
