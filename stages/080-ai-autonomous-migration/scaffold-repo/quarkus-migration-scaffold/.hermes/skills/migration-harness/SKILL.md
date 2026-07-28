---
name: migration-harness
description: Orchestrates the autonomous legacy-to-Quarkus M-process (M1–M5) — analyzes findings, sequences stories, specifies per story, dispatches rewrite/infer work with sensors, and ships through the factory gate. Use in harness sessions when executing any M-stage of the migration runbook.
---

# Migration harness runbook (Hermes orchestrator)

You are the harness orchestrator for this migration workspace. You own the
plan, the task queue, the sensor schedule, correction packets, and the
iteration budget. Application code is written by the worker; you may edit
source directly only through the escalation valve (see EXECUTION.md).

## The M-process (canonical vocabulary)

| Stage | Name | Owns |
|---|---|---|
| **M1** | ANALYZE | Ground truth + architecture profile — [ANALYSIS.md](ANALYSIS.md); script bundle via `analyze.sh` |
| **M2** | SEQUENCE | Roadmap + briefs — [SEQUENCING.md](SEQUENCING.md); outer loop only |
| **M3** | SPECIFY | Spec / plan / tasks for one story — [PLANNING.md](PLANNING.md) |
| **M4** | IMPLEMENT | Task loop (rewrite / infer / sensors) — [EXECUTION.md](EXECUTION.md) |
| **M5** | EVALUATE | Preflight, factory ship, findings delta — [SHIPPING.md](SHIPPING.md) |
| **Retro** | Steering | Proposals after a story/run — briefs may be auto-applied; skills stay human |

Commit message prefixes (load-bearing for resume): `M1 analyze:`, `M2 sequence:`,
`M3 spec:` / `<Sxx> spec:`, `M3 revision:`, `T-NNN:`, `M5 evaluate:`, `Retro:`.

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

## Stage procedures — read the file for the stage you are executing

| Stage | File |
|---|---|
| M1 architecture profile | [ANALYSIS.md](ANALYSIS.md) |
| M2 roadmap + briefs | [SEQUENCING.md](SEQUENCING.md), [BRIEF-TEMPLATE.md](BRIEF-TEMPLATE.md) |
| M3 spec / plan / tasks | [PLANNING.md](PLANNING.md), [TASKS-TEMPLATE.md](TASKS-TEMPLATE.md) |
| M4 task execution | [EXECUTION.md](EXECUTION.md) |
| M5 evaluate + factory | [SHIPPING.md](SHIPPING.md) |
| Jakarta→Quarkus mapping catalog | [MAPPINGS.md](MAPPINGS.md) |
| Model routing and cost discipline | [REFERENCE.md](REFERENCE.md) |

Read ONLY the file for your current stage — each is self-contained.

## Feedback loops

- **Inner loop (automated):** lint → revision; sensors → fix sessions.
- **Outer loop (automated):** after each story, Retro may update **remaining
  briefs** so the next story starts smarter. Roadmap structure is not
  rewritten mid-run; a failed story stops the run (resume via
  `migration/story-state.csv`).
- **Steering loop (human):** Retro proposes skill/sensor/runbook changes;
  humans apply them in a follow-up PR. Never auto-edit `.hermes/skills/**`
  or harness scripts from Retro.

## Stop conditions

| Condition | Action |
|---|---|
| All story tasks done, sensors green, re-analysis clean | M5 ship |
| Budget exhausted on a task | `migration/debt.md`, continue |
| Two consecutive full-suite failures after corrections | HALT: write run-log + debt, report, do not push, never bypass sensors |
| Story ship failed under outer loop | Stop before dependent stories; resume later from `story-state.csv` |
