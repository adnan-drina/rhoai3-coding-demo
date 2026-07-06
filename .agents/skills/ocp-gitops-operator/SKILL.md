---
name: ocp-gitops-operator
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "ocp"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when documenting, reviewing, or rebuilding OpenShift Container Platform
  GitOps platform guidance from official OCP documentation: Red Hat OpenShift
  GitOps, OpenShift GitOps Operator, Argo CD as the declarative GitOps engine,
  multicluster GitOps workflows, OpenShift integration, enterprise support
  boundaries, release-cadence boundaries, and the handoff to separate Red Hat
  OpenShift GitOps documentation. Do NOT use for repo-specific Argo CD
  Application layout, Kustomize step authoring, demo sync-wave conventions, or
  manifest edits; use project-gitops-authoring. Do NOT invent ArgoCD,
  Application, AppProject, RBAC, or Operator CR fields from the OCP overview
  page alone.
---

# OCP GitOps Operator

Use this skill to ground OpenShift GitOps platform guidance in the official OCP
GitOps overview for the active baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority. This skill captures the OCP-level
GitOps definition and product boundary. Detailed Red Hat OpenShift GitOps
installation, Argo CD instance configuration, Application schema, RBAC, and
operational procedures must come from the separate Red Hat OpenShift GitOps
documentation set and active cluster schema.

## Demo GitOps Posture

For this AWS-hosted RHOAI demo:

- Use OpenShift GitOps as the platform-supported Argo CD distribution when the
  new clean-slate GitOps implementation is introduced.
- Treat Argo CD as the deployment reconciler for GitOps-managed resources; new
  deployment automation must apply Argo CD Applications first.
- Keep repo-specific Application layout, Kustomize structure, sync waves,
  target revisions, and demo labels in `project-gitops-authoring`.
- Keep `resourceTrackingMethod: annotation` as a project constraint unless a
  future official-source review and implementation decision changes it.
- Do not claim Operator install, channel, namespace, CR fields, RBAC, SSO, or
  multi-cluster behavior from the OCP overview page alone.

## GitOps Model

Use the official docs to frame:

- **Red Hat OpenShift GitOps**: an Operator that uses Argo CD as the
  declarative GitOps engine.
- **Argo CD**: the engine used to implement declarative GitOps workflows.
- **Workflow scope**: OpenShift GitOps enables workflows across multicluster
  OpenShift and Kubernetes infrastructure.
- **Operational value**: administrators can consistently configure and deploy
  Kubernetes-based infrastructure and applications across clusters and
  development lifecycles.
- **Product boundary**: OpenShift GitOps is based on upstream Argo CD and adds
  Red Hat OpenShift integration, automation, enterprise support, quality
  assurance, and security focus.
- **Documentation boundary**: Red Hat OpenShift GitOps releases on a different
  cadence from OCP, so detailed documentation is maintained separately.

## Workflow

1. Confirm the active OpenShift baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Identify whether the task concerns:
   - OCP-level GitOps narrative or platform positioning
   - OpenShift GitOps Operator source boundaries
   - Argo CD as the OpenShift GitOps engine
   - demo-specific GitOps authoring, which belongs in
     `project-gitops-authoring`
   - detailed Operator or Argo CD behavior, which requires separate Red Hat
     OpenShift GitOps documentation and schema verification
4. For GitOps manifests, verify all API versions, CRDs, fields, namespaces,
   RBAC, cluster roles, and resource-tracking behavior before committing.
5. For live operations, use the repo environment guard and pair this skill with
   `env-troubleshoot`, `env-manage-resources`, or `env-deploy-and-evaluate`.
6. Validate the output with `references/validation-checklist.md`.

## Related Skills

- Use `project-gitops-authoring` for repo-specific `gitops/**`,
  Kustomize, Argo CD Application, sync-wave, targetRevision, label, and
  app-of-apps authoring.
- Use `project-manifest-review` for read-only review of Kubernetes, OpenShift,
  Argo CD, and RHOAI manifests.
- Use `ocp-cicd-builds` for OpenShift CI/CD overview and build workflows.
- Create future detailed skills from the separate Red Hat OpenShift GitOps
  documentation when the GitOps product baseline is pinned.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/gitops-review-patterns.md`
