# Serial GO — native `hermes kanban dispatch --max 1`

Default `DISPATCH_MAX=0` **creates** the card (`ready`) and does **not** spawn.
Serial GO is a **one-shot native dispatch**, which is the only path that claims
the card, sets `running`, and writes `$HERMES_HOME/kanban/logs/<task_id>.log`.

```bash
export HERMES_HOME="${HERMES_HOME:-/projects/modernized/.hermes/home}"
export HERMES_MANAGED_DIR="${HERMES_MANAGED_DIR:-/projects/.platform/hermes}"
cd /projects/modernized
hermes kanban dispatch --max 1
tail -f .hermes/home/kanban/logs/<task_id>.log
# or: hermes kanban log <task_id>
```

Do **not** substitute `hermes -p default --cli chat -q "work kanban task t_…"`.
That skips `_default_spawn`: sqlite stays `ready`, no official log,
`hermes kanban log` reports "task may not have spawned yet".

Do **not** `hermes kanban daemon --force` (deprecated; two dispatchers on one
`kanban.db` cause claim races and are not supported).

`dispatch-phase.sh --help` documents the same GO. There is no wrapper script.

## M3 children

M3 children take the dedicated create path (`--parent` is **required**):

```bash
bash .hermes/skills/harness/dispatch-phase/scripts/mint-m3-wave.sh \
  --parent <m2_task_id>
# or per-story:
bash "${HERMES_SKILL_DIR}/scripts/create-m3-implementer.sh" \
  --title "M3 IMPLEMENT: <story>" \
  --body-json evidence/bodies/m3-s-010.json \
  --parent <m2_task_id>
```
