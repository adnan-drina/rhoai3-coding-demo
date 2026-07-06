# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product baseline | `docs/PLATFORM_BASELINE.md` |
| Chapter title | Chapter 12. Managing observability |
| Chapter URL | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_openshift_ai/managing-observability_managing-rhoai |
| Documentation category | Administer |
| Retrieved date | 2026-06-10 |
| Sections used | 12.1 Enabling the observability stack; 12.2 Enable the observability dashboard in the UI; 12.3 Collecting metrics from user workloads; 12.4 Exporting metrics to external observability tools; 12.5 Viewing traces in external tracing platforms; 12.6 Accessing built-in alerts |

## Supporting Red Hat Sources

| Source | Role |
|--------|------|
| `docs/PLATFORM_BASELINE.md` | Active product baseline and documentation category index |
| Technology Preview Features Support Scope linked from the official chapter | Support posture context |
| Red Hat build of OpenTelemetry documentation linked from the official chapter | Supplemental instrumentation and OTLP behavior |
| Tempo Operator documentation linked from the official chapter | Supplemental Tempo query behavior |

## Source Boundaries

- Product configuration truth: official Red Hat OpenShift AI 3.4 chapter above.
- Support posture truth: Technology Preview support scope linked from the
  official chapter.
- Demo policy: observability is optional until an active demo step introduces
  it, and external exporter secrets are not committed.
- Verification: readonly `oc get`, `oc describe`, and port-forward checks
  listed in this skill.
- Not authoritative: upstream OpenTelemetry, Prometheus, Grafana, Jaeger, or
  Tempo documentation unless explicitly labeled as supplemental.

## Unresolved Or Environment-Specific Items

- Storage size, retention period, and replica count for the demo Prometheus and
  Tempo instances.
  Verification: choose values during active GitOps implementation based on
  available cluster resources and demo retention needs.
- External metrics or tracing endpoints.
  Verification: obtain approved receiver endpoint, protocol, and credential
  handling before adding exporter configuration.
- Whether to expose Tempo Query or Alertmanager through a route.
  Verification: prefer temporary port-forward examples unless the demo requires
  external access.
- RHOAI 3.4 sandbox compatibility for the generated monitoring stack:
  some clusters create the service-ca bundle as
  `ConfigMap/prometheus-web-tls-ca` while the generated `MonitoringStack`
  references `Secret/prometheus-web-tls-ca`. Keep the sync-hook pattern
  environment-specific and remove it when the product-generated stack creates
  the Secret natively or changes the reference.
- Perses dashboard access in demo persona workflows:
  the dashboard UI can require read access to Perses dashboard/datasource
  resources plus narrow access to the OpenShift monitoring Prometheus API. Keep
  this as least-privilege RBAC for the demo admin group, not broad
  cluster-admin access.
- Cluster Observability Operator compatibility:
  Stage 110 uses OLM `startingCSV` plus manual approval automation to install
  `cluster-observability-operator.v1.4.0` for the active RHOAI 3.4
  observability dashboard. This is an operator lifecycle compatibility hold,
  not an operand image pin. Do not patch the product-generated `Perses` CR
  image, generated `PersesDatasource` resources, copied CSVs, or
  operator-created observability Deployments as the normal fix. Comparing those
  values against the installed CSV `relatedImages` is diagnostic only.
