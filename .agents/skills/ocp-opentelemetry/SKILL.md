---
name: ocp-opentelemetry
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "ocp"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when documenting, reviewing, or rebuilding Red Hat build of
  OpenTelemetry on OpenShift from official Red Hat documentation:
  OpenTelemetry Operator installation, OpenTelemetryCollector custom
  resources, Collector deployment modes, receivers, processors, exporters,
  connectors, extensions, Instrumentation custom resources,
  auto-instrumentation annotations, metrics integration with the OpenShift
  monitoring stack, telemetry forwarding, telemetry receiving, Collector
  metrics, and troubleshooting. Do NOT use for generic OCP observability
  overview, logging, or default monitoring posture; use ocp-observability. Do
  NOT use for RHOAI-specific observability stack behavior or guardrails
  telemetry semantics; use the relevant rhoai-* skill. Do NOT invent
  OpenTelemetry Collector component fields or Technology Preview support
  posture from upstream docs.
---

# OCP OpenTelemetry

Use this skill to ground Red Hat build of OpenTelemetry work on OpenShift in
the official product documentation pinned in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority. This skill captures the Red Hat build
of OpenTelemetry 3.9 product docs and adapts them to the repo's OCP platform
skill model.

OpenTelemetry is adjacent to, but not the same as, OCP default monitoring,
logging, or RHOAI observability. Use this skill for the Red Hat build of
OpenTelemetry Operator, Collector, and instrumentation resources. Use
`ocp-observability` for the broader OCP observability model.

## Demo OpenTelemetry Posture

For this AWS-hosted RHOAI demo:

- Treat OpenTelemetry as a platform observability integration layer for
  traces, metrics, and logs from demo workloads, guardrails, MaaS, and
  application components.
- Keep Operator installation, Collector instances, `Instrumentation`
  resources, RBAC, routes, secrets, and service accounts GitOps-managed once
  active implementation artifacts exist.
- Prefer one clearly named demo Collector namespace unless a component needs a
  dedicated Collector for isolation, tenancy, or routing.
- Do not claim telemetry delivery, storage, querying, dashboards, or alerts
  unless the receiving backend and validation path are implemented.
- Do not commit backend credentials, bearer tokens, API keys, or sensitive
  telemetry samples.
- Treat Technology Preview Collector components and auto-instrumentation modes
  as demo-only unless a future baseline documents a different support posture.

## Product Model

Use the official docs to frame:

- Red Hat build of OpenTelemetry is based on the upstream OpenTelemetry
  project and provides support for deploying and managing the Collector and
  simplifying workload instrumentation.
- The Collector can receive, process, and forward telemetry data in multiple
  formats and provides a unified path for metrics, traces, and logs.
- The Collector is a telemetry pipeline made from receivers, processors,
  exporters, connectors, and extensions.
- The `OpenTelemetryCollector` custom resource uses `opentelemetry.io/v1beta1`
  in the captured examples.
- Supported Collector deployment modes include `deployment`, `daemonset`,
  `statefulset`, and `sidecar`.
- OpenTelemetry does not guarantee telemetry delivery and does not provide
  built-in storage or query capabilities.
- Collector metrics require user-defined project monitoring when scraped by
  the OpenShift monitoring stack.

## Workflow

1. Confirm the active OCP and Red Hat build of OpenTelemetry baselines in
   `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Identify whether the task concerns:
   - Operator installation or upgrade
   - Collector namespace, mode, pipeline, service account, RBAC, or SCC
   - Collector receivers, processors, exporters, connectors, or extensions
   - `Instrumentation` custom resources and injection annotations
   - metrics integration with Prometheus, `ServiceMonitor`, or `PodMonitor`
   - telemetry forwarding to TempoStack, LokiStack, AWS, Google Cloud, or
     third-party systems
   - Collector diagnostics, logs, metrics, or must-gather
   - RHOAI-specific telemetry semantics, which belong in the relevant
     `rhoai-*` skill
4. Verify API versions, CRDs, fields, namespaces, Operator channel, RBAC,
   service accounts, secrets, endpoints, and Technology Preview posture before
   authoring manifests.
5. For live operations, use the repo environment guard and pair this skill with
   `env-troubleshoot`, `env-manage-resources`, or `env-deploy-and-evaluate`.
6. Validate the output with `references/validation-checklist.md`.

## Related Skills

- Use `ocp-observability` for the broad OCP observability model, default
  monitoring stack, logging overview, and COO boundary.
- Use `ocp-distributed-tracing` for Tempo Operator, `TempoStack`,
  `TempoMonolithic`, trace tenants, query RBAC, Jaeger UI, and distributed
  tracing backend behavior.
- Use `rhoai-observability` for RHOAI observability stack enablement and
  dashboard behavior.
- Use `rhoai-guardrails-safety` for guardrails-specific OpenTelemetry fields,
  spans, detector metrics, and guardrails telemetry semantics.
- Use `rhoai-maas-governance` for MaaS usage export and telemetry behavior.
- Use `project-gitops-authoring` for repo-specific GitOps implementation.
- Use `project-manifest-review` for structural and security review of
  Kubernetes and OpenShift manifests.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/opentelemetry-review-patterns.md`
