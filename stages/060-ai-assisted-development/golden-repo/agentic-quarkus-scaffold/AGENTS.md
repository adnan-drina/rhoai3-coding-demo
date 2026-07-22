# Agent Guide

This is a corporate Quarkus application scaffold. You (the coding agent)
build the application described by a spec in `specs/`, following the
standards in `.opencode/skills/`. The standards steer the work — do not ask
the user to restate them in prompts.

## Project identity

- Quarkus 3.27 application (Red Hat build, `com.redhat.quarkus.platform` BOM),
  Java 21, Maven (no wrapper — use `mvn`).
- Package root: `com.demo`.
- REST resources under `/api/`; JSON via Jackson.
- Health endpoints come from `quarkus-smallrye-health` (`/q/health`).

## Workflow

Feature work follows spec-driven development. Before running any
`/speckit.*` command, consult the `spec-driven-workflow` skill for the
command order and the artifacts each phase must produce.

1. Read the active spec in `specs/` (the user names it; otherwise the most
   recent non-TEMPLATE file).
2. Consult every skill in `.opencode/skills/` before **every** workflow
   phase — planning and task breakdown included, not just coding. Plans
   and data models that contradict a skill are defects. The constitution
   (`.specify/memory/constitution.md`) binds all `/speckit` phases.
3. Implement in small, verifiable increments. Run `mvn -q test` after each.
4. Update the README API table in the same change as any endpoint change —
   the definition of done lives in the skills.

## Build and test commands

The container's default Java is 17 but this project targets 21. The base
image provides `JAVA_HOME_21` (the documented way to select a JDK) — set
it once per shell before any Maven command:

```bash
export JAVA_HOME="${JAVA_HOME_21}" && export PATH="${JAVA_HOME}/bin:${PATH}"

mvn quarkus:dev          # dev mode with hot reload
mvn -q test              # unit + component tests
mvn -q package           # full build (what the platform pipeline runs)
```

## Platform integration

- LLM access is only through the MaaS gateway. The workspace injects
  `MAAS_API_BASE_URL`, `MAAS_API_KEY`, and `MAAS_MODEL_NAME`; the
  `llm-integration` skill defines the required wiring and error handling.
- Every push to `main` runs the shared platform pipeline: Maven build →
  SonarQube quality gate (fails on any new issue) → image build. Write code
  that passes the gate; never weaken tests to get past it.
