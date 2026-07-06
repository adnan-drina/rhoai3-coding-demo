---
name: ocp-distributed-tracing
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "ocp"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when documenting, reviewing, or rebuilding Red Hat OpenShift distributed
  tracing platform on OpenShift from official Red Hat documentation: Tempo
  Operator installation, TempoStack, TempoMonolithic, object storage secrets,
  tenants, read/write RBAC, gateway authentication and authorization, Jaeger
  UI, distributed tracing UI plugin, TempoStack sizing, retention, receiver
  TLS, query RBAC, monitoring and alerts, Tempo Operator upgrades, removal,
  and must-gather troubleshooting. Do NOT use for OpenTelemetry Collector or
  workload instrumentation configuration; use ocp-opentelemetry. Do NOT use
  for generic OCP observability, logging, or default monitoring posture; use
  ocp-observability. Do NOT invent Tempo CR fields, storage settings, tenant
  configuration, or Technology Preview support posture.
---

# OCP Distributed Tracing

Use this skill to ground Red Hat OpenShift distributed tracing platform work in
the official product documentation pinned in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority. This skill captures Red Hat OpenShift
distributed tracing platform 3.9 and adapts it to the repo's OCP observability
skill model.

Distributed tracing is adjacent to, but not the same as, OpenTelemetry
collection. Use this skill for Tempo Operator, `TempoStack`,
`TempoMonolithic`, trace storage, tenants, trace query/read/write RBAC,
Jaeger UI, distributed tracing UI plugin, and Tempo troubleshooting. Use
`ocp-opentelemetry` for sending telemetry to Tempo.

## Demo Distributed Tracing Posture

For this AWS-hosted RHOAI demo:

- Prefer `TempoStack` for GitOps-managed distributed tracing back ends.
- Treat `TempoMonolithic` as Technology Preview and use it only for small
  demonstrations, tests, or proof-of-concept paths where non-production status
  is explicit.
- Do not deploy a `TempoStack` without object storage, object storage
  credentials, tenants, and tenant read/write RBAC.
- Do not claim tracing is available until a backend, Collector/export path,
  tenant authorization, and validation path are implemented.
- Keep object storage credentials, cloud role details, and trace data samples
  out of Git.
- Use Red Hat build of OpenTelemetry to forward traces to Tempo; do not
  duplicate Collector configuration in this skill.
- Treat Jaeger UI and distributed tracing UI plugin exposure as access-control
  surfaces that require explicit tenant and route review.

## Product Model

Use the official docs to frame:

- Distributed tracing records the path of requests through microservices and
  presents them as traces made of spans.
- A span represents a logical unit of work with operation name, start time,
  duration, and potentially tags and logs.
- Distributed tracing supports monitoring distributed transactions,
  optimizing performance and latency, and root cause analysis.
- Red Hat build of OpenTelemetry forwards traces to `TempoStack`.
- The distributed tracing UI plugin of the Cluster Observability Operator can
  provide a UI for distributed tracing.
- `TempoStack` is the scalable Tempo deployment path and is configured to
  receive Jaeger Thrift over HTTP and OTLP.
- `TempoMonolithic` runs Tempo components in one container, does not scale
  horizontally, and is Technology Preview in the captured docs.

## Workflow

1. Confirm the active OCP and distributed tracing baselines in
   `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Identify whether the task concerns:
   - Tempo Operator installation or upgrade
   - object storage prerequisites and storage secrets
   - tenant definition and read/write RBAC
   - `TempoStack` installation, sizing, retention, gateway, Jaeger UI, or
     monitoring
   - `TempoMonolithic` Technology Preview demo/test usage
   - receiver TLS, query RBAC, taints, tolerations, monitoring, or alerts
   - distributed tracing UI plugin integration
   - Tempo removal or troubleshooting
   - OpenTelemetry Collector forwarding, which belongs in `ocp-opentelemetry`
4. Verify API versions, CRDs, fields, namespaces, Operator channel, object
   storage settings, secrets, RBAC, tenants, routes, TLS, and Technology
   Preview posture before authoring manifests.
5. For live operations, use the repo environment guard and pair this skill with
   `env-troubleshoot`, `env-manage-resources`, or `env-deploy-and-evaluate`.
6. Validate the output with `references/validation-checklist.md`.

## Related Skills

- Use `ocp-opentelemetry` for OpenTelemetry Collector, `Instrumentation`,
  workload annotations, and telemetry forwarding into Tempo.
- Use `ocp-observability` for the broad OCP observability model, default
  monitoring stack, logging overview, and COO boundary.
- Use `rhoai-observability` for RHOAI observability stack enablement and
  dashboard behavior.
- Use `rhoai-guardrails-safety` for guardrails-specific spans, detector
  metrics, and guardrails telemetry semantics.
- Use `project-gitops-authoring` for repo-specific GitOps implementation.
- Use `project-manifest-review` for structural and security review of
  Kubernetes and OpenShift manifests.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/distributed-tracing-review-patterns.md`
