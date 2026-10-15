---
name: rhoai-model-management-monitoring
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when operating or monitoring deployed models in this repo: the vLLM
  serving-health PrometheusRule and `monitoring-rules-view` RoleBinding in
  `internal-models`, user workload monitoring for model metrics, the Kueue
  `kueue.x-k8s.io/queue-name` label on the Qwen deployments, the DCGM GPU
  ServiceMonitor for the LLM utilization dashboard, the Stage 050 candidate
  `ServingRuntime` made from `vllm-cuda-runtime-template`, or sizing, latency,
  throughput and cost-per-token questions. Do NOT use for first deployment of
  a model (use rhoai-model-deployment), llm-d topology (use
  rhoai-distributed-inference-llmd), MaaS usage dashboards and quotas (use
  rhoai-maas-governance), or TrustyAI bias and drift (use
  rhoai-monitoring-trustyai).
---

# RHOAI Model Management And Monitoring

Thin skill: repo decisions and pitfalls here, product behavior in the linked
OpenShift AI 3.5 sections. Detailed record:
`gitops/stages/040-governed-models-as-a-service/040-local-models/README.md`
(`monitoring/`) and `gitops/stages/040-governed-models-as-a-service/040-maas-platform/README.md`.

## When to use

- A serving alert fires (`VLLMHighTimeToFirstToken`, `VLLMRequestQueueBacklog`,
  `VLLMKVCachePressure`, `VLLMModelServingDown`) or model metrics are empty.
- A model pod stays pending behind a Kueue queue.
- Sizing a model, comparing latency and throughput, or pricing tokens.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| User workload monitoring enabled cluster-wide (`enableUserWorkload: true`), owned by Stage 010 | `gitops/stages/010-openshift-ai-platform-foundation/010-observability-operators/cluster-monitoring/` | [Configure monitoring for model serving][monitorcfg] |
| `monitoring-rules-view` for `rhoai-developers` and `rhods-admins` in `internal-models` | `gitops/stages/040-governed-models-as-a-service/040-local-models/monitoring/rolebinding-monitoring-rules-view.yaml` | [Configure monitoring for model serving][monitorcfg] |
| Demo alert thresholds on vLLM metrics (p95 TTFT > 2 s, > 8 waiting, KV cache > 90 %), not an SLA | `gitops/stages/040-governed-models-as-a-service/040-local-models/monitoring/prometheusrule-vllm-serving-health.yaml` | [vLLM metrics][vllm] |
| Every model carries `kueue.x-k8s.io/queue-name` (`lq-gpu-rtxpro6000` production, `lq-gpu-reserved-demo` candidate) | `gitops/stages/040-governed-models-as-a-service/040-local-models/qwen38-27b-llminferenceservice.yaml`, `gitops/stages/050-model-evaluation/050-model-qualification/candidate-qwen3-8-27b-int4.yaml` | [Inference service for Kueue][kueue] |
| No custom runtime template: the candidate `ServingRuntime` is instantiated from the platform `vllm-cuda-runtime-template` | `gitops/stages/050-model-evaluation/050-model-qualification/candidate-qwen3-8-27b-int4.yaml` | [Add a custom runtime][runtime] |
| No Grafana; dashboards are the product Observability page plus two repo PersesDashboards (cost per token, tokenomics) maintained directly as YAML | `gitops/stages/040-governed-models-as-a-service/040-maas-platform/observability/` | [Cost per million tokens][cost] |
| DCGM exporter scraped by a repo ServiceMonitor with `monitoring.opendatahub.io/scrape=true` | `gitops/stages/020-gpu-infrastructure-private-ai/020-nvidia-gpu-operator/rhoai-monitoring/` | [Accelerator metrics][accel] |
| Not used: KServe timeout annotation, multi-node vLLM, Spyre, NIM, metrics-based autoscaling (no KEDA) | not in Git | [Multiple GPU nodes][multinode], [Autoscaling][autoscale] |

## Procedure

1. Change rules or bindings in Git and deploy the owning stage
   (`./stages/040-governed-models-as-a-service/deploy.sh`, then
   `validate.sh --readiness`). Dashboards: edit the PersesDashboard YAML
   directly (the former generator `gen-cost-dashboards.py` is in git history
   at `82092e01`).
2. Inspect read-only, after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get prometheusrule vllm-serving-health -n internal-models
   oc get llminferenceservice,inferenceservice -A
   oc get workloads.kueue.x-k8s.io -n internal-models
   ```

3. Measure latency and throughput with `run-guidellm-load-test`; record
   results in `docs/OPERATIONS.md`, not in the skill.

## Pitfalls

- `VLLMModelServingDown` is severity `info`: it also fires while GPU nodes are
  scaled to zero (`resume-gpu-demo`).
- The candidate is stopped with `serving.kserve.io/stop: "true"` and sits in
  the last sync wave so a Suspended model does not block other waves.
- No Kueue workload for a model:
  `docs/TROUBLESHOOTING.md#private-models-do-not-produce-kueue-workloads`.
- Empty observability page or rejected monitors:
  `docs/TROUBLESHOOTING.md#observability-dashboard-shows-no-dashboards-found`,
  `docs/TROUBLESHOOTING.md#prometheusoperatorrejectedresources-warning-alert-fires`.
- The book's Grafana chapter does not apply here; use the Observability page.

## Official documentation (OpenShift AI 3.5)

| Topic | Section |
|---|---|
| Runtimes | [Add a custom model-serving runtime][runtime] |
| Deployment options | [KServe timeout][timeout], [Multiple GPU nodes][multinode], [Kueue][kueue] |
| Sizing and performance | [GPU requirements][gpu], [RAG and summarization][rag], [Inference metrics][metrics], [Cost per million tokens][cost] |
| Autoscaling | [Metrics-based autoscaling][autoscale], [Guidelines][autoscaleguide] |
| Monitoring | [Configure monitoring][monitorcfg], [vLLM metrics][vllm], [Accelerator metrics][accel] |

## Related skills

`rhoai-model-deployment`, `rhoai-distributed-inference-llmd`,
`rhoai-observability`, `rhoai-kueue-workload-management`,
`rhoai-maas-governance`, `run-guidellm-load-test`, `resume-gpu-demo`.

[runtime]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_and_monitoring_models/index#adding-a-custom-model-serving-runtime_cluster-admin
[timeout]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_and_monitoring_models/index#setting-timeout-for-kserve_cluster-admin
[multinode]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_and_monitoring_models/index#deploying-models-using-multiple-gpu-nodes_cluster-admin
[kueue]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_and_monitoring_models/index#configuring-an-inference-service-for-kueue_cluster-admin
[gpu]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_and_monitoring_models/index#determining-gpu-requirements-for-llm-powered-applications_cluster-admin
[rag]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_and_monitoring_models/index#performance-considerations-for-document-based-apps_cluster-admin
[metrics]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_and_monitoring_models/index#inference-performance-metrics_cluster-admin
[cost]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_and_monitoring_models/index#cost_per_million_tokens
[autoscale]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_and_monitoring_models/index#configuring-metrics-based-autoscaling_cluster-admin
[autoscaleguide]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_and_monitoring_models/index#guidelines-for-metrics-based-autoscaling_cluster-admin
[monitorcfg]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_and_monitoring_models/index#configuring-monitoring-for-the-model-serving-platform_cluster-admin
[vllm]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_and_monitoring_models/index#ref-vllm-metrics_cluster-admin
[accel]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_and_monitoring_models/index#ref-accelerator-metrics_cluster-admin
