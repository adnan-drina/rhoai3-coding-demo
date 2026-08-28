---
name: hermes-goals
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "hermes"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Hermes Agent"
description: >
  Use when designing or reviewing Hermes Persistent Goals (/goal) for
  stage 080: the judge loop, completion contracts, quality gates,
  background-process parking, turn budgets, and when to choose /goal vs
  a kanban card vs kanban --goal. Do NOT use for board orchestration (use
  hermes-kanban) or auxiliary.goal_judge key wiring (use
  hermes-configuration).
---

# Hermes Persistent Goals (`/goal`)

Use this skill for single-session autonomous iteration — "a standing
objective that survives across turns" (Hermes' take on the Ralph loop,
independently implemented; user-facing design credited to Codex CLI's
`/goal` by Eric Traut).

## Source Grounding

Official page (captured 2026-08-12, see `references/source-capture.md`):
https://hermes-agent.nousresearch.com/docs/user-guide/features/goals

## Key Concepts

### The loop

After each turn a lightweight judge checks the goal; if unmet, Hermes
"automatically feeds a continuation prompt back into the same session and
keeps working — until the goal is achieved, you pause or clear it, or the
turn budget runs out." The judge sees the goal text + ~4 KB of the recent
response and returns strict JSON (`done | continue | wait`); it is
"deliberately conservative" (marks `done` only on explicit confirmation)
and **fail-open**: "a broken judge never wedges progress" — errors count
as `continue`. Real user messages always preempt the loop.

### Scope — one session, never the board

`/goal` is single-session: it "never creates a kanban card, never assigns
work to another profile, and never fans out". A kanban card created with
`--goal` "borrows the engine, not the board" — the same loop inside that
one card's worker session. Many tasks / dependencies / other profiles →
kanban (see `hermes-kanban`).

### Completion contracts

A contract names "what done means, how to prove it, what not to break,
what's in scope, and when to stop". Fields (all optional): `outcome`,
`verification`, `constraints`, `boundaries`, `stop_when`. Two ways to set:
`/goal draft <one-liner>` (the `goal_judge` auxiliary expands it —
recommended) or inline field prefixes:

```text
/goal Migrate auth to JWT
verify: pytest tests/auth passes
constraints: keep the /login response shape unchanged
boundaries: only touch services/auth and its tests
stop when: a DB schema migration is required
```

"The judge is only as good as your goal text" — write the body as
explicit acceptance criteria.

### Quality gates (deterministic floor under the LLM judge)

A gate is "a deterministic shell command that must exit 0 before the goal
can complete at all" — gates "run before the judge. If any fails, the
judge is not called." Unchanged workspace (git fingerprint) skips
re-runs; each gate defaults to 3 retries / 5-minute timeout, and
exhausting retries auto-pauses the goal. Manage with `/goal gate
add|list|remove|clear`. This is the official numeric-oracle pattern:
put the objective bar in a gate, not in judge prose.

### Parking (no busy-waiting)

The judge sees live background processes and can return `wait`: the loop
"parks" — "no judge call, no continuation, no turn consumed" — until the
wait releases (`wait_on_session`, `wait_on_pid`, `wait_for_seconds`;
manual `/goal wait <pid>` / `/goal unwait`). The right shape for CI,
builds, and deploys.

### Budget and controls

`goals.max_turns` default 20; on exhaustion the goal auto-pauses and
`/goal resume` "resets the counter to zero, so you can keep going in
measured chunks". Commands: `/goal <text>` (set/replace), `/goal
status|pause|resume|clear`, `/subgoal <text>` (append acceptance criteria
mid-loop), `/subgoal remove <N>`. Judge model routes via
`auxiliary.goal_judge` (~200 output tokens/turn — "a cheap fast model is
usually the right call"; wiring in `hermes-configuration`).

### When the judge is wrong

False negative (says continue when done) — "the turn budget catches
this." False positive (says done early) — follow up or re-set the goal
more precisely; the conservative prompt makes false positives the rarer
mode.

## Workflow

1. Choose the primitive first: this-chat iteration → `/goal`; board
   card that iterates → kanban `--goal`; multi-task/multi-profile →
   kanban proper.
2. Always attach a contract (draft or inline) — vague goal text is the
   main failure mode.
3. Put every objective criterion into a quality gate (test suite, lint,
   build) so completion has a deterministic floor.
4. For long external waits, rely on parking — never poll from goal text.
5. Size `goals.max_turns` to the work; resume in measured chunks rather
   than raising it blindly.
6. Cite the official section in the PR (stage 080 official-first rule).

## Validation

```shell
/goal status              # goal text, turns used, gates, wait state
/goal gate list           # gates and their pass/fail state
hermes config get goals --json          # effective budget
hermes config get auxiliary.goal_judge --json   # judge routing
```

## Pitfalls

- Expecting `/goal` to touch the kanban board — it never does; the
  overlap is deliberate and small (`--goal` cards borrow the engine
  only).
- Relying on the judge for objective criteria — gates exist precisely
  because "the judge is only as good as your goal text".
- Treating a judge error as a stop — fail-open means `continue`; the
  budget is the real backstop.
- Raising `max_turns` instead of fixing a vague contract — the budget
  catching false negatives is a feature.
- Busy-wait goal text ("keep checking CI") — use parking verdicts or
  `/goal wait <pid>`.
- Skipping `--goal` cost thinking on cheap one-shot cards — per-turn
  judge overhead isn't worth it (kanban capture's own guidance).

## Related Skills

- `hermes-kanban` — the board; `--goal` cards and the goals-vs-kanban
  decision table.
- `hermes-configuration` — `goals.*` and `auxiliary.goal_judge` wiring.
- `hermes-delegation` — fork-join subagents (a third, different
  primitive).

## References

- `references/source-capture.md`
