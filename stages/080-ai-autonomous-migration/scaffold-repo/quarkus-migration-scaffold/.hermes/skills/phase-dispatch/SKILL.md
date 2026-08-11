---
name: phase-dispatch
description: >
  Create and dispatch Hermes Kanban tasks for M1–M5 from
  .hermes/phase-dispatch.yaml. Use when starting ANALYZE/PLAN/IMPLEMENT/VERIFY/CLOSE
  so orchestration stays Hermes-native — never a Lead-owned detached shell for M1 MTA.
---

# Phase dispatch (Hermes Kanban)

## When to use

- Starting **any** M-phase, especially **M1 ANALYZE** (derive + MTA + inventory)
- Replacing a forbidden detached `mta-analyze-legacy.sh` / derive shell under PPID 1
- Seeding the next phase after an ack is granted

## Standing rule

**Hermes owns orchestration for M1–M5.** Domain scripts (`mta-analyze-legacy.sh`,
`derive-legacy-boot3.sh`, …) run **inside** a Kanban worker that loaded the
declared skills — they are not the demo control plane.

## Procedure

```bash
export HERMES_HOME="${HERMES_HOME:-/projects/modernized/.hermes/home}"
export HERMES_MANAGED_DIR="${HERMES_MANAGED_DIR:-/projects/.platform/hermes}"
cd /projects/modernized

# Ensure watch is already running in another pane (demo Act D).
bash "${HERMES_SKILL_DIR}/scripts/dispatch-phase.sh" M1
# later:
bash "${HERMES_SKILL_DIR}/scripts/dispatch-phase.sh" M2 --parent <m1_task_id>
```

From a shell without the skill loaded:

```bash
bash .hermes/skills/phase-dispatch/scripts/dispatch-phase.sh M1
```

### What the script does

1. Reads `.hermes/phase-dispatch.yaml` for `role`, `skills[]`, `max_runtime_seconds`.
2. R-HX.5: does **not** copy Managed Scope `config.yaml` / `.env` into
   `HERMES_HOME` (DB/logs only; provider/auth stay under `HERMES_MANAGED_DIR`).
3. Ensures a standalone `hermes kanban daemon --force` (Dev Spaces has no gateway).
4. `hermes kanban create` with `workspace=dir:/projects/modernized`, skills,
   budget, idempotency key `migration-<phase>-v1`.
5. One `hermes kanban dispatch --max 1` tick.

### M1 body contract (evidence-analyst)

The created M1 task instructs the worker to, in order:

1. `derive-legacy-boot3` (manifest check / derive if missing)
2. `inventory-entry-points` → `migration/entry-point-inventory.json` (before handoff emit)
3. `mta-analysis` → `mta-analyze-legacy.sh` (writable clone + `MTA_RUN_CWD`; emits findings-handoff)
4. Validate findings + handoff — **do not** grant stage-advance acks (Operator writes `m1-findings.ack.yaml` per AR-1.1)

## Pitfalls

- Do **not** start M1 by `nohup …/mta-analyze-legacy.sh &` — that yields
  `tasks=0` and cannot stamp `orchestration=hermes_native`.
- Do **not** omit `--workspace dir:/projects/modernized` (scratch default is wrong).
- Start `hermes kanban watch` **before** dispatch for the demo audience.
  Convenience wrapper (native only): `bash .hermes/home/scripts/kanban-track.sh follow`
  (daemon + watch) or `… watch` / `… dispatch` in two panes.
