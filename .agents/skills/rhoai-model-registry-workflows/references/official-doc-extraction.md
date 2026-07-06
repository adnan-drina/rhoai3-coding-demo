# Official Documentation Extraction

## Concept Model

The model catalog helps users discover and evaluate available generative AI
models. The model registry stores metadata and lifecycle records for models
from development through deployment.

With access to a model registry, data scientists and AI engineers can register,
store, version, deploy, archive, restore, and track models.

## Dashboard Paths

The official chapter uses these dashboard paths:

```text
AI hub -> Registry
AI hub -> Models -> Registry
```

Use the active dashboard label in runbooks, but preserve the official source
link when documenting the workflow.

## Registering A Model

Registering a new model creates the model record and its first version.

Prerequisites:

- user is logged in to OpenShift AI
- user has access to an available model registry

Required or optional inputs:

- model name
- optional model description
- version name
- optional version description
- source model format, for example `ONNX`
- source model format version
- model location, either object storage details or URI

Object storage details:

- endpoint
- S3-compatible bucket
- region
- path to a model or folder

The object storage path cannot point to a root folder. Existing connections can
autofill object storage details when the connection type contains a bucket.

URI registration:

- provide the model URI
- deployment of URI-registered models is currently supported for public OCI
  repositories only

Verification:

- model and version details appear on the version Details tab
- model and version appear on the Model registry page

## Registering A Model Version

Registering a new version adds another version record to an existing model.
The version workflow uses the same version metadata and model location model as
initial registration:

- version name
- optional version description
- source model format and format version
- object storage or URI location

Verification:

- the new version appears in Latest versions on the model Overview tab
- the new version appears in the Latest version column on the Model registry
  page

## Register And Store As OCI ModelCar

The Register and store option transforms model artifacts from object storage or
a URL into an OCI ModelCar image and registers the resulting metadata.

Key behavior:

- ModelCar target format supports fast deployment with KServe.
- The model transfer job runs as a background Kubernetes Job.
- Register and store copies the model into an OCI registry as a ModelCar image.
- Register metadata only points to an artifact already stored elsewhere.
- If a catalog model source is already an `oci://` URI, the UI forces Register
  mode only because the model is already in OCI format.

Required workflow inputs:

- model transfer job display name
- optional Kubernetes Job resource name
- project or namespace where the transfer job runs
- source location: object storage or URI
- destination OCI registry host and image reference
- source and destination credentials
- remaining model and version metadata

Source options:

- S3-compatible object storage with endpoint, bucket, region, path, access key
  ID, and secret access key
- URI with `https://`, `http://`, or `hf://` for Hugging Face Hub via
  `snapshot_download`

Destination options:

- registry host, such as `quay.io`
- image reference without scheme, such as `myorg/model:v1`
- username
- password or token

Background resources:

- ConfigMap with model metadata
- Secret with source credentials for S3 sources
- Secret with destination registry credentials in `.dockerconfigjson` format
- Kubernetes Job running the async-upload container image

The ConfigMap and Secrets are owned by the Job and garbage-collected when the
Job is deleted. A successful transfer sets the artifact URI to
`oci://<registry>/<image>:<tag>` for KServe ModelCar use.

## Model Transfer Jobs

Model transfer jobs copy models from a source location to an OCI registry as
ModelCar images.

The transfer jobs table includes:

- job display name and resource name
- model and version links when transfer succeeds
- namespace
- created timestamp
- author
- status: `Pending`, `Running`, `Complete`, or `Failed`

The page auto-polls while any job is pending or running. Failed jobs expose a
status dialog with Kubernetes events.

Retry behavior:

- retry creates a new transfer job with the same configuration
- retry creates a new Kubernetes resource name
- the failed job can optionally be deleted as part of retry

Delete behavior:

- deleting a transfer job removes the Kubernetes Job and owned ConfigMap and
  Secrets from the namespace
- deleting a transfer job does not remove the model from the OCI registry or
  model registry when the transfer completed successfully

## Viewing And Editing Metadata

Registered model list fields include:

- model name
- latest version
- deployments
- labels
- last modified timestamp
- owner

Model details include:

- labels
- description
- owner
- model ID
- last modified and created timestamps
- custom properties
- latest versions
- deployments

Version details include:

- labels
- description
- custom properties
- version ID
- author
- last modified and registered timestamps
- model source location
- model format information
- deployments

Model metadata edits affect all versions of the model. Version metadata edits
affect only that version. Editable metadata includes labels, description, and
custom properties. Version metadata also includes model format and format
version. URL property values are displayed as clickable links.

## Deploying From A Registry

Users can deploy a registered model version directly from the registry when the
model serving platform prerequisites are met.

High-level flow:

- select a target project
- OpenShift AI checks project connections for matches to the registered model
  location
- one matching connection is autoselected
- multiple matching connections are presented for selection
- if no matching connection exists, deployment can continue and the wizard
  autofills model location data as a new connection
- deployment wizard completes the model details, deployment, advanced settings,
  review, and deploy steps

Verification:

- deployment appears on AI hub -> Deployments
- deployment appears in Latest deployments on the model details page
- model version shows the deployment on its Deployments tab

## Editing Or Deleting Deployments

For deployments initiated from the registry, users can edit properties such as:

- deployment name
- model framework
- number of model server replicas
- model server size
- external route exposure
- token authentication and service accounts
- model location connection
- additional serving runtime arguments
- additional environment variables

The Model framework list shows only frameworks supported by the selected model
serving runtime.

Do not modify the port or model serving runtime arguments because they require
specific values; overriding them can cause deployment failure.

Deleting a deployed model version from the registry removes the deployment from
the version's Deployments tab after name confirmation.

## Archive And Restore

Archiving a model archives the model and all of its versions. Archiving a model
version archives only that version. Archived models and versions are unavailable
until restored.

Important constraints:

- models with deployed versions cannot be archived
- deployed model versions cannot be archived
- deployments must be deleted first from AI hub -> Deployments

Restore behavior:

- restoring an archived model returns the model and all versions to the
  registered models list
- restoring an archived model version returns the version to the versions list
  for the model
