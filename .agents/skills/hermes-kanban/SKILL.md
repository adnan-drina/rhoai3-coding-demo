---
name: hermes-kanban
metadata:
  author: rhoai3-coding-demo
  version: 1.1.0
  platform-family: "hermes"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Hermes Agent"
description: >
  Use when designing or reviewing Hermes Kanban orchestration for stage
  080: task lifecycle and states, dispatcher and worker-lane behavior,
  retry and recovery paths, orchestrator fan-out, collaboration patterns,
  boards and attachments, dashboard/notifications, task bodies and
  completion metadata, and the kanban CLI/tool/event surfaces. Do NOT use
  for kanban config-key schema wiring (use hermes-configuration), hooks
  mechanics (use hermes-hooks), delegate_task fork-join work (use
  hermes-delegation), or seat pins (use hermes-managed-scope).
---

# Hermes Kanban

Use this skill for any stage 080 change touching multi-agent orchestration
on the Hermes Kanban board.

## Source Grounding

Read `references/source-capture.md` for provenance and
`references/official-doc-extraction.md` for the full validated extraction —
complete state/config/CLI/tool/event tables, the four tutorial stories,
the worker-lanes capture, verbatim examples, and the recovered v1 design
spec. The live feature docs are the product authority for behavior; the
v1 spec (`hermes-kanban-v1-spec.pdf`, April 2026) is design rationale
only — the shipped product evolved past it (8 states vs 6, the `kanban_*`
toolset, 9 patterns, boards, runs, review).

## Key Concepts

### Tasks, states, and runs

Canonical status enum (8 values):
`triage | todo | ready | running | blocked | review | done | archived`.
The dispatcher promotes `todo → ready` when all parents are `done`. There
is NO `scheduled` status — `scheduled_at` is a column; the dispatcher
"skips ready tasks whose `scheduled_at` is in the future" (the CLI
reference's "park in scheduled" wording is loose). A **task** is the
logical unit; a **run** is one attempt — `task_runs` keeps one row per
attempt, and retrying workers read their own prior attempts so they don't
repeat a failed path. The dashboard renders six columns
(Triage/Todo/Ready/In progress/Blocked/Done) with per-profile lanes.

### The dispatcher and worker lanes

A gateway-embedded loop (default tick 60s): reclaim stale claims, reclaim
crashed workers, promote ready tasks, atomically claim, spawn assigned
profiles. **No running gateway ⇒ `ready` tasks just wait** — `create`
warns about this. Standalone `hermes kanban daemon` is deprecated; two
dispatchers on one `kanban.db` "causes claim races and is not supported".

A **worker lane** is "a class of process that the kanban dispatcher can
route tasks to": an assignee identity + a spawn mechanism + a lifecycle
contract. The default lane spawns full Hermes processes
(`hermes -p <assignee> chat -q …`) in the task's pinned workspace with
the board pinned via env: `HERMES_KANBAN_TASK`, `_DB`, `_BOARD`,
`_WORKSPACES_ROOT`, `_WORKSPACE`, `_RUN_ID`, `_CLAIM_LOCK`,
`HERMES_PROFILE`, `HERMES_TENANT`. Unresolvable assignees stay `ready`
with a `skipped_nonspawnable` event; external (non-Hermes) CLI lanes are
"not yet a paved path". Workers never own lifecycle truth — every state
change flows through `kanban_*` tools, ending in exactly one terminator:
`kanban_complete`, `kanban_request_review`, or `kanban_block` (a clean
exit without one is the `protocol_violation` failure path).

### Recovery and retry (six distinct paths — name the right one)

- `reclaimed` — claim TTL expired without completion (default TTL 15 min).
- `crashed` — worker PID gone before TTL expiry.
- `stale` — ran past `kanban.dispatch_stale_timeout_seconds` (default 4h)
  with no heartbeat in the last hour; does NOT tick the failure counter.
- `reconciled` — orphaned claim bookkeeping with no live worker
  (`kanban.reconcile_orphans`, default true).
- `gave_up` — circuit breaker; threshold resolves task `--max-retries` →
  `kanban.failure_limit` (default 2) → built-in default.
- `protocol_violation` — worker exited 0 while still `running`; bounded
  retry (default 3 consecutive) before auto-block.

Plus the respawn guard (`blocker_auth`, `recent_success`, `active_pr`
keep a ready task unspawned), stranded-task detection
(`kanban.stranded_threshold_seconds`, ~30 min default, surfaced by
`diagnostics`), and the block-loop breaker: same-cause re-block twice
(`BLOCK_RECURRENCE_LIMIT`) routes to `triage` for a human — "a
deterministic DB guard, not an LLM judgment call".

### Worker protocol and handoff evidence

`kanban_show()` → do the work → `kanban_heartbeat` at least hourly for
long work → one terminator. Handoff metadata convention: `changed_files`,
`verification`, `dependencies`, `blocked_reason`, `retry_notes`,
`residual_risk` — never secrets, tokens, or raw PII (rows are
audit-durable). Reviews are first-class: `kanban_request_review` →
reviewer `kanban_request_changes` (returns to the implementer WITHOUT
block-loop accounting) or `kanban_complete` to approve; same-card review
and a pre-created downstream review card are mutually exclusive patterns.
`kanban_block` is "reserved for a real external escalation… not normal
review feedback". Spawned workers never see the dashboard or CLI — if it
isn't in `kanban show <id>`, the worker can't see it.

### Orchestration

Workers cannot see sibling cards — "every child card body must carry
every decision it depends on"; decide before you fan out. The dispatcher
**silently fails on unknown assignee names** — ground every card in
profiles that exist (give worker profiles `--description` for decomposer
routing). Orchestrator profiles exclude execution toolsets (`terminal`,
`file`, `code`, `web`) so they "literally cannot execute implementation
tasks". Parent links are the context channel: children read each parent's
most recent completed run's summary + metadata; done cards are immutable —
follow-up work is a new child card (the tutorial's CI-remediation
example), never a reopen. Colliding worker branches get a reconciliation
card assigned to a third neutral profile — never self-adjudication; repeat
collisions on one file get a `hotspot:` comment and a decomposition card.

### The nine collaboration patterns

| P | Pattern | Shape |
|---|---------|-------|
| P1 | Fan-out | N siblings, same role ("research 5 angles in parallel") |
| P2 | Pipeline | role chain: scout → editor → writer |
| P3 | Voting/quorum | N siblings + 1 aggregator |
| P4 | Long-running journal | same profile + shared dir + cron |
| P5 | Human-in-the-loop | worker blocks → user comments → unblock |
| P6 | @mention | inline routing from prose (`@reviewer look at this`) |
| P7 | Thread-scoped workspace | `/kanban here` in a gateway thread |
| P8 | Fleet farming | one profile, N subjects (50 accounts) |
| P9 | Triage specifier | rough idea → `triage` → `specify` → `todo` |

`hermes kanban swarm "<goal>" --workers … --verifier … --synthesizer …`
creates a root + workers + verifier + synthesizer graph in one atomic
commit.

### Boards, attachments, tenants, scale

Boards isolate projects (slug-validated; workers spawn with
`HERMES_KANBAN_BOARD` pinned so "they can't see other boards";
resolution: `--board` > `HERMES_KANBAN_BOARD` > `~/.hermes/kanban/current`
> `default`; `HERMES_KANBAN_DB` beats everything). Attachments: 25 MB/file
under `~/.hermes/kanban/attachments/<task_id>/`; workers get absolute
paths in context — on Docker/Modal backends, mount the attachments
directory into the sandbox. Tenants namespace tasks/workspaces/memory
(`--tenant`/`HERMES_TENANT`). Kanban is deliberately **single-host**;
concurrency caps: `kanban.max_in_progress` / `max_in_progress_per_profile`
(unset = unlimited). Relative `dir:` workspace paths are rejected at
dispatch (confused-deputy vector); scratch artifacts survive only via
`kanban_complete(artifacts=[...])`.

### Dashboard, slash surface, notifications

The dashboard is a thin bundled plugin over the same `kanban_db`:
six-column board, drag-drop, side drawer (runs history, exit-status
badges, Decompose/Specify LLM actions), Auto/Manual orchestration pill
(decomposer "NEVER lands a child task with `assignee=None`" — unknown
picks route to `kanban.default_assignee`). Its plugin routes are
unauthenticated by design (localhost binding) — never
`--host 0.0.0.0` on a shared host. `/kanban` mirrors the CLI argument
surface in chat, bypasses the running-agent guard mid-run, and
auto-subscribes the creating chat to terminal events (`completed`,
`blocked`, `gave_up`, `crashed`, `timed_out`; completed also delivers the
result's first line). Multi-profile delivery is profile-owned with atomic
per-event claiming — no duplicate delivery.

## Workflow

1. Read the official Kanban page + tutorial before designing
   dispatcher/worker behavior; cite sections (stage 080 official-first
   rule).
2. Pick the collaboration pattern (P1–P9) explicitly and model task
   bodies on the documented handoff convention; stamp every shared
   decision into each child body.
3. For stuck/retry design, cite the specific event kind (`stale`,
   `crashed`, `gave_up`, `respawn_guarded`, `protocol_violation`,
   `reconciled`, `skipped_nonspawnable`) — never a generic "task failed".
4. Prefer Kanban-native dispatch and official knobs (`--max-retries`,
   `--max-runtime`, heartbeats, `scheduled_at`, concurrency caps) over
   external process management or custom watchdogs; record any gap the
   official mechanism leaves before building around it.
5. Verify every assignee profile exists (`hermes kanban assignees`) —
   unknown names fail silently.
6. Use first-class review (`request-review`/`request-changes`) for
   quality loops; reserve `block` for genuine external escalation.
7. Pin task-specific skills with `--skill` only if installed on the
   assignee's profile (no runtime install); per-task `--model`/`set-model`
   for quality-sensitive cards; `--goal` only for open-ended cards (judge
   overhead isn't worth it for one-shot work).

## Validation

```shell
hermes kanban diagnostics --json        # board health, stranded tasks, deadlocks
hermes kanban runs <id> --json          # attempt history (circuit-breaker evidence)
hermes kanban dispatch --dry-run --json # ready-queue state without side effects
hermes kanban context <id>              # exactly what the worker will see
hermes kanban tail <id>                 # follow one task's event stream
hermes kanban watch --kinds gave_up,timed_out,stale,protocol_violation
hermes kanban assignees --json          # profiles on disk + task counts
hermes kanban log <id>                  # worker log from ~/.hermes/kanban/logs/
```

## Pitfalls

- Unknown assignee = silent dispatcher failure (or `skipped_nonspawnable`
  for non-profile lanes), not an error.
- Bulk `complete` with a shared `--summary` is refused by design —
  structured handoff is per-run.
- No gateway process means nothing dispatches; the deprecated `daemon
  --force` next to a gateway dispatcher causes unsupported claim races.
- Stale-reclaim is fault-neutral (no failure-counter tick) — don't count
  it toward "the task keeps failing".
- `kanban.orchestrator_profile` only sets who owns the root task after
  decomposition — it does not load that profile's prompt or skills into
  the decomposer call.
- Goal-mode cards share the `/goal` engine but not its state.
- `hermes dashboard --host 0.0.0.0` exposes unauthenticated kanban plugin
  routes — never on a shared host.
- Secrets/tokens/raw PII in `summary`/`metadata` — the rows are durable
  audit records; store pointers, not credentials.
- Same-card review AND a pre-created downstream review card on one task —
  the two patterns are mutually exclusive.
- Messaging output is truncated (~3,800 chars) — don't put load-bearing
  detail only in a chat-delivered result.
- `BLOCK_RECURRENCE_LIMIT` / `_PROTOCOL_VIOLATION_FAILURE_LIMIT` have no
  documented config-key names — treat as internal constants.
- `worker_session_id` in completion metadata is a stage 080 convention
  the worker itself must write — not official kanban behavior (see
  `hermes-sessions`).

## Related Skills

- `hermes-delegation` — the fork-join primitive this board is NOT
  (durable, peer-readable, human-in-loop vs function call).
- `hermes-configuration` — schema wiring for `kanban.*`/`auxiliary.*`.
- `hermes-hooks` — kanban lifecycle hooks and their process split.
- `hermes-sessions` — worker sessions vs task_runs durability.
- `hermes-tools` — the kanban toolset's opt-in gating.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
