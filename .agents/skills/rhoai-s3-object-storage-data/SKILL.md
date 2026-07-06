---
name: rhoai-s3-object-storage-data
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when documenting, reviewing, or authoring Red Hat OpenShift AI workbench
  workflows for S3-compatible object storage: creating a Boto3 S3 client from
  project-scoped connection environment variables, listing buckets, creating
  buckets, listing objects, downloading files, uploading files, copying objects
  between buckets, deleting objects, deleting empty buckets, formatting MinIO,
  Amazon S3, and other S3-compatible endpoints, troubleshooting endpoint,
  authentication, and network access, and handling self-signed certificate trust
  for in-cluster object stores. Do NOT use for connection type template
  administration (use rhoai-connection-types), storage class administration
  (use rhoai-storage-classes), broad certificate management (use
  rhoai-certificate-management), AI pipeline server artifact storage and
  pipeline object-store configuration (use rhoai-ai-pipelines),
  project/workbench/connection lifecycle (use
  rhoai-project-workflows), model registry/model serving storage, or live
  cluster changes without the OpenShift safety guard.
---

# RHOAI S3 Object Storage Data

Use this skill for OpenShift AI user workflows that access S3-compatible object
storage from workbenches on the active product baseline in
`docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product workflow details.
Official Red Hat documentation is product authority. This skill adapts the
official S3-compatible object storage guide to this repo's demo workflow and
GitOps review model.

## Scope

This skill covers:

- workbench prerequisites for using S3-compatible object storage
- project-scoped S3 credentials and connection handling
- Boto3 client setup from workbench environment variables
- bucket operations: list, create, and delete empty buckets
- object operations: list, download, upload, copy, and delete objects
- endpoint formatting for on-cluster MinIO, Amazon S3, and other
  S3-compatible stores
- connection verification and troubleshooting for endpoint reachability,
  authentication, and endpoint formatting
- self-signed certificate trust for in-cluster object stores and databases

Use other skills for adjacent work:

- `rhoai-connection-types` for administrator connection type templates and
  dashboard form design
- `rhoai-project-workflows` for creating projects, workbenches, project
  connections, and attaching connections to workbench workflows
- `rhoai-storage-classes` for OpenShift persistent storage classes and access
  modes
- `rhoai-certificate-management` for broader `DSCInitialization` trusted CA
  bundle policy and GitOps review
- `rhoai-workbenches-custom-images` and `rhoai-workbench-image-import` for
  workbench image behavior and package availability
- `rhoai-ai-pipelines` for AI Pipelines artifact storage, pipeline server
  object storage, workspaces, and pipeline object-store configuration
- `rhoai-automl` for AutoML training-data CSV requirements and AutoML
  S3-backed optimization run handoff
- `rhoai-autorag` for AutoRAG document source rules, JSON evaluation data, and
  generated notebook storage handoff
- `rhoai-mlflow` for MLflow artifact storage, project-specific S3 artifact
  overrides, and MLflowConfig review
- `rhoai-evaluation` for EvalHub custom data, LM-Eval S3 support, risk
  assessment artifacts, and disconnected translation-model cache handoff
- `rhoai-kfp-pipeline-authoring` for repo-specific KFP pipeline code that
  consumes object storage
- `rhoai-distributed-workload-workflows` for S3-compatible checkpoint storage
  in distributed training
- `rhoai-model-registry` and `rhoai-model-serving-platform` for model artifact
  storage consumption by registry or serving workflows

## Demo Policy

For this repo:

- Treat S3-compatible object storage credentials as project-scoped secrets.
  Never share credentials across projects in examples or demo manifests.
- Do not commit access keys, secret keys, session tokens, endpoint secrets, or
  bucket-specific credentials.
- Prefer IAM or bucket policies that grant only the minimum permissions needed
  for the specific project bucket.
- Use environment variables injected by OpenShift AI connections when showing
  Boto3 client setup from a workbench.
- Keep Boto3 package installation as an explicit notebook/workbench step unless
  the selected workbench image already includes it.
- Verify endpoint formatting before blaming application code.
- Use HTTPS endpoints where the storage provider supports it.
- For on-cluster object stores or databases with self-signed certificates,
  route CA trust decisions through `rhoai-certificate-management`.
- Treat destructive operations, especially object and bucket deletion, as
  explicit demo steps with verification before and after.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/source-capture.md` and
   `references/official-doc-extraction.md`.
3. Decide whether the task is:
   - connection and credential review
   - Boto3 client setup
   - bucket listing or creation
   - object list/download/upload/copy/delete
   - bucket deletion
   - endpoint formatting
   - self-signed CA trust
   - troubleshooting
4. Use `examples/s3-object-storage-patterns.md` for focused review patterns.
5. Validate with `references/validation-checklist.md`.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/s3-object-storage-patterns.md`
