# Source Capture

## Pattern Sources

| Field | Value |
|-------|-------|
| Pattern family | Red Hat Community of Practice GitOps Catalog |
| Catalog item | https://github.com/redhat-cop/gitops-catalog/tree/main/grafana-operator |
| Raw README | https://raw.githubusercontent.com/redhat-cop/gitops-catalog/main/grafana-operator/README.md |
| Capture date | 2026-06-10 |

| Source | Role |
|--------|------|
| https://raw.githubusercontent.com/redhat-cop/gitops-catalog/main/grafana-operator/base/operator/subscription.yaml | Grafana Operator Subscription shape |
| https://raw.githubusercontent.com/redhat-cop/gitops-catalog/main/grafana-operator/base/instance/grafana.yaml | Grafana instance, OAuth proxy, Route, TLS, and config pattern |
| https://raw.githubusercontent.com/redhat-cop/gitops-catalog/main/grafana-operator/base/instance/grafana-proxy-rbac.yaml | OAuth proxy TokenReview and SubjectAccessReview RBAC pattern |
| https://raw.githubusercontent.com/redhat-cop/gitops-catalog/main/grafana-operator/base/instance/injected-certs-cm.yaml | OpenShift injected CA bundle pattern |
| https://raw.githubusercontent.com/redhat-cop/gitops-catalog/main/grafana-operator/base/instance/session-secret.yaml | OAuth proxy session-secret placeholder pattern |
| https://raw.githubusercontent.com/redhat-cop/gitops-catalog/main/grafana-operator/overlays/aggregate/kustomization.yaml | Aggregate overlay with Argo CD dry-run handling |
| https://raw.githubusercontent.com/redhat-cop/gitops-catalog/main/grafana-operator/overlays/example/kustomization.yaml | Namespace and OperatorGroup overlay example |
| https://raw.githubusercontent.com/redhat-cop/gitops-catalog/main/grafana-operator/overlays/user-app/kustomization.yaml | User monitoring datasource overlay pattern |
| https://raw.githubusercontent.com/redhat-cop/gitops-catalog/main/grafana-operator/overlays/user-app/grafana-ds.yaml | `GrafanaDatasource` for OpenShift Thanos Querier |
| https://raw.githubusercontent.com/redhat-cop/gitops-catalog/main/grafana-operator/overlays/user-app/cluster-monitor-view-rb.yaml | `cluster-monitoring-view` binding pattern |
| https://raw.githubusercontent.com/redhat-cop/gitops-catalog/main/grafana-operator/overlays/user-app-example/kustomization.yaml | Downstream namespace patching example |

## Supporting Official Sources

| Source | URL | Use |
|--------|-----|-----|
| Grafana Operator documentation | https://grafana.com/docs/grafana/latest/as-code/infrastructure-as-code/grafana-operator/ | Official entry point for Grafana Operator behavior and supported resource-management concepts |
| Grafana Operator resources guide | https://grafana.com/docs/grafana/latest/as-code/infrastructure-as-code/grafana-operator/operator-dashboards-folders-datasources/ | Official examples for `Grafana`, `GrafanaDatasource`, `GrafanaDashboard`, `instanceSelector`, datasource config, dashboard JSON, and folders |
| Grafana Operator with Argo CD | https://grafana.com/docs/grafana/latest/as-code/infrastructure-as-code/grafana-operator/manage-dashboards-argocd/ | Official Argo CD GitOps workflow for dashboard custom resources |
| Grafana Operator Kustomize installation | https://grafana.github.io/grafana-operator/docs/installation/kustomize/ | Official Kustomize installation options and install-method caveats |
| Grafana Operator API reference | https://grafana.github.io/grafana-operator/docs/api/ | Official CRD field reference for `grafana.integreatly.org/v1beta1` |
| OCP 4.20 Operators - Understanding Operators | https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/operators/understanding-operators | OLM concepts, Subscription, InstallPlan, CSV, OperatorGroup, channel, update graph |
| OCP 4.20 Operators - Administrator tasks | https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/operators/administrator-tasks | Operator install, channel, approval, status, and uninstall workflows |
| OCP 4.20 Monitoring | https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html-single/monitoring/index | OpenShift monitoring and user workload monitoring concepts |
| OCP 4.20 Ingress and Routes | https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/networking/index | Route and TLS behavior |
| OCP 4.20 Authentication and Authorization | https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/authentication_and_authorization/index | RBAC, service account, TokenReview, and SubjectAccessReview concepts |

## Captured Catalog Layout

The CoP item uses this shape:

```text
grafana-operator/
  base/
    operator/
      subscription.yaml
      kustomization.yaml
    instance/
      grafana.yaml
      grafana-proxy-rbac.yaml
      injected-certs-cm.yaml
      session-secret.yaml
      kustomization.yaml
  overlays/
    aggregate/
    example/
    user-app/
    user-app-example/
```

The README states that the base is split into operator and Grafana instance
folders. It warns that a first-time install needs the operator before the
instance so the CRDs exist, and that deployable overlays must add a Namespace
and OperatorGroup. It also notes that OpenShift permits only one OperatorGroup
per namespace.

The aggregate overlay deploys the operator and custom resources together by
using Argo CD retry/dry-run behavior while the operator creates CRDs.

## Captured Operator Pattern

The catalog Subscription:

- uses API `operators.coreos.com/v1alpha1`
- has metadata name `grafana`
- subscribes to package `grafana-operator`
- uses channel `v5`
- sets `installPlanApproval: Automatic`
- uses catalog source `community-operators`
- uses source namespace `openshift-marketplace`

Source boundary: this is a community Operator pattern. Verify package,
channels, install modes, CRDs, and support posture from the active cluster
catalog before using it in the demo.

## Captured Grafana Instance Pattern

The catalog `Grafana` resource:

- uses API `grafana.integreatly.org/v1beta1`
- is named `grafana`
- uses label `instance: grafana`
- adds Argo CD `SkipDryRunOnMissingResource=true`
- uses sync wave `1`
- configures an OpenShift OAuth redirect reference on the service account
- creates a reencrypt Route to `grafana-service`
- uses OpenShift service serving certificate annotation for `grafana-tls`
- mounts the serving certificate, OAuth proxy session secret, and injected CA
  bundle into an OAuth proxy sidecar
- configures `quay.io/openshift/origin-oauth-proxy` as the proxy image in the
  catalog example
- configures Grafana auth settings including anonymous, basic, and proxy auth

Project boundary: review the OAuth proxy image and Grafana auth settings before
implementation. Prefer the active OpenShift-supported proxy image source where
possible. Do not enable anonymous or basic auth unless the demo explicitly
accepts that access posture and documents the reason.

The catalog `session-secret.yaml` contains a placeholder secret value. Do not
copy it as a real session secret.

## Captured Datasource Pattern

The `user-app` overlay adds:

- `GrafanaDatasource` named `prometheus`
- datasource URL pointing to
  `https://thanos-querier.openshift-monitoring.svc.cluster.local:9091`
- `Authorization` header configured in `secureJsonData.httpHeaderValue1`
- `spec.valuesFrom` substitution that reads the `token` key from
  `grafana-auth-secret` and writes `Bearer ${token}` into
  `secureJsonData.httpHeaderValue1`
- a Kubernetes service-account token Secret annotated for `grafana-sa`
- a `ClusterRoleBinding` to `cluster-monitoring-view`
- downstream patches that set the namespace and make ClusterRoleBinding names
  unique

Project boundary: never commit generated token data. Validate whether a
long-lived service-account token Secret is acceptable for the demo, or whether
a short-lived or operator-supported token mechanism is available in the active
cluster. Patch namespace placeholders and ClusterRoleBinding names before use.
Do not assume environment variables injected into the Grafana pod are expanded
inside `GrafanaDatasource` CR fields; use `valuesFrom` and verify a live
Grafana datasource query.

## Source Boundaries

- The CoP catalog is not product support authority.
- Grafana Operator CRDs and fields must be verified with official Grafana
  Operator docs, the API reference, `oc explain`, active CRDs, or the
  installed package documentation before manifests are committed.
- OpenShift monitoring access must be validated against the active cluster's
  user workload monitoring and RBAC configuration.
- Grafana dashboard content must be grounded in the component skill that owns
  the metrics being visualized.
- Secrets, generated tokens, bearer values, API keys, and external datasource
  credentials must not be committed.
