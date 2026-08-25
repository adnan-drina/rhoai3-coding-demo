---
name: m2-m3-native-dispatch
skill-group: Demo Environment
applies-to:
  - stages/080-ai-autonomous-migration/scaffold-repo/**/AGENTS.md
  - gitops/stages/050-advanced-app-platform/base/devspaces/**
---

# Minted M3 children claim through the native dispatcher

Operator `105355ZO`: dest-4 dispatcher claimed `T0_1_BOOTSTRAP` as soon
as M2 minted it `ready`. That is **native kanban**, not a missing
Operator GO.

Official: the dispatcher promotes `todo → ready` when all parents are
`done`, then claims the assignee lane. v2 is card-at-a-time
(`122908Z`). Operator GO for dest-4 was M2 **create** (`094435ZA` /
`075906ZO` lineage). Children of a granted M2 follow the parent graph.

## Non-negotiable

1. Do **not** require a second Operator GO between M2 `kanban_complete`
   and first M3 claim as a Gate K control. Holding M3 needs an explicit
   Operator GO to mint children `blocked` / not `ready` — a **new** GO,
   not Architect rewriting dispatch.
2. Do **not** auto-create M2 without a named Operator GO (unchanged).
   Do not dest-dispatch M4 without a named Operator GO (`104843ZA`).
3. Gate K story cards inherit Gate K retry intent: mint `--max-retries 1`
   onto minted T0/M3 children. `max_retries: None` →
   `kanban.failure_limit` 2 is not the dest-4 intent (Operator
   `105355ZO` item 5).
4. `autoStartMigration` is **removed** from the RHDH template and
   destfile stamp (Operator `115007ZO`). Do not restore a UI toggle
   without a dest-init consumer. Native M3 claim is not that flag.

Official cite: `.agents/skills/hermes-kanban/` dispatcher and worker
lanes. Do not run `hermes kanban daemon --force`.
