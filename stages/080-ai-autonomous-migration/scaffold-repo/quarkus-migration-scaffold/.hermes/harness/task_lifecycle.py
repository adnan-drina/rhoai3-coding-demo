#!/usr/bin/env python3
"""Task lifecycle — shared predicates + typed state machine (step 3 / B).

Predicates (W4-736 §5 / W4-738 §5.2):
  task_has_run / assert_applies_to_outputs — tip commit subject ``{tid}:``

State machine (whiteboard / ADR-47 B / ADR-48 REV-1):
  READY → RUNNING → TIPPED → VERIFY → ADVANCE
                  ↘ BLOCKED | DEBT (re-enter READY/RUNNING after clear)
  ADVANCE → READY  (typed REOPEN — reason ∈ REOPEN_REASONS)
  ADVANCE → DEBT   (O-DEBTADVANCE demotion — freeze-worthy debt projection)

TIPPED is first-class success evidence (tip SHA). Filesystem ALREADY COMPLETE
is not a substitute for typed ADVANCE + tip_sha (M5←M4 handoff).

ADR-48: tip_sha is an *observation* (attribution), never a restore authority.
REOPEN increments reopen_gen; completion claims are valid only while
state == ADVANCE with no unresolved freeze-worthy debt.md (c / O-DEBTADVANCE).

Ledger: migration/task-lifecycle.json
Verify dims: pure function of (wave, task_class) — not a second spelling of edges.

Usage:
  task_lifecycle.py transition --task TID --to STATE [--tip SHA] [--reason R]
  task_lifecycle.py reopen --task TID --reason REOPEN_REASON
  task_lifecycle.py on-committed --task TID [--tip SHA]
  task_lifecycle.py show [--task TID]
  task_lifecycle.py m5-check [--ids TID ...]
  task_lifecycle.py dims --wave A|B --class rewrite|infer|...
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(os.environ.get("SENSOR_ROOT", ".")).resolve()
LEDGER = ROOT / "migration" / "task-lifecycle.json"

READY = "READY"
RUNNING = "RUNNING"
TIPPED = "TIPPED"
VERIFY = "VERIFY"
ADVANCE = "ADVANCE"
BLOCKED = "BLOCKED"
DEBT = "DEBT"

STATES = frozenset({READY, RUNNING, TIPPED, VERIFY, ADVANCE, BLOCKED, DEBT})

# Legal transitions (specimen-agnostic).
# W4-742 §4: READY→ADVANCE removed — ADVANCE requires tip_sha via TIPPED→VERIFY.
# ADR-48 (b): ADVANCE→READY is typed REOPEN (reason ∈ REOPEN_REASONS), not --force.
# ADR-48 (c): ADVANCE→DEBT demotes completion when freeze-worthy debt is projected.
TRANSITIONS: dict[str, frozenset[str]] = {
    READY: frozenset({RUNNING, BLOCKED, DEBT, TIPPED}),
    RUNNING: frozenset({TIPPED, BLOCKED, DEBT, READY}),
    TIPPED: frozenset({VERIFY, BLOCKED, DEBT}),
    VERIFY: frozenset({ADVANCE, BLOCKED, DEBT, RUNNING}),
    ADVANCE: frozenset({READY, DEBT}),  # REOPEN or debt demotion (O-DEBTADVANCE)
    BLOCKED: frozenset({READY, RUNNING, DEBT}),
    DEBT: frozenset({READY, RUNNING}),
}

# ADR-48 REV-1 — closed reopen reason enum (F-reopen-typed).
REOPEN_REASONS = frozenset(
    {
        "consumer_assert",
        "phase_rewind",
        "replan_orphan",
        "operator",
    }
)

# Dim matrix — pure function of (wave, class). Not ADR-46 edges.
_DIMS: dict[tuple[str, str], list[str]] = {
    ("A", "infer"): ["task-sensor", "scoped-sonar"],
    ("A", "characterize"): ["task-sensor", "scoped-sonar"],
    ("B", "rewrite"): ["fidelity", "spring-residue"],
    ("B", "infer"): ["redesign-sig", "compile-test"],
    ("B", "structure"): ["task-sensor", "package-presence"],
}


def task_has_run(tid: str, *, root: Path | None = None) -> bool:
    """True when a tip commit subject starts with ``{tid}:``."""
    if not tid:
        return False
    base = root if root is not None else ROOT
    try:
        r = subprocess.run(
            [
                "git",
                "-C",
                str(base),
                "log",
                "--all",
                "--pretty=%s",
                "-E",
                "--grep",
                f"^{re.escape(tid)}:",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception:
        return False
    return bool((r.stdout or "").strip())


def assert_applies_to_outputs(tid: str, *, root: Path | None = None) -> bool:
    """Gate for asserts over task outputs (Owns paths, produced tests, …)."""
    return task_has_run(tid, root=root)


def tip_sha_for(tid: str, *, root: Path | None = None) -> str:
    """Newest tip SHA whose subject starts with ``{tid}:``."""
    if not tid:
        return ""
    base = root if root is not None else ROOT
    try:
        r = subprocess.run(
            [
                "git",
                "-C",
                str(base),
                "log",
                "--all",
                "--pretty=%H",
                "-E",
                "--grep",
                f"^{re.escape(tid)}:",
                "-n",
                "1",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception:
        return ""
    return (r.stdout or "").strip().splitlines()[0] if (r.stdout or "").strip() else ""


def dims_for(wave: str, task_class: str) -> list[str]:
    """Verify dims from (wave, class) — never authored per-task."""
    w = (wave or "").strip().upper() or "B"
    c = (task_class or "").strip().lower()
    if c == "characterize":
        c = "infer"
        w = "A"
    return list(_DIMS.get((w, c), ["task-sensor"]))


def _load_ledger(path: Path | None = None) -> dict[str, Any]:
    p = path or LEDGER
    if not p.is_file():
        return {"version": 1, "tasks": {}}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"version": 1, "tasks": {}}


def _save_ledger(data: dict[str, Any], path: Path | None = None) -> None:
    p = path or LEDGER
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def get_state(tid: str, *, ledger: dict | None = None) -> str:
    data = ledger if ledger is not None else _load_ledger()
    row = (data.get("tasks") or {}).get(tid) or {}
    return str(row.get("state") or READY)


def _normalize_reopen_reason(reason: str) -> str:
    """Map legacy reopen labels onto ADR-48 REOPEN_REASONS."""
    r = (reason or "").strip()
    if r in REOPEN_REASONS:
        return r
    low = r.lower()
    if "charsurefuse" in low or "char_surface" in low or "refuse-char" in low:
        return "consumer_assert"
    if "phase-rewind" in low or "phase_rewind" in low or low.startswith("o-m3rewind"):
        return "phase_rewind"
    if "replan" in low or "orphan" in low:
        return "replan_orphan"
    if low.startswith("o-lifecycle") or low == "operator" or "operator" in low:
        return "operator"
    return r


def transition(
    tid: str,
    to_state: str,
    *,
    tip_sha: str = "",
    reason: str = "",
    dims: list[str] | None = None,
    blocked_on: str = "",
    force: bool = False,
    root: Path | None = None,
) -> dict[str, Any]:
    """Apply a typed transition; refuse illegal ones unless force.

    BLOCKED carries ``blocked_on`` (unit key or task id) — recorded outcome,
    not an error path (W4-740 §3 / W4-697 T-010 class).

    W4-742: ``force`` is a named emergency escape (O-LIFECYCLEFORCE) — every
    use is logged. Happy-path supervisor sites must not pass ``--force``.
    ADVANCE requires tip_sha (unless force) so READY→ADVANCE cannot launder
    tip-less completion.

    ADR-48 (b): ADVANCE→READY requires reason ∈ REOPEN_REASONS (typed REOPEN).
    tip_sha is never cleared on reopen — it remains an observation (a).

    ADR-48 (c): ADVANCE with unresolved freeze-worthy debt.md is unrepresentable
    (O-DEBTADVANCE). ADVANCE→DEBT is the demotion edge when debt is projected.
    """
    # ledger path fixed via LEDGER / SENSOR_ROOT; root used for debt.md check
    debt_root = root if root is not None else ROOT
    to_state = (to_state or "").strip().upper()
    if to_state not in STATES:
        raise SystemExit(f"unknown state {to_state!r}")
    data = _load_ledger()
    tasks = data.setdefault("tasks", {})
    row = tasks.get(tid) or {"state": READY, "history": [], "reopen_gen": 0}
    cur = str(row.get("state") or READY)
    effective_tip = tip_sha or str(row.get("tip_sha") or "")
    if to_state == ADVANCE and not effective_tip and not force:
        raise SystemExit(
            f"O-LIFECYCLESM: ADVANCE requires tip_sha for {tid} "
            f"(W4-742 / O-ADVANCETIP)"
        )
    if to_state == ADVANCE and not force:
        # Import locally so instruments can run without debt_journal on PATH quirks
        try:
            from debt_journal import advance_with_debt_forbidden
        except ImportError:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from debt_journal import advance_with_debt_forbidden
        _debt_refuse = advance_with_debt_forbidden(tid, root=debt_root)
        if _debt_refuse:
            raise SystemExit(_debt_refuse)
    if cur == ADVANCE and to_state == DEBT:
        if not (reason or "").strip() and not force:
            raise SystemExit(
                f"O-DEBTADVANCE: ADVANCE→DEBT for {tid} requires --reason "
                f"(freeze-worthy debt projection / ADR-48c)"
            )
        print(
            f"O-DEBTADVANCE: {tid} ADVANCE→DEBT reason={reason or '-'} "
            f"tip_obs={effective_tip[:12] or 'none'}",
            file=sys.stderr,
        )
    reopen_reason = ""
    if cur == ADVANCE and to_state == READY:
        reopen_reason = _normalize_reopen_reason(reason)
        if reopen_reason not in REOPEN_REASONS and not force:
            raise SystemExit(
                f"O-LIFECYCLEREOPEN: ADVANCE→READY for {tid} requires "
                f"reason in {sorted(REOPEN_REASONS)} (got {reason!r}); "
                f"use: task_lifecycle.py reopen --task {tid} --reason …"
            )
        reason = reopen_reason or reason
    if cur != to_state:
        allowed = TRANSITIONS.get(cur, frozenset())
        illegal = to_state not in allowed
        if illegal and not force:
            raise SystemExit(
                f"O-LIFECYCLESM: illegal {cur}→{to_state} for {tid} "
                f"(allowed={sorted(allowed)})"
            )
        if force:
            # O-LIFECYCLEFORCE — log every force use (W4-742 ask 2 / W4-744 §3),
            # not only illegal edges. Countable named omission (O-COVERDEPTH class).
            print(
                f"O-LIFECYCLEFORCE: {tid} {cur}→{to_state} "
                f"illegal={illegal} reason={reason or '-'}",
                file=sys.stderr,
            )
        # ADR-48 (b): typed REOPEN semantics before state flip
        if cur == ADVANCE and to_state == READY:
            gen = int(row.get("reopen_gen") or 0) + 1
            row["reopen_gen"] = gen
            tip_hist = list(row.get("tip_history") or [])
            obs = str(row.get("tip_sha") or "")
            if obs:
                tip_hist.append(
                    {
                        "sha": obs,
                        "reopen_gen": gen,
                        "reason": reason,
                        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    }
                )
                row["tip_history"] = tip_hist[-20:]
            # tip_sha stays — observation only (ADR-48 a); never checkout
            print(
                f"O-LIFECYCLEREOPEN: {tid} ADVANCE→READY reason={reason} "
                f"reopen_gen={gen} tip_obs={obs[:12] or 'none'}",
                file=sys.stderr,
            )
        hist = list(row.get("history") or [])
        hist.append(
            {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "from": cur,
                "to": to_state,
                "reason": reason,
                "tip_sha": tip_sha,
                "blocked_on": blocked_on,
                "force": bool(force and illegal),
                "reopen": bool(cur == ADVANCE and to_state == READY),
                "reopen_gen": row.get("reopen_gen"),
            }
        )
        row["history"] = hist[-40:]
        row["state"] = to_state
    if tip_sha:
        # Observation / attribution only — callers must not restore tree from this.
        row["tip_sha"] = tip_sha
    if dims is not None:
        row["dims"] = list(dims)
    if reason and to_state in (BLOCKED, DEBT):
        row["reason"] = reason
    if to_state == ADVANCE:
        row["completed_gen"] = int(row.get("reopen_gen") or 0)
    if to_state == BLOCKED:
        if not blocked_on and not reason:
            raise SystemExit(
                f"O-LIFECYCLESM: BLOCKED requires blocked_on=unit (or reason) for {tid}"
            )
        if blocked_on:
            row["blocked_on"] = blocked_on
    elif to_state in (READY, RUNNING, ADVANCE) and "blocked_on" in row:
        row.pop("blocked_on", None)
    tasks[tid] = row
    _save_ledger(data)
    return row


def reopen(
    tid: str,
    reason: str,
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    """ADR-48 typed REOPEN — ADVANCE→READY with reason ∈ REOPEN_REASONS."""
    norm = _normalize_reopen_reason(reason)
    if norm not in REOPEN_REASONS:
        raise SystemExit(
            f"O-LIFECYCLEREOPEN: reason must be one of {sorted(REOPEN_REASONS)} "
            f"(got {reason!r})"
        )
    cur = get_state(tid)
    if cur != ADVANCE:
        raise SystemExit(
            f"O-LIFECYCLEREOPEN: {tid} is {cur}, not ADVANCE — reopen refused"
        )
    return transition(tid, READY, reason=norm, root=root)


def on_committed(
    tid: str,
    *,
    tip_sha: str = "",
    wave: str = "B",
    task_class: str = "rewrite",
) -> dict[str, Any]:
    """Record tip → verify dims → ADVANCE (happy path after tip lands).

    W4-742: walks only legal edges — no ``force``. Path depends on current
    state so mid-path re-entry (TIPPED/VERIFY) does not rewind illegally.
    """
    sha = (tip_sha or tip_sha_for(tid) or "").strip()
    if not sha:
        raise SystemExit(
            f"O-LIFECYCLESM: on-committed requires tip_sha for {tid} (O-ADVANCETIP)"
        )
    dims = dims_for(wave, task_class)
    cur = get_state(tid)
    if cur == ADVANCE:
        row = (_load_ledger().get("tasks") or {}).get(tid) or {}
        prev = str(row.get("tip_sha") or "").strip()
        # Same observation (full or abbreviated) — idempotent.
        if prev and (
            prev == sha
            or prev.startswith(sha[:12])
            or sha.startswith(prev[:12])
        ):
            return row
        # O-ADVANCETIPSHA: newer tip landed while still ADVANCE (replan/escalation).
        # tip_sha is attribution only (ADR-48a) — refresh observation; do not restore tree.
        print(
            f"O-ADVANCETIPSHA: {tid} tip_obs {prev[:12] or 'none'}→{sha[:12]} "
            f"(refresh; not restore)",
            file=sys.stderr,
        )
        return transition(
            tid, ADVANCE, tip_sha=sha, dims=dims, reason="tip-obs-refresh"
        )
    # Legal cascade (no force): BLOCKED|DEBT|READY → RUNNING → TIPPED → VERIFY → ADVANCE
    if cur in (BLOCKED, DEBT, READY):
        transition(tid, RUNNING, reason="on-committed")
        cur = RUNNING
    if cur == RUNNING:
        transition(tid, TIPPED, tip_sha=sha, reason="tip-commit")
        cur = TIPPED
    if cur == TIPPED:
        transition(tid, VERIFY, tip_sha=sha, dims=dims, reason="verify-dims")
        cur = VERIFY
    if cur == VERIFY:
        transition(
            tid,
            ADVANCE,
            tip_sha=sha,
            dims=dims,
            reason="verify-dims-recorded",
        )
    return (_load_ledger().get("tasks") or {}).get(tid) or {}

def m5_check(ids: list[str]) -> list[dict[str, str]]:
    """Return gaps: tasks lacking ADVANCE + tip_sha (M5←M4 handoff).

    W4-741 §3b — lifecycle-aware: *"not yet run"* is not a gap; only
    *"ran and produced no typed tip/ADVANCE"* is. Uses
    ``assert_applies_to_outputs`` (same predicate as Owns-missing).

    ADR-48 (d): ``BLOCKED`` is a recorded outcome (not a silent gap); listed
    separately so M5 can refuse without treating it as crash.
    """
    data = _load_ledger()
    tasks = data.get("tasks") or {}
    gaps: list[dict[str, str]] = []
    for tid in ids:
        row = tasks.get(tid) or {}
        st = str(row.get("state") or "")
        tip = str(row.get("tip_sha") or "")
        if st == ADVANCE and tip:
            continue
        if st == BLOCKED:
            gaps.append(
                {
                    "task": tid,
                    "detail": (
                        f"BLOCKED(on={row.get('blocked_on') or '?'}; "
                        f"reason={row.get('reason') or '?'}; O-BLOCKSCHED / ADR-48d)"
                    ),
                }
            )
            continue
        ran = assert_applies_to_outputs(tid) or bool(tip)
        if not ran:
            # Pre-dispatch / never tipped — not a ship defect
            continue
        gaps.append(
            {
                "task": tid,
                "detail": (
                    f"ran but not ADVANCE+tip_sha "
                    f"(state={st or READY} tip_sha={'yes' if tip else 'missing'}; "
                    f"O-M5LIFECYCLE / W4-741)"
                ),
            }
        )
    return gaps


def blocked_among(ids: list[str]) -> list[str]:
    """ADR-48 (d) — task ids currently in BLOCKED (scheduler observation)."""
    data = _load_ledger()
    tasks = data.get("tasks") or {}
    out: list[str] = []
    for tid in ids:
        row = tasks.get(tid) or {}
        if str(row.get("state") or "") == BLOCKED:
            out.append(tid)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="O-LIFECYCLESM task lifecycle")
    ap.add_argument(
        "cmd",
        choices=(
            "transition",
            "reopen",
            "on-committed",
            "show",
            "m5-check",
            "blocked",
            "dims",
            "matrix",
        ),
    )
    ap.add_argument("--task", default="")
    ap.add_argument("--to", default="")
    ap.add_argument("--tip", default="")
    ap.add_argument("--reason", default="")
    ap.add_argument(
        "--blocked-on",
        default="",
        help="Unit key or dependency id for BLOCKED(on=…) (W4-740 §3)",
    )
    ap.add_argument("--wave", default="B")
    ap.add_argument("--class", dest="task_class", default="rewrite")
    ap.add_argument("--ids", nargs="*", default=[])
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    if args.cmd == "dims":
        print(" ".join(dims_for(args.wave, args.task_class)))
        return 0

    if args.cmd == "matrix":
        # W4-741 §3a — publish transition edges for review
        print("O-LIFECYCLESM:TRANSITION-MATRIX")
        for src in sorted(STATES):
            dests = sorted(TRANSITIONS.get(src, frozenset()))
            print(f"  {src} → {', '.join(dests) if dests else '(terminal)'}")
        return 0

    if args.cmd == "show":
        data = _load_ledger()
        if args.task:
            print(json.dumps((data.get("tasks") or {}).get(args.task, {}), indent=2))
        else:
            print(json.dumps(data, indent=2))
        return 0

    if args.cmd == "m5-check":
        ids = list(args.ids or [])
        gaps = m5_check(ids)
        if not gaps:
            print("O-LIFECYCLESM:M5-CHECK OK")
            return 0
        print(f"O-LIFECYCLESM:M5-CHECK GAPS {len(gaps)}")
        for g in gaps[:20]:
            print(f"  GAP {g['task']}: {g['detail']}")
        return 1

    if args.cmd == "blocked":
        # ADR-48 (d) / O-BLOCKSCHED — list BLOCKED ids among --ids
        ids = list(args.ids or [])
        blocked = blocked_among(ids)
        if not blocked:
            print("O-BLOCKSCHED:NONE")
            return 0
        print(f"O-BLOCKSCHED:BLOCKED {len(blocked)}")
        for tid in blocked:
            row = (_load_ledger().get("tasks") or {}).get(tid) or {}
            print(
                f"  {tid} on={row.get('blocked_on') or '?'} "
                f"reason={row.get('reason') or '?'}"
            )
        return 1

    if args.cmd == "reopen":
        if not args.task or not args.reason:
            print("reopen needs --task and --reason", file=sys.stderr)
            return 2
        row = reopen(args.task, args.reason)
        print(
            f"O-LIFECYCLEREOPEN:READY task={args.task} "
            f"reopen_gen={row.get('reopen_gen')} "
            f"tip_obs={str(row.get('tip_sha') or '')[:12]}"
        )
        return 0

    if args.cmd == "on-committed":
        if not args.task:
            print("missing --task", file=sys.stderr)
            return 2
        row = on_committed(
            args.task,
            tip_sha=args.tip,
            wave=args.wave,
            task_class=args.task_class,
        )
        print(
            f"O-LIFECYCLESM:ADVANCE task={args.task} "
            f"tip={row.get('tip_sha', '')[:12]} dims={row.get('dims')}"
        )
        return 0

    # transition
    if not args.task or not args.to:
        print("need --task and --to", file=sys.stderr)
        return 2
    row = transition(
        args.task,
        args.to,
        tip_sha=args.tip,
        reason=args.reason,
        blocked_on=args.blocked_on,
        force=args.force,
    )
    extra = f" blocked_on={row.get('blocked_on')}" if row.get("blocked_on") else ""
    print(f"O-LIFECYCLESM:{row.get('state')} task={args.task}{extra}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
