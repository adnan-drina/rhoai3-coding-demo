# Agent Guide

This is a corporate Quarkus **migration** scaffold. The workspace holds two
projects: you migrate the legacy application in `/projects/legacy` into this
repository (`/projects/modernized`).

## Workspace rules

- `/projects/legacy` — the application being migrated (**legacy@2.x**
  provenance). **READ-ONLY**: never modify, commit, or push it. It is not
  registered anywhere and has no write credentials.
- `/projects/modernized/.derived/legacy-at-3` — **legacy@3.x**, a
  pure derivation of the RO mount (inside the dest tree so the fence can
  inspect it). Produced once, hashed, and frozen. Never edit. Do not add
  `/projects/.derived` to `K2_ALLOW_ROOT`.
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

## Hermes — classify, then place

**Kind determines home.** Map: `.hermes/LAYOUT.md`. Do not add top-level
`scripts/` or `.hermes/home/scripts/` for new procedures.

| Kind | Home |
|------|------|
| Standing conventions | this `AGENTS.md` only |
| Identity | authored `.hermes/SOUL.md` → loaded `$HERMES_HOME/SOUL.md` |
| Guidance procedures | `.hermes/skills/<category>/<name>/` (card-attachable) |
| Domain gates G-1..G-4 | skill `check-domain-parity` |
| M4/M5 verdict routing | skill `check-release-readiness` |
| M4 pinned-gate evidence | skill `assert-pinned-gates-ran` |
| M4 retrievable `src/` + `pom.xml` | skill `assert-retrievable-tree` |
| Fence-evasion detector (observation, not a boundary) | skill `assert-no-fence-evasion` |
| Run / phase data | `evidence/` |
| SDD stack | `.specify/` (workspace provision only — never commit in golden) |
| Destination POM authoring | skill `author-destination-pom` |
| Seat config template | `.hermes/config/config.yaml.template` (no secrets) |
| Dest worker profiles | `.hermes/config/profiles/{orchestrator,implementer}.yaml.template` |

### Paths

| Path | Role |
|------|------|
| `$HERMES_MANAGED_DIR` | Platform config + secrets — not in this repo |
| `$HERMES_HOME` | Runtime (sessions/logs gitignored). Relocated dest-time. |
| `.hermes/skills/` | Scaffold golden **guidance** skills on `skills.external_dirs` |
| Seat Kanban assignees | M2 PLAN / M3 / M4 VERDICT → `implementer`; mint-verifier → `orchestrator`. Official `--assignee` (hermes-kanban). Not `default`. OBJECT EX-4 `analyzer`/`planner`/`validator`. dest orchestrator disables `file`/`terminal`/`code_execution`/`skills` — it cannot run M2 PLAN or M4. |
| Hermes live config | **Not yours to change.** Factory-owned Managed Scope. Raise typed `needs_input` |
| Phase DAG | Kanban `--parent` / `link` graph (`hermes kanban show --json`) |
| `~/.hermes/skills/` | dest-user `/home/user/.hermes/skills` on `external_dirs` (dest-init literal; spec-kit install). Not worker `Path.home()`. |

Do **not** add `.hermes.md` / `HERMES.md` (shadows this file).
`auth.json` under any Hermes home means Portal onboarding — remove; use Managed Scope.

Worker **provider/auth** is Managed Scope only. Seat pins live in factory
Managed Scope — do not MiniMax either class. Do not add `fallback_providers`.

### Scope-stop

When evidence and intent diverge: stop the current scope, emit a typed block /
`needs_input`, and do not invent around the gap (pairs with `SOUL.md`).

On any gate refusal you **cannot** resolve within your `files_writable`,
emit a typed block and **stop**. Do not OOS-write, do not edit the refuser.
**Unclassifiable** is a legal outcome — typed `needs_input` + ESCALATE.

### Native worker protocol (hermes-kanban)

Workers never own lifecycle truth. End every turn with exactly one terminator:
`kanban_complete`, `kanban_request_review`, or `kanban_block`. A clean exit
without one is `protocol_violation`. Mint complete requires `created_cards`
(empty list forbidden). Serialize `kanban_create`. M2 PLAN and M4 VERDICT
use `--assignee implementer`; mint-verifier uses `--assignee orchestrator`;
M3 uses `--assignee implementer`. Do not seat M2 or M4 on orchestrator
(dest `orchestrator.yaml.template` disables `file`/`terminal`/`skills`).
M4 `--body` is acceptance and oracles only (dest-4 `t_9acd47cb`). Do not
name `Token:` / `verdict:` `PROVISIONAL_ACCEPT`/`ACCEPT` or `ship:`.
`assert-m4-card-body.py` refuses a body that pre-specifies the verdict.
Story `kanban_create` passes `--max-retries 1` (null inherits `failure_limit` 2
and masks a Gate K first failure). Mint those cards through
`.hermes/kernel/k4_mint.py` from K4 payloads (CLI `hermes kanban create`).
M3 argv also passes `--workspace dir:/projects/modernized`, `--skill` per
story, `--max-runtime 2h`, and `--idempotency-key`. After `--exec`,
`kanban_complete` `created_cards` is the native `t_*` list (empty after a
mint is OBJECT). Scratch workspace on a story is REFUSE.
M1 KEEP evidence also `python3 .hermes/kernel/kanban_attach.py --task "$HERMES_KANBAN_TASK"`
(PVC paths stay; 25 MB/file). Do not `kanban decompose`. Do not `kanban swarm`
for serial T0. Do not run `hermes kanban daemon --force`.

`hermes kanban block` marks the **card**, not the **process**. Seat ops
contain workers from outside the worker.

### Spec Kit stop rule

After `/speckit-tasks` (optional `/speckit-analyze`) → `.hermes/kernel/k4_convert.py`
then `.hermes/kernel/k4_mint.py`, not by grepping `tasks.md` paths. **Never**
`/speckit-implement`. Run `specify workflow run speckit` so the project overlay
removes `implement` and inserts `clarify`.

### Task-id correlation

Every Kanban task, commit prefix, session/log ref, domain-gate result, and
run-report line must carry the **same task id**.

### SDD ordering

Brief identity carries unchanged; graph order build → security → schema →
API → test infra → feature → surfaces; IMPLEMENT workers must not re-plan.
Authoritative: `.hermes/skills/sdd/check-spec-readiness/references/sdd-ordering.md`.

### Standing conventions home

`AGENTS.md` (plus Spec Kit constitution sync) is the **sole**
standing-convention surface. Leave `agent.coding_instructions` empty.

## Skill routers

One line each: what it governs → which skill. When a skill is loaded, prefer
`"${HERMES_SKILL_DIR}/scripts/…"`.

| Governs | Skill |
|---------|-------|
| Spec/story-body legality + 1:N partition coverage | `check-spec-readiness` |
| Story-class exit / oracle derivation | `derive-story-oracles` |
| G-1..G-4 measurement oracles | `check-domain-parity` |
| M4/M5 verdict routing | `check-release-readiness` |
| M4 pinned-gate evidence (silence fails) | `assert-pinned-gates-ran` |
| M4 retrievable `src/` + `pom.xml` | `assert-retrievable-tree` |
| Fence-evasion detector (not containment evidence) | `assert-no-fence-evasion` |
| Quarkus config / profiles | `configure-quarkus-profiles` |
| Entity / persistence form | `form-entity-persistence` |
| Spec Kit provision (postStart only) | `init-spec-workspace` |
| Entry-point + type inventory | `inventory-legacy-surface` |
| MTA analyze + findings handoff | `scan-with-mta` |
| Spring→Quarkus pattern cards | `spring-to-quarkus-patterns` |
| Quarkus extension add/rm | `manage-quarkus-extensions` |
| RH Quarkus POM structure | `reference-rh-quarkus-pom` |
| Destination Quarkus POM authoring | `author-destination-pom` |

## Governance

- **No `governance/` folder** on the tip. Pins: `.hermes/pins.json`.
- **Scope + exit are one concern** — `derive-story-oracles` +
  `check-spec-readiness/references/story-scope-and-exit.md`.
- **Phase / verdict legality** is `check-release-readiness` plus native Kanban
  state — not a second dispatcher YAML.
- **1:N dest_file split** is legal coverage (supersede + successor set). HTTP
  routes stay 1:1.
