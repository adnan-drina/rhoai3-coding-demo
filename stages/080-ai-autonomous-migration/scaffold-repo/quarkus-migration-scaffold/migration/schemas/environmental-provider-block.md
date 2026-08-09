# AD-009 — Environmental provider BLOCK stamp

When a Kanban task terminals because the primary MaaS/OpenCode provider is
unresponsive (provider-stale / consecutive failures → Hermes `gave_up`), stamp a
typed environmental terminal — **not** a soft retry loop and **not** MiniMax
escalate (AD-008).

## Verdict / provenance fields (required)

| Field | Example |
|-------|---------|
| `block_class` | `environmental_provider` |
| `model_id` | `qwen3-6-27b` / `qwen27b/qwen3-6-27b` |
| `provider_stale_events` | integer count (Monitor joinable) |
| `prior_run_ids` | list of reclaim run ids |

Write under `migration/verdicts/environmental-provider-<task_id>.json` via:

```bash
python3 .hermes/home/scripts/stamp-environmental-provider-block.py \
  --task-id t_xxx --model-id qwen3-6-27b \
  --provider-stale-events 5 --prior-run-ids 19,22,25,27
```

Also append interventions ledger only if a **human** Class A/B response occurred;
native Hermes reclaim alone is **not** an intervention (AD-009).

## Campaign circuit-breaker

| Phase | K (env BLOCKs ⇒ stop) |
|-------|------------------------|
| M1 / M2 fresh-run gate | **1** → Review NO-GO (successful measurement) |
| M3 | **2** → campaign INCONCLUSIVE / BLOCK (environmental) |

## max_runtime_seconds

Phase-dispatch **must** pass `--max-runtime` from `.hermes/phase-dispatch.yaml`.
M2-created M3 children **must** set the same M3 `max_runtime_seconds` (2700)
explicitly — copy-payload / untyped creates without it are forbidden on fresh runs.
