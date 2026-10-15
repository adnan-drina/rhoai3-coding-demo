---
name: ocp-distributed-tracing
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: ocp
  docs-version: "4.22"
  skill-group: "OpenShift Platform"
description: >
  Use when reviewing or changing the Tempo Operator (distributed tracing
  platform) in this repo: the tempo-product Subscription in Stage 010
  observability-operators/tempo/, the trace reader/writer ClusterRoles in
  trace-roles/, the RHOAI-generated TempoMonolithic tenant
  redhat-ods-monitoring, or trace read-back failures in
  stages/010-openshift-ai-platform-foundation/validate.sh. Do NOT use for the collector and
  instrumentation (use ocp-opentelemetry) or the DSCI traces block (use
  rhoai-observability).
---

# OCP distributed tracing

Thin skill: repo decisions and pitfalls here, product behavior in the linked
Red Hat OpenShift distributed tracing platform 3.11 sections. Detailed record:
`gitops/stages/010-openshift-ai-platform-foundation/010-observability-operators/README.md`.

## When to use

- A change touches `010-observability-operators/tempo/` or `trace-roles/`.
- Someone proposes a `TempoStack`, object storage for traces, or wider trace
  read access.
- Spans are rejected, unauthorized, or cannot be read back.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Operator only: namespace `openshift-tempo-operator` (cluster-monitoring label), AllNamespaces OperatorGroup, Subscription `tempo-product`, `stable`, Automatic | `010-observability-operators/tempo/` | [Installing the Tempo Operator][install] |
| Rolling `stable` bounded fail-closed: minimum `0.22.0-2` (operator 0.22 = product 3.11) | `check_operator_policy` in `scripts/lib.sh` | [Installing the Tempo Operator][install] |
| No `TempoStack`/`TempoMonolithic` in Git: RHOAI generates a `TempoMonolithic` in `redhat-ods-monitoring` (multitenancy `openshift`, tenant `redhat-ods-monitoring`), PV storage, retention `2160h0m0s` | `gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-platform/dsc-init.yaml` | [Configuring Tempo][configure] |
| Read access: ClusterRole `rhoai-monitoring-traces-reader` (`get` on `tempo.grafana.com` / tenant / `traces`) bound to group `rhods-admins` only | `trace-roles/tempo-traces-reader-*.yaml` | [Configuring query RBAC][query-rbac] |
| Write access: ClusterRole `rhoai-monitoring-traces-writer` (`create`) bound to SA `redhat-ods-monitoring/data-science-collector-collector`; not in the 3.11 docs (upstream-backed deviation, recorded in the README) | `trace-roles/tempo-traces-writer-*.yaml` | [Configuring Tempo][configure] |
| No object storage secret (PV backend) | — | [Configuring Tempo][configure] |

Paths are relative to `gitops/stages/010-openshift-ai-platform-foundation/010-observability-operators/` unless they start with `gitops/` or `scripts/`.

## Procedure

1. Change the Subscription, policy minimum and trace roles in Git; never
   patch the generated `TempoMonolithic`.
2. Deploy and validate:
   `./stages/010-openshift-ai-platform-foundation/deploy.sh`,
   `./stages/010-openshift-ai-platform-foundation/validate.sh` and
   `./stages/010-openshift-ai-platform-foundation/validate.sh`
   (SubjectAccessReview for `create` as the collector SA, then one span
   written and read back by trace ID through the `tempo-datasource`).
3. By hand, after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get subscription,csv -n openshift-tempo-operator
   oc get tempomonolithic -n redhat-ods-monitoring
   oc get clusterrolebinding rhoai-monitoring-traces-writer rhoai-monitoring-traces-reader -o wide
   ```

## Pitfalls

- The writer binding names a service account created later by the
  OpenTelemetry Operator; a binding to a missing subject is valid, so check
  the SubjectAccessReview, not the binding.
- The guide's query RBAC example binds `system:authenticated`; the repo
  narrows reads to `rhods-admins` on purpose. Do not widen it casually.
- A new operator minor on `stable` fails `deploy.sh` closed until the policy
  minimum and the map's `distributed_tracing` docs_version are updated.

## Official documentation (distributed tracing platform 3.11)

| Topic | Section |
|---|---|
| Install | [Installing the Tempo Operator][install] |
| Configure | [Configuring Tempo][configure], [Configuring query RBAC][query-rbac] |
| Architecture (OCP 4.22 entry) | [Tempo architecture][arch] |

## Related skills

`ocp-opentelemetry`, `ocp-observability`, `rhoai-observability`,
`ocp-security-rbac-scc`.

[install]: https://docs.redhat.com/en/documentation/red_hat_openshift_distributed_tracing_platform/3.11/html-single/installing_distributed_tracing/index#distr-tracing-tempo-installing
[configure]: https://docs.redhat.com/en/documentation/red_hat_openshift_distributed_tracing_platform/3.11/html-single/configuring_distributed_tracing/index#distr-tracing-tempo-configuring
[query-rbac]: https://docs.redhat.com/en/documentation/red_hat_openshift_distributed_tracing_platform/3.11/html-single/configuring_distributed_tracing/index#distr-tracing-tempo-configuring-query-rbac_distr-tracing-tempo-configuring
[arch]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/distributed_tracing/index#distr-tracing-tempo-architecture
