# Validation Checklist

Use this checklist before accepting connection type documentation, runbooks, or
operations changes.

## Source Review

- Product links use the active baseline in `docs/PLATFORM_BASELINE.md`.
- The official chapter URL uses the active `/3.4/` baseline path.
- The work is about dashboard-managed connection type templates.
- The change does not store real secret values in the connection type.
- Component-specific connection consumption is delegated to the relevant
  `rhoai-*` skill.

## Access And Visibility Review

- Operator has OpenShift AI administrator privileges.
- The Connection types menu is visible:

  ```text
  OpenShift AI dashboard -> Settings -> Environment setup -> Connection types
  ```

- If the menu is hidden, review
  `spec.dashboardConfig.disableAdminConnectionTypes` with
  `rhoai-dashboard-customization`.
- The current project context is intentional.

## Create Or Duplicate Review

- Required and optional environment variables are known before creating the
  type.
- Resource name is reviewed before creation because it cannot be changed after
  the type is created.
- At least one category label is set.
- Category labels are treated as descriptive dashboard metadata only.
- Connection name and description fields are not duplicated.
- Section headings make the user form easier to scan.
- Optional defaults do not contain real credentials or environment-specific
  private values.
- Model-serving compatible type is selected only when the target use case
  matches the corresponding model serving method.
- User form preview is reviewed before saving.

## Edit Review

- The target type is custom, not pre-installed.
- Existing user-created connections are not expected to update from the edit.
- Duplication is used instead of editing when version history matters.
- User form preview is reviewed before saving.

## Enable Or Disable Review

- Enablement matches whether users should see the type when adding a
  connection to a project resource.
- Disabling is not expected to affect existing user-created connections.
- Disabled pre-installed types are acceptable when they should not be visible
  to users.
- User selection is tested from a workbench or model server connection flow
  when the type is part of an active demo.

## Delete Review

- The target type is custom, not pre-installed.
- The type is no longer required by active demo workflows.
- Users and runbooks no longer reference the type.
- Delete confirmation uses the exact type name.
- The type is absent from the Connection types list after deletion.

## GitOps Review

- Do not add a GitOps representation until official docs or active schema
  verification identifies the backing resource.
- If future GitOps support is added, keep real connection values in Secrets or
  component-specific resources, not in the connection type template.
- Document stable demo connection types in `docs/OPERATIONS.md` when
  implemented.

## Fail Conditions

- A connection type template contains real credentials.
- A runbook expects edits to update existing user-created connections.
- A pre-installed type is edited or deleted instead of duplicated or disabled.
- The resource name is created without review.
- A disabled type is expected to appear for new user connections.
- A custom type is deleted while an active demo workflow still depends on it.
