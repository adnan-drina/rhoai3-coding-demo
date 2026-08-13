# Crash requeue ceiling

**Status:** binding proving-min
**Peer:** `wall-exit-eval.md` (bounds `timed_out` only)

## Rule

`apply-wall-requeue-policy.py` does **not** count `crashed`. Crash/reclaim loops
must not be unbounded while wall soft-K reports green.

| Mode | Rule |
|------|------|
| Soft | At most **K_crash=1** crash reclaim; does **not** spend wall soft-K |
| Hard | Next crash after K → **block** + typed stamp; primary `harness_fault` / `environmental_provider` / `context_budget` per cause |
| Forbidden | Silent unbounded crash→requeue; primary `timed_out` / budget / wall-fit evidence for config/provider faults |

## Procedure

On `crashed` (dispatcher hook) — after F4 restore-or-refuse:

```bash
python3 .hermes/skills/gates/check-release-readiness/scripts/restore-or-refuse-requeue.py \
 . --terminal crashed

python3 .hermes/skills/gates/check-release-readiness/scripts/apply-crash-requeue-policy.py \
 . --task-id t_xxx --k-crash 1 --cause harness_fault --stamp
```

Exit codes: `0` soft OK / exhausted warning · `2` hard ceiling · `1` usage error.

Stamp: `evidence/verdicts/crash-requeue-<cause>-<task_id>.json`
(`rhoai3.crash-requeue-block/v1`). Then `hermes kanban block` — do not MiniMax.
