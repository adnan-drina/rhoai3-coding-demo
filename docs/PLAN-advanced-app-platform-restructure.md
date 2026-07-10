# Plan: Advanced App Platform Restructure

Status: APPROVED — decisions taken 2026-07-10.
Supersedes: `docs/PLAN-developer-arc-restructure.md` (phase 1 of that plan was
executed 2026-07-06; this plan reorganizes its result).
Inputs: `tmp/REVIEW-FINDINGS.md` (enrichment review), user decisions 2026-07-10.

## Decisions

| # | Decision |
|---|----------|
| 1 | Combine old 080 (trusted delivery) + old 090 (portal) into a new stage `050-advanced-app-platform`, positioned directly after 040. |
| 2 | Dev stages shift up: 050→`060-ai-assisted-development`, 060→`070-ai-agentic-development`, 070→`080-ai-autonomous-migration`. No stage 090. |
| 3 | Stage 050 owns deployment/config of **everything the dev stages consume**: identity (RHBK), Dev Spaces (CheCluster), OpenShift Pipelines + shared push pipeline, SonarQube + custom quality gate, Developer Hub (catalog, plugins, golden-path templates), ArgoCD wiring. |
| 4 | Templates provision **per-run isolated GitHub repos** (copy source into a fresh repo, wire webhook + catalog entity automatically). Solves demo reset; pipeline triggers on each new repo's `main`. |
| 5 | Developer Lightspeed for RHDH ships as an **optional overlay**, not base — the LCS↔MaaS protocol question stays open and must not block the platform stage. |
| 6 | MigIQ = the MTA + Developer Lightspeed stack the migration stage already deploys (`sshaaf/migIQ`, Kai, MTA operator). Rebrand references; the template provisions the legacy Spring app (`migiq-spring-boot-sample`) and wires it to that stack. |
| 7 | Identity: stage 050 deploys **RHBK as the platform identity broker** (brokered to OpenShift OAuth), realm `platform`, clients `rhdh` + `mta`. The migration stage reuses it — inverting today's dependency (RHDH depending on MTA's Keycloak). |

## Target stage map

| Stage | Name | Role | dependsOn |
|-------|------|------|-----------|
| 010–040 | (unchanged) | Governed AI platform foundation | as today |
| 050 | Advanced Application Platform | Identity, workspaces, CI/CD + quality gates, portal + templates — the app-platform layer every dev rung consumes | 040 |
| 060 | AI-Assisted Development | Rung 1 — one-shot prompts (Continue) on an existing Quarkus app provisioned by template | 040, 050 |
| 070 | AI-Agentic Development | Rung 2 — skills + spec-driven build of a brand-new Quarkus app (OpenCode) from a scaffold template | 040, 050 |
| 080 | AI-Autonomous Migration | Rung 3 — MigIQ multi-agent migration of a legacy Spring app provisioned by template | 040, 050 |

## Narrative reframe

The maturity ladder becomes three rungs (assisted → agentic → autonomous).
Trusted delivery and self-service stop being rungs and become **constants**:
every rung *enters* through the portal (a golden-path template) and *exits*
through the pipeline (SonarQube quality gate). The demo line is:

> "Self-service in, trusted delivery out — at every maturity level."

This fixes two review findings at once: the 050→080 dead-air gap (the pipeline
now pays off inside each stage, minutes after the push) and the portal-as-
afterthought problem (self-service is now how every stage begins). The
old 090 wrap-up beat moves to the end of stage 080 plus a closing README
section: return to the portal and the MaaS telemetry dashboard, walk the arc
backwards.

## Stage 050 composition

```
gitops/stages/050-advanced-app-platform/
├── base/
│   ├── identity/        # RHBK operator + instance, realm `platform`,
│   │                    # clients rhdh + mta, brokered to OpenShift OAuth
│   ├── devspaces/       # CheCluster (moved unchanged from old 050 base)
│   ├── pipelines/       # OpenShift Pipelines operator (from old 080 base),
│   │                    # `app-platform-build` namespace + RBAC + secrets,
│   │                    # generic push pipeline + tasks, EventListener,
│   │                    # TriggerBinding/Template (payload-derived repo)
│   ├── sonarqube/       # SonarQube + PostgreSQL, PostSync job provisioning
│   │                    # token secret + CUSTOM quality gate ("new issues > 0")
│   └── rhdh/            # RHDH operator + instance (from old 090 base),
│   │                    # Parasol-centric catalog, three golden-path
│   │                    # templates, plugins: K8s/topology, Tekton, ArgoCD,
│   │                    # GitHub scaffolder (NO bulk-import, NO global-header)
└── overlays/
    └── lightspeed/      # LCS + MCP plugins + llama-stack adapter Deployment
                         # (blocked on LCS↔MaaS protocol verification)
```

Old 090's coolstore catalog entities are retired in favor of the
Parasol/template-centric catalog (per review: one app carries the dev arc;
coolstore appears only as the legacy estate in stage 080).

### Dev-stage gitops ownership (decided 2026-07-10)

- **060 (assisted)** — becomes README + scripts only after Phase 2: the
  CheCluster and MaaS key provisioning move into 050's `devspaces/`
  component, and per-run workspaces come from the golden-path template
  instead of Git-tracked DevWorkspace manifests. Until Phase 2 executes, 060
  keeps its current `devspaces/` gitops base.
- **070 (agentic)** — already thin (one static workspace manifest); becomes
  README-only once the `agentic-quarkus-scaffold` template replaces the
  static `agentic-coolstore` DevWorkspace.
- **080 (migration)** — **keeps its gitops base.** The MigIQ stack (MTA
  operator, Tackle instance, Lightspeed config, hook jobs) is stage-specific
  migration infrastructure consumed by exactly one rung — moving it into 050
  would bloat the platform stage and force MTA deployment even when the
  migration rung is not being demoed. Only the Keycloak moves out (to 050's
  `identity/`) in Phase 2.
- Flow implication: README-only stages keep thin `deploy.sh`/`validate.sh`
  wrappers (validate-only), and `flows/default.yaml` entries drop their
  `gitopsApplication`/`gitopsPath` keys — `scripts/validate-stage-flow.sh`
  must learn to accept stages without gitops ownership.

## Golden-path templates

All three follow the same step shape: `fetch` golden source → `publish:github`
(new repo under `${GITHUB_ORG}`) → `github:webhook` (pointing at the shared
EventListener route, shared secret) → `catalog:register` (catalog-info
templated per run with a unique component name) → output links (repo,
DevSpaces, PipelineRuns, SonarQube).

1. **`assisted-quarkus-feature`** (stage 060). Param: app/repo name. Source:
   golden `parasol-insurance` repo (existing Quarkus Claims app; carries
   devfile + `.continue/config.yaml` + MaaS env wiring). Demo: add
   `ClaimsStatsResource` via Continue → push → gate fails on smells → AI fix →
   gate passes.
2. **`agentic-quarkus-scaffold`** (stage 070). Param: app name. Source:
   minimal Quarkus skeleton + `AGENTS.md` + `.opencode/skills/` (corporate
   Quarkus standards, adapted from `coolstore-inventory-service`
   `demo/agentic-skills` content) + `specs/` directory with a spec template
   for spec-driven development. Demo: OpenCode builds the app from the spec
   per corporate standards → push → gate passes first time (the maturity
   contrast with 060). **Default decision (flagged, reversible):** the spec
   describes an app with one LLM-powered feature consuming MaaS — this absorbs
   the dropped email-routing module's key message ("the same gateway serves
   developers' tools AND applications") without a second codebase.
3. **`autonomous-migration`** (stage 080). Param: app name. Source: golden
   `migiq-spring-boot-sample` legacy Spring app. Registers the repo with the
   MigIQ/MTA inventory (job or documented step). Demo: MigIQ analysis +
   multi-agent migration → migrated code pushes through the same pipeline and
   gate.

## Shared pipeline architecture

- One EventListener in `app-platform-build`; TriggerBinding extracts
  `body.repository.clone_url`, `body.repository.name`, `body.after`; CEL
  filter: push to `main` + repo naming convention/topic marking
  template-created repos.
- Pipeline params: `repo-url`, `repo-name`, `revision`. SonarQube project key
  = `repo-name`; image = `quay.io/${QUAY_ORG}/${repo-name}:${revision}`
  (git-revision tags, **not** `latest`).
- Remove `SSL_VERIFY: false` / `TLSVERIFY: false` (review finding — real
  certs on github.com/quay.io).
- Quality-gate reliability: the template's initial push triggers the first
  PipelineRun → clean **baseline** analysis; the developer's smelly commit is
  then genuinely "new code" against a custom gate ("new issues > 0"). This
  makes the 060 fail-forward moment deterministic — a direct fix for review
  risk #2.
- Recommended follow-up (not in scope of first pass): enable Tekton Chains
  for signed provenance, restoring the "trusted delivery" claim materially.

## Review findings adopted into this plan

- Per-run repos → demo reset solved structurally; add a cleanup script that
  deletes template-created repos, SonarQube projects, and catalog entities.
- Two MaaS keys (IDE vs application) with MaaS telemetry as a recurring
  per-stage closing beat.
- Data-classification beat: the agentic app's LLM feature pins the private
  model; talk track says why.
- Verify Continue `${VAR}` interpolation in `.continue/config.yaml` before
  relying on it (silently breaks stage 060 otherwise).
- Identity inversion (decision 7) resolves the review's "portal depends on
  the migration stage's Keycloak" ordering problem.

## Rename/move mechanics (Phase 1)

| From | To |
|------|----|
| `stages/080-ai-trusted-delivery/` + `stages/090-ai-self-service-portal/` | merged → `stages/050-advanced-app-platform/` |
| `stages/050-ai-assisted-development/` | `stages/060-ai-assisted-development/` |
| `stages/060-ai-agentic-development/` | `stages/070-ai-agentic-development/` |
| `stages/070-ai-autonomous-migration/` | `stages/080-ai-autonomous-migration/` |
| same four moves under `gitops/stages/` | |
| `gitops/argocd/app-of-apps/*.yaml` | renamed; Application names + paths updated |

- Renames overlap (050→060 while 060→070): execute with temporary names or in
  dependency order, using `git mv` to preserve history.
- `flows/default.yaml`: new ids, names, paths, dependsOn per the table above.
- Reference updates: `README.md` (ladder table + stage list), `AGENTS.md`,
  `docs/OPERATIONS.md`, `docs/TROUBLESHOOTING.md`, `docs/README.md`,
  `docs/DEVELOPER_WORKFLOW_VALIDATION.md`, `.agents/skills/manage-devspaces/`,
  `.agents/skills/validate-demo-step/`, `CONTRIBUTING.md`, stage READMEs'
  cross-references and stage-number mentions.
- Architecture SVGs named per stage (e.g., `stage-090-capability-map.svg`)
  need renaming and eventual regeneration.
- **On-cluster impact:** ArgoCD Application names change — old Applications
  must be deleted and new ones created (document the migration in
  OPERATIONS.md; namespaces are mostly unchanged so resources re-adopt).

## External prerequisites (outside this repo)

- GitHub org/account with golden repos: `parasol-insurance` (template
  source), the Quarkus scaffold source, `migiq-spring-boot-sample` (exists).
- Org-scoped PAT or GitHub App with repo-create + webhook permissions for the
  scaffolder.
- quay.io org + robot account with push permission.

## Phases

1. **Mechanical restructure** — renames, merged 050 skeleton, all reference
   updates, flows/app-of-apps. Repo stays internally coherent; stage content
   otherwise unchanged.
2. **Stage 050 build-out** — identity (RHBK), move devspaces, pipelines +
   SonarQube (adapting `tmp/stage-050-enrichment/` tekton + sonarqube assets),
   RHDH core with trimmed plugin list, Parasol-centric catalog.
3. **Templates + golden repos** — three templates, webhook flow, per-run
   catalog-info templating, end-to-end test of template → repo → pipeline →
   gate.
4. **Dev-stage rewrites** — stage 060/070/080 READMEs and demo scripts rebuilt
   around the template-driven flow; README maturity-ladder reframe; wrap-up
   beat at end of 080.
5. **Lightspeed overlay + Chains** — after LCS↔MaaS protocol verification;
   Tekton Chains provenance enhancement.

## Open items

- Tackle CR external-auth support: can MTA consume the platform RHBK realm
  directly? Fallback: MTA keeps its bundled Keycloak for its own UI; portal
  identity is unaffected (platform RHBK serves RHDH either way).
- LCS↔MaaS protocol verification (blocks Phase 5 only).
- `github:repo:push` vs `publish:github` semantics for copying golden-repo
  content — verify the chosen scaffolder actions against RHDH 1.9 before
  Phase 3 (review finding A2).
- Exact spec content for the agentic scaffold (including the LLM-feature
  default) to be drafted in Phase 3/4.
