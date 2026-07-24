# Agent Guide

This is a corporate Quarkus **migration** scaffold. You (the coding agent)
migrate the legacy application in `/projects/legacy` into this repository
(`/projects/modernized`), following the standards in `.opencode/skills/`.
The standards steer the work — do not ask the user to restate them in
prompts.

## Workspace layout — two projects, two rules

- `/projects/legacy` — the application being migrated. **READ-ONLY**: read
  it for behavior, structure, and business rules; never modify, commit, or
  push it. It is not registered anywhere and has no write credentials.
- `/projects/modernized` — this repository. All new code, specs, tests, and
  commits happen here, and only here. Its provenance record is
  `migration.yaml` (source repository of the migration).

## Project identity (modernized)

- Quarkus 3.27 application (Red Hat build, `com.redhat.quarkus.platform` BOM),
  Java 21, Maven (no wrapper — use `mvn`).
- Package root: `com.demo`.
- REST resources under `/api/`; JSON via Jackson.
- Health endpoints come from `quarkus-smallrye-health` (`/q/health`).

## Migration workflow

Migration work is analysis-grounded and spec-driven. Before running any
`/speckit.*` command, consult the `spec-driven-workflow` and
`legacy-migration-workflow` skills.

1. **Analysis first**: the MTA analysis of `/projects/legacy` is the
   migration's ground truth — its findings are the checklist the migrated
   result must satisfy. Do not start writing code from a raw read of the
   legacy tree.
2. Specs in `specs/` capture the legacy service's observed behavior and API
   contract; plans map MTA findings to Quarkus-native equivalents.
3. Consult every skill in `.opencode/skills/` before **every** workflow
   phase — planning and task breakdown included. The constitution
   (`.specify/memory/constitution.md`) binds all `/speckit` phases.
4. Implement in small, verifiable increments; prefer deterministic
   OpenRewrite recipes for mechanical transforms and inference for
   judgment calls. Run `mvn -q test` after each increment.
5. Migration is done when the MTA findings are resolved and the tests
   pass — not when the code "looks migrated".

## Build and test commands

The container's default Java is 17 but this project targets 21. The base
image provides `JAVA_HOME_21` (the documented way to select a JDK) — set
it once per shell before any Maven command:

```bash
export JAVA_HOME="${JAVA_HOME_21}" && export PATH="${JAVA_HOME}/bin:${PATH}"

mvn quarkus:dev          # dev mode with hot reload (run in /projects/modernized)
mvn -q test              # unit + component tests
mvn -q package           # full build (what the platform pipeline runs)
```

## Platform integration

- LLM access is only through the MaaS gateway. The workspace injects
  `MAAS_API_BASE_URL`, `MAAS_API_KEY`, and `MAAS_MODEL_NAME`; the
  `llm-integration` skill defines the required wiring and error handling.
- Every push to `main` runs this project's own pipeline: Maven build →
  SonarQube quality gate (fails on any new issue) → image build. Write code
  that passes the gate; never weaken tests to get past it.
- The legacy project never enters the pipeline or the catalog — the only
  path out of this workspace is a gated push of `/projects/modernized`.
