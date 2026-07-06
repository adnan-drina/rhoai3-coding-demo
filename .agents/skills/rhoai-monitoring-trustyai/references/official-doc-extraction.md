# Official Documentation Extraction

This extraction is derived from the official RHOAI 3.4 Monitoring your AI
systems guide captured in `source-capture.md`.

## Monitoring Overview

The guide uses TrustyAI to monitor models for:

- bias: unfair patterns in data or predictions
- data drift: changes in incoming data distribution compared with training
  data

TrustyAI monitoring helps data scientists check whether machine-learning
models remain transparent, fair, and reliable. It is not a general-purpose LLM
evaluation or guardrails workflow.

## Administrator Configuration

Administrator tasks:

- configure monitoring for the model-serving platform
- enable the TrustyAI component in OpenShift AI
- optionally configure TrustyAI to use a database instead of PVC storage
- install a TrustyAI service in each project that contains monitored models
- optionally configure TrustyAI with KServe RawDeployment mode

TrustyAI component enablement:

- `DataScienceCluster.spec.components.trustyai.managementState: Managed`
- the `trustyai-service-operator-controller-manager` deployment should have a
  running pod in `redhat-ods-applications`

## Storage And Database Configuration

TrustyAI can use:

- PVC storage
- database storage

The guide recommends database storage for improved scalability, performance,
and data management.

Database notes:

- supported `databaseKind` value shown by the guide is `mariadb`
- external MySQL must be in-cluster and at least MySQL 5.x; the guide
  recommends MySQL 8.x
- MariaDB must be in-cluster and MariaDB 10.3 or later; the guide recommends
  at least MariaDB 10.5
- TLS does not work with MariaDB Operator 0.29 or later
- MariaDB Operator for `s390x` is not supported

Database Secret fields from the guide:

- `databaseKind`
- `databaseUsername`
- `databasePassword`
- `databaseService`
- `databasePort`
- `databaseGeneration`
- `databaseName`

TLS database Secret:

- Secret type `kubernetes.io/tls`
- fields `tls.crt` and `tls.key`

PVC-to-database migration:

- `TrustyAIService` annotation `trustyai.opendatahub.io/db-migration: "true"`
- `spec.storage.format: "DATABASE"`
- `spec.storage.databaseConfigurations`
- keep existing folder, size, data filename, and metrics schedule aligned with
  the previous CR.

## TrustyAIService Installation

Install one TrustyAI service instance per project namespace that contains
monitored models. The guide warns that multiple instances in one project can
cause unexpected behavior.

Important support boundary:

- the guide states that TrustyAI only supports models deployed with OpenVINO
  Model Server
- non-OVMS models are not supported
- installing TrustyAI in a namespace with non-OVMS models can cause TrustyAI
  service errors

Resource:

- `apiVersion: trustyai.opendatahub.io/v1`
- `kind: TrustyAIService`
- `metadata.name: trustyai-service`
- `spec.storage.format: "DATABASE"` or `"PVC"`
- database path: `spec.storage.databaseConfigurations`
- PVC path: `spec.storage.folder`, `spec.data.filename`,
  `spec.data.format: "CSV"`
- metric schedule: `spec.metrics.schedule`
- optional batch size: `spec.metrics.batchSize`

Healthy signal:

- `oc get pods | grep trustyai` shows the TrustyAI service pod running.

## KServe RawDeployment Integration

For KServe RawDeployment mode, the guide requires:

- updating the `inferenceservice-config` ConfigMap in `redhat-ods-applications`
- adding logger settings:
  - `caBundle`
  - `caCertFile`
  - `tlsSkipVerify: false`
- creating a model-namespace ConfigMap with
  `service.beta.openshift.io/inject-cabundle: "true"`

Verification:

- when inferences are sent to the KServe Raw model, TrustyAI acknowledges data
  capture in output logs
- if no data appears in TrustyAI logs, complete the configuration and redeploy
  the pod

## Project Setup And Data

Data scientist setup tasks:

- authenticate to TrustyAI external endpoints through the OAuth proxy
- obtain a user token or sufficiently privileged service account token
- upload training data
- send model inference data
- optionally label fields with readable names

Endpoints:

- route: `trustyai-service`
- `/data/upload` for training data upload
- `/info` for model metadata and uploaded data verification
- `/info/names` for input and output field name mappings
- `/q/openapi` for endpoint and payload discovery

Training data requirements:

- training/reference data must be uploaded before bias or data-drift metrics
  are meaningful
- the deployed model must be registered with TrustyAI
- the `InferenceService` logger should show mode `all` and a URL pointing to
  the TrustyAI service in the model namespace

Observation metric:

- `trustyai_model_observations_total` verifies observed model inferences in
  OpenShift metrics.

## Bias Monitoring

Bias monitoring checks for model behavior that might skew outcomes for
protected groups or features.

Bias metric setup requires:

- metric name
- metric type
- protected attribute
- privileged value
- unprivileged value
- model output
- favorable output value
- violation threshold
- metric batch size

CLI endpoint from the guide:

- `POST /metrics/group/fairness/spd/request`

Payload fields:

- `modelId`
- `protectedAttribute`
- `privilegedAttribute`
- `unprivilegedAttribute`
- `outcomeName`
- `favorableOutcome`
- `batchSize`

Metric lifecycle:

- dashboard creation
- CLI creation
- dashboard duplication when edits are needed
- dashboard deletion
- CLI deletion through `DELETE /metrics/$METRIC/request`
- request listing through `GET /metrics/{{metric}}/requests` or
  `GET /metrics/all/requests`

Bias metrics captured by the guide:

- Statistical Parity Difference
- Disparate Impact Ratio

Interpretation examples from the guide:

- SPD value of `0` indicates fairness for the selected attribute.
- SPD between `-0.1` and `0.1` is considered reasonably fair in the guide's
  example.
- SPD outside that range indicates unfairness for the selected attribute.
- Negative SPD indicates bias against the unprivileged group.
- Positive SPD indicates bias against the privileged group.
- DIR threshold depends on the use case; the guide gives `0.8` to `1.2` as an
  example reasonable range.

## Data Drift Monitoring

Data drift compares incoming inference data distributions with original
training/reference data.

Drift metrics captured by the guide:

- MeanShift
- FourierMMD
- KSTest
- ApproxKSTest

CLI endpoint from the guide:

- `POST /metrics/drift/meanshift/request`

Payload fields:

- `modelId`
- `referenceTag`

Metric lifecycle:

- CLI creation
- CLI deletion through `DELETE /metrics/drift/meanshift/request`
- request listing through `GET /metrics/drift/meanshift/requests` or
  `GET /metrics/all/requests`
- dashboard viewing through OpenShift Observe and `trustyai_*` queries

Interpretation guidance:

- MeanShift is best when each feature is normally distributed.
- For unknown or non-normal distributions, choose a different drift metric.
- A p-value less than `0.05` indicates statistically significant drift in the
  guide's MeanShift discussion.
- A p-value of at least `0.05` indicates no statistically significant evidence
  of drift in that discussion.

## Credit Card Scenario

The guide includes a credit-card scenario that:

- deploys a storage container, serving runtime, and model
- downloads training data
- labels `model_name`, `data_tag`, request, and response fields
- uploads training data
- maps input/output field names
- verifies data through `/info`
- creates a recurring MeanShift drift metric with `referenceTag: TRAINING`
- views `trustyai_meanshift` in OpenShift Observe
- sends simulated real-world inferences to observe drift

Treat this as an example scenario. Do not reuse its model, data, or field names
unless the demo explicitly adopts that example.
