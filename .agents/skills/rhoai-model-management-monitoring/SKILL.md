---
name: rhoai-model-management-monitoring
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when documenting, reviewing, or operating Red Hat OpenShift AI deployed
  model management and monitoring: custom model-serving runtime administration,
  KServe progress-deadline timeouts, multi-node vLLM deployments, Kueue labels
  for InferenceService workloads, Spyre scheduler/toleration post-deploy
  changes, inference performance sizing, latency/throughput/cost metrics,
  metrics-based autoscaling with KEDA/CMA, User Workload Monitoring for model
  serving, Service Mesh monitoring, Grafana dashboards for KServe, OVMS, vLLM
  and GPU metrics, NVIDIA NIM model selection lists, and NIM metrics
  annotations. Do NOT use for model-serving platform enablement and runtime
  platform design (use rhoai-model-serving-platform), general RHOAI
  observability stack setup (use rhoai-observability), NVIDIA GPU enablement
  (use rhoai-nvidia-gpu-accelerators), TrustyAI fairness/drift monitoring
  (use rhoai-monitoring-trustyai), initial Deploy a model wizard and endpoint
  smoke-test workflows (use rhoai-model-deployment), model evaluation workflows
  (use rhoai-model-evaluation), GitOps-managed Grafana Operator deployment,
  Grafana instance lifecycle, datasource authentication, OAuth routes, or
  Grafana RBAC (use ocp-grafana-operator), or live cluster changes without the
  OpenShift safety guard.
---

# RHOAI Model Management And Monitoring

Use this skill for administrator operations on deployed OpenShift AI models and
their monitoring surfaces on the active product baseline in
`docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior details.
Official Red Hat documentation is product authority. This skill adapts the
official Managing and monitoring models guide to this repo's operations and
GitOps review model.

## Scope

This skill covers:

- adding and editing custom model-serving runtimes from the OpenShift AI
  dashboard
- setting KServe `serving.knative.dev/progress-deadline` for slow large-model
  deployments
- multi-node vLLM model deployment with `vllm-multinode-runtime`
- Kueue `kueue.x-k8s.io/queue-name` labels on `InferenceService` resources
- Spyre scheduler and toleration updates after deployment
- performance tuning concepts for GPU memory, quantization, KV cache, tensor
  parallelism, and RAG/text summarization workloads
- inference performance metrics: TTFT, ITL, TPOT, TPS, RPS, and cost per
  million tokens
- metrics-based autoscaling with KEDA and OpenShift Custom Metrics Autoscaler
- model-serving User Workload Monitoring and Service Mesh monitoring setup
- Grafana dashboards and common vLLM/GPU metrics
- NVIDIA NIM model list configuration through an `Account` CR and ConfigMap
- NIM graph generation and metrics annotations for existing deployments

Use other skills for adjacent work:

- `rhoai-model-serving-platform` for model-serving platform enablement,
  supported runtimes, `ServingRuntime`/`InferenceService` concepts, NIM
  platform enablement, and deployment strategy
- `rhoai-model-deployment` for initial model deployment, storage selection,
  routes, token authentication, and runtime-specific inference smoke tests
- `rhoai-observability` for the general OpenShift AI observability stack and
  dashboard
- `rhoai-nvidia-gpu-accelerators` for NVIDIA GPU Operators and hardware
  profiles
- `rhoai-monitoring-trustyai` for TrustyAI bias metrics, data drift metrics,
  `TrustyAIService`, model observations, and OVMS support boundaries
- `ocp-grafana-operator` for deploying and managing the Grafana Operator,
  Grafana instance, datasource authentication, OAuth route, and Grafana RBAC
- `rhoai-kueue-workload-management` for Kueue installation, queues, and
  namespace enforcement
- `rhoai-storage-classes` for RWX storage class readiness when multi-node
  deployments use PVC-backed model storage
- `rhoai-evaluation` for official EvalHub, LM-Eval, LMEvalJob, and automated
  risk assessment workflows
- `rhoai-model-evaluation` for legacy repo-specific RAGAS, custom judge, and
  Step 08 evaluation rebuild details

## Demo Policy

For this repo:

- Use this skill for day-2 operations around deployed model behavior, not for
  initial platform installation.
- Treat multi-node vLLM and metrics-based autoscaling as Technology Preview for
  the active baseline. Label that posture in demo READMEs and presentations.
- Keep NVIDIA as the active accelerator family for this demo. Treat Spyre
  content as source-grounded review knowledge unless the baseline changes.
- Do not make NVIDIA NIM part of the demo unless the project explicitly adopts
  NIM and documents NGC account, model list, and credential handling.
- Prefer GitOps-managed `InferenceService`, `ServingRuntime`, monitoring, and
  Grafana dashboard resources once the active implementation exists.
- Convert official one-off `oc apply` and `oc patch` examples into reviewed
  GitOps or runbook steps, depending on whether the setting is long-lived.
- Do not tune autoscaling from synthetic examples alone. Use load tests with
  realistic prompt/output length distributions.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/source-capture.md` and
   `references/official-doc-extraction.md`.
3. Decide whether the task is:
   - model-serving runtime administration
   - KServe timeout tuning
   - multi-node vLLM deployment
   - Kueue routing for an inference service
   - performance sizing or autoscaling
   - model-serving monitoring or Grafana dashboards
   - NVIDIA NIM model selection or metrics enablement
4. Use `examples/model-management-monitoring-patterns.md` for focused patterns.
5. Validate with `references/validation-checklist.md`.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/model-management-monitoring-patterns.md`
