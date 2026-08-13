# Contract: Managed Scope must be active at kanban spawn

**Status:** binding (in-tree).

## Official rule (Hermes Managed Scope)

Hermes reads administrator-pinned provider/auth from **Managed Scope**:

- Default: `/etc/hermes/{config.yaml,.env}`
- Relocate: `HERMES_MANAGED_DIR` (deployment knob — never persist into user `.env`)

Managed keys **overlay** `$HERMES_HOME/config.yaml` and `.env`. See:
https://hermes-agent.nousresearch.com/docs/user-guide/managed-scope

## NEVER

- Symlink or copy Managed Scope `config.yaml` / `.env` into `HERMES_HOME` (R-HX.5).
- Spawn `hermes kanban daemon` / `dispatch` / workers without `HERMES_MANAGED_DIR` in the **process** environment.
- Rely on `~/.bashrc` alone — non-login spawns (`oc exec` python, bare nohup) drop bashrc exports.
- Export `HERMES_MANAGED_DIR` to the specimen workspace (`/projects/modernized`), `HERMES_HOME`, or `HERMES_WRITE_SAFE_ROOT` — that stillborns with the Hermes Setup banner even when a directory exists.

## MUST

1. Export `HERMES_MANAGED_DIR` to the **pinned** platform path (demo default `/projects/.platform/hermes`) in every dispatch/daemon wrapper. Wrong inherited values must be **refused**, not silently defaulted-over only when unset.
2. Run `assert-managed-scope-active.py` before spawn — refuse if unset / missing / provider-false / **not equal to pin** .
3. Keep `HERMES_HOME/config.yaml` as non-secret workspace knobs only (`skills.external_dirs`, …); providers stay managed.
4. Prefer `.hermes/home/scripts/kanban-dispatch-guarded.sh` (or `dispatch-phase.sh`) over bare `hermes kanban dispatch` from ad-hoc shells.

## Symptom of breach

Worker log: `Hermes isn't configured yet -- no API keys or providers found` / `hermes setup` while board status stays `running` with `last_heartbeat_at=NULL` (stillborn).
