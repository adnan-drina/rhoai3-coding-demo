---
name: hermes-self-improvement
metadata:
  author: rhoai3-coding-demo
  version: 1.1.0
  platform-family: "hermes"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Hermes Agent"
description: >
  Use when designing or governing Hermes' self-improvement loop for stage
  080: dest-init honest-off vs the official governed-on fleet recipe, the
  post-turn background review that writes memory and skills, the product
  off-switch (auxiliary.background_review.enabled), the consent gates
  (memory.write_approval, skills.write_approval), the curator, /journey,
  and routing the review to a cheaper model. Do NOT use for skill
  authoring mechanics (use hermes-skills) or curator command depth (also
  hermes-skills).
---

# Hermes Self-Improvement Loop

Use this skill for the loop that makes Hermes "the self-improving AI
agent": what it writes autonomously, where the consent gates are, and how
stage 080 governs it.

## Source Grounding

Official pages (Memory re-fetched 2026-08-27; Skills/Curator captured
2026-08-12; see `references/source-capture.md`): Persistent Memory
(background review, write approval, journey, `enabled: false`), Skills
System (agent-managed skills, background writes), Curator (lifecycle).
There is no single "self-improvement" page — this skill is the
cross-cutting synthesis, every fact quoted from its owning page.

## Key Concepts

### The loop

"After a turn, the background self-improvement review may quietly save a
memory or update a skill." The division of labor is documented: "memory
stores small durable facts that should always be in context, while skills
store longer procedures that should load only when relevant" — "repeated
corrections and durable workflow lessons become compact memory entries or
procedural skills". Skill writes go through `skill_manage` (the agent's
procedural memory); every agent-created skill lands in
`~/.hermes/skills/` under curator jurisdiction.

### The consent gates (both default OFF — a stage 080 governance decision)

- **`memory.write_approval: true`** stages ALL memory saves including
  background-review ones: `/memory pending` → `/memory approve|reject
  <id>` (CLI foreground writes prompt inline).
- **`skills.write_approval: true`** stages every `skill_manage` write —
  "staging applies regardless of whether the write came from a foreground
  turn or the background review" — reviewed via `/skills
  pending|diff|approve|reject`.
- Both default to write-freely; `skills.guard_agent_created` (content
  scanner) is a third, independent mechanism. Memory writes are also
  injection/exfiltration-scanned before acceptance regardless of gates.

### The product off-switch (live Memory page, 2026-08-27)

`auxiliary.background_review.enabled: false` skips automatic post-turn
forks. Manual `/refine` still works. `display.memory_notifications: off`
only hides the chat line — the review still runs and still writes.

Setting both `memory.memory_enabled` and `memory.user_profile_enabled`
false drops the built-in memory tool and its prompt block. Only the first
false leaves USER.md on and the tool in schema.

### Cost and routing

By default the review "runs on your main chat model" with full warm-cache
replay (cheap cache reads). Route it to a cheaper model via
`auxiliary.background_review` — which switches it to replaying "a compact
digest" instead of the full transcript to avoid cold cache writes. Dest
does not author `fallback_providers` (AD-008); do not silently point this
slot at MiniMax.

### Dest campaign postures

Live pins are Managed Scope dest-init
(`maas-api-key-provisioning.yaml`), not the seat
`config.yaml.template`. Seat templates stay silent.

- **A — Honest off (dest default, AD-H):** both memory stores false,
  `auxiliary.background_review.enabled: false`, `curator.enabled: false`,
  skill gates stay true. Typed Kanban cards are the durable lesson
  channel. Assert the review pin next to W1 `title_generation.enabled:
  false`.
- **B — Governed on (official fleet recipe):** both stores on with
  `memory.write_approval: true`, keep skill gates, give implementer the
  memory toolset (or accept a split loop), put learned skills in a
  gitignored writable dir — not golden `.hermes/skills/` — Operator
  drains `/skills pending` on dest dashboard :9119. Needs an Operator GO.
  Do not dest-apply unpublished dest-init onto a running dest.

### Downstream lifecycle

What the loop writes, the **curator** later maintains: agent-created
skills (3-condition jurisdiction test) age through stale (30d) → archive
(90d, recoverable, "never auto-deletes"); pin what must persist;
cron-referenced skills are auto-protected. **`/journey`** (aliases
`/learning`, `/memory-graph`) is the audit surface: a timeline of every
saved skill and memory entry, with list/delete/edit.

## Workflow

1. Dest default is posture A unless Operator GO for posture B. Do not treat
   `memory_enabled: false` alone as off — pin `user_profile_enabled:
   false` and `auxiliary.background_review.enabled: false`.
2. Official fleet recipe (posture B) is both write-approval gates on —
   product defaults are write-freely. That is a dest GO, not the campaign
   default.
3. Do not route `auxiliary.background_review` at MiniMax without a named
   AD-008 GO. Leave the slot at auto / main, or keep the fork disabled.
4. If posture B is granted: audit via `/journey` and `hermes curator
   status`; pin load-bearing learned skills; drain pending on dest
   dashboard, not a TTY. Learned skills must not land on writable golden
   `.hermes/skills/` `external_dirs`.
5. Cite the official section in the PR (stage 080 official-first rule).
   Campaign "persist HARD off" is the overlay gateway persist helper —
   not this loop.

## Validation

```shell
/memory pending                         # staged memory writes (gate on)
/skills pending                         # staged skill writes (gate on)
/journey list                           # what the loop has learned
hermes curator status                   # lifecycle state of learned skills
hermes config get auxiliary.background_review --json   # review routing
```

## Pitfalls

- Assuming the loop is off by default — it isn't; only the GATES default
  off. An ungoverned worker quietly accumulates memory and skills.
- Pinning `memory_enabled: false` without `user_profile_enabled: false`
  — USER.md stays on and the memory tool is not dropped.
- Using `display.memory_notifications: off` as a disable — it is not.
- Gating skills but not memory (or vice versa) — two separate keys, one
  loop. Dest implementer has skills not memory; orchestrator has memory
  not skills. Official loop needs both on one seat.
- Headless `approvals.mode: off` is terminal consent, not the skill gate.
  Nobody on dest is seated to drain `/skills pending`.
- K2 script denies `skill_manage` but dest-init matcher omits it —
  product `skills.write_approval` is the live gate.
- Routing the review to a cheap model and expecting full-transcript
  fidelity — digest replay is the documented trade-off.

## Related Skills

- `hermes-skills` — skill_manage actions, write-approval mechanics,
  curator depth.
- `hermes-configuration` — `auxiliary.background_review` wiring.
- `hermes-managed-scope` — fleet-pinning the gates at the admin tier.

## References

- `references/source-capture.md`
