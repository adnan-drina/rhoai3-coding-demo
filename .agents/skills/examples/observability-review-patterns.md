# Observability Review Patterns

These examples are review patterns, not copy-paste manifests. The OCP
observability overview pages do not provide enough schema detail for full
monitoring, logging, or COO implementation. Verify separate Red Hat docs and
active cluster CRDs before committing resources.

## Source Boundary Review

Use this decision flow:

| Task | Skill |
|------|-------|
| Explain OCP observability components and value | `ocp-observability` |
| Review default platform monitoring posture | `ocp-observability` |
| Review user workload monitoring intent | `ocp-observability` plus Monitoring stack docs or active CRDs |
| Review logging collection, visualization, forwarding, or storage intent | `ocp-observability` plus Red Hat OpenShift Logging docs or active CRDs |
| Review COO purpose or high-level positioning | `ocp-observability` |
| Configure RHOAI observability stack | `rhoai-observability` |
| Review deployed model metrics or Grafana dashboards | `rhoai-model-management-monitoring` |
| Review TrustyAI drift, bias, or fairness monitoring | `rhoai-monitoring-trustyai` |
| Author GitOps manifests | `project-gitops-authoring` |
| Review manifest correctness and security posture | `project-manifest-review` |
| Deploy or troubleshoot against a live cluster | relevant `env-*` skill plus the OpenShift safety guard |

## Read-Only Discovery Pattern

After the OpenShift safety guard confirms the target cluster:

```bash
oc get co monitoring
oc get pods -n openshift-monitoring
oc get pods -n openshift-user-workload-monitoring
oc get subscription -A | grep -Ei 'logging|observability|monitoring'
oc get csv -A | grep -Ei 'logging|observability|monitoring'
oc api-resources | grep -Ei 'monitoring|observability|logging|loki|opentelemetry'
oc get crd | grep -Ei 'monitoring|observability|logging|loki|opentelemetry'
```

Review points:

- Discover installed Operators and exposed APIs before authoring manifests.
- Do not assume non-monitoring observability component versions from OCP 4.20
  alone.
- Do not assume upstream Prometheus, Loki, OpenTelemetry, or tracing behavior
  is Red Hat product behavior until verified.

## README Claim Review

Use this pattern when reviewing a demo README:

| README claim | Required source | Required project evidence |
|--------------|-----------------|---------------------------|
| OCP has a default monitoring stack | OCP Monitoring docs | None for platform statement; live validation if demo depends on it |
| A demo workload is scraped by user workload monitoring | Monitoring stack docs or CRDs | GitOps resource and validation command |
| A log pipeline forwards app logs externally | Red Hat OpenShift Logging docs or CRDs | GitOps resource, approved sink, and no committed credentials |
| COO provides a custom monitoring stack | OCP COO overview and standalone COO docs | COO manifests and validation command |
| RHOAI dashboard shows model observability | RHOAI docs | RHOAI observability implementation and validation |

## Implementation Guard

Before accepting an observability manifest, check:

- Which product documentation proves the API and field.
- Whether the API is installed on the active cluster.
- Whether the namespace is operator-managed or project-managed.
- Whether the resource introduces credentials, external endpoints, or data
  retention cost.
- Whether the README and operations docs describe only implemented behavior.
