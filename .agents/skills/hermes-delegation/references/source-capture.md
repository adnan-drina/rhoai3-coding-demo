# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product | Hermes Agent (Nous Research) |
| Product version | no version marker on doc pages (family anchor: v0.20.0, 2026-08-03); SubDD optional skill v1.1.0 (author: Hermes Agent, adapted from obra/superpowers, MIT) |
| Chapter or page title | Subagent Delegation (feature); Subagent Driven Development (optional skill, software-development category) |
| Source URL | https://hermes-agent.nousresearch.com/docs/user-guide/features/delegation |
| Source URL | https://hermes-agent.nousresearch.com/docs/user-guide/skills/optional/software-development/software-development-subagent-driven-development |
| Documentation category | Features / Optional Skills |
| Capture date | 2026-08-12 |
| Capture method | Reviewer-direct capture (maintainer-requested gap-fill): verbatim extraction from both pages, cross-checked against four prior sibling captures — max_spawn_depth default and 27-leaf cost warning (hermes-about), subagent_start/stop hook semantics incl. "not a blocking policy hook" (hermes-hooks), delegate sessions as real state.db rows with cascade delete (hermes-sessions), kanban-vs-delegate_task boundary table (hermes-kanban/about) — all consistent |

## Captured Content

- delegate_task call shapes (single goal/context; parallel tasks=[...]).
- Context isolation: children start fresh; only goal + context carry in.
- Tool inheritance + leaf blocklist (delegate_task, clarify, memory,
  send_message, cronjob blocked; execute_code retained).
- Bounds: max_iterations 50; child_timeout_seconds 0 default (30s floor);
  stall detection defaults 450s/1200s/120s grace; max_concurrent_children
  3; max_spawn_depth 1, role="orchestrator" + depth raise for nesting;
  orchestrator_enabled global kill.
- Durability: restarts do not resume children; undelivered completed
  results restored; durable work → cronjob/background terminal/kanban.
- Monitoring: /agents overlay, steer_subagent, live transcripts under
  ~/.hermes/cache/delegation/live/.
- delegation.* config block (model/provider/api_mode/base_url/api_key).
- SubDD methodology: fresh subagent per plan task + two-stage review
  (spec compliance, then code quality) + final integration review; use
  with detailed plans and independent tasks; anti-patterns (no plan,
  skipped reviews, same-file parallel dispatch).

## Naming disambiguation (repo policy)

"SDD" in this repository and the stage 080 scaffold ALWAYS means
Specification-Driven Development (Spec Kit / AD-S / scaffold
`sdd-readiness`). The Hermes optional skill "Subagent Driven Development"
is abbreviated **SubDD** in all stage 080 material. This rule exists
because both legitimately abbreviate to SDD and the collision is real.

## Source Boundaries

Delegation mechanics and SubDD methodology live here. Kanban board
orchestration → `hermes-kanban`; subagent lifecycle hooks →
`hermes-hooks`; delegate session storage → `hermes-sessions`; delegation
toolset wiring → `hermes-tools`/`hermes-configuration`.

## Known Open Items

- The subagent-fallback-inheritance discrepancy first flagged in the
  hermes-configuration capture (user-guide says subagents inherit the
  parent fallback chain; an unread developer-guide snippet suggested
  otherwise) remains unresolved — it lives on that skill's open items;
  relevant here because it concerns delegated children.
- delegation.api_mode auto-detection detail not deep-read (same enum as
  model.api_mode per the configuration capture).

## Coverage audit (2026-08-12)

Full heading outline of the delegation feature page (27 headings) diffed
against this capture — every section represented. Facts added by the
audit beyond the initial extraction: batch results sorted by task index
regardless of completion order; each child gets its own terminal session;
children inherit the parent's API key, provider configuration, and
credential pool; only the final summary enters the parent's context
(context-flooding offload pattern, e.g. the multi-file refactoring
example); orchestrator children retain delegate_task but keep the other
leaf blocks; cancellation follows ownership (/stop or owning-session
close/reset); diagnostic dump on zero-call timeout; "background
completion durability is not durable execution".

## Enhancement (2026-08-12): delegation-patterns guide folded in

Source URL added:
https://hermes-agent.nousresearch.com/docs/guides/delegation-patterns
(full outline read: When to Delegate; five patterns — Parallel Research,
Code Review, Compare Alternatives, Multi-File Refactoring, Gather Then
Analyze; Inherited Tool Access; Constraints/Tuning; Tips). Added to
SKILL.md v1.1.0: the five-pattern table, don't-delegate list, goal/context
authoring guidance ("Be specific… Include file paths… subagents don't
know your project structure"), max_iterations cost tuning, and the
no-hard-ceiling note on max_concurrent_children (guide example: 30).
