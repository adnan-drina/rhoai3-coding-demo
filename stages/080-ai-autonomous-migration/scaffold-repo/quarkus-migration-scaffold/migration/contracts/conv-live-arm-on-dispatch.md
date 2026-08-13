# CONV-LIVE arm on dispatch path (D4)

**Status:** binding (in-tree).
**Bank:** BANK-CONV-LIVE-WD-1

## Problem

Hermes `kanban-stuck-watchdog` cron does not fire when the gateway is down
(common in Dev Spaces). Remint run#71 stalled ~28m with zero CONV-LIVE
detector process — reclaim minutes-scale detectors never engaged.

## Rule

1. Every M3 `kanban-dispatch-guarded.sh` invocation **must** call
 `arm-conv-live-watchdog.sh` before `hermes kanban dispatch`.
2. The arm script starts (or reuses) a seat-local poller that runs
 `kanban-stuck-watchdog.py` on an interval (default 120s). That watchdog
 already invokes `check-conversation-liveness.py` and stamps
 `classify-conv-live-stall.py` on FAIL.
3. Fail-closed: missing arm script or arm failure ⇒ refuse dispatch.
4. Idempotent: re-dispatch must not spawn duplicate pollers (pidfile).

## Scripts

| Script | Role |
|--------|------|
| `arm-conv-live-watchdog.sh` | seat-local poller arm |
| `kanban-dispatch-guarded.sh` | calls arm before dispatch |
| `kanban-stuck-watchdog.py` | CONV-LIVE + classify stamp |
| `check-conversation-liveness.py` | flat transcript + warm hb |
| `classify-conv-live-stall.py` | RW-1 stream-layer classify |
