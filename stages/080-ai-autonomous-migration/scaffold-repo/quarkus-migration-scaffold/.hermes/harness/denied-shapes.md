# Denied command shapes (V6 P2.2 / E.4)

Headless Hermes command policy must **fail in seconds**, not hang ~5
minutes then deny. Enforcement is written into every Dev Spaces workspace
by `maas-api-key-provisioning.yaml` → `~/.hermes/config.yaml`:

```yaml
approvals:
  mode: smart
  timeout: 5          # was ~300s deny-tax
  cron_mode: deny
  deny:
    - "*python3*<<*"
    - "*python *<<*"
    - "*python3 - <<*"
    - "*bash*<<*"
    - "*sh *<<*"
    - "*python3 -c*"
    - "*python -c*"
    - "*rewrite-staging*"
    - "*rewrite-maven-plugin*"
```

`approvals.deny` blocks even under yolo. `timeout: 5` fail-closes any other
dangerous-command prompt when no human is present.

## Allow (do not deny)

- `python3 .hermes/harness/*.py` and
  `python3 .hermes/skills/migration-harness/scripts/*.py`
- `.hermes/harness/sensors.sh`, `style-autofix.sh`, `recipe-transform.sh`
- `.hermes/skills/migration-harness/scripts/harvest-from-staging.sh`
- Foreground `opencode run …` (no `&`)
- `mvn`, `git`, `curl`, `oc` (read-only harness paths)

## Feedforward

Sessions must use bundled scripts per `EXECUTION.md` / `SKILL.md`. Existing
workspaces: re-run the Dev Spaces postStart init (or recreate the workspace)
so `ensure_hermes` rewrites config.
