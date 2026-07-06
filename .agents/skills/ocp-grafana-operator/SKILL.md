---
name: ocp-grafana-operator
metadata:
  author: rhoai3-demo
  version: 1.1.0
  platform-family: "ocp"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when documenting, reviewing, or rebuilding GitOps-managed Grafana on
  OpenShift for the rhoai3-demo: Grafana Operator Subscription from the
  community operator catalog, Grafana custom resources, OpenShift OAuth proxy
  route posture, service serving certificates, injected CA bundles, session
  secrets, GrafanaDatasource resources, GrafanaDashboard resources,
  cluster-monitoring-view access to Thanos Querier, Argo CD sync options,
  namespace and OperatorGroup handling, official Grafana Operator docs, API
  reference checks, Kustomize installation boundaries, Argo CD dashboard GitOps
  patterns, and Red Hat CoP grafana-operator catalog curation. Do NOT use for
  RHOAI model monitoring semantics, vLLM/KServe metrics, or dashboard content
  design; use rhoai-model-management-monitoring. Do NOT treat the CoP catalog
  as product authority; verify fields with official Grafana Operator docs,
  official OCP docs, installed OLM package metadata, and active CRDs.
---

# OCP Grafana Operator

Use this skill to deploy and manage Grafana through GitOps for the
rhoai3-demo observability layer. It captures the Red Hat Community of Practice
`grafana-operator` catalog pattern and adapts it to the repo's local-curation
and OpenShift safety model.

## Source Grounding

Read `references/official-grafana-operator-docs.md` before validating
Grafana Operator CRs, datasource CRs, dashboard CRs, or Argo CD dashboard
GitOps behavior. Use it to distinguish official Grafana Operator behavior from
repo-specific OpenShift/OLM adaptation.

Read `references/source-capture.md` before using product behavior. The CoP
catalog is a GitOps pattern source, not product support authority. The Grafana
Operator in the captured catalog is installed from `community-operators`, so
channel, install mode, custom resource fields, images, and support posture must
be verified from the active cluster catalog, CRDs, official Grafana Operator
docs, and relevant OpenShift docs.

Read `references/gitops-catalog-grafana-pattern.md` when rebuilding operator,
instance, OAuth proxy, datasource, dashboard, or aggregate overlays.

## Demo Grafana Posture

For this AWS-hosted RHOAI demo:

- Treat Grafana as an optional demo observability UI, introduced only when a
  step needs dashboards for platform, model-serving, GPU, or application
  metrics.
- Curate the CoP pattern locally. Do not commit remote Kustomize references to
  `redhat-cop/gitops-catalog`.
- Prefer a dedicated namespace for the Grafana Operator and instance. Verify
  there is only one `OperatorGroup` in that namespace.
- Keep operator install resources separate from Grafana instance, datasource,
  dashboard, route, RBAC, and secret resources unless a single aggregate Argo
  CD Application is deliberately selected.
- Use OpenShift OAuth and route TLS for browser access. Do not copy anonymous
  or basic-auth settings without documenting the demo-specific reason.
- Never commit generated service-account tokens, real session secrets, API
  keys, or datasource credentials.
- Use `cluster-monitoring-view` or narrower RBAC only when the Grafana service
  account needs access to OpenShift monitoring data.
- Keep dashboard content ownership in the component skill that owns the metric
  semantics. For model-serving dashboards, use `rhoai-model-management-monitoring`.

## Grafana GitOps Model

Use the CoP pattern to frame:

- **Operator layer**: OLM `Subscription` for package `grafana-operator` from
  `community-operators`.
- **Namespace and OperatorGroup layer**: namespace-specific install scope
  supplied by the deployable overlay.
- **Instance layer**: `Grafana` custom resource plus service account, OAuth
  proxy, serving certificate, injected CA bundle, session secret, route, and
  RBAC resources.
- **Datasource layer**: `GrafanaDatasource` for OpenShift monitoring or user
  workload monitoring endpoints, with token handling reviewed as sensitive.
- **Dashboard layer**: `GrafanaDashboard` or operator-supported dashboard
  resources after CRDs and selectors are verified.
- **Aggregate layer**: optional overlay that combines operator and instance
  resources with Argo CD dry-run handling while CRDs become available.

## Workflow

1. Confirm the active OpenShift baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-grafana-operator-docs.md`.
3. Read `references/source-capture.md`.
4. Read `references/gitops-catalog-grafana-pattern.md`.
5. Identify whether the task concerns:
   - Grafana Operator installation or lifecycle
   - namespace and OperatorGroup scope
   - `Grafana` instance configuration
   - OAuth proxy, Route, service serving certificate, or injected CA bundle
   - datasource access to OpenShift monitoring or user workload monitoring
   - dashboard CRs and dashboard selectors
   - RBAC, service-account tokens, session secrets, or external credentials
6. Pair with `project-red-hat-operator-gitops` for layout and lifecycle
   management, and with `project-gitops-authoring` for repo-specific Argo CD
   Application standards.
7. Verify all API versions, CR fields, channel values, images, route settings,
   RBAC, datasource fields, dashboard fields, and secret handling against the
   active cluster schema and official Grafana Operator API reference before
   committing manifests.
8. For live operations, use the repo environment guard and pair this skill with
   `env-troubleshoot`, `env-manage-resources`, or `env-deploy-and-evaluate`.
9. Validate the output with `references/validation-checklist.md`.

## Related Skills

- Use `project-red-hat-operator-gitops` for the local operator, instance, and
  aggregate GitOps pattern.
- Use `project-gitops-authoring` for repo-specific Kustomize and Argo CD
  Application conventions.
- Use `project-manifest-review` for structural and security review of
  Kubernetes, OpenShift, and Argo CD manifests.
- Use `ocp-observability` for OCP monitoring and user workload monitoring
  concepts.
- Use `ocp-ingress-gateway-routes` for Route and TLS behavior.
- Use `ocp-security-rbac-scc` for service accounts, ClusterRoles,
  ClusterRoleBindings, RoleBindings, and token review permissions.
- Use `rhoai-model-management-monitoring` for RHOAI model-serving metrics and
  dashboard content.

## References

- `references/source-capture.md`
- `references/official-grafana-operator-docs.md`
- `references/gitops-catalog-grafana-pattern.md`
- `references/validation-checklist.md`
- `examples/grafana-review-patterns.md`
