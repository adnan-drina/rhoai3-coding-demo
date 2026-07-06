---
name: rhoai-connection-types
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when documenting, reviewing, or performing the Red Hat OpenShift AI
  dashboard workflow for managing connection types: viewing available
  connection type templates, previewing user connection forms, creating custom
  connection types with environment-variable fields and optional defaults,
  assigning category labels, duplicating existing or pre-installed types,
  editing custom types, enabling or disabling types for project users, deleting
  custom types, and understanding that edits or disablement do not update or
  remove existing user connections. Do NOT use for creating, updating, deleting,
  or consuming project connections (use rhoai-project-workflows), storing
  connection secrets,
  workbench S3 object storage data workflows or endpoint formatting (use
  rhoai-s3-object-storage-data), storage class administration (use
  rhoai-storage-classes), model registry setup, workbench creation, model
  serving configuration, or live cluster changes without the OpenShift safety
  guard.
---

# RHOAI Connection Types

Use this skill for the OpenShift AI dashboard workflow that manages connection
type templates for project resources on the active baseline in
`docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior details.
Official Red Hat documentation is product authority. This skill adapts the
official Managing resources chapter to this repo's operations and GitOps review
model.

## Scope

This skill covers:

- connection types as templates for user-created connections
- viewing available connection types in the current project
- previewing the connection form shown to users
- creating custom connection types with fields, section headings, category
  labels, and optional default values
- duplicating existing connection types, including pre-installed types
- editing custom connection types
- enabling or disabling connection types for project users
- deleting custom connection types
- preserving version history by duplicating instead of editing when needed

Use component-specific skills for how a connection is consumed by workbenches,
model servers, pipelines, model registry, object storage, or other resources.
Use `rhoai-project-workflows` for project connection lifecycle and connection
API annotations.
Use `rhoai-s3-object-storage-data` when a workbench consumes an S3-compatible
object storage connection.

## Demo Policy

For this repo:

- Treat connection types as user-facing templates, not as places to store real
  secret values.
- Prefer clear demo-specific names and descriptions that explain the target
  resource, such as object storage, model registry, external provider, or URI
  repository.
- Use category labels for dashboard filtering only; do not treat them as
  authorization or runtime behavior.
- Duplicate a pre-installed connection type before tailoring it for demo use.
- Duplicate a custom type before changing it when existing user-created
  connections must remain traceable to the old form design.
- Do not delete a custom type until the active demo no longer needs it and
  dependent user workflows have been checked.
- Keep dashboard workflows as runbook-backed operations until official docs or
  active schema verification identifies a reviewed GitOps representation.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/source-capture.md` and
   `references/official-doc-extraction.md`.
3. Confirm the operator has OpenShift AI administrator privileges.
4. Use the dashboard path:

   ```text
   OpenShift AI dashboard -> Settings -> Environment setup -> Connection types
   ```

5. Decide whether the task is view, create, duplicate, edit, enable/disable,
   or delete.
6. Preview the user form before saving changes that affect users.
7. Validate with `references/validation-checklist.md`.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/connection-type-patterns.md`
