# CONV-LIVE bounded in-turn retry (RW-1)

**Status:** binding (in-tree).
**Bank:** BANK-CONV-LIVE-WD-1

## Problem

Post-tool stalls (S-003 runs #66–#68) keep `last_heartbeat_at` warm while the
Hermes `conversation_loop` stops consuming streams. External reclaim alone is
slow and loses the in-turn context. ELB idle-timeout was ruled out (`3600`
present).

## Rule

**BOUNDED_RETRY** budget = **1** in-turn attempt per run (then reclaim).

1. When `check-conversation-liveness.py` fails, dispatcher run
 `classify-conv-live-stall.py --task-id … --stamp` before reclaim.
2. **BOUNDED_RETRY** budget = 1 per run: one typed in-turn resume/retry attempt
 is authorized when class is `client_unconsumed` or `unknown`; then reclaim.
3. Class `provider_idle` ⇒ do **not** burn the retry on the same send path —
 stamp + reclaim; escalate send/close diagnosis.
4. Detector remains alert-only (no board mutate). Reclaim stays steward-owned.

## Scripts

| Script | Role |
|--------|------|
| `check-conversation-liveness.py` | Flat transcript + idle API + fresh hb |
| `classify-conv-live-stall.py` | Server-vs-client classify + receipt |

## Evidence

`monitoring/20260812-v12-m3-s003-conv-live-stream-layer-diagnosis.md`
