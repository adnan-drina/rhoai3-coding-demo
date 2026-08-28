---
name: hermes-sessions
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "hermes"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Hermes Agent"
description: >
  Use when working with Hermes sessions in stage 080: session identity and
  storage (state.db), resume/handoff/search, retention and pruning,
  checkpoints and rollback, and building provenance/audit trails on
  session ids. Do NOT use for compression config (use
  hermes-configuration), kanban task/run durability (use hermes-kanban),
  or session-lifecycle hook events (use hermes-hooks).
---

# Hermes Sessions

Use this skill for any stage 080 design touching session storage,
provenance keyed on session ids, retention, or checkpoint safety nets.

## Source Grounding

Read `references/source-capture.md` for provenance and
`references/official-doc-extraction.md` for the full validated extraction
(paths, config keys, schema facts, CLI tables, verbatim examples, and the
reviewer's source-verified provenance findings). Official Hermes Agent
documentation (Nous Research) is the product authority.

## Key Concepts

### One canonical store

Every conversation — CLI, gateway, cron, delegate/subagent, kanban worker —
is an ordinary session in `~/.hermes/state.db` (SQLite, WAL, FTS5; schema
v23). `sessions.json` is a legacy, gateway-only mirror — "not the session
list"; provenance and audits read `state.db`, never the JSON. Multiple
processes (gateway + CLI + workers) share one `state.db`; the documented
retry/jitter/WAL strategy is the only concurrency guarantee. Batch-runner
and trajectory data are separate systems.

### Identity and lineage

Session IDs are parseable: `YYYYMMDD_HHMMSS_<hex>` — 6-char hex for
CLI/TUI, 8-char for gateway. Gateway routing keys follow
`agent:main:{platform}:{chat_type}:{chat_id}` (thread- and per-user
variants exist). Delegate/subagent runs are real session rows with
parent/child lineage (`parent_session_id`); deleting a parent cascades to
its delegate sessions. `/handoff` preserves the session id across
platforms.

### Stage 080 provenance — the honest ground truth

`worker_session_id` in kanban completion metadata is a **stage 080 project
convention, not documented product behavior**. Verified against docs and
shipped source: `kanban_complete`'s `metadata` is free-form JSON;
`task_runs` has NO session column; `tasks.session_id` records the
*creating* chat session (list-filterable via `--session`); worker sessions
are ordinary `state.db` rows kanban merely retags with a worker label. If
the harness wants the worker's session id in completion metadata, the
worker must write it itself — the official primitive to source it is
`HERMES_SESSION_ID`, auto-exported into tool subprocesses ("You should not
set this manually").

### Retention

`sessions.auto_prune` defaults `false` ("session history is valuable for
`session_search` recall"); only ENDED sessions are pruned, aged from their
latest message — active sessions never. Sizing signal from the docs: a
384 MB `state.db` at ~1000 sessions degraded FTS5 inserts — opt in for
heavy worker fleets. Non-destructive first: `hermes sessions optimize`.

### Checkpoints are a separate, opt-in system

`checkpoints.enabled` defaults `false` (v2). A single shared shadow git
store under `~/.hermes/checkpoints/store/` — "your real project `.git` is
never touched". At most one checkpoint per directory per turn. Restore is
four steps: verify → pre-rollback snapshot ("undo the undo") → restore
tracked files → undo the last conversation turn, so filesystem and agent
context roll back together. Guards: transparently disabled without `git`
on PATH; >50,000-file directories skipped; >10 MB files skipped; store
capped at 500 MB. Checkpoint identity is the **workdir path hash**, not a
session id. `/snapshot` is a different feature (config/state snapshots) —
don't conflate.

## Workflow

1. For provenance designs, key on `state.db` session rows and the
   documented ID grammar; never on `sessions.json`.
2. For worker provenance, have the worker write its own session id into
   `kanban_complete(metadata=…)` (project convention; source from
   `HERMES_SESSION_ID`) — do not claim Hermes records it.
3. For unattended workers wanting a rollback net, set
   `checkpoints.enabled: true` explicitly and size
   `max_total_size_mb`/`retention_days` for the fleet; pair with git
   worktrees per the official best practice.
4. For high-volume harnesses, opt into `sessions.auto_prune` deliberately;
   note session retention (90d default) and checkpoint retention (7d
   default) are independent namespaces with no documented interaction.
5. Extract audit evidence with
   `hermes sessions export --format jsonl --session-id <id> --redact`.
6. Cite the official section in the PR (stage 080 official-first rule).

## Validation

```shell
hermes sessions list --workspace <path>   # sessions recorded for a worker workspace
hermes sessions stats                     # state.db size within expected bounds
hermes sessions optimize                  # non-destructive FTS merge + VACUUM
hermes checkpoints status                 # store growth bounded when enabled
hermes logs --session <substr>            # log lines filtered by session id
```

## Pitfalls

- Reading `sessions.json` for audits — it's a legacy, gateway-only mirror.
- Assuming `worker_session_id` is official kanban behavior — it's our
  convention; the field exists only if the worker writes it.
- Assuming checkpoints are on — they're opt-in, and silently absent
  without `git` on PATH or in >50k-file workspaces (large migration
  trees can exceed this).
- Conflating `/snapshot` (config/state) with `/rollback` (filesystem
  checkpoints), or checkpoint identity (workdir hash) with session
  identity.
- Expecting cron deliveries in chat history — they live in their own cron
  session by deliberate design.
- Backing up `state.db` by copying only the main file mid-write — WAL
  sidecars matter; `hermes backup` deliberately excludes `-wal/-shm`
  (quiesce first), and repair guidance starts with
  `cp state.db state.db.bak`.
- `--clone-all` for profiles explicitly excludes session history,
  `state.db`, and checkpoints — cloning a profile never clones its
  sessions.

## Related Skills

- `hermes-kanban` — `task_runs`/`task_events` durability (separate DB,
  separate model).
- `hermes-hooks` — `session:start/end/reset` and
  `on_session_*` lifecycle events.
- `hermes-configuration` — compression/compaction and profile mechanics.
- `hermes-cli` — canonical `hermes sessions`/`hermes checkpoints`
  reference.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
