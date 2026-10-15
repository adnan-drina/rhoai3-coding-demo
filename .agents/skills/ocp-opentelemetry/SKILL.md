---
name: ocp-opentelemetry
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: ocp
  docs-version: "4.22"
  skill-group: "OpenShift Platform"
description: >
  Use when reviewing or changing the Red Hat build of OpenTelemetry in this
  repo: the opentelemetry-product Subscription in Stage 010
  observability-operators/opentelemetry/, its channel bound in
  check_operator_policy, the RHOAI-generated data-science-collector in
  redhat-ods-monitoring, or the OTLP round trip in
  stages/010-openshift-ai-platform-foundation/validate.sh. Do NOT use for Tempo storage and trace
  read/write RBAC (use ocp-distributed-tracing) or the DSCI monitoring block
  (use rhoai-observability).
---

# OCP OpenTelemetry

Thin skill: repo decisions and pitfalls here, product behavior in the linked
Red Hat build of OpenTelemetry 3.11 sections. Detailed record:
`gitops/stages/010-openshift-ai-platform-foundation/010-observability-operators/README.md`.

## When to use

- A change touches `010-observability-operators/opentelemetry/` or the
  `opentelemetry-product` entries in `check_operator_policy` in `scripts/lib.sh`.
- Someone proposes an own `OpenTelemetryCollector`, `Instrumentation` or
  auto-instrumentation annotation.
- The collector rejects spans or `stages/010-openshift-ai-platform-foundation/validate.sh` fails.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Operator only: namespace `openshift-opentelemetry-operator` (cluster-monitoring label), AllNamespaces OperatorGroup `opentelemetry-product`, Subscription `opentelemetry-product`, `stable`, Automatic | `010-observability-operators/opentelemetry/` | [Installing (CLI)][install] |
| Rolling `stable` bounded fail-closed: minimum `0.158.0-2` (operator 0.158 = product 3.11) | `check_operator_policy` in `scripts/lib.sh` | [Installing (CLI)][install] |
| No collector or `Instrumentation` in Git: RHOAI generates `OpenTelemetryCollector` `data-science-collector` in `redhat-ods-monitoring` from the DSCI | `gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-platform/dsc-init.yaml` | [Installing (CLI)][install] |
| Collector SA gets Tempo write access from a repo ClusterRole (not in the generated RBAC) | `010-observability-operators/trace-roles/` | see `ocp-distributed-tracing` |
| No external telemetry sinks or exporters | — | — |

Paths are relative to `gitops/stages/010-openshift-ai-platform-foundation/` unless they start with `gitops/` or `scripts/`.

## Procedure

1. Change the Subscription and policy minimum together in Git; never patch
   the generated collector (the RHOAI operator reconciles it).
2. Deploy and validate:
   `./stages/010-openshift-ai-platform-foundation/deploy.sh`,
   `./stages/010-openshift-ai-platform-foundation/validate.sh` (CSV
   `Succeeded`, `check_operator_policy --verify`) and
   `./stages/010-openshift-ai-platform-foundation/validate.sh`
   (writer SubjectAccessReview, one OTLP span read back from Tempo).
3. By hand, after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get subscription,csv -n openshift-opentelemetry-operator
   oc get opentelemetrycollector -n redhat-ods-monitoring
   ```

## Pitfalls

- A new operator minor on `stable` makes `deploy.sh` fail closed until the
  policy minimum and the map's `opentelemetry` docs_version are updated.
- The repo OperatorGroup name differs from the guide's example name; behavior
  is the same (README alignment table).
- Stage 040 GenAI Studio tracing is a separate, opt-in Technology Preview
  capability (`stages/040-governed-models-as-a-service/README.md`), not this
  collector.

## Official documentation (Red Hat build of OpenTelemetry 3.11)

| Topic | Section |
|---|---|
| Install | [Installing the Red Hat build of OpenTelemetry][install] |
| Architecture (OCP 4.22 entry) | [OpenTelemetry architecture][arch] |

## Related skills

`ocp-distributed-tracing`, `ocp-observability`, `rhoai-observability`.

[install]: https://docs.redhat.com/en/documentation/red_hat_build_of_opentelemetry/3.11/html-single/installing_red_hat_build_of_opentelemetry/index#install-otel
[arch]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/red_hat_build_of_opentelemetry/index#otel-architecture
