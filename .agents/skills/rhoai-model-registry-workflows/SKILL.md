---
name: rhoai-model-registry-workflows
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when documenting, reviewing, or operating data scientist and AI engineer
  workflows in the Red Hat OpenShift AI model registry: registering models,
  registering model versions, setting source model format metadata, recording
  object storage or URI locations, registering and storing models as OCI
  ModelCar images, monitoring/retrying/deleting model transfer jobs, viewing
  model and version metadata, editing labels/descriptions/custom properties,
  deploying model versions from the registry, editing or deleting deployments,
  and archiving/restoring models or versions. Do NOT use for model registry
  administrator provisioning, database configuration, catalog source governance,
  deployment wizard details after registry handoff (use
  rhoai-model-deployment), or live cluster changes without the OpenShift
  safety guard.
---

# RHOAI Model Registry Workflows

Use this skill for OpenShift AI model registry workflows performed by data
scientists and AI engineers after an administrator has provisioned registry
access.

## Source Grounding

Read `references/source-capture.md` before using product workflow details.
Official Red Hat documentation is product authority. This skill adapts the
official Working with model registries guide to this repo's demo workflow and
governance review model.

## Scope

This skill covers:

- registering a new model and its first version from the dashboard
- registering additional model versions
- recording object storage or URI model locations
- registering and storing a model as an OCI ModelCar image
- monitoring, retrying, and deleting model transfer jobs
- viewing registered models and versions
- editing model-level and version-level metadata
- deploying model versions from a registry
- editing deployment properties for deployments created from the registry
- deleting deployments created from registry versions
- archiving and restoring models and model versions

Use other skills for adjacent work:

- `rhoai-model-registry` for administrator provisioning, database choices,
  permissions, generated RBAC, and registry deletion
- `rhoai-model-catalog-sources` for governing which catalog models are visible
  before registration
- `rhoai-model-catalog-workflows` for model catalog discovery, performance
  evaluation, tensor variant assessment, and starting catalog registration or
  deployment flows
- `rhoai-model-serving-platform` for serving runtime prerequisites and the
  serving platform configuration beyond the registry handoff
- `rhoai-model-deployment` for deploying registered model versions, deployment
  wizard behavior, routes, token authentication, deployment strategy, and
  inference endpoint smoke tests
- `rhoai-automl` for AutoML leaderboard registration, saved prediction
  notebooks, and AutoGluon serving runtime handoff
- `rhoai-model-customization-training` for registering and deploying
  customized model versions after fine-tuning workflows
- `rhoai-model-management-monitoring` for operating deployed models and metrics
- `rhoai-connection-types` for connection type templates used by object storage
  or model locations
- `rhoai-mlflow` for MLflow registered model APIs, experiments, prompts,
  datasets, traces, and SDK authentication when using MLflow rather than the
  OpenShift AI model registry
- `rhoai-api-tiers` for model registry API support posture

## Demo Policy

For this repo:

- Treat the registry as the governed model lifecycle record for demo assets:
  source, version, metadata, deployment handoff, archive, and restore.
- Prefer metadata that helps enterprise review: owner, description, labels,
  license, source, benchmark or evaluation references, and deployment intent.
- Do not register a model location that points to a bucket root.
- Label URI-registered deployment limits clearly: deployment of URI-registered
  models is currently supported for public OCI repositories only.
- Keep source and destination credentials out of committed files and logs.
- Treat model transfer jobs as ephemeral operational resources; deleting a
  transfer job does not remove successfully transferred model artifacts.
- Do not archive models or versions that still have deployments. Delete the
  deployments first.
- Use the model serving skill when changing runtime parameters, route exposure,
  token authentication, model server size, replicas, or serving-runtime
  arguments.
- Do not modify protected port or model serving runtime arguments during
  redeploys; the official workflow warns that overriding them can break
  deployments.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/source-capture.md` and
   `references/official-doc-extraction.md`.
3. Confirm the user has access to an available model registry.
4. Decide whether the task is registration, versioning, ModelCar storage,
   transfer-job operation, metadata edit, deployment handoff, or archive/restore.
5. Use the dashboard paths and constraints in
   `examples/model-registry-workflow-patterns.md`.
6. For deployment operations, hand off deployment workflow details to
   `rhoai-model-deployment` and platform/runtime configuration details to
   `rhoai-model-serving-platform`.
7. Validate with `references/validation-checklist.md`.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/model-registry-workflow-patterns.md`
