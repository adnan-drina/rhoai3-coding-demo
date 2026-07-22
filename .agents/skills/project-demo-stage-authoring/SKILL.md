---
name: project-demo-stage-authoring
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Project Structure"
description: >
  Use when creating, planning, implementing, or reviewing a new rhoai3-coding-demo
  stage from ideation to validated GitOps implementation. Covers stage scope,
  dependencies, skill routing, README drafting, GitOps ownership decisions,
  Argo CD Application setup, Kustomize manifests, deploy and validation scripts,
  operations and troubleshooting updates, and definition-of-done gates. Do NOT use
  for product authority on RHOAI, OCP, or operator APIs (consult official docs),
  live troubleshooting (use rhoai-troubleshoot), or operational doc creation
  (use demo-operations-docs).
---

# Demo Stage Authoring

Use this skill as the repeatable process for turning a demo idea into a validated Red Hat product demo stage. A stage is not complete until its documentation, GitOps, scripts, validation, and operational notes move together.

## Core Rule

Every new stage must pass the same phase gates:

1. intent and scope
2. source capture
3. skill routing
4. implementation plan
5. README story
6. GitOps ownership
7. manifest generation
8. deploy and validation scripts
9. operations and troubleshooting updates
10. review and acceptance

Do not start the next demo stage until the current stage has an explicit definition of done and the user accepts any deferred work.

Do not silently defer or remove components from an agreed stage scope or user requirement. If a component is blocked, risky, expensive, or better suited for a later stage, stop and discuss the tradeoff with the user before marking it `deferred`, `future`, or backlog.

## Stage Artifact Contract

Each stage produces this artifact set:

```text
stages/NNN-descriptive-slug/
  README.md
  deploy.sh
  validate.sh
gitops/
  argocd/app-of-apps/NNN-descriptive-slug.yaml
  stages/NNN-descriptive-slug/base/kustomization.yaml
```

Stages that patch shared platform resources (e.g., RHOAI DataScienceCluster, OpenShift GitOps bootstrap) record the shared owner path and avoid duplicate full-resource ownership.

### Workflow-Only Stage Pattern

Stages 060, 070, and 080 are workflow-only stages. They have only `validate.sh` and `README.md` — no `deploy.sh` and no Argo CD Application. Their platform infrastructure (Dev Spaces workspaces, RHDH templates, MTA operator) is owned by Stage 050 (`050-advanced-app-platform`). These stages validate that the platform capabilities they depend on are healthy, and their READMEs describe developer workflows that consume those capabilities.

Note: Stage 050 absorbed the former Stage 090 (RHDH portal). All developer portal resources are now part of Stage 050's GitOps ownership.

## Workflow

1. Read `references/stage-lifecycle.md`.
2. Read `references/definition-of-done.md` for acceptance criteria.
3. Define scope: stage number, slug, concept, audience, dependencies,
   components, and non-goals.
4. Verify no existing stage already covers the concept.
5. Check official Red Hat documentation for every product component introduced.
6. Draft the stage README with `project-documentation-authoring` and the
   readme-standard reference.
7. Design GitOps using `review-gitops-change` skill patterns and existing stage
   Argo CD Applications as reference.
8. Generate manifests only from official docs, verified live schema (`oc explain`),
   or explicitly documented demo exceptions.
9. Add `deploy.sh` and `validate.sh` following existing stage script patterns.
10. Add an Architecture section with an ASCII or Mermaid diagram showing new
    capabilities (inline in the README).
11. Update `docs/OPERATIONS.md` and `docs/TROUBLESHOOTING.md` when the stage
    creates reusable operational knowledge.
12. Run the quality gates in `references/definition-of-done.md`.
13. Use `review-gitops-change` before treating the stage as ready.

## Required Handoffs

- `project-documentation-authoring`: README, operations, troubleshooting, and
  backlog updates.
- `project-documentation-authoring`: README narrative and structure.
- `review-gitops-change`: structural and security review of manifests.
- `validate-demo-step`: static and live validation.
- `demo-operations-docs`: operational documentation.
- `update-demo-docs`: documentation consistency check.

## Stop Conditions

Stop and resolve before implementation if:

- the stage concept has no clear audience value
- required official product docs are missing
- a custom resource field, API version, operator channel, or image cannot be
  sourced or verified
- the GitOps ownership model would create duplicate owners for a shared resource
- required credentials or tokens would be committed
- deploy or validate scripts would touch a live cluster without the safety guard
- the README claims a capability that manifests and validation do not provide

## References

- `references/stage-lifecycle.md`
- `references/definition-of-done.md`
