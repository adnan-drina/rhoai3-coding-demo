# Validation Checklist

Use this checklist before accepting AutoML README content, runbooks, notebooks,
GitOps manifests, or demo scripts.

## Source Alignment

- Product links use the active baseline in `docs/PLATFORM_BASELINE.md`.
- The official Working with AutoML source is recorded when the workflow is
  introduced.
- AutoML is labeled Technology Preview in user-facing material.
- AI Pipelines prerequisites are checked with `rhoai-ai-pipelines`.
- S3-compatible storage and project connections are checked with
  `rhoai-project-workflows` and `rhoai-s3-object-storage-data`.
- Workbench notebook behavior is checked with
  `rhoai-data-science-ide-workflows`.
- Model registry and deployment handoff are checked with
  `rhoai-model-registry-workflows`.
- AutoGluon serving runtime details are checked with
  `rhoai-model-serving-platform` and `rhoai-api-tiers`.

## Prerequisite Review

- User has editor access to the selected OpenShift AI project.
- Project has an AI Pipelines server configured.
- Schedulable cluster capacity includes at least 4 CPUs and 16 GiB memory for
  the AutoML run.
- Training data is stored in an S3-compatible bucket or uploaded through the
  dashboard within the documented size limit.
- Project connection or Secret handling keeps object storage credentials out
  of Git.
- Model registry exists before promising model registration.
- AutoGluon serving runtime exists before promising deployment.

## Data Review

- Training file is CSV.
- File uses UTF-8 encoding.
- File uses comma delimiters.
- File has a header row.
- Dashboard-uploaded file size is 32 MiB or smaller.
- S3-loaded file size is 100 MB or smaller.
- Selected task type matches the data and business question.
- Required columns exist:
  - label column for binary classification, multiclass classification, or
    regression
  - target, timestamp, and ID columns for time series forecasting
- Known covariates for time series forecasting are values known in advance
  across the forecast horizon.

## Run Configuration Review

- Optimization run name and description are meaningful for later evidence.
- S3 connection and training file are the intended inputs.
- Top models to consider stays within the documented range:
  - 1 to 10 for tabular tasks
  - 1 to 7 for time series tasks
- Run immutability is understood before creation.
- Run stop/archive/delete operations are routed through AI Pipelines run
  lifecycle guidance.
- Externally imported AutoML pipeline names match the documented AutoGluon
  tabular or time series naming pattern.

## Evaluation Review

- Leaderboard is reviewed only after the run status is Completed.
- Optimized metric matches the selected task type.
- Additional metrics are interpreted in task context.
- Feature importance is not expected for time series forecasting.
- Confusion matrix is expected only for binary and multiclass classification.
- Model selection captures both leaderboard score and explainability evidence
  where available.

## Registry, Notebook, And Deployment Review

- Registered model appears in the selected model registry.
- Saved notebook is uploaded to a running workbench.
- The workbench has the S3-compatible connection used by the pipeline server.
- Notebook runs all cells without errors and returns sample predictions.
- Deployment uses model framework `autogluon - 1`.
- Deployment uses `AutoGluon ServingRuntime for KServe`.
- The AutoGluon serving runtime image is from `registry.redhat.io/rhoai`.
- Time series deployments set `AUTOGLUON_TS_ID_COLUMN` and
  `AUTOGLUON_TS_TIMESTAMP_COLUMN` when training used non-default names.
- Deployment reaches Ready status before it is used by downstream demos.

## Optional Read-Only Checks

Run only after following the OpenShift safety guard in `AGENTS.md`:

```bash
oc get datasciencepipelinesapplications -A
oc get pipelinerun -A | rg -i 'autogluon|automl'
oc get servingruntime -A | rg -i 'autogluon'
oc get inferenceservice -A
```

Schema checks:

```bash
oc explain servingruntime.serving.kserve.io
oc explain servingruntime.spec.supportedModelFormats
oc explain inferenceservice.serving.kserve.io
```

## Fail Conditions

Stop and correct the work if any of these are true:

- AutoML is presented as production-supported without Technology Preview
  context.
- AutoML is promised without an AI Pipelines server.
- Training data format or size exceeds documented limits.
- READMEs claim custom algorithm or hyperparameter selection.
- A run is treated as editable after creation.
- S3 credentials or model registry credentials are committed.
- Feature importance is claimed for time series forecasting.
- Confusion matrix is claimed for regression or time series forecasting.
- Deployment is promised without the AutoGluon serving runtime.
- Time series deployment omits required runtime environment variables when
  non-default ID or timestamp column names were used.
