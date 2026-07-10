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
| 3 | Stage 050 owns deployment/config of **everything the dev stages consume**: identity (RHBK), Dev Spaces (CheCluster), OpenShift Pipelines + shared push pipeline, SonarQube + custom quality gate, Developer Hub (catalog, plugins, golden-path templates), the MigIQ stack (MTA operator + Tackle + Lightspeed config), ArgoCD wiring. Decided 2026-07-10: this includes MTA — the dev stages carry **no gitops of their own**. |
| 4 | Templates provision **per-run isolated GitHub repos** (copy source into a fresh repo, wire webhook + catalog entity automatically). Solves demo reset; pipeline triggers on each new repo's `main`. |
| 5 | Developer Lightspeed for RHDH ships as an **optional overlay**, not base — the LCS↔MaaS protocol question stays open and must not block the platform stage. |
| 6 | MigIQ = the MTA + Developer Lightspeed stack (`sshaaf/migIQ`, Kai, MTA operator). It deploys from stage 050 alongside the other platform components (moved out of the migration stage in Phase 2); the template provisions the legacy Spring app (`migiq-spring-boot-sample`) and wires it to that stack. |
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
│   ├── rhdh/            # RHDH operator + instance (from old 090 base),
│   │                    # Parasol-centric catalog, three golden-path
│   │                    # templates, plugins: K8s/topology, Tekton, ArgoCD,
│   │                    # GitHub scaffolder (NO bulk-import, NO global-header)
│   └── migiq/           # MTA operator + Tackle + Lightspeed/MaaS wiring
│                        # (moved from the migration stage's gitops base)
└── overlays/
    └── lightspeed/      # LCS + MCP plugins + llama-stack adapter Deployment
                         # (blocked on LCS↔MaaS protocol verification)
```

Structure the base as kustomize components (devspaces, pipelines, sonarqube,
rhdh, identity, migiq) so heavy single-rung pieces — MigIQ above all — can be
excluded via a slim overlay when that rung is not being demoed. This keeps
the "050 owns all infrastructure" model without forcing an MTA install on
every deployment.

Old 090's coolstore catalog entities are retired in favor of the
Parasol/template-centric catalog (per review: one app carries the dev arc;
coolstore appears only as the legacy estate in stage 080).

### Dev-stage gitops ownership (decided 2026-07-10, revised same day)

**All three dev stages become README-only after Phase 2.** Stage 050 owns
every piece of infrastructure, including MTA/MigIQ. The maturity-ladder
stages are pure workflow/demo stages: narrative, demo script, and read-only
validation of prerequisites that stage 050 provisioned.

- **060 (assisted)** — CheCluster, Dev Spaces operator, editor policy, and
  MaaS key provisioning move to 050 `devspaces/`. Per-run workspaces come
  from the `assisted-quarkus-feature` template.
- **070 (agentic)** — the static `agentic-coolstore` DevWorkspace is retired
  in favor of the `agentic-quarkus-scaffold` template; nothing remains to
  own in gitops.
- **080 (migration)** — MTA operator, Tackle instance, Lightspeed/MaaS hook
  jobs, and the elevated-key provisioning move to 050 `migiq/`; the Keycloak
  moves to 050 `identity/`. The `autonomous-migration` template provisions
  the legacy app repo.
- Mechanics: delete `gitops/stages/{060,070,080}-*` and their app-of-apps
  Applications in Phase 2; dev-stage dirs keep `README.md` + a validate-only
  `validate.sh` (checks live prerequisites read-only: workspace reachable,
  MigIQ healthy, template present); `deploy.sh` is removed. Flow entries
  drop `gitopsApplication`/`gitopsPath`; `scripts/validate-stage-flow.sh`
  must accept stages without gitops ownership.
- Tradeoff accepted: 050 becomes a heavyweight stage (RHBK + Dev Spaces +
  Pipelines + SonarQube + RHDH + MTA). Mitigation: kustomize components per
  capability with a slim overlay that omits `migiq/` when the migration rung
  is not demoed.

## Golden-path templates

All three follow the same step shape (as implemented): `fetch:plain` golden
source → `fetch:template` skeleton (per-run `catalog-info.yaml`) →
`publish:github` (new public repo, `protectDefaultBranch: false`, topic
`rhoai3-golden-path`) → `catalog:register` from the publish output. No
webhook step — the GitHub App delivers push events (see Status note).

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

Status 2026-07-10: Phases 1-4 executed on the repo side. Phase 4: dev-stage
READMEs rebuilt around the golden-path flow (060: template -> Continue ->
gate fails -> AI fix; 070: scaffold template -> spec-driven OpenCode build
incl. MaaS LLM feature -> gate green first push; 080: template entry +
arc-closing wrap-up beat); root README gained presenter guidance. Golden
repos bootstrapped live under github.com/adnan-drina (parasol-insurance
derived+build-verified, agentic-quarkus-scaffold authored+build-verified,
migiq-spring-boot-sample pre-existing). Remaining before demo-ready: user
setup (PAT, GitHub App, quay values, GITHUB_WEBHOOK_SECRET), live cluster
deploy + e2e template->pipeline->gate run, Continue env-interpolation check,
Phase 5 (Lightspeed overlay + Chains). Phase 3 executed
(repo side): three golden-path templates registered via the runtime catalog,
RHDH GitHub integration (preinstalled scaffolder module enabled, PAT via
rhdh-github secret), quay wiring behind .env placeholders with runtime
registry resolution, golden repos staged in golden-repos/ +
scripts/bootstrap-golden-repos.sh. Webhook decision (supersedes the
github:webhook step in the template sketch): RHDH's dynamic module wiring
passes no defaultWebhookSecret to github:webhook and templates cannot read
secrets, so per-repo webhooks would need the secret pasted per run; instead
a user-owned GitHub App (push events, installed on All repositories)
delivers webhooks for every current and future repo to the shared
EventListener with one HMAC secret. Note: GitHub App installation tokens
cannot create repos under a personal account, so the scaffolder keeps a
classic PAT. Phase 2 executed
(structural consolidation): 050 owns all five components; dev stages are
workflow-only; shared pipeline + SonarQube gate landed. Phase 2 deltas from
the original sketch: (a) the standalone platform RHBK was deferred — moving
MigIQ into 050 dissolved the cross-stage identity dependency, and RHDH keeps
brokering through the MTA Keycloak (now stage-internal, PostSync jobs wait);
building a fresh RHBK chain blind without a live cluster was judged
higher-risk than the working transitional path. The `slim` overlay depends
on that RHBK landing. (b) External quay.io wiring is deferred to Phase 3
(needs the org/robot account anyway); the pipeline defaults to the internal
OpenShift registry. Not validated against a live cluster — static review
only.

1. **Mechanical restructure** — renames, merged 050 skeleton, all reference
   updates, flows/app-of-apps. Repo stays internally coherent; stage content
   otherwise unchanged.
2. **Stage 050 build-out** — identity (RHBK), move devspaces (from 060) and
   the MigIQ stack (from 080), pipelines + SonarQube (adapting
   `tmp/stage-050-enrichment/` tekton + sonarqube assets), RHDH core with
   trimmed plugin list, Parasol-centric catalog. Retire the
   `gitops/stages/{060,070,080}-*` bases and their Argo CD Applications;
   convert dev stages to README-only with validate-only scripts; teach
   `validate-stage-flow.sh` about gitops-less stages.
3. **Templates + golden repos** — three templates, webhook flow, per-run
   catalog-info templating, end-to-end test of template → repo → pipeline →
   gate.
4. **Dev-stage rewrites** — stage 060/070/080 READMEs and demo scripts rebuilt
   around the template-driven flow; README maturity-ladder reframe; wrap-up
   beat at end of 080.
5. **Lightspeed overlay + Chains** — moved to BACKLOG.md ("Stage 050
   Phase 5 items", 2026-07-10) together with the standalone platform RHBK.

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
