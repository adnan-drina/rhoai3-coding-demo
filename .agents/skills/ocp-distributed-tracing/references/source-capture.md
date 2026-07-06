# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product family | Red Hat OpenShift distributed tracing platform |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Documentation version | 3.9 |
| Documentation landing page | https://docs.redhat.com/en/documentation/red_hat_openshift_distributed_tracing_platform/3.9 |
| Capture date | 2026-06-10 |

| Guide | Source URL | Sections captured |
|-------|------------|-------------------|
| About distributed tracing | https://docs.redhat.com/en/documentation/red_hat_openshift_distributed_tracing_platform/3.9/html/about_distributed_tracing/distr-tracing-tempo-architecture | key concepts, traces, spans, use cases, features, architecture, OpenTelemetry and UI plugin handoffs |
| Installing the distributed tracing platform | https://docs.redhat.com/en/documentation/red_hat_openshift_distributed_tracing_platform/3.9/html/installing_distributed_tracing/distr-tracing-tempo-installing | Tempo Operator install, object storage setup, tenant permissions, `TempoStack`, `TempoMonolithic`, network policies |
| Configuring the distributed tracing platform | https://docs.redhat.com/en/documentation/red_hat_openshift_distributed_tracing_platform/3.9/html/configuring_distributed_tracing/distr-tracing-tempo-configuring | Tempo Operator configuration, back-end storage, `TempoStack` parameters, sizing, query options, UI plugin, Jaeger UI Monitor tab, receiver TLS, query RBAC, taints, tolerations, metrics, alerts |
| Upgrading distributed tracing | https://docs.redhat.com/en/documentation/red_hat_openshift_distributed_tracing_platform/3.9/html/upgrading_distributed_tracing/distr-tracing-tempo-updating | Tempo Operator version upgrade management |
| Removing distributed tracing | https://docs.redhat.com/en/documentation/red_hat_openshift_distributed_tracing_platform/3.9/html/removing_distributed_tracing/distr-tracing-tempo-removing | `TempoStack` removal and Tempo Operator removal boundary |
| Troubleshooting distributed tracing | https://docs.redhat.com/en/documentation/red_hat_openshift_distributed_tracing_platform/3.9/html/troubleshooting_distributed_tracing/distr-tracing-tempo-troubleshooting | Tempo diagnostics and must-gather troubleshooting |
| Release notes for distributed tracing | https://docs.redhat.com/en/documentation/red_hat_openshift_distributed_tracing_platform/3.9/html/release_notes_for_distributed_tracing/distr-tracing-rn | documented-feature support boundary and release context |

## Captured Product Objects

- Tempo Operator
- Operator namespace `openshift-tempo-operator`
- Operator subscription name `tempo-product`
- Operator channel `stable`
- `TempoStack` custom resources
- `TempoMonolithic` custom resources
- `tempo.grafana.com/v1alpha1` examples
- Object storage Secrets
- Tenants in OpenShift authentication mode
- Read and write RBAC for trace tenants
- Tempo Gateway authentication and authorization
- Jaeger UI route and distributed tracing UI plugin
- Tempo metrics and alerting resources
- Tempo must-gather diagnostics

## Source Boundaries

Do not infer Tempo CR fields, storage modes, tenant configuration, TLS
settings, monitoring settings, or UI plugin behavior from upstream Grafana
Tempo docs. Upstream Tempo can explain concepts, but Red Hat product behavior,
supported fields, Operator channel, and support posture must come from Red Hat
documentation or active cluster schema.

The release notes state that only supported features are documented.
Undocumented distributed tracing features are unsupported unless Red Hat
documentation for the active baseline says otherwise.

`TempoMonolithic` is captured as Technology Preview. Do not present it as
production supported.

Object storage credentials and cloud identity details are sensitive. Do not
commit real secret values, cloud role ARNs, storage keys, or trace payloads.

## Related Official Sources To Add Later

- Version-specific Red Hat OpenShift Cluster Observability Operator docs when
  the distributed tracing UI plugin becomes active
- Version-specific Red Hat build of OpenTelemetry docs when trace forwarding
  becomes active
- Version-specific OpenShift Data Foundation docs when object bucket claims are
  used for Tempo storage
- Version-specific cloud-provider docs only as implementation examples after
  Red Hat product behavior is captured
