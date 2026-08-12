---
name: hermes-one-three-one-rule
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "hermes"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Hermes Agent"
description: >
  Use when presenting a decision, proposal, or escalation in stage 080
  work — kanban block escalations, review findings, ADR proposals, design
  choices with trade-offs: structure it as One-Three-One (1 problem, 3
  options, 1 recommendation) per the official Hermes communication skill.
  Do NOT use for simple questions with obvious answers, debugging, or
  when the decision is already made.
---

# One-Three-One Rule

Use this skill to structure decisions and escalations. It mirrors the
official Hermes optional skill (`official/communication/one-three-one-rule`
v1.0.0, by Willard Moore, MIT) — the same artifact the stage 080
scaffold's skill-authoring law uses as its worked example.

## Source Grounding

Official page:
https://hermes-agent.nousresearch.com/docs/user-guide/skills/optional/communication/communication-one-three-one-rule
(captured 2026-08-12; see `references/source-capture.md`).

## The Structure

1. **Problem** — "State the core decision or desired outcome in a single
   concise sentence."
2. **Options** — three distinct approaches (A, B, C), each with pros and
   cons; genuinely different, not one option and two strawmen.
3. **Recommendation** — pick ONE, with professional reasoning.
4. **Definition of Done** — concrete, verifiable success criteria.
5. **Implementation Plan** — the specific steps to execute the
   recommendation.

## When to Use

- Explicit requests for a "1-3-1" response.
- Technical decisions where the asker wants to see their choices.
- Tasks with multiple viable approaches and meaningful trade-offs.
- Proposals needing team or stakeholder review — in stage 080 terms:
  ADR proposals, harness design choices, kanban `blocked → needs_input`
  escalations, review-doc fix designs, and operator-backlog decide items.

## When NOT to Use

Simple questions with obvious answers, debugging sessions, or when the
decision has already been made — restating settled decisions as options
re-litigates them.

## For Hermes worker seats (stage 080)

The official skill installs at `official` trust tier (no third-party
warning):

```shell
hermes skills install official/communication/one-three-one-rule
```

Pin it to escalation-prone tasks with `--skill one-three-one-rule` at
`kanban create` time (skill must be installed on the assignee's profile —
no runtime install; see `hermes-kanban`).

## Verification

- The proposal names exactly one problem sentence, exactly three options
  with pros AND cons each, and exactly one recommendation.
- Definition of Done is checkable (a command, a gate, a measurable state
  — not "works well").
- The recommendation's reasoning references the trade-offs stated in the
  options, not new facts introduced afterward.

## Related Skills

- `hermes-skills` — install mechanics and trust tiers.
- `hermes-kanban` — task-pinning and block/escalation flows the structure
  slots into.

## References

- `references/source-capture.md`
