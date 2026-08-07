# Reference — model routing and cost

## Model routing

Seats are split by **strength + quota**:

| Seat | Model | Quota | Use for |
|------|-------|-------|---------|
| Orchestrator | MiniMax M2 (`custom:maas-m2`) | **Limited** (429 → supervisor backoff) | M1–M3, sensor-fix judgment, M5 evaluate, escalate after worker fail |
| Worker | Qwen3.6 27B (`qwen27b/qwen3-6-27b`) | **Unlimited** on this platform | All M4 coding — `rewrite` and `infer` |

```bash
# Orchestrator (Hermes) — judgment only
hermes chat --provider custom:maas-m2 --model minimax-m2 -q "..."

# Worker (OpenCode) — mechanical + infer coding
opencode run "<packet>" -m qwen27b/qwen3-6-27b --auto --format json ...
```

**V7 rule:** never send rewrite batches to MiniMax with “apply it
directly.” The supervisor builds packets via `task-packet.py` and runs
OpenCode first (`WORKER_FIRST`). MiniMax touches source only through the
escalation valve after the worker fails.

Trade-off (temporary): `maas-m2` is a direct external endpoint, so its
tokens do not appear on the platform's MaaS dashboard the same way —
treat the rate limit as real and scarce. Portal models with only 32K
context (e.g. gpt-oss-120b) are not orchestrator candidates: harness
sessions routinely exceed 65K input tokens.

## Cost discipline

- Prefer `Class: rewrite` (harvest) over infer wherever the change is
  mechanical — still run it on **Qwen**, not MiniMax.
- Keep worker packets bounded — one task, explicit acceptance.
- On MiniMax 429: wait for supervisor quota backoff; do not retry-spam.
