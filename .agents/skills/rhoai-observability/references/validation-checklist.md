# Validation Checklist

Use this checklist before accepting observability GitOps, documentation, or
runbook changes.

## Source And Scope

- The work references the active baseline in `docs/PLATFORM_BASELINE.md`.
- The official chapter URL uses the active `/3.4/` baseline path.
- Technology Preview status is called out in README, operation, or review
  material that enables this capability.
- Operator logs and audit records remain in `rhoai-logs-and-audit-records`.
- Model performance, fairness, drift, or TrustyAI monitoring remains outside
  this skill.

## Stack Enablement Review

- Required Operators are listed before enabling the stack:
  Cluster Observability Operator, Tempo Operator, and Red Hat build of
  OpenTelemetry.
- `DSCInitialization` uses the served storage API version for the active
  baseline. On current RHOAI 3.4 clusters this is
  `dscinitialization.opendatahub.io/v2`; verify with the CRD before editing.
- `DSCInitialization.spec.monitoring.managementState` is `Managed`.
- Monitoring namespace is explicitly set, normally `redhat-ods-monitoring`.
- Metrics storage, retention, and replicas are intentional for the demo
  environment. Do not use fields absent from the active DSCI schema; for
  example, `spec.monitoring.metrics.resources` is not present in the v2 schema.
- Metrics are not left empty; `MonitoringStackAvailable=True` is required for
  the dashboard to load real metrics-backed components.
- Trace storage backend is one of the documented values: `pv`, `s3`, or `gcs`.
- Traces are not left empty; `TempoAvailable=True` and
  `OpenTelemetryCollectorAvailable=True` are required before trace visibility
  is claimed.
- `PersesAvailable=True` is validated on the RHOAI `Monitoring` service before
  accepting the dashboard as working.
- If the generated `MonitoringStack` references
  `Secret/prometheus-web-tls-ca`, verify the Secret exists and contains
  `service-ca.crt`. In current demo environments, GitOps may need a sync hook
  that mirrors the service-ca injected `ConfigMap/prometheus-web-tls-ca` into
  the expected Secret without committing certificate material.
- Verify the Perses operator can reach the RHOAI Perses backend. If OLM installs
  the Perses operator outside the namespace allowed by product-generated
  NetworkPolicies, add a narrow NetworkPolicy that permits only the installed
  Perses operator namespace and pod selector.
- Verify the Cluster Observability Operator lifecycle policy before debugging
  operand images. For the active RHOAI 3.4 demo, the expected fresh-environment
  Subscription state is `installPlanApproval=Manual`,
  `startingCSV=cluster-observability-operator.v1.4.0`, and
  `status.installedCSV=cluster-observability-operator.v1.4.0`.
- Validate the installed CSV from the owning Subscription. Do not use copied
  CSVs from all-namespace installs or display-name matches as authoritative
  compatibility checks.
- If the RHOAI-generated `Perses` CR server image appears incompatible with the
  installed Perses operator, treat it as an operator/RHOAI compatibility
  mismatch. Do not pin or patch `Perses.spec.image` as the durable fix; align
  the Cluster Observability Operator lifecycle policy or wait for a product
  controller fix.
- If `Monitoring.status.phase` is `Not Ready` only because the generated
  `tempo-datasource` fails v1alpha2 validation on
  `spec.client.tls.caCert.namespace`, do not hand-edit the generated datasource.
  Treat it as an operator compatibility issue and either align the COO version
  with the RHOAI release or wait for an RHOAI controller fix.
- If observability operator pods fail only with API timeout or leader-election
  errors after control-plane instability, recreate the failed pods after
  ClusterOperators are healthy and rerun validation. Do not patch generated
  Deployments or images to resolve transient pod state.
- External exporter endpoints are placeholders unless approved endpoints exist.

## Dashboard Review

- `OdhDashboardConfig.spec.dashboardConfig.observabilityDashboard` is set to
  `true` only after the stack is enabled.
- The resource is reviewed in the OpenShift AI application namespace, normally
  `redhat-ods-applications`.
- User-facing docs describe the menu as "Observe & monitor".
- The demo RHOAI admin group can list/watch Perses dashboards and datasources
  and can access the `prometheuses/api/k8s` subresource in
  `openshift-monitoring`; Perses query POSTs require `create` on that
  subresource.

## User Workload Metrics Review

- `monitoring.opendatahub.io/scrape: 'true'` is applied under the workload pod
  template labels.
- The workload exposes metrics before the scrape label is added.
- Operator-managed workloads are not modified with the scrape label.
- Prometheus access is documented through route or temporary port-forward.

## Metrics And Traces Review

- Metrics exporters use documented `type` values: `otlp` or
  `prometheusremotewrite`.
- Exporter names avoid reserved values such as `prometheus` and `otlp/tempo`.
- OTLP endpoints use port `4317` for gRPC or `4318` for HTTP when applicable.
- Trace-producing applications are instrumented before trace visibility is
  claimed.
- Tempo Query access uses a route or port-forward only when intentionally
  required.

## Alerts Review

- Alertmanager is treated as internal by default.
- Built-in alert access uses the Alertmanager service in
  `redhat-ods-monitoring` and port `9093`.
- Port-forward commands are documented as temporary operator access.

## Static Checks

Run the repo whitespace check and the focused stale-marker search from
`project-rhoai-doc-chapter-skill-authoring` against this skill directory.
