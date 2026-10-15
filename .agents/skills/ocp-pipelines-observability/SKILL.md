---
name: ocp-pipelines-observability
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: ocp_pipelines
  docs-version: "1.24"
  skill-group: "OpenShift Platform"
description: >
  Use when someone asks about Tekton Results (long-term run and log storage,
  retention policies, opc queries) or the OpenShift Pipelines component
  metrics for OpenShift Pipelines 1.24. Tekton Results is not configured in
  this repo; this stub records that and links the official sections. Do NOT
  use for cluster monitoring (use ocp-observability), pruning (use
  ocp-pipelines-install-config), or reading a failed run (use
  ocp-pipelines-cicd).
---

# OpenShift Pipelines observability (not used in this repo)

Link-only stub. Product guidance lives in the linked OpenShift Pipelines 1.24
sections.

## When to use

- Someone needs run history beyond the pruner window, or Pipelines metrics.

## Not used in this repo

Tekton Results is not configured, and no Pipelines dashboard or alert is in
Git. Run history is short by design: the pruner keeps the last 10
PipelineRuns per namespace
(`gitops/stages/070-advanced-app-platform/pipelines/operators/configure-tekton-pruner.yaml`).
Durable evidence of a delivery is the digest in the delivery repository and
the Argo CD runtime Application (`docs/OPERATIONS.md#stage-070--coolstore-dev-environment`).
Developer Hub shows live PipelineRuns through the Tekton plugin
(`rhdh-dynamic-plugins-configure`).

## Official documentation (OpenShift Pipelines 1.24)

| Topic | Section |
|---|---|
| Tekton Results | [Using Tekton Results][results], [Concepts][concepts], [Configuring][configure], [Querying with opc][query] |
| Retention | [Retention policy][retention], [Fine-grained retention][fine] |
| Metrics | [Component metrics reference][metrics] |
| Service monitor | [Disabling the service monitor][sm] |

## Related skills

`ocp-pipelines-install-config`, `ocp-observability`, `ocp-pipelines-cli-reference`.

[results]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/observability_in_openshift_pipelines/index#using-tekton-results-for-openshift-pipelines-observability
[concepts]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/observability_in_openshift_pipelines/index#results-concepts_using-tekton-results-for-openshift-pipelines-observability
[configure]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/observability_in_openshift_pipelines/index#configuring-results_using-tekton-results-for-openshift-pipelines-observability
[query]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/observability_in_openshift_pipelines/index#querying-using-opc_using-tekton-results-for-openshift-pipelines-observability
[retention]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/observability_in_openshift_pipelines/index#understanding-the-tekton-results-retention-policy
[fine]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/observability_in_openshift_pipelines/index#op-fine-grained-retention-policies_understanding-the-tekton-results-retention-policy
[metrics]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/observability_in_openshift_pipelines/index#op-observability-metrics-reference
[sm]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/installing_and_configuring/index#op-disabling-the-service-monitor_customizing-configurations-in-the-tektonconfig-cr
