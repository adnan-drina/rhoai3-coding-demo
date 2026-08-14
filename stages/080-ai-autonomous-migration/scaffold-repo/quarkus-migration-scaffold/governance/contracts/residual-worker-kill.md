# Residual worker kill (Class A) — A-5

**Status:** binding (in-tree).

## Problem

`hermes kanban block` / status→`done` / triage **does not stop** the Hermes
worker process. On shared `dir:/projects/modernized`, a residual worker can keep
writing for tens of minutes after abort/terminal (proven: run#39 re-wrote
`*RepositoryOverride` post-quarantine; PID 85052 lived past `t_b5019586` done;
v17 S-001 completed ~6h after a board block; S-008 already terminal when
block was attempted).

**Never claim containment from `hermes kanban block` alone.** Board state is
not process death.

Tombstones (`quarantine-survives-dispatch.md`) catch **dispatch-time**
resurrection only. They **do not** stop mid-run zombie writes.

## Rule

1. **Abort / hard-block:** run the operator entry point
   `.hermes/home/scripts/stop-worker-session.sh [--kind KIND] <task_id> <reason>`
   (wraps `block-and-signal-worker.sh` **and**
   `kill-and-verify-task-worker.sh` — verify death).
2. **Terminal (`done` / triage / archive):** run `kill-and-verify-task-worker.sh`
   for that task_id; fail-closed if a hermes `kanban task <id>` process remains.
3. **Record PID:** after spawn/dispatch, run
   `python3 .hermes/home/scripts/stamp-worker-pid-from-ps.py . --task <id>`
   so `tasks.worker_pid` is non-NULL.
4. **Sweep:** `python3 .hermes/home/scripts/assert-no-residual-workers.py .`
   before next M3 dispatch and after every abort/terminal.
5. Never kill the legitimate in-flight product worker (protect by PID/task_id).

## Scripts

| Script | Role |
|--------|------|
| `stop-worker-session.sh` | **A-5 entry point** — block + signal + verify |
| `block-and-signal-worker.sh` | board block + signal (called by entry point) |
| `kill-and-verify-task-worker.sh` | SIGTERM→SIGKILL + verify death |
| `stamp-worker-pid-from-ps.py` | stamp `tasks.worker_pid` from ps |
| `assert-no-residual-workers.py` | fail if terminal tasks still have live workers |

## Mechanism note

Override "resurrection" on S-004 was **residual worker**, not provisioning
snapshot (steward forensics; absorbed). `t_b5019586` worker exoneration
on invent stands.
