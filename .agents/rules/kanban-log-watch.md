---
name: kanban-log-watch
skill-group: Demo Environment
applies-to:
  - stages/080-ai-autonomous-migration/**
  - harness-refactoring/**
---

# Kanban log watch

After **every** dest Hermes Kanban spawn, read the official worker log **in the same turn**. Sqlite `running` or `done` is not observation.

Official surfaces (do not substitute a session transcript or a `chat -q` pane):

- `hermes kanban log <task_id>`
- `$HERMES_HOME/kanban/logs/<task_id>.log` (usually `/projects/modernized/.hermes/home/kanban/logs/<id>.log`)

Confirm the worker is executing the card job. If the log shows a gap, poison, fence refusal, wrong child, or a false Done, address it before starting another card.

Do **not** dest-complete Operator ack gates. Do **not** dest-read `.env` values. Do **not** `kanban daemon --force`.

Procedure: `.hermes/skills/harness/dispatch-phase/references/native-dispatch.md` and `hermes-kanban`.
