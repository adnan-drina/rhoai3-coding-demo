# Lost-turn block (Architect E-20260810T144150Z)

**Status:** binding proving-min  
**Family:** `harness_fault` (peer of crash-requeue ceiling)

## Rule

A completed or billed provider turn with **no transcript growth / no durable
turn artifact**, or a stream that burns wall clock with **zero chunks** until
stale-kill, must not remain forever-`running` with `error=None`.

| Field | Value |
|-------|--------|
| `block_class` | `harness_fault` |
| `fault_subtype` | `lost_turn` |
| `schema` | `rhoai3.lost-turn-block/v1` |

Stamp: `evidence/verdicts/lost-turn-<task_id>.json`

```bash
python3 .hermes/home/scripts/stamp-lost-turn-block.py \
  --task-id t_xxx --run-id 4 \
  --transcript-bytes 80134 --transcript-frozen-sec 900 \
  --last-tool terminal --note "stream stale 900s zero chunks"
```

Then hard-block the task (crash-requeue policy / `hermes kanban block`).
Do not MiniMax. Wall-fit evidence contaminated for lost minutes.
