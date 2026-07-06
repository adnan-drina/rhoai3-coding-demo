---
name: rhoai-dashboard-customization
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when documenting, reviewing, or rebuilding Red Hat OpenShift AI dashboard
  customization through the OdhDashboardConfig custom resource: editing
  spec.dashboardConfig, showing or hiding dashboard navigation items, enabling
  or disabling dashboard feature flags, handling Technology Preview and
  Developer Preview dashboard controls, model server and workbench size
  configuration, notebookController visibility, template ordering, usage data
  collection visibility, and dashboard configuration validation. Do NOT use for
  OdhApplication tiles, application enablement flows, user/group selection,
  cluster default PVC size, storage class settings, connection type templates,
  custom workbench image import, Feature Store configuration, KServe serving
  configuration, or live cluster changes without the OpenShift safety guard.
---

# RHOAI Dashboard Customization

Use this skill to customize the OpenShift AI dashboard interface through
`OdhDashboardConfig` on the active product baseline in
`docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product configuration details.
Official Red Hat documentation is product authority. This skill adapts the
official Managing resources chapter to this repo's GitOps review model.

## Scope

This skill covers:

- editing the `odh-dashboard-config` instance in the OpenShift AI application
  namespace
- using `spec.dashboardConfig` to show or hide dashboard navigation items and
  feature controls
- preserving default behavior when a field is absent
- handling fields with inverted `disable*` semantics
- documenting Technology Preview and Developer Preview dashboard controls
- configuring `spec.notebookController.enabled`
- reviewing `spec.modelServerSizes`, `spec.notebookSizes`, and
  `spec.templateOrder`
- validating dashboard behavior after changes

Use other skills for adjacent work:

- `rhoai-dashboard-applications` for `OdhApplication` tiles and application
  enablement
- `rhoai-access-group-selection` for selecting existing administrator and user
  groups
- `rhoai-cluster-pvc-size` for Settings -> Cluster settings PVC size
- `rhoai-storage-classes` for Settings -> Cluster settings -> Storage classes
- `rhoai-connection-types` for Settings -> Environment setup -> Connection
  types
- `rhoai-basic-workbenches` for basic workbench administration and
  troubleshooting
- `rhoai-model-serving-platform` for KServe, NIM, serving runtime, runtime
  parameter, and deployment-strategy behavior
- `rhoai-model-catalog-sources` for AI hub -> Catalog source governance,
  Hugging Face or YAML catalog sources, and model visibility patterns
- `rhoai-model-catalog-workflows` for AI hub -> Catalog discovery, performance
  evaluation, registration, and deployment workflows
- `rhoai-gen-ai-playground` for Gen AI studio playground, custom endpoint, AI
  asset endpoint, RAG upload, reusable prompt, and MCP user workflows
- `rhoai-model-registry` for AI hub -> Registry provisioning, permissions, and
  administrator lifecycle
- `rhoai-model-registry-workflows` for AI hub -> Registry user workflows such
  as registering, deploying, archiving, and restoring models
- `rhoai-workbenches-custom-images` for importing custom workbench images
- component-specific `rhoai-*` skills for enabling the underlying platform
  components surfaced by dashboard flags

## Demo Policy

For this repo:

- Manage long-lived dashboard configuration through GitOps once active GitOps
  implementation exists.
- Treat `redhat-ods-applications` as the default OpenShift AI application
  namespace unless the active installation records another namespace.
- Preserve unrelated `OdhDashboardConfig` fields when adding or changing one
  option.
- Do not enable Technology Preview or Developer Preview dashboard features
  without documenting their support posture in the relevant README or
  operations notes.
- Do not claim that a feature works only because its dashboard menu is visible;
  the underlying component must also be installed and validated.
- Do not use deprecated or read-only options for new behavior.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/source-capture.md` and
   `references/official-doc-extraction.md`.
3. Identify the dashboard field that controls the desired UI behavior.
4. Check whether the option is absent and therefore using the documented
   default.
5. Add or edit only the needed field under the correct `spec` section.
6. Preserve unrelated existing `OdhDashboardConfig` settings.
7. Document any Technology Preview or Developer Preview status.
8. Validate with `references/validation-checklist.md`.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/dashboard-customization-patterns.md`
