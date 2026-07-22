# Demo Stage Definition Of Done

Use this checklist before declaring a stage ready.

## Scope

- Stage number, slug, title, concept, audience, dependencies, and non-goals are
  defined.
- The stage introduces one coherent capability or clearly bounded integration.
- Deferred work is listed in `BACKLOG.md` only after the user explicitly accepts
  the deferral.
- No component from an agreed stage scope or user requirement has been silently
  removed, downgraded, or moved to future work.

## Sources

- Active baseline versions are checked (root README product posture).
- Official Red Hat docs exist for every product component introduced.
- Unsupported, Technology Preview, community, or demo-only posture is explicit.

## README

- README follows the required stage shape (Why/Architecture/Adds/Notice/Products/Deploy/Next).
- Why/value section is concise and source-grounded.
- Technology mapping links to official product docs.
- Architecture section identifies new and existing components.
- README does not contain deployment runbooks or long command transcripts.

## GitOps

- GitOps ownership is explicit: stage-owned path or shared platform owner.
- No two Applications render competing full copies of the same shared resource.
- Argo CD Application uses project standards (`project: rhoai-demo`).
- Kustomize renders locally with `kustomize build`.
- Secrets, generated tokens, kubeconfigs, API keys, and real credentials are
  not committed.

## Manifests

- API versions and fields are sourced from official docs or verified schema.
- Images and model artifacts have documented provenance.
- Labels and annotations follow project standards.
- Cross-resource references resolve.
- Security-sensitive RBAC, SCC, Route, Gateway, and token choices are reviewed.

## Scripts

- `deploy.sh` applies the Argo CD Application or shared owner Application
  before waiting for resources.
- `validate.sh` proves the user-visible outcome.
- Live-cluster scripts use the OpenShift safety guard (`scripts/lib.sh`).
- Scripts are deterministic and safe to rerun.

## Reviews

- `review-gitops-change` has no unresolved blocking findings.
- Manifest schema validates against installed operators / cluster version.

## Validation

- Local render and static checks pass (`kustomize build`, `bash -n`).
- `./scripts/validate-stage-flow.sh` passes.
- Live validation passes when a target environment is available.
- If live validation is unavailable, the missing validation is documented.
- Operations and troubleshooting docs are updated when reusable knowledge was
  created.

## Architecture Diagrams

- Stage README includes an ASCII or Mermaid architecture diagram if the stage introduces new components.
- Root README ASCII diagram reflects all three platform layers and their key building blocks.
- Stage README references the correct stage capability map SVG.

## Commit Boundary

Commit each completed stage as an atomic unit:

- stage README
- GitOps manifests
- Argo CD Application
- deploy and validation scripts
- operations, troubleshooting, or backlog updates
- architecture diagram updates
