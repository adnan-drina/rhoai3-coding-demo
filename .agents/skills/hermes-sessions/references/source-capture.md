# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product | Hermes Agent (Nous Research) |
| Product version | no version marker on doc pages; `state.db` schema version 23; checkpoints subsystem "v2" |
| Chapter or page title | Sessions; Checkpoints & Rollback; Session Storage; Gateway Internals; Architecture; Profiles / Memory / Git Worktrees (boundary slices); CLI/Slash/Env references (session rows) |
| Source URL | https://hermes-agent.nousresearch.com/docs/user-guide/sessions |
| Source URL | https://hermes-agent.nousresearch.com/docs/user-guide/checkpoints-and-rollback |
| Source URL | https://hermes-agent.nousresearch.com/docs/developer-guide/session-storage |
| Source URL | https://hermes-agent.nousresearch.com/docs/developer-guide/gateway-internals |
| Source URL | https://hermes-agent.nousresearch.com/docs/developer-guide/architecture |
| Documentation category | Using Hermes / Developer Guide / Reference |
| Capture date | 2026-08-12 |
| Capture method | Research-agent dossier (`source-analysis/hermes/hermes-sessions-capture.md`); reviewer re-verified the sessions.json admonition, ID grammar, prune defaults/guarantees, delegate-cascade, checkpoint opt-in/shadow-store/restore/guards quotes verbatim against live pages on 2026-08-12; provenance gap resolved by reviewer against shipped source (`hermes_cli/kanban.py`, `kanban_db.py`) |

## Captured Sections

- Sessions: uniform session model and sources, storage locations
  (state.db canonical; sessions.json legacy gateway mirror), resume
  (`-c`/`-r`/`latest`/by-name/`--in`), cross-platform handoff, naming and
  lineage, management commands (list/export/delete/rename/prune/archive/
  stats/repair-routing/optimize), `session_search` (FTS5), per-platform
  session keys, reset policies, crash-continuity, expiry/auto-prune.
- Checkpoints & Rollback: opt-in v2 posture, triggers and
  once-per-dir-per-turn cap, shadow store layout, full config defaults,
  restore mechanics, eight safety guards, v1 migration.
- Session Storage: SQLite schema (9 tables), schema v23 + migration
  table, write-contention handling, lineage queries, DB location.
- Gateway Internals: session key format, expiry as background
  maintenance, delivery-path isolation for cron, memory-flush lifecycle.

## Provenance findings (reviewer, source-verified — repository, not docs)

- `task_runs` has NO session-id column (verified against all INSERT
  shapes in `kanban_db.py`).
- `tasks.session_id` exists (indexed; schema migration) and records the
  CREATING session at `create_task` time; filterable via
  `hermes kanban list --session`.
- Worker sessions are ordinary `state.db` sessions; kanban retags them
  with a worker label (`retag_kanban_worker_sessions`, keyed on the
  kanban workspaces root).
- Therefore `worker_session_id` in completion metadata is a stage 080
  convention the worker must write itself; the official sourcing
  primitive is `HERMES_SESSION_ID` (exported into tool subprocesses and
  delegated runs).

## Source Boundaries

This skill captures session identity, storage, resume/search, retention,
and checkpoints. Compression behavior and profile mechanics belong to
`hermes-configuration`; kanban run/event durability to `hermes-kanban`;
session-lifecycle hooks to `hermes-hooks`; the canonical CLI trees to
`hermes-cli`. `/snapshot` (config/state snapshots) is a distinct feature
from checkpoints — flagged to avoid conflation.

## Known Open Items

- "CLI Background Sessions" and "Session Heartbeats" pages are referenced
  by slash-command docs but have no locatable standalone URL.
- No documented interaction between `sessions.retention_days` (90d) and
  `checkpoints.retention_days` (7d) — independent namespaces.
- Delegation (`delegate_task`) session semantics have no owning `hermes-*`
  skill (taxonomy gap, alongside Cron and Plugins).
- Whether `HERMES_SESSION_ID` export applies to kanban dispatcher-spawned
  workers specifically (vs. documented tool subprocesses and delegated
  runs) is undocumented — verify on a live seat before relying on it as
  the metadata source.
