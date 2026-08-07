# Agent Guide

This is a corporate Quarkus **migration** scaffold. The workspace holds two
projects: you migrate the legacy application in `/projects/legacy` into this
repository (`/projects/modernized`).

## Workspace rules

- `/projects/legacy` — the application being migrated (**legacy@2.x**
  provenance). **READ-ONLY**: never modify, commit, or push it. It is not
  registered anywhere and has no write credentials.
- `/projects/.derived/legacy-at-3` — **legacy@3.x**, a pure derivation of the
  RO mount (W2 §3 amendment). Produced once, hashed, and frozen. Never edit.
- `/projects/modernized` — this repository. All new code, tests, and commits
  happen here, and only here.

### Boot 2→3 derivation (before M1)

The Quarkus migration analyzes and harvests against **legacy@3.x**, not the
2.x mount. Run once before M1:

```bash
bash scripts/derive-legacy-boot3.sh
```

- If `spring-boot.version >= 3` already: mode=`identity` — harvest referent is
  `/projects/legacy`.
- Otherwise: copy → Boot 2→3 upgrade → freeze under
  `/projects/.derived/legacy-at-3`; manifest at
  `migration/derived/legacy-at-3.json`.
- **Harvest faithfulness** compares the destination to
  `harvest_referent` from that manifest (**legacy@3.x**). Comparing to 2.x
  alone is wrong — Boot-3 API changes would look like infidelity.
- Override the upgrade command with `DERIVE_UPGRADE_CMD` when needed.

### Harness MTA analysis (AD-003 amendment A)

```bash
bash scripts/check-legacy-at-3-manifest.sh
bash scripts/mta-analyze-legacy.sh
```

Uses `migration.yaml` `analysis.targets` as repeated `--target` flags.
**Never pass `--source`** (excludes source-labelless rules — Track B
2026-07-27). Input is `harvest_referent` (legacy@3.x), not the RO 2.x mount.
Requires Java 21 and `JVM_MAX_MEM`.

## Project identity

- Quarkus application on the Red Hat build (`com.redhat.quarkus.platform` BOM
  **3.27.3.SP1**), Java 21, Maven (no wrapper — use `mvn`).
- Package root: `com.demo`.
- **Native Quarkus only** — never add `quarkus-spring-*` compatibility
  extensions to the destination (MTA may suggest them; reject).
- Default CDI scope for services and repositories: `@ApplicationScoped`.
- REST resources under `/api/`; JSON via Jackson; health at `/q/health`
  (`/q/*` deliberately sits outside the application root path).

## Build and test

The container's default Java is 17; this project targets 21. Set once per
shell:

```bash
export JAVA_HOME="${JAVA_HOME_21}" && export PATH="${JAVA_HOME}/bin:${PATH}"

mvn quarkus:dev          # dev mode with hot reload
mvn -q clean test        # always clean — incremental builds pass on stale classes
mvn -q clean verify      # full build, mirrors the pipeline
```

## Delivery gate

Every push to `main` runs this project's pipeline: Maven build → SonarQube
quality gate → image build → deploy. The bars are exact: **zero new
violations**, **≥ 80% new-code line coverage** (tests ship with the code),
**≤ 3% duplicated new lines**. Never weaken tests or suppress rules to pass.

The repository must **build self-contained**: the pipeline resolves from
Maven Central and in-repo sources only — it cannot see your workspace. Your
local green is not the factory's green until the build passes without
workspace state.

## Hermes project-context invariant (AD-001 / AD-002)

Do **not** add `.hermes.md` or `HERMES.md` anywhere in this repository.
Hermes loads project context first-match-wins (`.hermes.md` → `AGENTS.md` →
…); either file would silently stop this `AGENTS.md` from loading. Enforce
with:

```bash
bash scripts/check-no-hermes-context-override.sh
```
