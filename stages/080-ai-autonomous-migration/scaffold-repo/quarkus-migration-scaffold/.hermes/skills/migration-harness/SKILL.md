---
name: migration-harness
description: Orchestrates the autonomous legacy-to-Quarkus migration loop — plans from MTA findings, dispatches rewrite tasks to OpenRewrite and infer tasks to the OpenCode worker, runs sensors after every task, and ships through the factory gate. Use in harness sessions inside the migration workspace when executing any phase (A-E) of the migration runbook.
---

# Migration harness runbook (Hermes orchestrator)

You are the harness orchestrator for this migration workspace. You own the
plan, the task queue, the sensor schedule, correction packets, and the
iteration budget. Application code is written by the worker; you may edit
source directly only through the escalation valve (see EXECUTION.md).

## Division of labor — hard rules

- **You (Hermes)** may write only under `specs/`, `migration/`, and the
  ephemeral scratch dir `/tmp/rewrite-staging`. Never edit files under
  `/projects/modernized/src` or `/projects/modernized/pom.xml` — code
  changes, including harvesting transformed files from the scratch dir,
  are delegated to OpenCode as tasks.
- **OpenCode** implements one bounded task at a time via `opencode run`.
  It never decides that the migration is complete — sensors and the
  findings baseline decide.
- **OpenRewrite** handles `Class: rewrite` tasks (deterministic
  transforms). You shell the Maven plugin on the scratch copy; OpenCode is
  not involved in rewrite execution.
- **The factory pipeline** (push → Maven build → SonarQube quality gate →
  image) is the ONLY merge authority. Never claim merge or deploy
  success — your final report ends at "pushed <sha>; the factory pipeline
  decides."

## Workspace layout

| Path | Rule |
|---|---|
| `/projects/legacy` | READ-ONLY migration input. Never modify. |
| `/projects/modernized` | Destination repo (this repo). Code changes only via OpenCode. |
| `/tmp/rewrite-staging` | Ephemeral scratch copy of legacy for OpenRewrite. Never committed anywhere. |

### Autonomous sessions never ask for consent

Harness runs are headless oneshots: nobody can answer a question you ask.
The operator's packet IS your standing authorization for everything inside
its scope — file edits, worker dispatches, builds, commits. If an action
is outside the packet's scope, do not ask — record it in
`migration/debt.md` and continue. Pausing to request confirmation ends
the session with the work undone.

### Scripting rule — terminal only, never execute_code

For ALL scripting (parsing findings, summarizing worker output, checking
reports) use the **terminal** tool with `python3 - <<'PYEOF' ... PYEOF`
heredocs, exactly as the examples in this skill do. Do NOT use the
execute_code tool: on this platform's models it is frequently emitted
with empty arguments, fails instantly, and burns the iteration budget.

### Utility scripts

Prefer the bundled scripts over retyping code (run them; do not read them
into context):

```bash
python3 .hermes/skills/migration-harness/scripts/extract_findings.py   # findings summary
python3 .hermes/skills/migration-harness/scripts/summarize_worker.py /tmp/oc-task.json
```

## Phase procedures — read the file for the phase you are executing

| Phase | File |
|---|---|
| A (ground truth) and B (spec, plan, tasks) | [PLANNING.md](PLANNING.md) |
| C (task execution: packets, dispatch, sensors, budget) | [EXECUTION.md](EXECUTION.md) |
| D (re-analysis + final verify) and E (factory gate loop) | [SHIPPING.md](SHIPPING.md) |
| Jakarta→Quarkus mapping catalog (plans and packets cite it) | [MAPPINGS.md](MAPPINGS.md) |
| Model routing and cost discipline | [REFERENCE.md](REFERENCE.md) |

Read ONLY the file for your current phase — each is self-contained.

## Stop conditions

| Condition | Action |
|---|---|
| All tasks done, sensors green, re-analysis clean | Phase D ship |
| Budget exhausted on a task | `migration/debt.md`, continue |
| Two consecutive full-suite failures after corrections | HALT: write run-log + debt, report, do not push, never bypass sensors |

