# Demo Stage Lifecycle

Use this lifecycle for every new rhoai3-coding-demo stage. The goal is methodical product-demo delivery: each stage introduces a clear Red Hat-aligned concept, implements it with GitOps, and proves it with validation.

## Phase 0: Intake

Define the stage before creating files:

- stage number (NNN) and descriptive slug
- working title and one-line tagline
- concept introduced by the stage
- target audience: architect, platform engineer, developer experience team, or
  business stakeholder
- enterprise value: control, governance, compliance, cost, scale, safety,
  portability, productivity, traceability, or resilience
- dependency on previous stages
- new components introduced now
- reused components from earlier stages
- explicit non-goals
- acceptance criteria

If scope does not fit in one concise README and one deployable GitOps slice, split the stage or move future work to `BACKLOG.md`.

## Phase 1: Source Capture

Before writing implementation:

- confirm active product versions (see root README product posture)
- capture official Red Hat documentation for every product component introduced
- identify the operator channel, namespace, and CR schema
- record unsupported, technology-preview, community, or demo-only exceptions
- check existing stage patterns for reference

Do not create manifests from memory. If the official documentation is unclear, propose a verification command (`oc explain`, CRD inspection).

## Phase 2: Skill Routing

List the skills that will govern the stage:

- coordinator: `project-demo-stage-authoring`
- documentation: `project-documentation-authoring`
- architecture: inline ASCII or Mermaid diagram in the stage README
- GitOps review: `review-gitops-change`
- validation: `validate-demo-step`
- operations: `demo-operations-docs`
- troubleshooting: `rhoai-troubleshoot` (when issues arise)

## Phase 3: Plan

Before implementation, define:

- scope and non-goals
- source list (official docs, operator versions)
- selected skills
- GitOps ownership decision
- manifest inventory
- deploy script behavior
- validation script behavior
- required live-cluster checks
- expected user-visible outcome
- rollback or cleanup notes
- risks and deferred items

## Phase 4: README

Write `stages/NNN-descriptive-slug/README.md` using `project-documentation-authoring/references/readme-standard.md`.

The README should answer Why and What:

- `## Why This Matters`: define the concept and explain enterprise value
- `## Architecture`: show the architecture delta and new components
- `## What This Stage Adds`: concise capability description
- `## What To Notice And Why It Matters`: enterprise proof points
- `## References`: keep source links short and relevant

Do not put runbooks, long command walkthroughs, or validation transcripts in the README.

## Phase 5: GitOps Ownership

Decide where resources live before creating manifests.

Use a stage-owned GitOps path when the stage owns independent resources:

```text
gitops/stages/NNN-descriptive-slug/base/kustomization.yaml
gitops/argocd/app-of-apps/NNN-descriptive-slug.yaml
```

Use a shared-owner path when the stage changes global platform state:

```text
gitops/<shared-platform-owner>/base/
```

Never render competing full copies of a shared resource from multiple Argo CD Applications.

## Phase 6: Manifest Authoring

Author manifests from verified sources:

- official Red Hat product docs
- live schema verification with `oc explain` or CRD inspection
- existing stage manifests as patterns
- explicit demo exceptions documented in README

Use Red Hat product images and registry sources unless a demo exception is approved and documented.

## Phase 7: Scripts

Each stage normally has:

- `deploy.sh`: applies the Argo CD Application, then waits or reports status
- `validate.sh`: performs deterministic readiness, API, route, or model checks

Scripts that touch a live cluster must:

- source `scripts/lib.sh` for shared helpers
- call `load_env` and `check_oc_logged_in`
- verify `RHOAI_EXPECTED_API_SERVER`
- fail closed if the target cluster cannot be confirmed
- avoid direct `oc apply -k` against Argo CD-managed resources

## Phase 8: Validation

Run the narrowest useful checks before live deployment:

- `kustomize build` for GitOps paths
- `bash -n` for shell scripts
- `./scripts/validate-stage-flow.sh` for overall flow integrity
- Manifest review checklists

Live validation should prove the user-visible stage outcome, not just resource existence.

## Phase 9: Operations And Troubleshooting

Update promoted docs only when the stage creates reusable operational knowledge:

- `docs/OPERATIONS.md`: deployment order, day-2 operation, or credential setup
- `docs/TROUBLESHOOTING.md`: repeated symptoms, diagnostics, and recovery
- `BACKLOG.md`: deferred capabilities or follow-up work

Do not scatter runbook content across stage READMEs.

## Phase 10: Acceptance

A stage is ready only when:

- README, GitOps, scripts, and validation agree
- manifests render with `kustomize build`
- live validation passes when a live environment is available
- deferred work is explicit and accepted
- architecture diagrams include the new stage capabilities
