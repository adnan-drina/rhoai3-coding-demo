# Validation Checklist

Use this checklist when reviewing Grafana Operator documentation, GitOps
manifests, or live operations.

## Source And Baseline

- The task references the active OpenShift baseline in
  `docs/PLATFORM_BASELINE.md`.
- The Red Hat CoP catalog is used only as a local curation pattern.
- Official Grafana Operator docs and API reference are used for
  `Grafana`, `GrafanaDatasource`, and `GrafanaDashboard` custom resource
  behavior.
- Grafana Operator support posture, package name, channel, install mode, and
  custom resource fields are verified from the active OLM catalog, official
  Grafana Operator docs, and CRDs.
- OCP monitoring concepts are handled by `ocp-observability`.
- RHOAI model-serving dashboard semantics are handled by
  `rhoai-model-management-monitoring`.

## Manifest Review

- No committed Kustomize resource points directly to
  `github.com/redhat-cop/gitops-catalog`.
- Namespace, OperatorGroup, Subscription, channel, source, source namespace,
  and approval strategy are explicit and intentional.
- The Grafana Operator install namespace contains no conflicting
  `OperatorGroup`.
- `Grafana`, `GrafanaDatasource`, and `GrafanaDashboard` resources use verified
  API versions and fields.
- `GrafanaDatasource.spec.datasource` and `.spec.instanceSelector` are present,
  and `instanceSelector.matchLabels` matches the target `Grafana` labels.
- Datasource bearer tokens, API keys, or other Secret-backed values use
  `GrafanaDatasource.spec.valuesFrom` with an exact `targetPath` into the
  datasource field that contains the placeholder.
- The Grafana service account is explicitly present before token Secrets and
  RBAC bindings reference it. The rollout must not rely on
  `Grafana.spec.serviceAccount` creating the service account after Argo CD has
  already attempted dependent resources.
- `GrafanaDashboard.spec.instanceSelector` is present, and dashboard source is
  one of the installed CRD-supported fields such as `json`, `configMapRef`,
  `grafanaCom`, `url`, `oci`, `gzipJson`, or `jsonnet`.
- Cross-namespace dashboard or datasource import is disabled by omission unless
  `allowCrossNamespaceImport` is intentional and documented.
- Argo CD `SkipDryRunOnMissingResource=true` is used only when CRD ordering
  requires it.
- Argo CD sync waves separate operator, instance, datasource, and dashboard
  resources where ordering matters.
- Datasource and dashboard `resyncPeriod` values are deliberate. Use a shorter
  period for live demos where Grafana pod replacement must quickly repopulate
  its internal database.
- Route TLS, OAuth redirect annotations, service serving certificate
  annotations, and injected CA bundles are verified.
- OAuth proxy image and arguments are verified against the active OpenShift
  baseline and demo access model.
- Anonymous and basic-auth settings are disabled unless explicitly justified.
- RBAC for TokenReview, SubjectAccessReview, and monitoring access is least
  privilege for the demo.
- ClusterRoleBinding names are unique when multiple Grafana namespaces exist.
- `cluster-monitoring-view` is granted only when the Grafana service account
  needs OpenShift monitoring access.
- Session secrets, bearer tokens, API keys, datasource credentials, and
  generated service-account token data are not committed.
- Datasource URLs are internal cluster endpoints or approved external
  endpoints.
- Dashboard resources reference metrics that are actually produced by the
  active implementation.

## Read-Only Cluster Checks

Run only after the repo environment guard confirms the target cluster:

```bash
oc get clusterversion
oc get packagemanifest grafana-operator -n openshift-marketplace -o yaml
oc get subscription -A | grep -Ei 'grafana'
oc get csv -A | grep -Ei 'grafana'
oc get crd | grep -Ei 'grafana'
oc api-resources | grep -Ei 'grafana'
oc get grafana -A
oc get grafanadatasource -A
oc get grafanadashboard -A
oc get route -A | grep -Ei 'grafana'
oc get clusterrolebinding | grep -Ei 'grafana|cluster-monitoring-view'
oc get grafana grafana -n rhoai-demo-grafana -o jsonpath='{.status.conditions}'
oc get grafanadatasource prometheus -n rhoai-demo-grafana -o jsonpath='{.status.conditions}'
oc get grafanadashboard -n rhoai-demo-grafana -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.status.conditions}{"\n"}{end}'
```

For schema verification:

```bash
oc explain grafana.spec
oc explain grafanadatasource.spec
oc explain grafanadashboard.spec
```

For datasource and monitoring access:

```bash
oc get pods -n openshift-monitoring
oc get pods -n openshift-user-workload-monitoring
oc auth can-i get namespaces --as system:serviceaccount:<grafana_namespace>:grafana-sa
oc auth can-i get --raw=/api --as system:serviceaccount:<grafana_namespace>:grafana-sa
```

## Live Operation Review

- The repo-local OpenShift safety guard is used before any `oc` or `kubectl`
  command that touches the cluster.
- Operator installation, Grafana instance changes, route exposure, RBAC,
  datasource changes, dashboard changes, and secret handling have explicit
  user approval.
- Argo CD-managed resources are not also managed with direct `oc apply -k`
  unless the exception is documented.
- Grafana dashboards are not presented in the demo before metrics and
  datasource checks pass.
- Datasource checks include a live Grafana datasource API query, not only
  `DatasourceSynchronized=True`.
- Dashboard checks include representative Prometheus queries for the metrics
  shown by each dashboard. A dashboard that loads with "Datasource not found"
  or empty panels is not demo-ready.
- Community Operator upgrade behavior is understood before using automatic
  approval.

## Fail Conditions

Stop and ask for verification if:

- the active catalog does not expose `grafana-operator`
- the selected Grafana Operator channel is unavailable
- a manifest includes unverified `grafana.integreatly.org` fields
- OAuth, route, or RBAC settings would expose dashboards more broadly than
  intended
- generated token data, session secrets, API keys, or datasource credentials
  would be committed
- a dashboard depends on metrics that are not produced or scraped
- a live operation targets the wrong cluster or bypasses the OpenShift safety
  guard
