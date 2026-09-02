# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product | Hermes Agent (Nous Research) |
| Product version | no version marker on doc pages; v1 design spec dated April 25 2026 (Revision 01, DESIGN ONLY) — live product has evolved past it |
| Chapter or page title | Kanban Multi-Agent; Kanban Tutorial; CLI Commands (kanban section); Slash Commands (/kanban rows); Environment Variables (HERMES_KANBAN_* rows); Profiles (routing input); Hermes Kanban v1 design spec |
| Source URL | https://hermes-agent.nousresearch.com/docs/user-guide/features/kanban |
| Source URL | https://hermes-agent.nousresearch.com/docs/user-guide/features/kanban-tutorial |
| Source URL | https://hermes-agent.nousresearch.com/docs/reference/environment-variables (HERMES_KANBAN_* rows) |
| Source URL | https://hermes-agent.nousresearch.com/docs/reference/cli-commands (hermes kanban section; wording on `scheduled` is loose — see below) |
| Source URL | https://hermes-agent.nousresearch.com/docs/reference/slash-commands (/kanban rows) |
| Source URL | https://hermes-agent.nousresearch.com/docs/user-guide/profiles (--description routing input) |
| Source URL | https://raw.githubusercontent.com/NousResearch/hermes-agent/main/docs/hermes-kanban-v1-spec.pdf (design rationale only; copy at `source-analysis/hermes/hermes-kanban-v1-spec.pdf`) |
| Documentation category | Features / Reference / Design spec (repository) |
| Capture date | 2026-08-12 |
| Capture method | Research-agent dossier (`source-analysis/hermes/hermes-kanban-capture-B.md`, 962 lines); reviewer re-verified the state enum, failure_limit, stale timeout, scheduled_at semantics, silent-assignee-failure, and HERMES_KANBAN_* precedence verbatim against live pages on 2026-08-12; reviewer separately recovered and read the v1 spec PDF the research tools could not fetch |

## Captured Sections

- Kanban feature page (primary, read in full): core concepts, 8-state
  enum, boards, attachments, dispatcher (gateway-embedded, tick, circuit
  breaker), worker protocol and lifecycle, kanban_* tool surface, goal-mode
  cards, orchestrator behavior, dashboard plugin (REST, security), full
  CLI reference, respawn guard, runs model, event reference (22 kinds),
  multi-tenant, notifications, out-of-scope (single-host).
- Kanban tutorial: four worked stories (solo dev, fleet farming, review
  pipeline with retry, circuit breaker + crash recovery).
- v1 design spec (reviewer addendum in the extraction): design rationale,
  original 6-state model, SQLite schema, CAS/BEGIN IMMEDIATE concurrency
  argument, delegate_task boundary test, assignment non-goals, scope
  boundaries (governance is user-space).

## Discrepancies resolved by this capture

- **`scheduled` is not a task status.** Canonical enum has 8 values; the
  primary page: the dispatcher "skips ready tasks whose `scheduled_at` is
  in the future" — they remain `ready`. The CLI reference's "park
  time-delay/follow-up work in `scheduled`" wording is loose; cite the
  primary page.
- **Spec vs. live docs.** The spec's 6-state model, CLI+skill-only
  recommendation (no toolset), and 8 patterns are superseded by the live
  8-state enum, the 13-tool `kanban_*` surface, and 9 patterns (P9 Triage
  specifier). Cite live docs for behavior, the spec for rationale.

## Source Boundaries

This skill captures dispatcher/worker/orchestrator behavior, lifecycle,
recovery semantics, and the kanban CLI/tool/event surfaces. Config-key
schema wiring belongs to `hermes-configuration`; hook mechanics to
`hermes-hooks`; session persistence to `hermes-sessions`; the full CLI
encyclopedia to `hermes-cli`.

## Known Open Items

- Cross-page inconsistency on which `kanban_*` tools are baseline vs.
  orchestrator-gated (primary page's 13-tool table vs. CLI reference's
  9-tool baseline) — primary page treated as richer authority; unresolved.
- `BLOCK_RECURRENCE_LIMIT` and `_PROTOCOL_VIOLATION_FAILURE_LIMIT`: no
  documented config-key names (likely internal constants).
- No documented default/maximum for `--max-runtime`, `--ttl`, `--priority`,
  or `gc` retention flags.
- No cron→kanban integration documented beyond shared synchronous-fallback
  behavior for detached-result-incapable runtimes.
- Gateway Internals' background-maintenance list omits the kanban dispatch
  tick the feature page describes (coverage gap, not contradiction).

## Coverage audit + expansion (2026-08-12)

- Full-outline diff vs the live feature page: no new sections since
  capture. SKILL.md v1.1.0 is the thorough distillation (all sections +
  tutorial choreography + P1–P9 table).
- NEW page added to pins: kanban-worker-lanes (absent from llms.txt and
  the original inventory): lane abstraction, spawn env contract
  (adds HERMES_KANBAN_WORKSPACE/_RUN_ID/_CLAIM_LOCK, HERMES_PROFILE),
  skipped_nonspawnable event, DEFAULT_CLAIM_TTL 15 min,
  stranded_threshold_seconds, external-lanes-not-paved.
  URL: https://hermes-agent.nousresearch.com/docs/user-guide/features/kanban-worker-lanes
