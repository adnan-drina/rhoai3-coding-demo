---
name: hermes-self-improvement
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "hermes"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Hermes Agent"
description: >
  Use when designing or governing Hermes' self-improvement loop for stage
  080: the post-turn background review that writes memory and skills, the
  consent gates (memory.write_approval, skills.write_approval), the
  curator's lifecycle role, /journey auditability, and routing the review
  to a cheaper model. Do NOT use for skill authoring mechanics (use
  hermes-skills) or curator command depth (also hermes-skills).
---

# Hermes Self-Improvement Loop

Use this skill for the loop that makes Hermes "the self-improving AI
agent": what it writes autonomously, where the consent gates are, and how
stage 080 governs it.

## Source Grounding

Official pages (captured 2026-08-12, see `references/source-capture.md`):
Persistent Memory (background review, write approval, journey), Skills
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

### Cost and routing

By default the review "runs on your main chat model" with full warm-cache
replay (cheap cache reads). Route it to a cheaper model via
`auxiliary.background_review` — which switches it to replaying "a compact
digest" instead of the full transcript to avoid cold cache writes.

### Downstream lifecycle

What the loop writes, the **curator** later maintains: agent-created
skills (3-condition jurisdiction test) age through stale (30d) → archive
(90d, recoverable, "never auto-deletes"); pin what must persist;
cron-referenced skills are auto-protected. **`/journey`** (aliases
`/learning`, `/memory-graph`) is the audit surface: a timeline of every
saved skill and memory entry, with list/delete/edit.

## Workflow

1. Decide the fleet posture explicitly: for stage 080 governed workers,
   enabling both write-approval gates is the deliberate choice — the
   defaults are write-freely (this is the escalated posture decision from
   the family's maintainer handoff; it covers BOTH gates, not just
   skills).
2. Route `auxiliary.background_review` to an inexpensive model for
   high-volume worker fleets.
3. Audit periodically via `/journey` and `hermes curator status`; pin
   agent-created skills that became load-bearing.
4. Treat agent-authored skills as code: the official tip is to say yes to
   the agent saving skills ("these agent-authored skills capture the
   exact workflow including pitfalls"), but gate + review them like any
   contribution in a governed fleet.
5. Cite the official section in the PR (stage 080 official-first rule).

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
- Gating skills but not memory (or vice versa) — two separate keys, one
  loop.
- Background-review writes bypassing scrutiny on messaging platforms —
  there's no inline prompt there; only `/memory pending` review.
- Forgetting the curator will archive unused learned skills after 90
  days — pin what matters.
- Routing the review to a cheap model and expecting full-transcript
  fidelity — digest replay is the documented trade-off.

## Related Skills

- `hermes-skills` — skill_manage actions, write-approval mechanics,
  curator depth.
- `hermes-configuration` — `auxiliary.background_review` wiring.
- `hermes-managed-scope` — fleet-pinning the gates at the admin tier.

## References

- `references/source-capture.md`
