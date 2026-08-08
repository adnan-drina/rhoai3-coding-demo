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
- Prefer constructor injection; config via `@ConfigProperty` / `%profile` keys
  (or `QUARKUS_PROFILE`) — do not invent Spring-style `application-*.properties`
  trees on the destination.
- REST resources under `/api/`; JSON via Jackson; health at `/q/health`
  (`/q/*` deliberately sits outside the application root path).
- Pattern cards (on demand): skill `spring-to-quarkus-patterns`.

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

## Hermes (AD-H) — classify, then place

**Kind determines home.** Map: `.hermes/LAYOUT.md`. Do not add top-level
`scripts/` for new procedures (that directory is intentionally empty aside
from a pointer README).

| Kind | Home |
|------|------|
| Standing conventions | this `AGENTS.md` only (`agent.coding_instructions` unused) |
| Identity | `.hermes/SOUL.md` |
| Procedures / tool invocations | `.hermes/skills/<name>/` |
| Domain gates G-1..G-4 | skill `domain-gates` (vocabulary names below) |
| Run / phase data | `migration/` |
| SDD stack | `.specify/` (workspace provision only — AD-S) |

### Paths

| Path | Role |
|------|------|
| `$HERMES_MANAGED_DIR` | Platform config + secrets — not in this repo |
| `$HERMES_HOME` → `.hermes/home/` | Runtime (sessions/logs gitignored) |
| `.hermes/skills/` | Scaffold skills on `skills.external_dirs` |
| `~/.hermes/skills/` | Also on `external_dirs` (spec-kit `Path.home()` install) |
| `.hermes/provision/` | Provision assets (e.g. Spec Kit Non-Goals override) |

Do **not** add `.hermes.md` / `HERMES.md` (shadows this file). Lint:
`bash .hermes/skills/scaffold-invariants/scripts/check-no-hermes-context-override.sh`

`auth.json` under any Hermes home means Portal onboarding — remove; use Managed Scope.

### Domain gate vocabulary

| ID | Name | Skill script |
|----|------|----------------|
| G-1 | characterization | `domain-gates/scripts/g1-characterization.py` |
| G-2 | harvest-fidelity | `domain-gates/scripts/g2-harvest-fidelity.py` |
| G-3 | findings-delta | `domain-gates/scripts/g3-findings-delta.py` |
| G-4 | runtime-parity | `domain-gates/scripts/g4-runtime-parity.py` |

### Common invocations

```bash
# Specimen-free suite
bash .hermes/skills/harness-validate/scripts/validate.sh

# SDD readiness (pattern-steals + AD-S §S.6)
bash .hermes/skills/sdd-readiness/scripts/check-readiness.sh

# Entry-point inventory (W2 §11.3)
python3 .hermes/skills/inventory-entry-points/scripts/inventory-entry-points.py \
  /projects/.derived/legacy-at-3 -o migration/entry-point-inventory.json

# MTA analyze (skill mta-analysis)
bash .hermes/skills/mta-analysis/scripts/mta-analyze-legacy.sh

# Spec Kit provision (AD-S) — postStart / once
bash .hermes/skills/specify-workspace-init/scripts/init-workspace.sh /projects/modernized
```

When a skill is loaded, prefer `"${HERMES_SKILL_DIR}/scripts/…"`.

### Spec Kit stop rule (AD-S)

After `/speckit.tasks` (optional `/speckit.analyze`) → `kanban_create()`.
**Never** `/speckit.implement`.

### Task-id correlation (AD-H §7.5)

Every Kanban task, commit prefix, session/log ref, domain-gate result, and
run-report line must carry the **same task id**.

### SDD ordering (AD-S §S.6)

Brief identity carries unchanged; graph order build → security → schema →
API → test infra → feature → surfaces; IMPLEMENT workers must not re-plan.
See `migration/contracts/sdd-ordering.md`.

### Role authority (AD-H §16)

Hermes orchestrates tightly bounded roles (evidence analyst, planner, spec
author, implementer, reviewer, validator). One Kanban task ⇒ one role; phase
`skills[]` is declared preload (not Hermes RBAC) in
`.hermes/phase-dispatch.yaml`. Human checkpoints are ack artifacts under
`migration/acks/` — not mid-run approval prompts.

```bash
bash .hermes/skills/role-authority/scripts/check-acks.sh M2
python3 .hermes/skills/role-authority/scripts/check-role-writes.py .
```

See `migration/contracts/role-authority.md` and `migration/schemas/ack.md`.

### Grounded generation (AD-H §17)

Implementers consult, in order: task packet → approved brief/spec → legacy RO
→ destination reference/`AGENTS.md` → approved Quarkus docs (BOM-matched
version + scaffold skills/`RULES.md` only — how only).
Non-trivial changes cite task id, brief/story id, and legacy locus. Invention
outside evidence is a `blocked` outcome, not improvisation.

```bash
python3 .hermes/skills/grounded-generation/scripts/check-citation.py .
python3 .hermes/skills/grounded-generation/scripts/check-citation.py . --commit-msg MSGFILE
```

See `migration/contracts/grounded-generation.md`.

### Validation and release (AD-H §18)

M3: compile + task-scoped tests. M4: full verify, Sonar, boot, G-1 (G-2 if
harvest). M5: MTA re-scan → G-3, G-4 parity, preflight + deploy smoke. Factory
must not contradict M5 ACCEPT. REFUSE → fix/retry; INCONCLUSIVE → human queue;
rollback = last bad task tip only; wave block stops new stories.

```bash
python3 .hermes/skills/validation-release-gates/scripts/check-phase-matrix.py .
python3 .hermes/skills/validation-release-gates/scripts/check-phase-matrix.py . --print M4
python3 .hermes/skills/validation-release-gates/scripts/check-verdict-routing.py .
```

See `migration/contracts/validation-release-gates.md`.

### Standing conventions home

`AGENTS.md` (plus Spec Kit constitution sync into this file) is the **sole**
standing-convention surface. Leave `agent.coding_instructions` empty/omitted in
Managed Scope / factory writers — do not recreate a second home.

### Kanban body (W2 §6.1)

Typed `body` only — digest refs, not inlined blobs. See
`migration/schemas/kanban-body.md`.

```bash
python3 .hermes/skills/sdd-readiness/scripts/check-kanban-body.py .
```

### Auditability and repeatability (AD-H §19)

Task id joins Kanban, git subject, sessions/logs, gates, and run report.
Non-trivial IMPLEMENT must leave Kanban completion metadata with
`worker_session_id`, `soul_sha`, `skill_tips`, `model_id` (or `unknown`), plus
§17 citations. Kanban metadata is authoritative; do not dual-write full
provenance into commit trailers. Early bad-agent signal = unsupported claims
(§17).

```bash
python3 .hermes/skills/auditability-repeatability/scripts/check-provenance.py .
```

See `migration/contracts/auditability-repeatability.md`.
