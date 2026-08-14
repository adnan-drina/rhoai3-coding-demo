# Destination bootstrap (DD1 / DD2)

This golden scaffold ships the **harness tree only** for the destination
app shape: `.hermes/`, `governance/`, fixtures, `AGENTS.md`,
`.hermes/SOUL.md`. There is **no** hand-maintained destination `pom.xml`
or `src/` skeleton — foundation stories **author** those artefacts.

## How to create the destination Quarkus app

**Do not** run `quarkus create app` / `quarkus-maven-plugin:create` into the
destination (DD1 — Operator E-20260814T065925Z). Generation emits wrappers,
Dockerfiles, and sample resources this scaffold does not want.

Use guidance skill `bootstrap-quarkus-project`:

1. Read `governance/contracts/tooling-pins.md` (Red Hat Quarkus platform row).
2. **Author** destination `pom.xml` from skill `reference-rh-quarkus-pom`
   (BOM import via `dependencyManagement`, Red Hat
   `com.redhat.quarkus.platform:quarkus-maven-plugin` in `<build>`, story
   extension deps empty at mint — DD3). Carry foundation Jacoco/Sonar
   wiring from
   `.hermes/skills/migration/bootstrap-quarkus-project/references/foundation-jacoco-wiring.md`
   (A-3).
3. Lint:

```bash
python3 .hermes/skills/migration/manage-quarkus-extensions/scripts/check-pom-platform-pins.py .
python3 .hermes/skills/migration/manage-quarkus-extensions/scripts/check-pom-jacoco-wiring.py .
python3 .hermes/skills/migration/manage-quarkus-extensions/scripts/assert-extension-tooling.py
```

4. Add extensions **evidence-driven** with `manage-quarkus-extensions`
   (`quarkus ext ls/add/search` when CLI is present — W1 purpose; not create).
   Dev Spaces seats provision the CLI + RH-first `~/.quarkus/config.yaml` in
   `devfile.yaml` postStart (`provision-quarkus-cli.sh`). Pipeline / air-gap:
   typed Maven fallback (W3).

**Do not** require `rsync` (W2). The UDI seat has `tar`; the retired create
path no longer syncs a generated app tree. `derive-legacy-boot3` already
falls back to `tar` when `rsync` is absent.

Platform GAV values: `governance/contracts/tooling-pins.md` only.

Official corroboration: RHBQ chapter *"Creating a Quarkus project by
configuring the pom.xml file"* — hand-authoring is a first-class documented
path, not a workaround (Research E-20260814T074356Z).

## Keep

Do not delete or overwrite: `.hermes/`, `migration/` (legacy alias),
`governance/`, `AGENTS.md`, `.hermes/SOUL.md`, this `BOOTSTRAP.md`,
`devfile.yaml`, GitOps-unrelated provision assets.
