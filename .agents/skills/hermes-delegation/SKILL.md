---
name: hermes-delegation
metadata:
  author: rhoai3-coding-demo
  version: 1.1.0
  platform-family: "hermes"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Hermes Agent"
description: >
  Use when designing or reviewing Hermes subagent delegation for stage
  080: delegate_task mechanics (context isolation, tool inheritance,
  parallelism, depth limits, stall detection, steering), the
  Subagent-Driven Development (SubDD) methodology, and when to choose
  delegation vs kanban vs execute_code. Do NOT confuse SubDD with
  Specification-Driven Development — in this repo "SDD" always means
  Spec-Kit-based Specification-Driven Development. Kanban orchestration
  is hermes-kanban; subagent hooks are hermes-hooks.
---

# Hermes Subagent Delegation

Use this skill for `delegate_task`-based multi-agent work — the
fork-and-join primitive, as opposed to the durable kanban board.

> **Naming collision warning (deliberate, load-bearing):** Hermes ships
> an optional skill called "Subagent Driven Development". In this
> repository and the stage 080 scaffold, **"SDD" always means
> Specification-Driven Development** (Spec Kit, AD-S, the scaffold's
> `sdd-readiness`). Abbreviate the Hermes methodology as **SubDD** and
> never as plain "SDD" in any stage 080 doc, task body, or commit.

## Source Grounding

Official pages (captured 2026-08-12, see `references/source-capture.md`):
the Subagent Delegation feature page and the Subagent-Driven Development
optional skill page (v1.1.0, adapted from obra/superpowers, MIT).

## Key Concepts

### The primitive

`delegate_task(goal=…, context=…)` — single child — or
`delegate_task(tasks=[{goal, context}, …])` — parallel batch (default
cap: 3 concurrent; "results are sorted by task index to match input
order regardless of completion order"). Children start with "a completely
fresh conversation… zero knowledge of the parent's conversation history";
their "only context comes from the `goal` and `context` fields".
Everything a child needs must be stamped into those two fields — the same
decide-before-you-fan-out rule as kanban child bodies. Each child gets
its own terminal session; children inherit "the parent's API key,
provider configuration, and credential pool"; and "only the final summary
enters the parent's context" — which makes delegation the documented
pattern for offloading context-flooding work (e.g. "refactor all Python
files in src/" without drowning the parent).

### Tool inheritance and the leaf blocklist

Children inherit the parent's toolsets and "cannot select or widen
capabilities per call". Leaf subagents are hard-blocked from:
`delegate_task`, `clarify` (no user interaction), `memory` (no shared
writes), `send_message`, `cronjob`. Orchestrator-role children "retain
`delegate_task` but keep the other blocks"; both roles retain
`execute_code` for mechanical work.

### Bounds and recovery

`max_iterations: 50` per child; no wall-clock timeout by default
(`child_timeout_seconds: 0`; 30s floor when set); stall detection is "on
by default, zero config" (450s idle / 1200s in-tool / 120s grace).
Nesting is opt-in: `max_spawn_depth: 1` (flat) unless a child has
`role="orchestrator"` and depth is raised — official cost warning: depth
3 × 3 children = up to 27 concurrent leaves. A child that times out with
zero tool calls produces a diagnostic dump (mis-wired children fail
loudly, not silently). **Cancellation follows ownership**: "`/stop` or
closing/resetting the owning session cancels its background children" —
normal follow-up messages don't. **Not durable**: "a Hermes process
restart does not resume a running child" (completed-but-undelivered
results ARE restored — background completion durability is not durable
execution) — durable work belongs on the kanban board or in
`cronjob`/background terminal.

### Monitoring and steering

`/agents` overlay (live tree, per-branch cost rollups, kill/pause);
`steer_subagent(subagent_id, text)` queues redirection at the child's
iteration boundary; append-only live transcripts per task under
`~/.hermes/cache/delegation/live/<delegation_id>/`. Observability hooks:
`subagent_start`/`subagent_stop` (observer-only — block delegation via
`pre_tool_call` on `delegate_task`; see `hermes-hooks`).

### Cost strategy

Official recommendation mirrors the kanban one: frontier planner,
inexpensive workers — pin `delegation.model`/`provider` to a cheap model;
"decomposing a problem into well-specified subtasks takes frontier-level
judgment; executing a subtask that already comes with a clear goal, full
context, and an output contract usually doesn't." Tune bounds to the
task: "set `max_iterations` lower for simple tasks to save cost";
`max_concurrent_children` has no hard ceiling (the guide's tuning example
shows 30).

### The five documented delegation patterns (delegation-patterns guide)

| Pattern | Shape |
|---|---|
| Parallel Research | N independent researchers → parent synthesizes ("research three topics simultaneously") |
| Code Review | "a fresh-context subagent that approaches the code without preconceptions" — explicit file paths + test command in context |
| Compare Alternatives | one subagent per option, "without cross-contamination"; parent picks |
| Multi-File Refactoring | split by codebase area across parallel children |
| Gather Then Analyze | "`execute_code` for mechanical data gathering, then delegate the reasoning-heavy analysis" |

**Don't delegate**: a single tool call (use the tool), mechanical
multi-step work (`execute_code`), anything needing user interaction
(`clarify` is blocked), quick file edits (do them directly).

### Writing goals and contexts

"Be specific in goals. 'Fix the bug' is too vague." "Include file paths.
Subagents don't know your project structure." The guide's canonical
context shape: project path, stack, exact files, test command, focus
list, and the verification expectation — because "if you delegate 'fix
the bug we were discussing,' the subagent has no idea what bug you
mean."

### SubDD — the methodology (official optional skill)

"Execute implementation plans by dispatching fresh subagents per task
with systematic two-stage review": parse the plan into a todo list →
per task: fresh implementer subagent → spec-compliance review →
code-quality review → mark complete → final integration review → full
test suite + commit. Use with a detailed plan and mostly-independent
tasks; never skip a review stage, never dispatch parallel subagents onto
the same files. (Structurally close to stage 080's M-process
implementer/reviewer split — SubDD is the in-session, non-durable
analogue of what our kanban story pipeline does durably.)

Install on a seat (official trust tier):

```shell
hermes skills install official/software-development/subagent-driven-development
```

## Choosing the right primitive

- Needs to outlive one API loop, be visible to others, or involve humans
  → **kanban** (see `hermes-kanban`).
- Short reasoning subtask, answer back into the parent's context →
  **delegate_task**.
- Mechanical multi-step processing, no judgment → **execute_code**.
- Keep iterating in THIS chat until done → **/goal**.

## Validation

```shell
# In-session:
/agents                          # live subagent tree, cost rollups
hermes config get delegation --json   # effective delegation config
ls ~/.hermes/cache/delegation/live/   # live transcripts exist for a dispatch
```

## Pitfalls

- Writing "SDD" for the Hermes methodology anywhere in stage 080 —
  reserved for Specification-Driven Development; use SubDD.
- Assuming children see parent history — they see `goal` + `context`
  only.
- Expecting a child to ask for clarification — `clarify` is blocked;
  under-specified goals fail, not escalate.
- Treating delegation as durable — restarts kill running children;
  kanban is the durable primitive.
- Raising `max_spawn_depth` without the concurrency math — the official
  27-leaf warning.
- Parallel-batching tasks that touch the same files — SubDD's own
  anti-pattern; serialize or split by file ownership.
- Delegating what shouldn't be delegated: single tool calls, mechanical
  pipelines, quick edits, or anything that might need to ask the user.
- Vague goals referencing conversation state ("fix the bug we
  discussed") — children start blank; name files, commands, and criteria.

## Related Skills

- `hermes-kanban` — the durable board this primitive is NOT.
- `hermes-hooks` — subagent lifecycle observability.
- `hermes-sessions` — delegate sessions are real `state.db` rows with
  parent/child lineage.
- `hermes-tools` — the delegation toolset and inheritance model.

## References

- `references/source-capture.md`
