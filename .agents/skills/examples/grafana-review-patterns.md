# Grafana Review Patterns

Use these snippets as review anchors. Verify fields against the active CRDs
before committing implementation manifests.

## Operator Subscription Pattern

The CoP catalog uses this Subscription shape:

```yaml
apiVersion: operators.coreos.com/v1alpha1
kind: Subscription
metadata:
  name: grafana
spec:
  channel: v5
  installPlanApproval: Automatic
  name: grafana-operator
  source: community-operators
  sourceNamespace: openshift-marketplace
```

Review points:

- `community-operators` is a support-boundary decision, not a Red Hat product
  default.
- Verify channel `v5` exists in the active cluster catalog.
- Decide whether automatic approval is acceptable for the demo.
- Add Namespace and OperatorGroup in the local deployable overlay.

## Aggregate Overlay Pattern

The CoP aggregate overlay combines operator and instance resources and adds
Argo CD dry-run handling:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
commonAnnotations:
  argocd.argoproj.io/sync-options: SkipDryRunOnMissingResource=true
resources:
  - ../../base/operator
  - ../../base/instance
```

Review points:

- Prefer separate Applications when CRD readiness ordering is material.
- If using one aggregate Application, add sync waves and retries in the repo's
  Argo CD Application layer.
- Do not deploy a base that lacks namespace and OperatorGroup context.

## OAuth Proxy And Route Pattern

The CoP Grafana instance uses:

- OpenShift OAuth redirect reference on the Grafana service account
- a reencrypt Route to `grafana-service`
- OpenShift service serving certificate annotation
- injected CA bundle ConfigMap
- OAuth proxy sidecar with TokenReview and SubjectAccessReview permissions

Review points:

- Verify the OAuth proxy image source for the active OpenShift baseline.
- Replace placeholder session-secret handling.
- Review `openshift-sar` and delegated URL checks for the intended audience.
- Do not enable anonymous access unless the demo explicitly accepts it.

## Prometheus Datasource Pattern

Official Grafana docs require a `GrafanaDatasource` to include
`spec.datasource` and `spec.instanceSelector`. The CoP `user-app` overlay
adapts this for OpenShift by querying the OpenShift Thanos Querier with a
bearer token. In this repo, use the Grafana Operator `valuesFrom` field to
substitute the service-account token Secret into `secureJsonData`; do not rely
on Grafana pod environment variables being expanded inside datasource CRs.

```yaml
apiVersion: grafana.integreatly.org/v1beta1
kind: GrafanaDatasource
metadata:
  name: prometheus
spec:
  datasource:
    access: proxy
    isDefault: true
    jsonData:
      httpHeaderName1: Authorization
      tlsSkipVerify: true
    secureJsonData:
      httpHeaderValue1: "Bearer ${token}"
    type: prometheus
    url: https://thanos-querier.openshift-monitoring.svc.cluster.local:9091
  valuesFrom:
    - targetPath: secureJsonData.httpHeaderValue1
      valueFrom:
        secretKeyRef:
          name: grafana-auth-secret
          key: token
  instanceSelector:
    matchLabels:
      instance: grafana
```

Review points:

- Verify `grafana.integreatly.org/v1beta1` in the active CRD and confirm
  `spec.datasource`, `spec.instanceSelector`, and optional `spec.uid` with
  `oc explain grafanadatasource.spec`.
- Verify `instanceSelector.matchLabels` matches labels on the target
  `Grafana` resource.
- Verify `spec.valuesFrom.targetPath` points to the exact datasource field that
  contains the placeholder and that the referenced Secret key exists.
- Do not commit generated token data.
- Prefer the narrowest monitoring RBAC that supports the dashboard use case.
- Verify user workload monitoring before expecting application or model
  metrics.
- Verify a live query through Grafana's datasource API; synchronized CR status
  does not prove Prometheus authentication works.
- Patch namespace placeholders and ClusterRoleBinding names in downstream
  overlays.

## Dashboard Ownership Pattern

Keep dashboard content close to the metric owner:

```text
instance/components/
  openshift-monitoring-datasource/
  model-serving-dashboards/
  gpu-dashboards/
```

Review points:

- Official Grafana docs support GitOps-managed `GrafanaDashboard` resources
  with Argo CD; Argo CD syncs the CR and the operator syncs it into Grafana.
- Verify `spec.instanceSelector` and the selected dashboard source field
  (`json`, `configMapRef`, `grafanaCom`, `url`, `oci`, `gzipJson`, or
  `jsonnet`) against the active CRD.
- For same-namespace dashboards, omit `allowCrossNamespaceImport`.
- The Grafana skill owns deployment mechanics.
- The component skill owns metric meaning, dashboard panels, and demo claims.
- Dashboard resources must not claim unavailable metrics.
