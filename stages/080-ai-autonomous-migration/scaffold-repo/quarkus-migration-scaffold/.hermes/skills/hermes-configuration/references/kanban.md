# Kanban dispatcher keys

**Official sources (cite these):**
- Kanban feature: https://hermes-agent.nousresearch.com/docs/user-guide/features/kanban
- Configuration (kanban / verify-on-stop sections): https://hermes-agent.nousresearch.com/docs/user-guide/configuration
- Research pack: `harness-refactoring/source-analysis/hermes/20260812-official-kanban-alignment.md` (CS-5)

## Keys agents commonly touch

| Key / surface | Official role | Platform note |
|---------------|---------------|---------------|
| `failure_limit` / `--max-retries` | Attempt budget → `gave_up` | Prefer official over homegrown wall scripts when equivalent |
| `stale` / `dispatch_stale_timeout` + heartbeat | SIGTERM stale workers; **no** failure tick | Distinct from provider `stale_timeout_seconds` (stream) |
| `max_in_progress` / `max_in_progress_per_profile` | Concurrency caps | Prefer `kanban dispatch --max N` |
| `review_dispatch` | When false, review lane does not auto-dispatch | Pair with review status tooling |
| `auto_decompose` | When false, no auto child decomposition | Demo pin: `false` (ack / human gate) |
| `kanban dispatch --max N` | Official guarded dispatch | CS-5 #5 largely covered |

## Hard warnings (official)

- `workflow_template_id` / `current_step_key`: reserved v2 — **do not build on**.
- Approval gates are **user-space** (spec §14) — not a new status.
- Create-park paved road: **unassigned** / `--triage` / `scheduled_at` —
  not invent create-in-blocked.

## Related contracts (policy KEEP; mechanism may REHOST)

See CS-5 taxonomy map:
`harness-refactoring/source-analysis/hermes/20260812-cs5-contracts-scripts-taxonomy-map.md`.
