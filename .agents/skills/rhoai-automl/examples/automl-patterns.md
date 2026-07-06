# AutoML Patterns

These examples are review patterns. Verify active dashboard behavior,
pipeline server state, object storage credentials, registry availability,
serving runtimes, CRDs, and project access before copying anything into GitOps
or runbooks.

## AutoML Run Design Record

```text
Project: <data-science-project>
AutoML run: <run-name>
Task type: binary classification | multiclass classification | regression | time series forecasting
S3 connection: <project-connection-name>
Training file: s3://<bucket>/<path>.csv
Top models to consider: <1-10 tabular | 1-7 time series>
Technology Preview label: required
```

Review points:

- Confirm project editor access and AI Pipelines server availability.
- Confirm the CSV is UTF-8, comma-delimited, header-bearing, and within the
  documented size limit.
- Record the business question separately from the technical task type so the
  README can explain why the task matters.

## Task Column Mapping

```text
Tabular classification or regression:
  Label column: <column-to-predict>

Time series forecasting:
  Target column: <numeric-column-to-forecast>
  Timestamp column: <date-or-time-column>
  ID column: <series-id-column>
  Known covariates: <optional-columns-known-in-advance>
  Prediction length: <positive-integer>
```

Review points:

- Do not start the run until column names are verified from the CSV schema.
- Do not use known covariates unless the values are known across the forecast
  horizon.

## External AutoML Pipeline Naming

```text
Tabular pipeline:
  name: autogluon-tabular-training-pipeline
  version: autogluon-tabular-training-pipeline-<product-version>

Time series pipeline:
  name: autogluon-timeseries-training-pipeline
  version: autogluon-timeseries-training-pipeline-<product-version>
```

Review points:

- Use `rhoai-ai-pipelines` for importing pipelines and managing runs.
- Replace `<product-version>` with the active RHOAI product version from
  `docs/PLATFORM_BASELINE.md` when the imported pipeline is version-specific.

## AutoGluon ServingRuntime Review

```yaml
apiVersion: serving.kserve.io/v1alpha1
kind: ServingRuntime
metadata:
  name: kserve-autogluonserver
  annotations:
    openshift.io/display-name: AutoGluon ServingRuntime for KServe
spec:
  supportedModelFormats:
    - name: autogluon
      version: "1"
  protocolVersions:
    - v1
    - v2
  containers:
    - name: kserve-container
      image: registry.redhat.io/rhoai/odh-kserve-autogluon-server-rhel9@sha256:6d55374ef2e2ac09d772701a72d2ea370c57c34eb89c7b7a71ee204559c699a3
```

Review points:

- Keep this as a field-placement review pattern until the active GitOps design
  decides whether the runtime is cluster-wide desired state.
- Verify the full runtime spec against the official doc and live CRD schema
  before applying.
- Use `rhoai-api-tiers` for KServe API support posture.

## Time Series Deployment Environment

```text
AUTOGLUON_TS_ID_COLUMN=<training-run-id-column>
AUTOGLUON_TS_TIMESTAMP_COLUMN=<training-run-timestamp-column>
```

Review points:

- Set these only when the time series training data used non-default column
  names.
- Values must match the columns selected during optimization run creation.

## Saved Notebook Handoff

```text
1. Save notebook from the completed AutoML leaderboard.
2. Open a running workbench in the same project.
3. Attach the S3-compatible connection used by the AI Pipelines server.
4. Upload the notebook.
5. Run all cells.
6. Confirm sample predictions are returned.
```

Review points:

- Do not commit notebooks that include credentials or local outputs with
  sensitive data.
- Move reusable notebook logic into source-controlled examples only after it is
  scrubbed and tied back to the official workflow.

## Metric Interpretation

```text
Binary classification: accuracy
Multiclass classification: accuracy
Regression: R^2
Time series forecasting: MASE
```

Review points:

- Do not compare models with a metric that does not fit the selected task.
- Use feature importance and confusion matrices where available to explain why
  the selected model is plausible, not only because it tops the leaderboard.
