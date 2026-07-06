---
name: rhoai-workbenches-custom-images
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when creating, documenting, reviewing, or rebuilding Red Hat OpenShift AI
  workbenches and custom workbench images: deriving images from default RHOAI
  workbench images, building compatible bring-your-own workbench images,
  ImageStream resources for dashboard-visible images, Kubeflow Notebook CRs for
  workbench pods, OAuth proxy injection, workbench display annotations,
  JUPYTER_IMAGE and NOTEBOOK_ARGS, custom CA environment variables and mounts,
  persistent workbench PVCs, /dev/shm emptyDir, optional Kueue queue labels,
  accelerator identifiers, and dashboard verification. For Gateway API
  path-prefix compatibility and NB_PREFIX migration, use
  rhoai-workbench-gateway-api-migration. For the dashboard-only import workflow
  for an existing custom image, use rhoai-workbench-image-import. For basic
  workbench administration, idle timeout, pod tolerations, and administrator
  troubleshooting, use rhoai-basic-workbenches. For project workbench
  lifecycle, use rhoai-project-workflows. For JupyterLab or code-server usage
  inside a running workbench, use rhoai-data-science-ide-workflows. Do NOT use
  for generic
  container image design unrelated to RHOAI workbenches, model serving,
  pipelines, Dev Spaces, or live troubleshooting; use the relevant rhoai-* or
  env-* skill.
---

# RHOAI Workbenches And Custom Images

Use this skill to create and review OpenShift AI workbench and custom image
guidance for the active baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product configuration details.
Official Red Hat documentation is product authority. This skill adapts the
official workbench image, dashboard import, CRD, and CLI guidance to this
repo's GitOps operating model where appropriate.

## Scope

This skill covers:

- custom workbench image purpose and Red Hat support boundaries
- building from a default OpenShift AI workbench image
- building a compatible custom image from another base image
- `USER 1001`, random UID/GID 0 compatibility, file permissions, `$HOME`,
  `/opt/app-root/src`, `/api`, and `NB_PREFIX` constraints
- deciding when detailed Gateway API path-prefix migration belongs in
  `rhoai-workbench-gateway-api-migration`
- deciding when to use dashboard import versus GitOps-managed registration
- dashboard Workbench images menu enablement and
  `dashboardConfig: disableBYONImageStream`
- optional software/package metadata and accelerator identifiers on imported
  images
- `ImageStream` resources that make custom workbench images available in the
  OpenShift AI dashboard
- `Notebook` resources that define workbench pods
- dashboard labels and annotations for custom images and workbenches
- OAuth proxy injection and workbench logout URL wiring
- `JUPYTER_IMAGE`, `NOTEBOOK_ARGS`, and custom certificate environment variables
- PVC-backed workbench storage and `/dev/shm` memory volume
- optional Kueue queue labels for queued workbench pods

This skill does not cover project workbench lifecycle, basic workbench
administration, idle timeout, pod
tolerations, cluster default PVC size, generic container hardening, enterprise
image signing, writing notebook code, Dev Spaces workspaces, model serving, or
pipeline authoring. Use `rhoai-project-workflows` for project workbench
creation/update/delete, `rhoai-basic-workbenches` for basic workbench
operations, `rhoai-data-science-ide-workflows` for IDE usage, and
`rhoai-cluster-pvc-size` for the Settings -> Cluster settings PVC-size
workflow.

## GitOps Policy

For this repo:

- Translate official `oc create` examples into ArgoCD-managed manifests.
- Treat dashboard-imported custom images as a product-supported operation, but
  prefer GitOps-managed `ImageStream` resources when the demo needs stable,
  reviewable desired state.
- Keep custom image `ImageStream` resources in the RHOAI application layer,
  normally `redhat-ods-applications`, unless a future design intentionally
  scopes images elsewhere.
- Keep user/team workbench `Notebook` resources in their target project.
- Verify the active CRDs before adding fields:
  - `oc explain imagestream.spec`
  - `oc explain notebook.spec`
- Do not copy dashboard-generated timestamps, last-activity values, or
  user-specific annotations into stable GitOps unless they are required.
- Do not handwrite OAuth, TLS, or CA fields from memory. Use the official
  pattern and verify active CRDs/secrets/configmaps.
- Do not claim Red Hat supports the contents of custom workbench images. Red
  Hat supports making custom images selectable in OpenShift AI; custom image
  contents remain the customer's responsibility.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Decide whether the task is:
   - custom workbench image build guidance
   - Gateway API path-prefix migration with
     `rhoai-workbench-gateway-api-migration`
   - dashboard custom image import with `rhoai-workbench-image-import`
   - custom workbench image registration
   - GitOps-managed workbench creation
   - Kueue-queued workbench scheduling
   - custom CA integration for workbench clients
4. Use `examples/custom-image-build-and-import-patterns.md` for build/import
   patterns and `examples/workbench-crd-patterns.md` for minimal manifest
   patterns.
5. Verify labels, annotations, image URL, project, PVC, and queue references.
6. Validate with `references/validation-checklist.md`.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/custom-image-build-and-import-patterns.md`
- `examples/workbench-crd-patterns.md`
