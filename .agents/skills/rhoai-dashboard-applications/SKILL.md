---
name: rhoai-dashboard-applications
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when documenting, reviewing, or rebuilding Red Hat OpenShift AI dashboard
  application visibility: adding application tiles with OdhApplication,
  controlling whether administrators can add applications, showing or hiding
  application information panels and support-level badges, disabling connected
  applications, hiding the default Start basic workbench application, and
  GitOps review of OdhDashboardConfig and OdhApplication resources. For general
  dashboard feature flags, navigation visibility, Technology Preview dashboard
  controls, size profiles, and global OdhDashboardConfig customization, use
  rhoai-dashboard-customization. For user-facing connected application
  discovery, enablement, disabled tile removal, endpoint handling, and Start
  basic workbench access, use rhoai-connected-applications. Do NOT use for user/group access, custom
  workbench image import, general OpenShift console plugins, model catalog
  source governance, product installation, or destructive Operator uninstall
  work without explicit approval.
---

# RHOAI Dashboard Applications

Use this skill to manage OpenShift AI dashboard application tiles and related
dashboard visibility settings for the active baseline in
`docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product configuration details.
Official Red Hat documentation is product authority. This skill adapts the
official dashboard application-management chapter to this repo's GitOps review
model.

## Scope

This skill covers:

- adding dashboard application tiles with `OdhApplication`
- reviewing `OdhApplication` metadata and spec fields
- controlling the dashboard application enablement feature through
  `OdhDashboardConfig.spec.dashboardConfig.enablement`
- showing or hiding application information panels with `disableInfo`
- showing or hiding support-level badges with `disableISVBadges`
- hiding the default Start basic workbench application through the documented
  notebook controller setting
- understanding the effect and risk of disabling connected applications by
  uninstalling Operators

This skill does not cover OpenShift AI user permissions, dashboard custom
workbench image import, model catalog source governance, Models-as-a-Service
catalog entries, OpenShift console plugins, broad `OdhDashboardConfig`
feature-flag tuning, or general Operator lifecycle management. Use
`rhoai-connected-applications` for user-facing connected application workflows
and `rhoai-model-catalog-sources` for model catalog source governance.

## Demo Policy

For this repo:

- Prefer GitOps-managed `OdhApplication` and `OdhDashboardConfig` resources for
  stable demo dashboard behavior.
- Keep dashboard resources in the OpenShift AI application namespace, normally
  `redhat-ods-applications`, unless the active installation records a different
  applications namespace.
- Treat Operator uninstall and resource cleanup as destructive; do not perform
  it without explicit user approval.
- Use application tiles only for implemented demo capabilities. Do not add
  dashboard entries that imply an unavailable workflow.
- Do not invent `OdhApplication` or `OdhDashboardConfig` fields. Verify active
  schema before adding new fields.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Decide whether the task is:
   - adding a dashboard application tile
   - preventing dashboard users from adding applications
   - hiding information panels or support badges
   - hiding the default basic workbench tile
   - disabling a connected application and removing the underlying Operator
4. Use `examples/dashboard-application-patterns.md` for minimal review
   patterns.
5. Validate with `references/validation-checklist.md`.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/dashboard-application-patterns.md`
