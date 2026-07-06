# Validation Checklist

Use this checklist when reviewing model registry workflow documentation,
notebooks, runbooks, or demo scripts.

## Source Alignment

- The RHOAI documentation version matches `docs/PLATFORM_BASELINE.md`.
- The official Working with model registries source is recorded when the
  workflow is introduced.
- The task is a user workflow in an existing registry, not administrator
  provisioning or database configuration.
- Serving-runtime details are checked against `rhoai-model-serving-platform`.

## Access And Registry Selection

- The user has access to an available registry.
- The runbook identifies the correct registry from the Model registry drop-down.
- The runbook uses the active dashboard path while preserving the official
  source link.

## Registration

- Model name and version name are present.
- Source model format and format version are recorded.
- Object storage registration includes endpoint, bucket, region, and non-root
  path.
- Connection autofill is used only with object storage connections that contain
  a bucket.
- URI registration is not described as deployable unless the URI is a public
  OCI repository.

## Register And Store

- Register and store is used only when artifacts should be copied into an OCI
  ModelCar image.
- Source credentials and destination registry credentials are not committed.
- Destination image reference has no URI scheme.
- Transfer job namespace is intentional and accessible to the user.
- Non-admin users select only projects or namespaces they can access.
- The model registry access warning is handled by selecting a different project
  or fixing permissions.

## Transfer Jobs

- Transfer job status is monitored until `Complete` or `Failed`.
- Failed transfer jobs are inspected through the status dialog and event log.
- Retry is described as creating a new transfer job and Kubernetes resource
  name.
- Deleting a transfer job is not described as deleting successfully transferred
  model artifacts.

## Metadata

- Model-level metadata changes are documented as affecting all versions.
- Version-level metadata changes are documented as affecting only that version.
- Labels, descriptions, custom properties, model format, and format version are
  used intentionally.
- URL custom property values are expected to render as clickable links.

## Deployment

- The model serving platform prerequisites are satisfied before deployment.
- Matching project connections are reviewed before continuing.
- Deployment verification checks AI hub -> Deployments and registry Deployments
  tabs.
- Port and protected model serving runtime arguments are not overwritten.
- Token authentication, routes, replicas, model server size, and runtime
  arguments are reviewed with `rhoai-model-serving-platform`.

## Archive And Restore

- Models with deployed versions are not archived.
- Deployed model versions are not archived.
- Deployments are deleted before archive operations.
- Restore behavior is checked on the active model or version list.

## Fail Conditions

Stop and correct the work if any of these are true:

- A model location path points to a bucket root.
- URI-registered models are described as deployable from non-public or
  non-OCI repositories.
- Source or destination credentials are committed.
- A transfer job delete step claims to delete OCI registry artifacts.
- A deployed model or deployed version is archived without deleting
  deployments first.
- Deployment runtime parameters are changed without serving-platform review.
