# Validation Checklist

Use this checklist when reviewing OCP observability documentation, manifests,
or live operations.

## Source And Baseline

- The task references the active OCP baseline in `docs/PLATFORM_BASELINE.md`.
- OCP-level observability claims are traced to the official OCP Observability
  overview.
- OCP monitoring claims are traced to the official OCP Monitoring page or the
  separate Monitoring stack for Red Hat OpenShift documentation.
- OCP logging claims are traced to the official OCP Logging page or the
  separate Red Hat OpenShift Logging documentation.
- COO claims are traced to the official OCP Cluster Observability Operator page
  or the standalone COO documentation.
- RHOAI observability, model monitoring, and TrustyAI monitoring are handled by
  the relevant `rhoai-*` skills.

## Manifest Review

- Monitoring, logging, and COO Operator installation channels, namespaces,
  subscriptions, and install modes are verified from product docs or the active
  cluster catalog.
- Generated operand images, CSV `relatedImages`, copied CSVs, and
  operator-created observability Deployments are not committed or patched as
  GitOps desired state.
- `ServiceMonitor`, `PodMonitor`, `PrometheusRule`, `AlertmanagerConfig`, and
  related monitoring resources use verified API versions and fields.
- Core platform Alertmanager notification routing is configured through the
  documented `openshift-monitoring/alertmanager-main` Secret or console
  workflow; receivers must contain an actual supported integration, not only a
  receiver name.
- User workload monitoring ConfigMaps and namespace assumptions are verified
  before authoring.
- Log collector, log store, log forwarder, output, retention, and visualization
  fields are verified from Red Hat OpenShift Logging docs or active CRDs.
- COO resources use verified API versions and fields.
- RBAC, service accounts, SCCs, cluster roles, and route exposure are reviewed
  as platform-sensitive resources.
- External log, trace, metric, and telemetry endpoints are approved and do not
  expose secrets in Git.
- Retention and storage settings are explicit where they affect cost or data
  lifecycle.
- Alert names, thresholds, and routing policies are tied to implemented
  resources and documented operational intent.

## Read-Only Cluster Checks

Run only after the repo environment guard confirms the target cluster:

```bash
oc get clusterversion
oc get co monitoring
oc get pods -n openshift-monitoring
oc get pods -n openshift-user-workload-monitoring
oc get configmap cluster-monitoring-config -n openshift-monitoring -o yaml
oc get configmap user-workload-monitoring-config -n openshift-user-workload-monitoring -o yaml
oc get prometheusrule -A
oc get servicemonitor -A
oc get podmonitor -A
oc get alertmanagerconfig -A
oc get secret alertmanager-main -n openshift-monitoring -o yaml
oc get subscription -A | grep -Ei 'logging|observability|monitoring'
oc get csv -A | grep -Ei 'logging|observability|monitoring'
oc api-resources | grep -Ei 'monitoring|observability|logging|loki|opentelemetry'
oc get crd | grep -Ei 'monitoring|observability|logging|loki|opentelemetry'
```

For schema verification:

```bash
oc explain servicemonitor.spec
oc explain podmonitor.spec
oc explain prometheusrule.spec
oc explain alertmanagerconfig.spec
```

Use component-specific `oc explain` commands only after the relevant CRDs are
confirmed on the cluster.

For platform Alertmanager notification routing, validate the rendered config
with Alertmanager tooling and verify the integration count:

```bash
oc -n openshift-monitoring exec alertmanager-main-0 -c alertmanager -- \
  amtool config routes show --alertmanager.url http://localhost:9093
oc -n openshift-monitoring exec prometheus-k8s-0 -c prometheus -- \
  curl -s 'http://localhost:9090/api/v1/query?query=cluster%3Aalertmanager_integrations%3Amax' | jq
```

## Live Operation Review

- The repo-local OpenShift safety guard is used before any `oc` or `kubectl`
  command that touches the cluster.
- Operator installation, monitoring stack changes, user workload monitoring
  enablement, logging output changes, COO changes, RBAC changes, external sink
  changes, and credential changes have explicit user approval.
- OCP platform monitoring is not confused with RHOAI observability or TrustyAI
  monitoring.
- Argo CD-managed resources are not also managed with direct `oc apply -k`
  unless the exception is documented.
- Secrets, tokens, external endpoints, and sensitive log samples are not
  committed to Git.

## Fail Conditions

Stop and ask for verification if:

- the documentation version does not match `docs/PLATFORM_BASELINE.md`
- a detailed monitoring, logging, or COO claim is based only on an OCP overview
  page
- a manifest includes unverified monitoring, logging, COO, OpenTelemetry,
  tracing, Network Observability, or Power monitoring fields
- credentials, tokens, customer data, or sensitive log content would be
  committed to Git
- a dashboard, alert, log pipeline, trace, or metric is claimed without
  implementation and validation evidence
- a live operation targets the wrong cluster or bypasses the OpenShift safety
  guard
