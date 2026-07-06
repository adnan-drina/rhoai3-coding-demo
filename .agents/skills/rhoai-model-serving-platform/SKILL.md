---
name: rhoai-model-serving-platform
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when documenting, reviewing, or configuring the Red Hat OpenShift AI
  model-serving platform from the official configuration guide: KServe-based
  model serving, NVIDIA NIM platform enablement, ServingRuntime and
  InferenceService concepts, supported and tested model-serving runtime
  posture, accelerator-specific runtimes, dashboard enablement of the model
  serving platform and runtimes, custom and tested runtime addition,
  speculative decoding, multi-modal vLLM configuration, runtime argument and
  environment-variable customization, vLLM KV cache configuration, and default
  deployment strategy. Do NOT use for deployed-model monitoring, KServe timeout
  tuning, multi-node vLLM operations, Kueue routing, Grafana dashboards, or NIM
  metrics operations (use rhoai-model-management-monitoring), installing RHOAI
  or KServe components (use rhoai-self-managed-installation), GPU enablement (use
  rhoai-nvidia-gpu-accelerators), project connection API annotations (use
  rhoai-project-workflows), project-scoped runtime templates (use
  rhoai-project-scoped-resources), model deployment user workflows (use
  rhoai-model-deployment), MaaS governance (use rhoai-maas-governance), llm-d
  distributed inference (use rhoai-distributed-inference-llmd), NeMo/FMS
  Guardrails services or detector serving workflows (use
  rhoai-guardrails-safety), or live cluster changes without the OpenShift
  safety guard.
---

# RHOAI Model-Serving Platform

Use this skill for OpenShift AI administrator workflows that configure the
model-serving platform and model-serving runtimes on the active baseline in
`docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior details.
Official Red Hat documentation is product authority. This skill adapts the
official model-serving platform configuration guide to this repo's operations
and GitOps review model.

## Scope

This skill covers:

- model serving platform selection and use-case boundaries
- KServe-based model serving as the production-oriented platform for dedicated
  per-model runtime servers
- NVIDIA NIM model serving platform enablement prerequisites and dashboard
  workflow
- `ServingRuntime` and `InferenceService` responsibilities
- preinstalled model-serving runtime enablement
- custom model-serving runtime addition through the dashboard
- tested and verified runtime addition and support boundary
- accelerator runtime choices for NVIDIA GPUs, Intel Gaudi, AMD GPUs, and IBM
  Spyre accelerators
- vLLM NVIDIA GPU runtime configuration for speculative decoding and
  multi-modal inferencing
- per-deployment runtime argument and environment-variable customization
- vLLM `VLLM_CPU_KVCACHE_SPACE` tuning guidance from the official docs
- cluster-wide default deployment strategy: Rolling update or Recreate

Use other skills for adjacent work:

- `rhoai-self-managed-installation` for installing KServe and OpenShift AI
  components through DSC/DSCI
- `rhoai-nvidia-gpu-accelerators` for GPU Operators, accelerator readiness,
  and NVIDIA-only demo policy
- `rhoai-hardware-profiles` for accelerator identifiers, hardware profile
  lifecycle, and recommended serving runtime accelerator tags
- `rhoai-project-scoped-resources` for project-scoped serving runtime templates
- `rhoai-project-workflows` for project connections and connection API
  annotations used by `InferenceService` or `LLMInferenceService`
- `rhoai-dashboard-customization` for KServe, NIM, serving runtime, metrics,
  authentication, and runtime-parameter dashboard flags
- `rhoai-storage-classes` and `rhoai-connection-types` for model storage and
  object storage connection context
- `rhoai-model-deployment` for Deploy a model wizard behavior, model storage
  selection, runtime auto-selection, routes, token authentication, OCI
  deployment by CLI, and runtime-specific inference endpoint paths
- `rhoai-model-management-monitoring` for deployed-model monitoring, KServe
  timeout tuning, multi-node vLLM operations, Kueue routing, Grafana
  dashboards, and NIM metrics operations
- `rhoai-monitoring-trustyai` for TrustyAI model observation, KServe logger
  handoff, bias metrics, data-drift metrics, and OVMS support boundaries
- `rhoai-gen-ai-playground` for AI asset endpoint requirements and product
  playground testing of deployed generative models
- `rhoai-automl` for AutoGluon `ServingRuntime` requirements and AutoML model
  deployment handoff from a model registry
- `rhoai-model-customization-training` for serving handoff after customization
  and OpenAI-compatible endpoints used by ITS Hub
- `rhoai-evaluation` for official model endpoint evaluation, KServe/vLLM
  `LMEvalJob` scenarios, and risk assessment target/judge endpoints
- `rhoai-guardrails-safety` for guarding model endpoints with NeMo Guardrails,
  FMS Guardrails, detector services, and validation-only safety checks
- `rhoai-maas-governance` for MaaS governance, subscriptions, authorization
  policies, API keys, observability, external OIDC, and external models
- `rhoai-distributed-inference-llmd` for `LLMInferenceService`, Gateway
  discovery, Connectivity Link auth, scheduler, autoscaling, and flow-control
  workflows

## Demo Policy

For this repo:

- Prefer the standard model serving platform with the vLLM NVIDIA GPU runtime
  for private model serving unless the project explicitly introduces another
  serving platform.
- Keep NVIDIA as the only accelerator family for the active demo unless the
  platform baseline changes.
- Treat official Granite, Llama, Mistral, Triton, and IBM examples as field
  placement references, not as the demo's model selection.
- Do not enable NVIDIA NIM unless the demo explicitly needs NIM and the NGC
  account, NVIDIA AI Enterprise Viewer role, and personal API key handling are
  documented.
- Do not add custom or tested runtimes without recording the support boundary:
  Red Hat does not support custom runtimes, and tested and verified runtimes
  are not directly supported by Red Hat.
- Do not modify required port or model-serving runtime arguments for deployed
  models unless official docs or runtime documentation confirms the change.
- Use GitOps for long-lived `ServingRuntime`, `InferenceService`, and dashboard
  configuration once active implementation exists, but verify CRD schemas
  before authoring fields.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/source-capture.md` and
   `references/official-doc-extraction.md`.
3. Decide whether the task is:
   - enabling the model serving platform
   - enabling preinstalled serving runtimes
   - adding or reviewing a custom runtime
   - adding or reviewing a tested and verified runtime
   - enabling NVIDIA NIM
   - customizing runtime arguments or environment variables for a deployment
   - setting the cluster default deployment strategy
   - reviewing `ServingRuntime` or `InferenceService` manifests
4. Use `examples/model-serving-platform-patterns.md` for review patterns.
   For Nemotron 3 Nano, use
   `examples/nemotron-vllm-configurations.md` before changing model args,
   resources, or MaaS serving shape.
5. Validate with `references/validation-checklist.md`.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/model-serving-platform-patterns.md`
- `examples/nemotron-vllm-configurations.md`
