# Kanban / dispatcher config keys

**Official pages:**
- https://hermes-agent.nousresearch.com/docs/user-guide/features/kanban
- Configuration cross-links: https://hermes-agent.nousresearch.com/docs/user-guide/configuration

**CS-5 pack (§5 coverage):**
`harness-refactoring/source-analysis/hermes/20260812-official-kanban-alignment.md`

## Keys (digest + adopt posture)

| Key / surface | Official role | Platform note |
|---------------|---------------|---------------|
| `failure_limit` / `--max-retries` | Attempt budget → `gave_up` | Prefer official over homegrown wall wrappers when equivalent |
| `max_in_progress` / `max_in_progress_per_profile` | Concurrency caps | Pair with `kanban dispatch --max N` |
| `dispatch_stale_timeout_seconds` + heartbeat | Stale → SIGTERM; **no** failure tick | ≠ provider `stale_timeout_seconds` (stream) |
| `reconcile_orphans` | Reconcile stranded runs | Official dispatcher suite |
| `auto_decompose` | Auto child decomposition | Demo pin: `false` |
| `auto_promote_children` | Auto promote after parent | Prefer explicit ack when gated |
| `review_dispatch` | Auto-dispatch review lane | `false` when human review required |
| `scheduled_at` | Deferred ready | Official park surface |
| Born-unassigned (spec §12) | Unassigned never dispatches | Official park-at-birth paved road |
| `BLOCK_RECURRENCE_LIMIT` (=2) | Block-loop → triage | Deterministic breaker |

## Hard warnings

- `workflow_template_id` / `current_step_key`: reserved v2 — do not build on.
- Approval gates are user-space (spec §14) — not a new status.
