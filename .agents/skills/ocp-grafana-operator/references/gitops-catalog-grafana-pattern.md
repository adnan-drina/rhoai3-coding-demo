# Red Hat CoP Grafana GitOps Pattern

Use this reference when rebuilding a GitOps-managed Grafana layer for
rhoai3-demo.

## Source Role

The Red Hat Community of Practice GitOps Catalog is a curation and layout
pattern source. It is not product support authority. The captured Grafana
Operator Subscription uses `community-operators`; verify support posture,
channels, CRDs, fields, images, and install modes before implementation.

## Catalog Shape

The CoP item uses an older but useful split:

```text
grafana-operator/
  base/operator/
  base/instance/
  overlays/aggregate/
  overlays/example/
  overlays/user-app/
  overlays/user-app-example/
```

Reusable ideas:

- keep OLM Subscription separate from Grafana instance resources
- require a deployable overlay to add Namespace and OperatorGroup
- use an aggregate overlay only when Argo CD should deploy operator and
  instance together
- include `SkipDryRunOnMissingResource=true` when a single Application renders
  CRs before CRDs are present
- keep datasource and monitoring-access resources in an optional overlay

## Project Adaptation

For this repo, normalize the catalog shape into the project operator GitOps
layout when implementation begins:

```text
gitops/platform/grafana/
  operator/
    base/
      namespace.yaml
      operator-group.yaml
      subscription.yaml
      kustomization.yaml
    overlays/
      v5/
        patch-channel.yaml
        kustomization.yaml
  instance/
    base/
      grafana.yaml
      grafana-proxy-rbac.yaml
      injected-certs-cm.yaml
      session-secret.yaml
      kustomization.yaml
    components/
      openshift-monitoring-datasource/
      model-serving-dashboards/
    overlays/
      demo/
        kustomization.yaml
  aggregate/
    overlays/
      demo/
        kustomization.yaml
```

This keeps compatibility with `project-red-hat-operator-gitops` while
preserving the CoP intent:

- operator install policy is managed in Git
- instance resources are managed after CRDs exist
- datasource and dashboard resources are optional components
- aggregate overlays are an explicit deployment choice, not the only path

## Operator Lifecycle

Manage Grafana Operator lifecycle as Git changes:

- verify available channels from the active OLM catalog
- keep channel and `installPlanApproval` in the Subscription overlay
- prefer automatic approval only when the demo accepts community Operator
  upgrade behavior
- use manual approval when upgrades need a human gate
- validate Subscription, InstallPlan, CSV, CRDs, and operand health after sync
- do not patch the live Subscription as the normal upgrade path

## Instance Guidance

Before committing a `Grafana` custom resource:

- verify `grafana.integreatly.org/v1beta1` is present on the active cluster
- run `oc explain grafana.spec` for the installed CRD
- review OpenShift OAuth proxy settings and service-account redirect
  annotation
- review route TLS and service serving certificate settings
- replace placeholder session-secret handling with a demo-approved secret
  strategy
- avoid anonymous or basic auth unless the demo explicitly chooses that access
  posture

## Datasource Guidance

For OpenShift monitoring access:

- verify user workload monitoring is enabled when dashboards target
  user-defined project metrics
- review whether the datasource should query platform Thanos,
  user workload monitoring, or another endpoint
- GitOps-manage the Grafana service account explicitly before any token Secret,
  RoleBinding, or ClusterRoleBinding references it. Do not assume
  `Grafana.spec.serviceAccount` creates the service account early enough for
  Argo CD sync ordering.
- bind the Grafana service account only to the required monitoring role
- patch namespace placeholders in RoleBindings and ClusterRoleBindings
- make ClusterRoleBinding names unique per namespace
- never commit generated token data or external datasource credentials
- validate the datasource through Grafana's datasource API or a live panel
  query. `GrafanaDatasource` status alone does not prove the token, URL, and
  Prometheus query permissions are correct.

## Dashboard Guidance

Dashboard resources should be owned by the capability that owns the metrics:

- platform dashboards: pair with `ocp-observability`
- model-serving dashboards: pair with `rhoai-model-management-monitoring`
- GPU dashboards: pair with `rhoai-nvidia-gpu-accelerators`
- application dashboards: pair with the step or component skill that owns the
  application

Before committing `GrafanaDashboard` resources, verify the CRD API version,
selector behavior, namespace behavior, and supported dashboard formats in the
active Grafana Operator CRDs.

## Do Not Copy Blindly

- Do not use remote Kustomize references to the CoP catalog in committed
  GitOps.
- Do not copy the placeholder session secret.
- Do not commit generated service-account token data.
- Do not rely on operator-created service-account timing for token Secrets or
  monitoring RBAC.
- Do not assume `community-operators`, channel `v5`, or automatic approval are
  acceptable without active catalog verification.
- Do not assume the CoP OAuth proxy image is the supported image for the active
  OpenShift baseline.
- Do not present Grafana dashboards as implemented until GitOps manifests,
  metrics, and validation checks exist.
