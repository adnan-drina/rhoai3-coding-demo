# AD-009 §3.1 — Protocol-untyped BLOCK stamp

When a worker exits `rc=0` without calling `kanban_complete` or `kanban_block`,
do **not** leave the board with an untyped `protocol_violation` narrative.
Stamp a typed terminal:

| Field | Value |
|-------|--------|
| `block_class` | `protocol_untyped` |
| `schema` | `rhoai3.protocol-untyped-block/v1` |

Write under `evidence/verdicts/protocol-untyped-<task_id>.json`:

```bash
python3 .hermes/home/scripts/stamp-protocol-untyped-block.py \
  --task-id t_xxx --run-id 5

# Detect from hermes show diagnostics + optional block:
python3 .hermes/home/scripts/apply-protocol-untyped-terminal.py \
  --task-id t_xxx --block

# Residual after environmental campaign class:
python3 .hermes/home/scripts/apply-protocol-untyped-terminal.py \
  --task-id t_xxx --secondary-to environmental_provider --force
```

This is **not** automatic proof of context overflow or findings-handoff seam
failure. Dual-annotate when the campaign class is `environmental_provider`
(AD-009). No MiniMax (AD-008).

## Related hard budget

`max_runtime_seconds` is a **control**, not an advisory percent. See
`enforce-max-runtime-hard.py` and `max-runtime-<task_id>.json`
(`block_class=max_runtime_exceeded`).
