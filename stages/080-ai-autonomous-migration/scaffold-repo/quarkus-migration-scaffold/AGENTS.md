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
- Extension add/rm (on demand): skill `manage-quarkus-extensions` (RH BOM policy;
  versions in `governance/contracts/tooling-pins.md` only).

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
| Identity | authored `.hermes/SOUL.md` → loaded `$HERMES_HOME/SOUL.md` (factory places + sha256-verifies) |
| Guidance procedures | `.hermes/skills/<category>/<name>/` (card-attachable) |
| Enforcement scripts | `.hermes/enforcement/<name>/` (path-invoke only — not `skills[]`) |
| Domain gates G-1..G-4 | skill `check-domain-parity` (router below) |
| Run / phase data | `migration/` |
| SDD stack | `.specify/` (workspace provision only — AD-S) |
| Destination app create | skill `bootstrap-quarkus-project` (see root `BOOTSTRAP.md`) |

### Paths

| Path | Role |
|------|------|
| `$HERMES_MANAGED_DIR` | Platform config + secrets — not in this repo |
| `$HERMES_HOME` → `.hermes/home/` | Runtime (sessions/logs gitignored) |
| `.hermes/skills/` | Scaffold golden **guidance** skills on `skills.external_dirs` (R-SK.9) |
| `.hermes/enforcement/` | Harness enforcement packages (path-invoke; not progressive-disclosure attach) |
| Hermes config | **Not yours to change.** Factory-owned / write-fenced (AD-013). Raise typed `needs_input` — never edit Managed Scope |
| `.hermes/enforcement/validate-contracts/` | Land-time lint (R-SK.*); naming law in `references/skill-naming-convention.md` |
| `~/.hermes/skills/` | Also on `external_dirs` (spec-kit `Path.home()` install) |
| `.hermes/provision/` | Provision assets (e.g. Spec Kit Non-Goals override) |

Do **not** add `.hermes.md` / `HERMES.md` (shadows this file).
`auth.json` under any Hermes home means Portal onboarding — remove; use Managed Scope.

Worker **provider/auth** is Managed Scope only (**R-HX.5**). Seat pins
(`stale_timeout_seconds`, TTFC, `max_tokens`, compaction / fast-deny) live in
factory Managed Scope + contracts `stream-liveness.md` /
`compaction-headroom-and-fast-deny.md` — do not MiniMax either class.

### Scope-stop and typed blockage

When evidence and intent diverge: stop the current scope, emit a typed block /
`needs_input`, and do not invent around the gap (pairs with `SOUL.md`).

### Spec Kit stop rule (AD-S)

After `/speckit-tasks` (optional `/speckit-analyze`) → `kanban_create()`.
**Never** `/speckit-implement`.

### Task-id correlation (AD-H §7.5)

Every Kanban task, commit prefix, session/log ref, domain-gate result, and
run-report line must carry the **same task id**.

### SDD ordering (AD-S §S.6)

Brief identity carries unchanged; graph order build → security → schema →
API → test infra → feature → surfaces; IMPLEMENT workers must not re-plan.
Authoritative: `governance/contracts/sdd-ordering.md` (skill `check-spec-readiness`).

### Standing conventions home

`AGENTS.md` (plus Spec Kit constitution sync into this file) is the **sole**
standing-convention surface. Leave `agent.coding_instructions` empty/omitted in
Managed Scope / factory writers — do not recreate a second home.

## Skill routers (procedure lives in the skill)

One line each: what it governs → which skill → authoritative contract/schema.
When a skill is loaded, prefer `"${HERMES_SKILL_DIR}/scripts/…"`.

| Governs | Skill / package | Authoritative |
|---------|-----------------|---------------|
| Task-type preload, one-task-one-type, ack artifacts | `enforce-authority-boundary` *(enforcement)* | `governance/contracts/task-authority.md` |
| Citation / no-invention write fence | `ground-in-harvest` *(enforcement)* | `governance/contracts/grounded-generation.md` |
| Phase matrix, verdict legality, M4/M5 routing | `check-release-readiness` | `governance/contracts/validation-release-gates.md` |
| G-1..G-4 measurement oracles | `check-domain-parity` | skill `SKILL.md` + gate scripts |
| Specimen-free harness self-lint | `validate-contracts` *(enforcement)* | `scripts/validate.sh` |
| M-phase mint/dispatch (Hermes-native) | `dispatch-phase` *(enforcement)* | `.hermes/phase-dispatch.yaml` |
| Spec/story-body legality + kanban body shape | `check-spec-readiness` | `governance/contracts/*` + `governance/schemas/kanban-body.md` |
| Spec Kit provision (postStart only) | `init-spec-workspace` | skill `SKILL.md` |
| Entry-point inventory | `inventory-entry-points` | skill `SKILL.md` |
| Provenance / reconstruct | `record-run-evidence` *(enforcement)* | `governance/contracts/auditability-repeatability.md` |
| Spring→Quarkus pattern cards | `spring-to-quarkus-patterns` | skill `references/` |
| Quarkus extension add/rm | `manage-quarkus-extensions` | skill + `tooling-pins.md` |
| Destination Quarkus project create | `bootstrap-quarkus-project` | root `BOOTSTRAP.md` + `tooling-pins.md` |
