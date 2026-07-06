---
name: rhoai-cluster-pvc-size
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when documenting, reviewing, or performing the Red Hat OpenShift AI
  dashboard workflow for managing the cluster default persistent volume claim
  size: Settings > Cluster settings PVC size, choosing a default size in GiB or
  MiB, understanding the workbench pod restart impact, restoring the default
  20GiB PVC size, and verifying that new PVCs use the configured size. Do NOT
  use for project cluster storage lifecycle or storage-class migration (use
  rhoai-project-workflows), storage class configuration, RWX storage design,
  object storage endpoints, resizing existing PVCs, workbench image PVC mounts, or live
  cluster changes without the OpenShift safety guard.
---

# RHOAI Cluster PVC Size

Use this skill for the OpenShift AI dashboard workflow that configures or
restores the cluster default PVC size for new OpenShift AI PVCs on the active
baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior details.
Official Red Hat documentation is product authority. This skill adapts the
official Managing resources chapter to this repo's operations and GitOps review
model.

## Scope

This skill covers:

- changing the cluster default PVC size from the OpenShift AI dashboard
- entering a default size in gibibytes or mebibytes
- understanding that changing the setting restarts the workbench pod and can
  make it unavailable for up to 30 seconds
- scheduling changes outside normal working hours when possible
- restoring the documented default PVC size of 20GiB
- verifying that new PVCs are created with the configured size

Use other skills for adjacent storage work:

- `rhoai-workbenches-custom-images` for workbench `Notebook` PVC mounts and
  custom image runtime behavior
- `rhoai-project-workflows` for project cluster storage lifecycle and
  storage-class migration inside a project
- `rhoai-storage-classes` for storage class visibility, access modes, RWX
  shared storage, default storage class selection, and object storage endpoint
  formatting
- `env-troubleshoot` for live storage or Pending pod diagnostics

## Demo Policy

For this repo:

- Pick a default PVC size that matches the demo's expected workbench data
  footprint and record it in `docs/OPERATIONS.md` when implemented.
- Do not imply this setting resizes existing PVCs; the official verification is
  about new PVCs.
- Treat PVC-size changes as live platform changes because they can restart a
  workbench pod.
- Prefer making the change outside the demo audience's working window.
- Keep dashboard configuration as a runbook-backed operation until the active
  GitOps implementation identifies an official or schema-verified field.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/source-capture.md` and
   `references/official-doc-extraction.md`.
3. Confirm the operator has OpenShift AI administrator privileges.
4. Decide whether the task is:
   - setting a custom default PVC size
   - restoring the documented 20GiB default
5. Use the dashboard path:

   ```text
   OpenShift AI dashboard -> Settings -> Cluster settings
   ```

6. Change the PVC size or click Restore Default.
7. Save changes.
8. Validate with `references/validation-checklist.md`.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/cluster-pvc-size-patterns.md`
