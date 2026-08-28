# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product | Hermes Agent (Nous Research) |
| Product version | no version marker on doc pages (family anchor: v0.20.0, 2026-08-03) |
| Chapter or page title | Persistent Memory (background review, write_approval, Learning Journey); Skills System (agent-managed skills, gating); Curator (lifecycle) — no dedicated self-improvement page exists |
| Source URL | https://hermes-agent.nousresearch.com/docs/user-guide/features/memory |
| Source URL | https://hermes-agent.nousresearch.com/docs/user-guide/features/skills (Agent-Managed Skills, Gating sections — full capture in hermes-skills) |
| Source URL | https://hermes-agent.nousresearch.com/docs/user-guide/features/curator (full capture in hermes-skills) |
| Documentation category | Features |
| Capture date | 2026-08-12 (Skills/Curator); Memory page re-fetched 2026-08-27 |
| Capture method | Reviewer-direct cross-cutting capture (maintainer-requested; the requested URL was a duplicate of the delegation-patterns guide — corrected to the actual sources): memory-page self-improvement sections fetched verbatim; skills/curator facts reused from the already-verified hermes-skills capture. 2026-08-27 re-fetch closed the off-switch gap (`auxiliary.background_review.enabled`). |

## Captured Content

- Loop: "After a turn, the background self-improvement review may quietly
  save a memory or update a skill"; memory-vs-skills division ("small
  durable facts" vs "longer procedures"); "repeated corrections and
  durable workflow lessons become compact memory entries or procedural
  skills".
- Gates: memory.write_approval (stages all saves incl. background;
  /memory pending|approve|reject; inline prompts CLI-only) and
  skills.write_approval (uniform staging, foreground + background) —
  both default off; guard_agent_created independent; memory writes
  injection/exfiltration-scanned regardless.
- Cost: review runs on the main chat model by default (warm-cache
  replay); auxiliary.background_review reroutes to a cheaper model with
  compact-digest replay. `auxiliary.background_review.enabled: false`
  skips automatic post-turn forks; `/refine` still works
  (Memory page "Disabling automatic reviews", fetched 2026-08-27).
  `display.memory_notifications: off` hides the chat line only.
- Full off for built-in stores: both `memory_enabled` and
  `user_profile_enabled` false — drops the memory tool. Either store
  alone true keeps the tool for that target.
- Audit/lifecycle: /journey timeline (list/delete/edit); curator
  jurisdiction over agent-created skills (stale 30d / archive 90d /
  never auto-deletes / pinning; captured in depth by hermes-skills).

## Source Boundaries

The cross-cutting loop and its governance live here. Skill authoring and
curator depth → `hermes-skills`; memory system depth (capacity,
targets, providers) remains an UNOWNED taxonomy topic — this skill covers
only memory's self-improvement-loop slice; `auxiliary.*` wiring →
`hermes-configuration`.

## Known Open Items

- Full Persistent Memory page depth (capacity management, MEMORY.md/
  USER.md targets, external providers) remains uncaptured — the memory
  taxonomy gap is narrowed, not closed, by this skill.
- CLOSED 2026-08-27: the background review can be disabled outright via
  `auxiliary.background_review.enabled: false` (Memory page, "Disabling
  automatic reviews"). Not a gate; `/refine` remains.
