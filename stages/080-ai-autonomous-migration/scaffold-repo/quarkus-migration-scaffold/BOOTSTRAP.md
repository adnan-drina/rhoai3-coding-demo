# Destination bootstrap (Wave B)

This golden scaffold ships the **harness tree only** for the destination
app shape: `.hermes/`, `governance/contracts/`, fixtures, `AGENTS.md`,
`.hermes/SOUL.md`. There is **no** hand-maintained destination `pom.xml`
or `src/` skeleton.

## How to create the destination Quarkus app

Use guidance skill:

```bash
bash .hermes/skills/migration/bootstrap-quarkus-project/scripts/bootstrap.sh
```

Dual path (plan
`harness-refactoring/monitoring/20260813-v14-quarkus-bootstrap-plan.md`):

1. **Prefer Quarkus CLI** with `registry.quarkus.redhat.com` first + Red Hat
   GA Maven reachability (`BOOTSTRAP_MODE=cli` or `auto`).
2. **Fallback** Maven `:create` on the Red Hat platform stream
   (`BOOTSTRAP_MODE=maven`).
3. Add extensions via `manage-quarkus-extensions` (evidence-driven).
4. Apply the declared harness pom patch, then lint:

```bash
python3 .hermes/skills/migration/manage-quarkus-extensions/scripts/check-pom-platform-pins.py .
```

Platform GAV values: `governance/contracts/tooling-pins.md` only.

## Keep

Do not delete or overwrite: `.hermes/`, `migration/`, `AGENTS.md`,
`.hermes/SOUL.md`, this `BOOTSTRAP.md`, `devfile.yaml`, GitOps-unrelated
provision assets.
