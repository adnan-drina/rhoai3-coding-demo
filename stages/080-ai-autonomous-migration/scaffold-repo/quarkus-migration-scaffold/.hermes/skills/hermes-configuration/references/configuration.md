# Configuration — locations, precedence, Managed Scope

**Official sources (cite these):**
- Configuration: https://hermes-agent.nousresearch.com/docs/user-guide/configuration
- Configuring Models: https://hermes-agent.nousresearch.com/docs/user-guide/configuring-models
- Managed Scope: https://hermes-agent.nousresearch.com/docs/user-guide/managed-scope
- Security: https://hermes-agent.nousresearch.com/docs/user-guide/security

**Internal digest (not a substitute for official cite):**
`harness-refactoring/source-analysis/hermes/configuration.md` (W1).

## Directory structure (official)

Under `$HERMES_HOME` (often `~/.hermes/`, relocated via `HERMES_HOME`):

| Path | Role |
|------|------|
| `config.yaml` | Non-secret settings |
| `.env` | Secrets / API keys |
| `skills/` | Agent-created skills (`skill_manage`) |
| `sessions/`, `logs/`, `cron/` | Runtime |

## Precedence (official)

1. CLI arguments (highest, per-invocation)
2. `$HERMES_HOME/config.yaml`
3. `$HERMES_HOME/.env`
4. Built-in defaults
5. **Managed Scope** — `/etc/hermes/{config.yaml,.env}` or
   `$HERMES_MANAGED_DIR/{config.yaml,.env}` pins selected keys over user
   config (leaf merge). Docs: enforcement is **filesystem permissions
   only**, not an un-escapable sandbox.

## Platform pin (demo-validated)

- Relocate knob: `HERMES_MANAGED_DIR=/projects/.platform/hermes`
- Provider/auth live in Managed Scope — **do not** dual-home secrets under
  writable `$HERMES_HOME` (R-HX.5).
- Demo pins commonly include: `model.context_length: 131072`,
  `model.max_tokens: 8192`, `providers.custom.models.<id>.stale_timeout_seconds: 900`,
  `compression.threshold_tokens: 110000`,
  `tool_loop_guardrails.hard_stop_enabled: true`.

## CLI verification

```bash
hermes config              # view resolved
hermes config get KEY
hermes config check
hermes doctor
```

`hermes config set` routes API keys → `.env`, other keys → `config.yaml`.
