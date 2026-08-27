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
   **M4 no longer needs a named GO** (Operator, 2026-08-27; supersedes
   `104843ZA` and lifts the `172724ZA` HOLD). Mint M4 with the rest of
   the chain, parented to the M3 stories, so the dispatcher promotes it
   when they are `done`. This restores `no-manual-approval-gates`: the
   campaign is autonomous by design and verifies with gates and an
   artifact trail, never human sign-off. The M1→M2 gate cost 62 idle
   minutes on dest-10 for nothing; the M4 gate is the same shape.
   Holding M4 again needs a **new** named GO, not a restored default.
3. Gate K story cards inherit Gate K retry intent: mint `--max-retries 1`
   onto minted T0/M3 children. `max_retries: None` →
   `kanban.failure_limit` 2 is not the dest-4 intent (Operator
   `105355ZO` item 5).
4. `autoStartMigration` is restored on the RHDH template **with** the
   dest-init consumer (`autostart-migration.sh`). Default `true`. Off
   skips mint (`AUTO_START_MIGRATION`). Do not mint M3/M4 at dest-init.

Official cite: `.agents/skills/hermes-kanban/` dispatcher and worker
lanes. Do not run `hermes kanban daemon --force`.
