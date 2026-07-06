---
name: rhoai-storage-classes
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when documenting, reviewing, or managing Red Hat OpenShift AI storage
  classes from the Managing resources documentation: persistent storage
  concepts, dashboard storage class enablement, display names, descriptions,
  access mode selection, OpenShift AI default storage class selection, RWO,
  RWX, ROX, and RWOP access-mode behavior, and safe shared RWX storage use. Do
  NOT use for project cluster storage lifecycle or storage-class migration
  inside a project (use rhoai-project-workflows), workbench S3-compatible
  object storage data workflows or endpoint formatting (use
  rhoai-s3-object-storage-data), cluster default PVC size management
  (use rhoai-cluster-pvc-size), connection type templates (use
  rhoai-connection-types), workbench PVC mounts (use
  rhoai-workbenches-custom-images), OpenShift storage backend installation, AI
  pipelines object-store configuration, model registry persistence, or live
  cluster changes without the OpenShift safety guard.
---

# RHOAI Storage Classes

Use this skill for OpenShift AI administrator workflows that expose OpenShift
cluster storage classes to OpenShift AI users on the active baseline in
`docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior details.
Official Red Hat documentation is product authority. This skill adapts the
official Managing resources chapter to this repo's operations and GitOps review
model.

## Scope

This skill covers:

- persistent storage concepts used by OpenShift AI workbenches, project data,
  and model training
- storage classes as OpenShift-provided cluster resources surfaced in
  OpenShift AI
- enabling or disabling storage classes for OpenShift AI users
- configuring OpenShift AI-only display names and descriptions
- enabling access modes exposed to users for cluster storage
- selecting the default storage class for OpenShift AI
- choosing between `ReadWriteOnce`, `ReadWriteMany`, `ReadOnlyMany`, and
  `ReadWriteOncePod`
- shared storage risks and guardrails for `ReadWriteMany`

Use other skills for adjacent work:

- `rhoai-cluster-pvc-size` for Settings -> Cluster settings PVC size
- `rhoai-project-workflows` for project cluster storage lifecycle, attachment
  to workbenches, and storage-class migration inside a project
- `rhoai-dashboard-customization` for hiding or showing the Storage classes
  dashboard menu with `disableStorageClasses`
- `rhoai-connection-types` for connection type templates that users select
  when creating object storage connections
- `rhoai-s3-object-storage-data` for workbench Boto3 data workflows and object
  storage endpoint formatting
- `rhoai-workbenches-custom-images` for workbench image behavior and Notebook
  PVC mount context
- `env-troubleshoot` for live Pending pod, PVC, or storage access diagnostics

## Demo Policy

For this repo:

- Treat OpenShift storage classes as platform prerequisites owned by the
  underlying OpenShift cluster, not as RHOAI-only resources.
- Use dashboard storage class settings to control what OpenShift AI users can
  select; do not assume those settings change the underlying OpenShift storage
  class.
- Keep `ReadWriteOnce` as the default access mode for individual workloads.
- Use `ReadWriteMany` only for explicit shared-data scenarios and document the
  data integrity, security, and backup expectations.
- Do not select a default OpenShift AI storage class until the target AWS
  environment's available storage classes and access modes are verified.
- Keep storage-class dashboard workflows as runbook-backed operations until
  official docs or active schema verification identifies a reviewed GitOps
  representation.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/source-capture.md` and
   `references/official-doc-extraction.md`.
3. Confirm the operator has OpenShift AI administrator privileges.
4. Confirm the target OpenShift storage class exists and supports the desired
   access mode before exposing it to users.
5. Use the dashboard path:

   ```text
   OpenShift AI dashboard -> Settings -> Cluster settings -> Storage classes
   ```

6. Decide whether the task is:
   - enabling or disabling a storage class for users
   - editing the OpenShift AI display name or description
   - selecting access modes shown to users
   - setting the OpenShift AI default storage class
7. Validate with `references/validation-checklist.md`.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/storage-class-patterns.md`
