---
name: rhoai-basic-workbenches
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when documenting, reviewing, or operating Red Hat OpenShift AI basic
  workbench administration: opening the Start basic workbench administration
  interface, starting another user's basic workbench, accessing a user's
  running basic workbench for troubleshooting, stopping one or all basic
  workbenches, configuring idle workbench timeout, adding workbench pod
  tolerations, verifying notebook-controller-culler-config, and troubleshooting
  Jupyter 404 access errors, workbench startup failures, and database or disk
  full errors. Do NOT use for project workbench creation or lifecycle (use
  rhoai-project-workflows), user-facing JupyterLab or code-server IDE
  workflows (use rhoai-data-science-ide-workflows), user-facing Start basic
  workbench access from the Enabled applications page (use
  rhoai-connected-applications), custom workbench
  image authoring, workbench image import, Gateway API migration, project
  connections, cluster default PVC size, storage class administration, or live
  cluster changes without the OpenShift safety guard.
---

# RHOAI Basic Workbenches

Use this skill for administrator workflows around basic workbenches on the
active product baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior details.
Official Red Hat documentation is product authority. This skill adapts the
official Managing resources chapter to this repo's operations and GitOps review
model.

## Scope

This skill covers:

- accessing the administration interface for basic workbenches
- starting a basic workbench owned by another user
- accessing another user's running basic workbench to fix configuration errors
  or troubleshoot environment issues
- stopping one user's basic workbench, multiple selected workbenches, or all
  running basic workbenches
- configuring idle workbench timeout from cluster settings
- verifying the `notebook-controller-culler-config` ConfigMap
- adding a toleration key to new workbench pods
- understanding that existing workbench pods receive the toleration only after
  restart
- troubleshooting common basic workbench administrator issues:
  - Jupyter 404 caused by missing OpenShift AI user group membership
  - workbench startup failure caused by failed pods or insufficient resources
  - database or disk full errors caused by exhausted workbench storage

Use other skills for adjacent work:

- `rhoai-project-workflows` for project workbench creation, start, update,
  deletion, connections, and project cluster storage
- `rhoai-connected-applications` for user-facing Start basic workbench access,
  image/container/accelerator selection, and settings restart workflow
- `rhoai-data-science-ide-workflows` for user-facing JupyterLab and
  code-server IDE workflows and initial symptom capture
- `rhoai-workbenches-custom-images` for workbench image and `Notebook` resource
  authoring
- `rhoai-workbench-image-import` for dashboard import of existing custom
  workbench images
- `rhoai-workbench-gateway-api-migration` for custom workbench image
  path-prefix behavior
- `rhoai-users-groups-access` for adding users to OpenShift AI user groups
- `rhoai-dashboard-customization` for showing or hiding the Start basic
  workbench tile
- `rhoai-cluster-pvc-size` and `rhoai-storage-classes` for storage size and
  storage class behavior
- `env-troubleshoot` for broader live cluster diagnostics

## Demo Policy

For this repo:

- Prefer project-scoped workbenches for the main demo architecture when the
  workflow needs projects, connections, data, models, or pipelines.
- Treat basic workbenches as an administrator-managed connected application for
  lightweight Jupyter workflows and troubleshooting support.
- Document any use of administrator access to another user's workbench as a
  support action, not a normal collaboration pattern.
- Use idle timeout and stop-all workflows to reduce cluster resource
  consumption before shutdown or when resource pressure affects the demo.
- Configure tolerations only after the target node taints and intended
  workbench node pools are documented.
- Do not claim a workbench troubleshooting case is resolved until the user can
  open the JupyterLab interface or the failure has been escalated to Red Hat
  Support with logs.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/source-capture.md` and
   `references/official-doc-extraction.md`.
3. Confirm the operator has OpenShift AI administrator privileges.
4. Decide whether the task is:
   - basic workbench administration interface access
   - start, access, or stop another user's basic workbench
   - idle timeout configuration
   - workbench pod toleration configuration
   - one of the documented administrator troubleshooting cases
5. Follow the relevant runbook in `examples/basic-workbench-admin-patterns.md`.
6. Validate with `references/validation-checklist.md`.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/basic-workbench-admin-patterns.md`
