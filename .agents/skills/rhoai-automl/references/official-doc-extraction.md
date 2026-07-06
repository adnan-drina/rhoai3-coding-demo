# Official Documentation Extraction

This extraction is derived from the official RHOAI 3.4 guide captured in
`source-capture.md`.

## Support Posture

AutoML is Technology Preview in Red Hat OpenShift AI 3.4. Technology Preview
features are not supported with Red Hat production SLAs, might not be
functionally complete, and are not recommended by Red Hat for production use.

## Concept Model

AutoML trains, evaluates, and compares multiple models for tabular CSV data.
The user supplies training data, selects a prediction task type, and creates an
optimization run from the OpenShift AI dashboard. AutoML produces a
leaderboard, detailed model views, and handoffs to either model registry
registration or a saved notebook for prediction exploration.

After a selected model is registered, it can be deployed for inference with a
compatible AutoGluon serving runtime.

## Supported Task Types

Supported task types:

- binary classification
- multiclass classification
- regression
- time series forecasting

Time series forecasting requires:

- a numeric target column
- a timestamp column
- an ID column that identifies each time series
- optional known covariates
- a positive integer prediction length

## Technology Preview Limits

Captured limits:

- training data must be CSV
- dashboard upload limit is 32 MiB
- S3-loaded data limit is 100 MB
- custom algorithm selection is not available
- custom hyperparameter configuration is not available
- optimization runs cannot be edited after creation

## Prerequisites

Before creating an optimization run, verify:

- the user has editor access to an OpenShift AI project
- the project has an AI Pipelines server configured
- the cluster has at least 4 CPUs and 16 GiB memory available for scheduling
- training data is available in an S3-compatible bucket in CSV format
- the CSV is UTF-8 encoded, comma-delimited, and includes a header row

## Optimization Run Workflow

Dashboard path:

```text
Develop and train -> AutoML
```

The user selects a project, creates an optimization run, chooses or creates an
S3 data connection, selects a CSV file, selects the prediction task type, and
sets task-specific columns. The user can adjust the number of top models to
consider:

- tabular classification/regression: 1 to 10, default 3
- time series forecasting: 1 to 7, default 3

AutoML then trains candidate models, evaluates them, and shows run status on
the AutoML page.

## Externally Created Runs

AutoML can show runs created from imported AutoML pipelines when the imported
pipeline and version names follow the documented task-specific naming pattern.

Tabular task naming:

- pipeline name: `autogluon-tabular-training-pipeline`
- version name pattern: `autogluon-tabular-training-pipeline-<version>`

Time series task naming:

- pipeline name: `autogluon-timeseries-training-pipeline`
- version name pattern: `autogluon-timeseries-training-pipeline-<version>`

Use `rhoai-ai-pipelines` for the actual pipeline import, version, and run
lifecycle workflow.

## Evaluation Workflow

After a run completes, the user reviews the leaderboard and model details.

Model details can include:

- evaluation metrics
- feature importance
- confusion matrix

Feature importance is available for binary classification, multiclass
classification, and regression. It is not available for time series
forecasting. Confusion matrices are available for binary and multiclass
classification only.

The user can register a selected model to a model registry or save a notebook
for exploration.

## Prediction Notebook Workflow

After saving a notebook from the AutoML leaderboard, the user opens a running
workbench, attaches the S3-compatible object storage connection used by the
pipeline server, uploads the notebook, and runs all cells. The notebook loads
the trained model from S3-compatible storage and runs sample predictions.

Use `rhoai-data-science-ide-workflows` for general notebook and workbench IDE
behavior, and `rhoai-s3-object-storage-data` for object-storage access details.

## Deployment Workflow

After registering a model from the leaderboard, the user can deploy the model
version from the model registry with an AutoGluon serving runtime.

The official guide uses an AutoGluon serving runtime with these key values:

- `apiVersion: serving.kserve.io/v1alpha1`
- `kind: ServingRuntime`
- runtime name: `kserve-autogluonserver`
- display name: `AutoGluon ServingRuntime for KServe`
- supported model format: `autogluon`, version `1`
- protocol versions: `v1` and `v2`
- image:
  `registry.redhat.io/rhoai/odh-kserve-autogluon-server-rhel9@sha256:6d55374ef2e2ac09d772701a72d2ea370c57c34eb89c7b7a71ee204559c699a3`
- container arguments include model name, model directory, and HTTP port
- security context disables privilege escalation, runs unprivileged, runs as
  non-root, and drops all Linux capabilities
- documented resource request and limit pattern is 1 CPU and 2 GiB memory

Deployment wizard values:

- Model framework: `autogluon - 1`
- Serving runtime: `AutoGluon ServingRuntime for KServe`

For time series models with non-default column names, add these runtime
environment variables before deploying:

- `AUTOGLUON_TS_ID_COLUMN`
- `AUTOGLUON_TS_TIMESTAMP_COLUMN`

Use the exact column names selected when the optimization run was created.

## Metrics

Optimized metrics by task type:

- binary classification: accuracy
- multiclass classification: accuracy
- regression: R^2
- time series forecasting: MASE

AutoML can show additional leaderboard metrics depending on task type. Do not
compare models using a metric that is not meaningful for the selected task.

## Configuration Parameters

Common parameters:

- S3 connection
- training data file
- prediction task type
- top models to consider

Tabular task parameter:

- label column

Time series task parameters:

- target column
- timestamp column
- ID column
- known covariates
- prediction length

Auto-selected parameters:

- algorithms and hyperparameters
- train/test split
- evaluation metric

## Verification Signals

Expected signals:

- optimization run appears on the AutoML page with running or complete status
- completed run opens to a leaderboard
- registered model appears in the model registry
- saved notebook runs all cells without errors in a workbench
- notebook returns sample predictions
- deployed model reaches Ready status on the Deployments page

Failure signals:

- AutoML page cannot create runs because no AI Pipelines server is configured
- CSV schema cannot be parsed or required columns are missing
- training data exceeds size limits
- run is created with the wrong task type or column selections
- model cannot be registered because no model registry is available
- saved notebook cannot access the S3-compatible storage connection
- deployment cannot find the AutoGluon serving runtime
- time series deployment uses non-default columns but lacks required runtime
  environment variables
