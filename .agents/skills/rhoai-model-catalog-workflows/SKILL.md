---
name: rhoai-model-catalog-workflows
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when documenting, reviewing, or operating data scientist and AI engineer
  workflows in the Red Hat OpenShift AI model catalog: discovering generative
  AI models, using catalog categories, searching and filtering by task,
  provider, license, language, and tensor type, viewing model cards and
  provider metadata, evaluating Red Hat AI validated model performance,
  using Model performance view, interpreting latency and throughput filters,
  comparing tensor variants, registering a catalog model into a model registry,
  and deploying a catalog model through the model serving wizard. Do NOT use
  for administrator catalog-source governance, model registry provisioning,
  general model-serving platform configuration, deployment wizard details
  after the catalog handoff (use rhoai-model-deployment), or live cluster
  changes without the OpenShift safety guard.
---

# RHOAI Model Catalog Workflows

Use this skill for OpenShift AI model catalog workflows performed by data
scientists and AI engineers: discover, evaluate, register, and deploy catalog
models.

## Source Grounding

Read `references/source-capture.md` before using product workflow details.
Official Red Hat documentation is product authority. This skill adapts the
official Working with the model catalog guide to this repo's demo workflow and
governance review model.

## Scope

This skill covers:

- discovering available generative AI models in AI hub -> Models -> Catalog
- model catalog categories such as All models, Red Hat AI models, Red Hat AI
  validated models, Other models, and administrator-defined labeled categories
- searching by model name, description, or provider
- filtering by task, provider, license, language, and tensor type
- reading model cards, intended use, limitations, training details, and
  evaluation results
- using Performance Insights for validated models
- using Model performance view and workload/hardware constraints
- interpreting validated-model performance metrics and tensor variants
- registering a catalog model into an available model registry
- deploying a catalog model through the model serving wizard

Use other skills for adjacent work:

- `rhoai-model-catalog-sources` for administrator control over which catalog
  sources and models are visible
- `rhoai-model-registry` for registry provisioning, database choices, and
  permissions
- `rhoai-model-registry-workflows` for registry-side model and version
  lifecycle after catalog registration
- `rhoai-model-serving-platform` for serving runtime prerequisites, automatic
  runtime selection prerequisites, and runtime platform configuration
- `rhoai-model-deployment` for deployment wizard details, model storage
  choices, runtime auto-selection behavior, routes, token authentication,
  deployment strategies, and inference endpoint smoke tests
- `rhoai-gen-ai-playground` for testing catalog-deployed generative models
  after they are added as AI asset endpoints
- `rhoai-model-management-monitoring` for operating deployed catalog models
- `rhoai-api-tiers` for API support posture when automating catalog-related
  workflows

## Demo Policy

For this repo:

- Treat the model catalog as the governed discovery and evaluation entry point
  for model selection.
- Prefer Red Hat AI and Red Hat AI validated categories for default demo
  narratives.
- Treat Red Hat AI validated performance data as deployment-selection evidence,
  not a replacement for the demo's own validation.
- Preserve catalog model card limitations and intended-use notes in README or
  presentation claims.
- Use Performance Insights and tensor variant comparisons when explaining
  hardware, latency, throughput, or cost trade-offs.
- Do not register catalog models on `s390x`; the official workflow says this
  registration path is not supported there.
- Do not claim broad catalog support on `s390x`; the official guide states only
  `granite-3.3-8b-instruct` is supported there.
- For catalog deployments, remember that model-serving deployments use the
  global cluster pull secret to pull OCI-compliant ModelCar models from the
  catalog.
- Hand off model-serving runtime choices and advanced deployment settings to
  `rhoai-model-serving-platform`.
- Label `s390x` advanced deployment settings as unsupported.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/source-capture.md` and
   `references/official-doc-extraction.md`.
3. Decide whether the task is discovery, performance evaluation, tensor variant
   assessment, catalog registration, or catalog deployment.
4. Use the dashboard paths and constraints in
   `examples/model-catalog-workflow-patterns.md`.
5. For registry registration, confirm access to an available model registry.
6. For deployment, confirm model serving prerequisites and hand off deployment
   workflow details to `rhoai-model-deployment`.
7. Validate with `references/validation-checklist.md`.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/model-catalog-workflow-patterns.md`
