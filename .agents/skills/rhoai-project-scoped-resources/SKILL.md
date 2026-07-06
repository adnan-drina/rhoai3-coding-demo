---
name: rhoai-project-scoped-resources
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when documenting, reviewing, or rebuilding Red Hat OpenShift AI
  project-scoped resources: project-local workbench images, hardware profiles,
  and KServe model-serving runtime templates; dashboard visibility controlled
  by disableProjectScoped; resource naming and namespace rules; copying trusted
  global resources into a target project; and GitOps review of project-scoped
  resource manifests. Do NOT use for global RHOAI installation, generic
  OpenShift project RBAC, creating data science projects, custom workbench image
  build/import, full hardware profile schema design, full KServe serving runtime
  authoring, or live cluster changes without the OpenShift safety guard.
---

# RHOAI Project-Scoped Resources

Use this skill to manage OpenShift AI resources that should be visible only in
specific projects for the active baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior details.
Official Red Hat documentation is product authority. This skill adapts the
official project-scoped resource workflow to this repo's GitOps review model.

## Scope

This skill covers project-scoped copies of:

- workbench images
- hardware profiles
- model-serving runtimes for KServe, represented by Templates whose
  `objects.kind` is `ServingRuntime`

This skill does not cover full object schemas for those resources. Use the
component owner skill and active CRD/schema verification for detailed fields:

- `rhoai-project-workflows` for creating data science projects and the
  user-facing project-scoped resource handoff workflow
- `rhoai-workbenches-custom-images` for workbench image content and dashboard
  discovery
- `rhoai-hardware-profiles` for hardware profile schema, lifecycle, and
  recommended accelerator tags
- `rhoai-nvidia-gpu-accelerators` for accelerator infrastructure intent
- `rhoai-model-serving-platform` for KServe `ServingRuntime` details and
  model-serving platform behavior

## Resource Boundary

OpenShift AI users can access global resources across OpenShift AI projects.
They can access project-scoped resources only in projects where they have
permissions.

All resource names must be unique within a project. Project-scoped resources
must set `metadata.namespace` to the target project.

## Demo Policy

For this repo:

- Prefer project-scoped resources when a demo step needs different options for
  different teams, model-serving projects, or regulated audience scenarios.
- Keep global resources in the OpenShift AI application layer only when they
  should be visible across projects.
- Keep project-scoped resources in the same GitOps stage as the project that
  consumes them, or in a clearly ordered prerequisite stage.
- Set `disableProjectScoped: false` only when project-scoped resources should
  be enabled in the dashboard.
- Copy YAML only from trusted sources: official docs, existing verified
  resources, or reviewed GitOps manifests.
- Do not invent resource schemas. Verify `ImageStream`, `HardwareProfile`,
  `Template`, and embedded `ServingRuntime` fields before authoring.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Decide whether the target resource is a project-scoped:
   - workbench image
   - hardware profile
   - model-serving runtime template
4. Confirm project-scoped dashboard support is enabled with
   `disableProjectScoped: false`.
5. Copy YAML from a trusted source, update `metadata.namespace`, make
   `metadata.name` unique in the target project, and adjust only documented
   display-name fields.
6. Use `examples/project-scoped-resource-patterns.md` for review patterns.
7. Validate with `references/validation-checklist.md`.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/project-scoped-resource-patterns.md`
