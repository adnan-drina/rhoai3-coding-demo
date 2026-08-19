# Known Hermes behaviours (platform compensating controls)

**Status:** reference · **Replaces:** residual-worker-kill, crash-requeue,
workspace-recovery, wall-exit-eval, stream-liveness, conv-live-arm-on-dispatch,
conv-live-bounded-retry, compaction-headroom-and-fast-deny,
devspaces-dispatcher-posture, managed-scope-at-spawn (prose contracts).

Operational kill path (doctrine): `.hermes/home/scripts/stop-worker-session.sh`
→ `block-and-signal-worker.sh` / `kill-and-verify-task-worker.sh`. See AGENTS.md
Worker containment. **Seat ops only** — a kanban worker must not SIGTERM
itself. Do not rediscover A-5 by reading attic contracts under stress.
