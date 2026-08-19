# Serial GO — native `hermes kanban dispatch --max 1`

Default `DISPATCH_MAX=0` **creates** the card (`ready`) and does **not** spawn.
Serial GO is a **one-shot native dispatch**, which is the only path that claims
the card, sets `running`, and writes `$HERMES_HOME/kanban/logs/<task_id>.log`.

```bash
export HERMES_HOME="${HERMES_HOME:-/projects/modernized/.hermes/home}"
export HERMES_MANAGED_DIR="${HERMES_MANAGED_DIR:-/projects/.platform/hermes}"
cd /projects/modernized
hermes kanban dispatch --max 1
# REQUIRED same-turn watch (not optional). Sqlite running/done is not observation.
hermes kanban log <task_id>
# same bytes: .hermes/home/kanban/logs/<task_id>.log
```

Do **not** substitute `hermes -p default --cli chat -q "work kanban task t_…"`.
That skips `_default_spawn`: sqlite stays `ready`, no official log,
`hermes kanban log` reports "task may not have spawned yet".

Do **not** `hermes kanban daemon --force` next to a gateway (deprecated;
two dispatchers on one `kanban.db` cause claim races and are not
supported). Official-first (AD-013 / Architect `21afefd3`): the
long-running native loop is the **gateway-embedded dispatcher**.
`--interval` / `--max` are **dispatch** flags, not daemon flags.
Hand-looping `dispatch --max 1` is a GO, not architecture.

```yaml
# dest .hermes/home/config.yaml — official Kanban keys
kanban:
  auto_decompose: false
  dispatch_in_gateway: true
  dispatch_interval_seconds: 60
  max_in_progress: 1
```

```bash
hermes gateway start
# native hygiene (no new reaper): gc / repair / diagnostics
hermes kanban gc
hermes kanban repair
hermes kanban diagnostics
```

`kanban_heartbeat` is the worker liveness signal; the dispatcher already
reclaims stale claims. Do not invent a harness reaper.

`dispatch-phase.sh --help` documents the same GO. There is no wrapper script.

## Triage after block_loop_detected

Official CLI `hermes kanban promote` / `unblock` / `block` refuse a
`triage` task (v33 dest-cite). Recovery is `specify` / `decompose`
(forbidden on the M3 holder) or a human. Do **not** invent a leave-triage CLI.
Do **not** sqlite-reset `block_recurrences` unless Operator GO.
Dest-home `auto_decompose: false` is the create-path pin so a holder in
triage is not auto-decomposed. C-3(a) remediation already forbids
leave-triage as a REFUSE path; this is the same OBJECT after the circuit
breaker.

## M3 children

Park-at-birth **M3 is the WAVE HOLDER** (title `M3 WAVE HOLDER`, holder
body, **zero** `--skill` pins). M3 **story** children take the dedicated
create path (`--parent` is **required**).
The wave-holder Hermes session follows
`references/mint-m3-hermes.md` (`kanban_create` + ack_gate). Do **not**
run a deleted `mint-m3-wave.sh` / `create-m3-implementer.sh` from Cursor
or ask the demo user to. Do **not** park M4/M5 as children of the holder.
Mint-time M4 `--parent` is the story-child id set (R-V14.6); M5 stays on
M4. Holder complete means "cards minted", not "work done".
