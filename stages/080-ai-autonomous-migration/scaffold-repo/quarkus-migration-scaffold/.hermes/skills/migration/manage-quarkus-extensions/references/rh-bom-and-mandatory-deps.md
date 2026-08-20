# Red Hat BOM + mandatory extension wiring

**Shared reference** for `manage-quarkus-extensions` and (at v14 mint)
`bootstrap-quarkus-project`. Policy only — **version values** live in
`.hermes/pins.json` and destination `pom.xml`.

## Platform policy

- Use **Red Hat build of Quarkus** only:
  `quarkus.platform.group-id=com.redhat.quarkus.platform`
  `quarkus.platform.artifact-id=quarkus-bom`
- Platform version: read `.hermes/pins.json` row **Red Hat Quarkus platform** —
  do not copy a version string into skills or cards.
- Extensions **inherit** the BOM version. Never add independent
  `<version>` on `io.quarkus:*` / platform-managed artifacts.
- Refuse rewrite to `io.quarkus.platform` (community) on create or `ext add`/`rm`.
- Refuse `quarkus-spring-*` compatibility extensions (native Quarkus only).

## CLI vs Maven (both first-class)

| Surface | When |
|---------|------|
| Quarkus CLI (`ext ls` / `list` / `add` / `rm`) | CLI on PATH **and** RH registry first + Red Hat GA Maven reachable |
| `quarkus-maven-plugin` goals | CLI absent, air-gap, or CLI prereq failure |

Factory/UDI must ship RH registry + GA repos before treating CLI as default.
Do **not** `sdk install quarkus` mid-chain on a live proving seat unless
Operator/Lead explicitly authorizes a probe.

## Remove-unused BAR (binding)

Compile-clean alone is **insufficient**. Before `ext rm` / Maven remove:

1. `quarkus ext ls` (or Maven list) shows the extension installed.
2. No M1 / story / brief / packet claim of **build-time wiring** for that
   extension (CDI producers, `@QuarkusTest` resource, Flyway, security
   identity, REST endpoint registration, Jacoco agent, …).
3. **Runtime smoke** covering that extension's responsibility still passes
   after a candidate remove (health and/or the relevant `/api/*` path) —
   or the remove is abandoned.

If any step is uncertain → **do not remove**.

## Gotcha — Jacoco dual report paths (worked example)

Mandatory Jacoco wiring is **not** "add `quarkus-jacoco`":

1. Dependency: `quarkus-jacoco` (BOM-managed).
2. Sonar property naming **both** report paths (QuarkusTest report **and**
   plain Surefire Jacoco report):
   `sonar.coverage.jacoco.xmlReportPaths` lists both
   `target/jacoco-report/jacoco.xml` and `target/site/jacoco/jacoco.xml`.
3. Surefire forwards `<argLine>${argLine}</argLine>` (or `@{argLine}`) so the
   coverage agent attaches.

Fragments + gate: `bootstrap-quarkus-project/references/foundation-jacoco-wiring.md`
and `scripts/check-pom-jacoco-wiring.py` (A-3 / H-3). Adding the dependency
without both paths / argLine produces a clean compile and a silent coverage
hole — the exact false-green class this reference exists to prevent.

## Related gates (do not weaken)

- `check-pom-platform-pins.py` / `check-pom-jacoco-wiring.py` (when pom exists)
- `assert-extension-tooling.py` (W3 — CLI+RH-first or typed Maven fallback)
- `check-runnable-db-config.py` / `runnable-db-security.md` (JDBC + one working schema mechanism)
- `check-semantics-manifest.py` (B8) for gate claim adequacy
