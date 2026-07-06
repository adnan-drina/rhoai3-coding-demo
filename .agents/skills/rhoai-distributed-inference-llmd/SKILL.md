---
name: rhoai-distributed-inference-llmd
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when documenting, reviewing, or rebuilding Red Hat OpenShift AI
  Distributed Inference with llm-d from the official deployment guide:
  LLMInferenceService resources, Gateway API discovery and selection,
  OpenShift Gateway Controller requirements, LeaderWorkerSet Operator
  prerequisites, Red Hat Connectivity Link and Kuadrant authentication,
  Authorino TLS setup, security.opendatahub.io/enable-auth, ServiceAccount JWT
  inference access, vLLM argument configuration for llm-d deployments,
  Endpoint Picker scheduler settings, ConfigMap-based scheduler references,
  Workload Variant Autoscaler enablement, VariantAutoscaling resources,
  saturation scaling ConfigMaps, mixed-workload flow control,
  InferenceObjective priority queuing, and llm-d observability. Do NOT use for
  standard single-model KServe deployment without llm-d (use
  rhoai-model-deployment), model-serving platform/runtime setup (use
  rhoai-model-serving-platform), MaaS governance over llm-d endpoints (use
  rhoai-maas-governance), Kueue/Ray/Training distributed workloads (use
  rhoai-distributed-workload-* skills), or live cluster changes without the
  OpenShift safety guard.
---

# RHOAI Distributed Inference With llm-d

Use this skill for Red Hat OpenShift AI Distributed Inference with llm-d on the
active product baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior details.
Official Red Hat documentation is product authority. This skill adapts the
official llm-d deployment guide to this repo's GitOps, README, and live-demo
review model.

## Scope

This skill covers:

- when to use `LLMInferenceService` instead of standard `InferenceService`
- Gateway API prerequisites, Gateway discovery, and YAML Gateway references
- OpenShift Gateway Controller preference and third-party Gateway risk
- LeaderWorkerSet Operator prerequisite
- Red Hat Connectivity Link, `Kuadrant`, and Authorino TLS setup for auth
- default authentication behavior and
  `security.opendatahub.io/enable-auth: "true"`
- authenticated requests with ServiceAccount JWTs or OIDC tokens
- vLLM argument patterns for llm-d deployments
- Endpoint Picker scheduler configuration, plugin selection, and ConfigMap
  references
- Workload Variant Autoscaler enablement and `VariantAutoscaling` resources
- saturation scaling thresholds and HPA behavior defaults
- mixed-workload flow control and `InferenceObjective` priority queuing
- llm-d metrics and observability support posture

Use other skills for adjacent work:

- `rhoai-model-serving-platform` for KServe, vLLM runtime templates, dashboard
  model-serving platform enablement, and runtime argument context outside
  llm-d
- `rhoai-model-deployment` for direct model deployment workflows, model
  storage, AI asset endpoints, routes, and token-auth choices outside llm-d
- `rhoai-maas-governance` when llm-d endpoints are exposed through MaaS
  subscriptions, auth policies, API keys, and usage governance
- `rhoai-nvidia-gpu-accelerators` for NVIDIA GPU Operator, GPU hardware
  profiles, and accelerator identifiers
- `rhoai-dashboard-customization` for dashboard flags such as llm-d visibility,
  Gateway discovery, and YAML preview controls
- `rhoai-model-management-monitoring` for deployed-model operational monitoring
  that is not specific to llm-d scheduler, WVA, or flow control
- `rhoai-observability` for platform observability stack configuration
- `rhoai-api-tiers` for support posture of llm-d APIs, alpha APIs, and preview
  functionality

## Demo Policy

For this repo:

- Prefer standard vLLM model serving for the baseline private model path unless
  a demo step explicitly needs distributed inference characteristics.
- Use llm-d when the README concept is about serving large LLMs at scale,
  prefix-cache-aware routing, disaggregated serving, scheduler behavior,
  autoscaling variants, or priority queuing.
- Treat Gateway discovery as Technology Preview.
- Treat llm-d monitoring as Developer Preview.
- Keep authentication enabled for shared demo endpoints. If it is disabled for
  a controlled test, document the exception and restore auth.
- Use OpenShift Gateway Controller-backed Gateways for the active demo unless a
  verified exception is documented.
- Do not use shared Gateways across untrusted namespaces.
- Keep model artifact sources and credentials traceable through official docs,
  Red Hat registry artifacts, or explicit demo exceptions.
- Verify installed CRD schemas before committing long-lived GitOps because the
  official guide includes versioned alpha APIs and examples may evolve across
  RHOAI releases.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/source-capture.md` and
   `references/official-doc-extraction.md`.
3. Decide whether the task is:
   - base `LLMInferenceService` deployment
   - Gateway discovery or YAML Gateway selection
   - Connectivity Link, Kuadrant, Authorino, or auth enablement
   - authenticated inference request setup
   - vLLM argument review
   - scheduler/Endpoint Picker configuration
   - Workload Variant Autoscaler setup
   - flow control and `InferenceObjective` priority queuing
   - llm-d metrics or observability review
4. Use `examples/llmd-distributed-inference-patterns.md` for compact manifest
   and review patterns.
5. For live cluster work, follow the OpenShift safety guard in `AGENTS.md`.
6. Validate with `references/validation-checklist.md`.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/llmd-distributed-inference-patterns.md`
