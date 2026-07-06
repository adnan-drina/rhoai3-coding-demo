---
name: rhoai-model-deployment
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when documenting, reviewing, deploying, or operating Red Hat OpenShift AI
  model deployment user workflows from the official Deploying models guide:
  model storage in S3, URI, PVC, or OCI containers/modelcars; building OCI
  model images; dashboard Deploy a model wizard; generative and predictive
  model deployment; automatic serving-runtime selection; hardware profile
  matching; manual runtime selection; administrator llm-d override behavior;
  Rolling update versus Recreate deployment strategy; AI asset endpoint
  registration; external routes; token authentication; MLServer deployment
  settings; CLI deployment from OCI images with ServingRuntime and
  InferenceService; NVIDIA NIM model deployment; endpoint token lookup; and
  runtime-specific inference endpoint paths for Caikit, OpenVINO, vLLM,
  Triton, and MLServer. Do NOT use for model-serving platform enablement,
  runtime template configuration, vLLM runtime arguments, or NIM platform
  enablement (use rhoai-model-serving-platform), deployed model metrics and
  day-2 operations (use rhoai-model-management-monitoring), TrustyAI bias or
  drift monitoring (use rhoai-monitoring-trustyai), model catalog or registry
  workflows before deployment handoff (use rhoai-model-catalog-workflows or
  rhoai-model-registry-workflows), MaaS governance (use
  rhoai-maas-governance), llm-d distributed inference (use
  rhoai-distributed-inference-llmd), or live cluster changes without the
  OpenShift safety guard.
---

# RHOAI Model Deployment

Use this skill for official Red Hat OpenShift AI model deployment and inference
request workflows on the active product baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior details.
Official Red Hat documentation is product authority. This skill adapts the
official Deploying models guide to this repo's GitOps and README review model.

## Scope

This skill covers:

- storing models before deployment in S3, URI sources, PVCs, or OCI images
- OCI model storage, also called modelcars in KServe
- building OCI model images with Podman and a shell-capable base image
- uploading model files to a model-storage PVC through a running workbench IDE
- Deploy a model wizard workflow for generative and predictive models
- model location, model type, deployment name, hardware profile, resources,
  serving runtime, model framework, replicas, and advanced settings
- automatic serving-runtime selection based on model type, model format, and
  hardware profile
- hardware profile matching, selection limitations, manual runtime selection,
  and administrator distributed-inference override behavior
- Rolling update versus Recreate deployment strategies
- AI asset endpoint registration for Gen AI studio playground testing
- external route and token authentication choices
- MLServer deployment settings and `MLSERVER_MODEL_URI`
- CLI deployment of OCI-stored models with `ServingRuntime`,
  `InferenceService`, `storageUri`, and `imagePullSecrets`
- NVIDIA NIM model deployment workflow after NIM platform enablement
- deployed model token lookup and inference endpoint lookup
- runtime-specific inference paths for Caikit TGIS, OpenVINO Model Server,
  vLLM, NVIDIA Triton, and MLServer
- dashboard and OpenShift metric handoff for deployed models

Use other skills for adjacent work:

- `rhoai-model-serving-platform` for KServe platform enablement, NIM platform
  enablement, preinstalled/custom runtime enablement, runtime templates, vLLM
  runtime arguments, and default deployment strategy configuration
- `rhoai-model-management-monitoring` for deployed-model metrics, KServe
  timeouts, multi-node vLLM operations, Kueue routing, Grafana dashboards,
  autoscaling, and NIM metrics operations
- `rhoai-monitoring-trustyai` for TrustyAI model observations, bias metrics,
  data-drift metrics, and OVMS support boundaries
- `rhoai-gen-ai-playground` for AI asset endpoint testing in Gen AI studio
- `rhoai-model-catalog-workflows` for catalog discovery, model card review,
  and catalog-to-deployment handoff
- `rhoai-model-registry-workflows` for registered model/version deployment
  handoff and OCI ModelCar transfer jobs
- `rhoai-project-workflows` for projects, connections, storage, and project
  access
- `rhoai-s3-object-storage-data` for S3-compatible object storage operations
  and credentials
- `rhoai-nvidia-gpu-accelerators` for NVIDIA GPU enablement and hardware
  profiles
- `rhoai-maas-governance` for MaaS subscriptions, model refs, authorization
  policies, API keys, observability, external OIDC, and external models
- `rhoai-distributed-inference-llmd` for `LLMInferenceService`, Gateway
  discovery, Connectivity Link auth, scheduler, autoscaling, and flow-control
  workflows

## Demo Policy

For this repo:

- Prefer the standard model serving platform with vLLM NVIDIA GPU runtime for
  the active private model deployment path unless the project explicitly
  introduces another serving platform.
- Use NVIDIA GPU hardware profiles for generative model deployment unless the
  active platform baseline changes.
- Treat the Deploy a model wizard as the source for user workflow narratives.
  Convert durable deployment intent into GitOps manifests only after fields are
  verified against official docs or active CRD schema.
- Prefer OCI model storage/modelcars for reproducible demo model artifacts when
  supported by the chosen runtime and model format.
- Keep private OCI registry credentials, object storage credentials, and model
  endpoint tokens in Kubernetes Secrets. Never commit secret values.
- Enable external routes only when the demo needs external clients. Require
  token authentication for shared demo endpoints unless there is a documented
  reason not to.
- Use Recreate for scarce GPU demo environments unless zero-downtime rollout
  and 200% resource headroom are available and documented.
- Add generative model deployments as AI asset endpoints when they should be
  tested in Gen AI studio playground.
- Do not make NVIDIA NIM part of the demo unless the project explicitly adopts
  NIM and documents NGC account, GPU, storage, and credential handling.
- Treat MLServer ServingRuntime for KServe and Spyre x86 paths as Technology
  Preview where the official guide labels them that way.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/source-capture.md` and
   `references/official-doc-extraction.md`.
3. Decide whether the task is:
   - model storage and artifact preparation
   - dashboard deployment workflow
   - runtime auto-selection or manual selection review
   - deployment strategy choice
   - AI asset endpoint, route, or token-auth setup
   - MLServer deployment detail
   - OCI model deployment by CLI
   - NIM model deployment
   - endpoint token lookup or inference request testing
4. Use `examples/model-deployment-patterns.md` for compact review patterns.
5. For live cluster work, follow the OpenShift safety guard in `AGENTS.md`.
6. Validate with `references/validation-checklist.md`.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/model-deployment-patterns.md`
