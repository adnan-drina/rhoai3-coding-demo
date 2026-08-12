# Configuration — locations, precedence, Managed Scope

**Official page:** https://hermes-agent.nousresearch.com/docs/user-guide/configuration

Also: https://hermes-agent.nousresearch.com/docs/user-guide/managed-scope

**CS-5 cross-pointer:**
`harness-refactoring/source-analysis/hermes/20260812-official-kanban-alignment.md`

## File map (official Directory Structure)

| Path under `$HERMES_HOME` | Role |
|---------------------------|------|
| `config.yaml` | Non-secret settings |
| `.env` | API keys / secrets |
| `auth.json` | OAuth (Portal) — remove on MaaS seats |
| `skills/`, `sessions/`, `logs/`, `cron/` | Runtime |

Relocate whole tree with `HERMES_HOME`. Secrets stay out of `config.yaml`
(official secrets rule).

## Precedence (official)

1. CLI arguments (highest)
2. `$HERMES_HOME/config.yaml`
3. `$HERMES_HOME/.env`
4. Built-in defaults

`${VAR}` / `${env:VAR}` substitution resolves inside `config.yaml`.

## Managed Scope (quote)

Official: an administrator can pin specific config and secret values that a
standard user cannot override — via `/etc/hermes/{config.yaml,.env}` or
`$HERMES_MANAGED_DIR/{config.yaml,.env}` (leaf merge over user config).

Docs also state the limit: enforcement is filesystem permissions only — not
an un-escapable sandbox. Pair with NetworkPolicy for endpoint control.

Demo pin path: `HERMES_MANAGED_DIR=/projects/.platform/hermes`.
