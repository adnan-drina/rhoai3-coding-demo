# Agent Guide

This is a corporate Quarkus **migration** scaffold. You (the coding agent)
migrate the legacy application in `/projects/legacy` into this repository
(`/projects/modernized`), following the standards in `.opencode/skills/`.
The standards steer the work — do not ask the user to restate them in
prompts.

## Skills index — what to consult when

| Skill (`.opencode/skills/`) | Consult when |
|---|---|
| `legacy-migration-workflow` | Any migration work — the overall analysis-grounded workflow |
| `spec-driven-workflow` | Before any `/speckit.*` command or reading spec artifacts |
| `quarkus-rest-conventions` | Creating or changing any REST endpoint |
| `quarkus-persistence-conventions` | Any entity, Flyway migration, or datasource change |
| `project-test-standards` | Every change — tests ship with code; coverage rules live here |
| `llm-integration` | Only if a task adds LLM features to the app |

The orchestrator's runbook is `.hermes/skills/migration-harness/` (its own
phase files); worker task packets arrive already aligned with it.

## Tool discipline (worker runs)

- **NEVER use the `task` (subagent) tool.** Explore and implement
  directly. Forensics across runs: every session that spawned a subagent
  died immediately after (parent emits empty text and exits with no
  changes); every session that worked directly succeeded.
- Dot-directories are invisible to `glob` — find skills and configs with
  `ls`/`read` at their exact paths (see the skills index above).
- Quote every file path in shell commands; a broken glob writes literal
  `*.java` files that poison the quality gate.

## Workspace layout — two projects, two rules

- `/projects/legacy` — the application being migrated. **READ-ONLY**: read
  it for behavior, structure, and business rules; never modify, commit, or
  push it. It is not registered anywhere and has no write credentials.
- `/projects/modernized` — this repository. All new code, specs, tests, and
  commits happen here, and only here. Its provenance record is
  `migration.yaml` (source repository of the migration).

## Harness roles (autonomous runs)

When the migration runs under the Hermes harness
(`.hermes/skills/migration-harness/`), the division of labor is fixed:

- **Hermes** orchestrates: plan, task queue, sensors, budgets. It writes
  only `specs/`, `migration/`, and the scratch dir `/tmp/rewrite-staging`
  — never application source in this repository.
- **OpenCode** (you, in worker runs) implements exactly the task packet it
  was handed — nothing more. You never declare the migration complete;
  the findings baseline in `migration/mta-findings.json` and the sensors
  decide.
- **OpenRewrite** performs mechanical transforms on the scratch copy;
  harvesting transformed files into this repository arrives as an
  explicit OpenCode task with source and destination paths.
- `/tmp/rewrite-staging` is ephemeral working space and is never
  committed to any repository.
- Merge authority is the factory pipeline (build + SonarQube gate), not
  any agent's summary.

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
   judgment calls. Run `mvn -q clean test` after each increment (`clean`
   is non-negotiable — incremental builds pass on stale classes the
   factory will catch); escalate to `mvn -q clean verify` whenever
   `pom.xml` or runtime configuration changed.
5. Migration is done when the MTA findings are resolved and the tests
   pass — not when the code "looks migrated".

## Build and test commands

The container's default Java is 17 but this project targets 21. The base
image provides `JAVA_HOME_21` (the documented way to select a JDK) — set
it once per shell before any Maven command:

```bash
export JAVA_HOME="${JAVA_HOME_21}" && export PATH="${JAVA_HOME}/bin:${PATH}"

mvn quarkus:dev          # dev mode with hot reload (run in /projects/modernized)
mvn -q clean test        # unit + component tests (always clean)
mvn -q clean verify      # full build incl. packaging — mirrors the pipeline
```

## Platform integration

- If (and only if) a task adds LLM features to the migrated app: LLM
  access is only through the MaaS gateway — the workspace injects
  `MAAS_API_BASE_URL`, `MAAS_API_KEY`, and `MAAS_MODEL_NAME`, and the
  `llm-integration` skill defines the wiring. The migration itself does
  not require this.
- Every push to `main` runs this project's own pipeline: Maven build →
  SonarQube quality gate → image build → deploy with a rollout gate. The
  gate bars are exact — write code that meets them the first time:
  **zero new violations** (constructor injection over field injection,
  comments INSIDE intentionally-empty method bodies, no unused imports,
  dedicated exceptions), **≥ 80% new-code line coverage** (tests ship in
  the same change as the code), **≤ 3% duplicated new lines** (consolidate
  near-identical classes — records, static factories — never copy
  through). Never weaken tests or suppress rules to get past the gate.
- **The repository must build self-contained.** The pipeline resolves
  dependencies from Maven Central and in-repo sources only — it cannot
  see your workspace. Never depend on locally-installed artifacts
  (`mvn install` output); vendor required legacy jars in-repo with a
  file-based repository declaration, or replace them. Your local green
  is not the factory's green until the build passes without workspace
  state.
- The legacy project never enters the pipeline or the catalog — the only
  path out of this workspace is a gated push of `/projects/modernized`.

## Task packets — ambiguity stop

Task packets you receive must carry the decided target design (file
mappings, signatures, annotations). If a packet asks you to make an
architecture decision — "modernize X", "integrate Y" without the target
shape — do NOT attempt it. Stop immediately and reply with exactly what
decision is missing (one short list), so the orchestrator can re-packet.
A fast, specific refusal is a success; a long exploratory attempt at
someone else's design decision is a failure.
