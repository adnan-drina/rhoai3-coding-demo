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
- Spec Kit reads `.specify/memory/constitution.md` (provision copy of
  `.hermes/skills/sdd/init-spec-workspace/assets/constitution.md`). That
  file is the spec-kit half of this identity and of **Delivery gate** —
  zero `[PLACEHOLDER]` / `[PROJECT_NAME]` tokens. Do not dump `pins.json`.
- Pattern cards (on demand): skill `spring-to-quarkus-patterns`.
- Extension add/rm (on demand): skill `manage-quarkus-extensions` (RH BOM policy;
  versions in `.hermes/pins.json` only).

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
| Enforcement scripts | `.hermes/skills/harness/<name>/` (path-invoke only — not `skills[]`) |
| Domain gates G-1..G-4 | skill `check-domain-parity` (router below) |
| Run / phase data | `evidence/` (SR-8 producers; retired `migration/` must not reappear) |
| SDD stack | `.specify/` (workspace provision only — AD-S) |
| Destination POM authoring | skill `bootstrap-quarkus-project` (create-app path retired DD1) |

### Paths

| Path | Role |
|------|------|
| `$HERMES_MANAGED_DIR` | Platform config + secrets — not in this repo |
| `$HERMES_HOME` → `.hermes/home/` | Runtime (sessions/logs gitignored) |
| `.hermes/skills/` | Scaffold golden **guidance** skills on `skills.external_dirs` (R-SK.9) |
| `.hermes/skills/harness/` | Harness enforcement packages (path-invoke; not progressive-disclosure attach). If `skill_view` says Enable `dispatch-phase`, ignore it — open `references/mint-m3-hermes.md`. |
| Seat Kanban assignees | Hermes profile `default` (C-2(a) single-persona). Named analyzer/planner/implementer/validator profiles are retired. Pillar heads stay Cursor. |
| Hermes config | **Not yours to change.** Factory-owned / write-fenced (AD-013). Raise typed `needs_input` — never edit Managed Scope |
| Seat constraint layers | EX-5 overlays: `approvals.deny` (survives `mode: off`), `HERMES_WRITE_SAFE_ROOT` in managed `.env`, `terminal.backend: local`. Do not retire the write-set hook. |
| Phase DAG | Kanban `--parent` / `link` graph (`hermes kanban show --json` parents/children). Not card titles. `evidence/derived/phase-*-task-id.txt` is a Review pointer only. |
| `.hermes/skills/harness/validate-contracts/` | Land-time lint (R-SK.*); naming law in `references/skill-naming-convention.md` |
| `~/.hermes/skills/` | Also on `external_dirs` (spec-kit `Path.home()` install) |
| `.hermes/provision/` | Provision assets (e.g. Spec Kit Non-Goals override) |

Do **not** add `.hermes.md` / `HERMES.md` (shadows this file).
`auth.json` under any Hermes home means Portal onboarding — remove; use Managed Scope.

Worker **provider/auth** is Managed Scope only (**R-HX.5**). Seat pins
(`stale_timeout_seconds`, TTFC, `max_tokens`, compaction / fast-deny) live in
factory Managed Scope + contracts `stream-liveness.md` /
`compaction-headroom-and-fast-deny.md` — do not MiniMax either class.

### Scope-stop and typed blockage (DD5)

When evidence and intent diverge: stop the current scope, emit a typed block /
`needs_input`, and do not invent around the gap (pairs with `SOUL.md`).

**Turn law:** keep reasoning short (≤ 8 lines) and execute one next command.
Long replanning of an underspecified wave is a harness defect — typed
`needs_input`, not a `search_files` loop and not "implement everything on
this card".

**Unconditional (always on — not a skill):**

1. **Never patch `.hermes/skills/harness/**`** (or any gate/lint to make a red check
   green). Enforcement is Lead/Operator territory. A-1: the write fence locks
   that tree read-only for implementers.
2. On any gate refusal you **cannot** resolve **within your `files_writable`**,
   emit a typed block and **stop**. Do not OOS-write, do not edit the refuser.
3. **"Unclassifiable" is a legal outcome** — typed `needs_input` + ESCALATE.

**Routing table (resolver must be named):**

| Class | Resolver | You |
|-------|----------|-----|
| body mint defect | Lead remints/restamps | stop |
| harness path miss | Lead fixes the path | stop |
| story-class false-fail (wrong oracle) | Lead remints the exit | stop |
| no route identifiable | typed `needs_input`, ESCALATE | stop |

Prose in `constraints` is **not** enforcement (F8). If a check has teeth and
you cannot see a resolver, stop — do not change the check.

### Worker containment (A-5)

`hermes kanban block` marks the **card**, not the **process**. A blocked card
can keep writing for hours (v17 S-001). **Seat ops only** (Operator / Lead
from outside the worker). Kanban workers terminate with `kanban_complete` /
`kanban_block`. They must **not** invoke this script on themselves.

```bash
bash .hermes/home/scripts/stop-worker-session.sh [--kind needs_input] <task_id> "<reason>"
```

Contract: `.hermes/platform/known-hermes-behaviours.md`. Never report
containment from board block alone.

### Spec Kit stop rule (AD-S)

After `/speckit-tasks` (optional `/speckit-analyze`) → Kanban mint.
**Never** `/speckit-implement`. Run `specify workflow run speckit` so the
project overlay removes `implement` and inserts `clarify`. Review gates
stay in the graph; unattended abort is scripted (spec-kit generates ·
scripts refuse).

### Task-id correlation (AD-H §7.5)

Every Kanban task, commit prefix, session/log ref, domain-gate result, and
run-report line must carry the **same task id**.

### SDD ordering (AD-S §S.6)

Brief identity carries unchanged; graph order build → security → schema →
API → test infra → feature → surfaces; IMPLEMENT workers must not re-plan.
Authoritative: `.hermes/skills/sdd/check-spec-readiness/references/sdd-ordering.md` (skill `check-spec-readiness`).

### Standing conventions home

`AGENTS.md` (plus Spec Kit constitution sync into this file) is the **sole**
standing-convention surface. Leave `agent.coding_instructions` empty/omitted in
Managed Scope / factory writers — do not recreate a second home.

## Skill routers (procedure lives in the skill)

One line each: what it governs → which skill → authoritative contract/schema.
When a skill is loaded, prefer `"${HERMES_SKILL_DIR}/scripts/…"`.

| Governs | Skill / package | Authoritative |
|---------|-----------------|---------------|
| Task-type preload, one-task-one-type, ack artifacts | `enforce-authority-boundary` *(enforcement)* | `.hermes/skills/harness/enforce-authority-boundary/references/task-authority.md` |
| Citation / no-invention write fence | `ground-in-harvest` *(enforcement)* | write-fence + citation gates |
| Phase matrix, verdict legality, M4/M5 routing | `check-release-readiness` | phase-dispatch + skill (doctrine) |
| G-1..G-4 measurement oracles | `check-domain-parity` | skill `SKILL.md` + gate scripts |
| Specimen-free harness self-lint | `validate-contracts` *(enforcement)* | `scripts/validate.sh` |
| M-phase mint/dispatch (Hermes-native) | `dispatch-phase` *(enforcement)* | `.hermes/phase-dispatch.yaml` |
| Spec/story-body legality + kanban body shape | `check-spec-readiness` | `references/story-scope-and-exit.md` + `body-integrity.md` |
| Story-class exit / oracle derivation (T-8) | `derive-story-oracles` | `story-scope-and-exit.md` + skill references/ |
| Quarkus config / profiles / `config_profile_load` (RS1) | `configure-quarkus-profiles` | skill references/ (sources, oracles) |
| Entity / persistence form (T-7) | `form-entity-persistence` | skill references/ + `persistence.md` cards |
| Spec Kit provision (postStart only) | `init-spec-workspace` | skill `SKILL.md` |
| Entry-point inventory | `inventory-entry-points` | skill `SKILL.md` |
| Provenance / reconstruct | `record-run-evidence` *(enforcement)* | evidence layout + digests |
| Spring→Quarkus pattern cards | `spring-to-quarkus-patterns` | skill `references/` |
| Quarkus extension add/rm + obligations (T-3) | `manage-quarkus-extensions` | skill + `extension-obligations.md` + pins |
| RH Quarkus POM structure (T-1) | `reference-rh-quarkus-pom` | skill `references/pom-structure.md` + pins |
| Destination Quarkus POM authoring | `bootstrap-quarkus-project` | T-1 skill + `.hermes/pins.json` (DD1: no create-app) |
| Hard-stop a Hermes worker session | `stop-worker-session.sh` *(home script)* | `.hermes/platform/known-hermes-behaviours.md` (A-5) |


## Governance doctrine (GRX/GRT)

- **No `governance/` folder** on the tip. Pins: `.hermes/pins.json`. Fixtures:
  per enforcement/skill package. Platform Hermes behaviours:
  `.hermes/platform/known-hermes-behaviours.md`.
- **Scope + exit are one concern** — skill `derive-story-oracles` +
  `check-spec-readiness/references/story-scope-and-exit.md`. Dual-oracle refuse
  stands.
- **Phase / verdict legality** is enforced by `dispatch-phase` /
  `check-release-readiness` — do not restate matrix prose as a contract.
- **Worker containment:** seat ops use `stop-worker-session.sh` (A-5);
  workers do not. Do not rediscover kill procedure from attic contracts.
