---
name: rhoai-automl
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when documenting, reviewing, or operating Red Hat OpenShift AI AutoML
  workflows from the official Working with AutoML guide: Technology Preview
  posture, CSV training data in S3-compatible storage, AutoML optimization
  runs, binary classification, multiclass classification, regression, time
  series forecasting, externally imported AutoML pipeline naming, leaderboard
  evaluation, feature importance, confusion matrices, model registry handoff,
  saved prediction notebooks, AutoGluon ServingRuntime deployment, task metrics,
  and AutoML configuration parameters. Do NOT use for generic AI Pipelines
  server administration (use rhoai-ai-pipelines), S3 object operations outside
  AutoML (use rhoai-s3-object-storage-data), project/workbench lifecycle (use
  rhoai-project-workflows), IDE workflows outside saved AutoML notebooks (use
  rhoai-data-science-ide-workflows), model registry administration (use
  rhoai-model-registry), general model-serving platform configuration (use
  rhoai-model-serving-platform), or live cluster changes without the OpenShift
  safety guard.
---

# RHOAI AutoML

Use this skill for Red Hat OpenShift AI AutoML user workflows on the active
product baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product workflow details.
Official Red Hat documentation is product authority. This skill adapts the
official Working with AutoML guide to this repo's demo workflow and governance
review model.

## Scope

This skill covers:

- AutoML Technology Preview support posture
- AutoML concept model and workflow
- supported task types: binary classification, multiclass classification,
  regression, and time series forecasting
- CSV training data requirements and size limits
- S3-compatible object storage and AI Pipelines server prerequisites
- AutoML optimization run creation and immutable run configuration
- externally imported AutoML pipeline naming rules
- leaderboard evaluation, model details, feature importance, and confusion
  matrix boundaries
- model registry handoff from the AutoML leaderboard
- saved notebook prediction workflow from a workbench
- AutoGluon `ServingRuntime` prerequisite and deployment handoff
- time series runtime environment variables for non-default column names
- optimized metrics and configuration parameters by task type

Use other skills for adjacent work:

- `rhoai-ai-pipelines` for pipeline server configuration, pipeline run
  lifecycle, imported pipeline management, caching, logs, and DSPA
  troubleshooting
- `rhoai-s3-object-storage-data` for object storage operations from
  workbenches
- `rhoai-project-workflows` for projects, workbenches, connections, project
  access, and cluster storage
- `rhoai-data-science-ide-workflows` for running saved notebooks and Git or
  Python package workflows inside a workbench
- `rhoai-model-registry` for administrator provisioning of model registries
- `rhoai-model-registry-workflows` for registered model/version metadata,
  deployment handoff, archive, and restore
- `rhoai-model-serving-platform` for `ServingRuntime` review and serving
  platform configuration
- `rhoai-model-management-monitoring` for day-2 deployed model operations and
  monitoring
- `rhoai-api-tiers` for API support posture, including KServe
  `serving.kserve.io/v1alpha1` resources

## Demo Policy

For this repo:

- Label AutoML as Technology Preview in READMEs, runbooks, presentations, and
  demo scripts. Do not present it as production SLA-backed.
- Treat AutoML as a rapid model exploration and comparison workflow for
  tabular CSV data, not as a replacement for governed pipeline engineering.
- Require a data science project with an AI Pipelines server before any AutoML
  run is promised.
- Store training data in S3-compatible object storage and keep object storage
  credentials in project-scoped connections or Secrets.
- Keep training CSV files UTF-8 encoded, comma-delimited, and header-bearing.
- Respect the documented data size limits: 32 MiB for dashboard upload and
  100 MB when loaded from S3-compatible storage.
- Do not claim custom algorithm or hyperparameter selection; AutoML chooses
  algorithms, hyperparameters, train/test split, and optimization metric.
- Treat an optimization run as immutable after creation. Use AI Pipelines run
  workflows to stop, archive, or delete the underlying pipeline run.
- Register selected models to a model registry before deployment when the demo
  needs a governed handoff.
- Use saved notebooks for transparent prediction exploration in a workbench.
- Deploy AutoML models only after the AutoGluon serving runtime is available
  and its Red Hat registry image and KServe schema are verified.
- For time series forecasting, set runtime environment variables when the
  trained data used non-default series ID or timestamp column names.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/source-capture.md` and
   `references/official-doc-extraction.md`.
3. Confirm Technology Preview posture is acceptable for the requested demo
   surface.
4. Decide whether the task is:
   - AutoML concept or README authoring
   - prerequisite review for project, AI Pipelines, S3 data, and cluster
     capacity
   - optimization run design
   - external AutoML pipeline import review
   - leaderboard evaluation and model selection
   - model registry or saved notebook handoff
   - AutoGluon serving runtime or deployment review
   - metric and parameter interpretation
5. Use `examples/automl-patterns.md` for focused review patterns.
6. For live cluster work, follow the OpenShift safety guard in `AGENTS.md`.
7. Validate with `references/validation-checklist.md`.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/automl-patterns.md`
