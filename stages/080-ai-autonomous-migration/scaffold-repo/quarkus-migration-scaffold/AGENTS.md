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

## Hermes project-context invariant (AD-H / AD-001 / AD-002)

Do **not** add `.hermes.md` or `HERMES.md` anywhere in this repository.
Hermes loads project context first-match-wins (`.hermes.md` → `AGENTS.md` →
…); either file would silently stop this `AGENTS.md` from loading. Enforce
with:

```bash
bash scripts/check-no-hermes-context-override.sh
```

### Hermes paths (AD-H)

| Path | Role |
|------|------|
| `$HERMES_MANAGED_DIR` (`/etc/hermes` or `/projects/.platform/hermes`) | Platform config + secrets (`.env`) — not in this repo |
| `$HERMES_HOME` → `.hermes/home/` | Runtime tree (sessions/logs gitignored; agent-created skills versioned) |
| `.hermes/skills/` | Scaffold procedures via `skills.external_dirs` (no symlink loop) |
| `~/.hermes/skills/` | Also on `external_dirs` — spec-kit installs here (`Path.home()`, ignores `$HERMES_HOME`) |
| `.hermes/SOUL.md` | Identity source; provisioning places a copy at `$HERMES_HOME/SOUL.md` |

`auth.json` must **not** exist anywhere under Hermes homes — its presence
means Portal onboarding was used instead of Managed Scope.

### Task-id correlation (AD-H §7.5)

Every Kanban task, commit-message prefix, Hermes session/log reference,
domain-gate result, and run-report line must carry the **same task id**.
This is a phase-schema requirement (not a logging feature): a reviewer who
starts on any surface must reach the others for that task.
