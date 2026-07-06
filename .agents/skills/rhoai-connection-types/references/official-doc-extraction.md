# Official Documentation Extraction

This extraction is derived from the official RHOAI 3.4 chapter captured in
`source-capture.md`.

## Concept Model

A connection in OpenShift AI is made up of environment variables and their
values. Data scientists can add connections to project resources such as
workbenches and model servers.

A connection type is a template that users select when creating a connection.
The template includes customizable fields and optional default values. Using a
connection type reduces the time needed to add connections to data sources and
sinks.

OpenShift AI includes pre-installed connection types for common patterns such
as S3-compatible object storage, databases, and URI-based repositories.

## Administrator Capabilities

OpenShift AI administrators can:

- view connection types and preview user forms
- create a connection type
- duplicate an existing connection type
- edit a connection type
- enable or disable a connection type for users in a project
- delete a custom connection type

## Dashboard Path

Official dashboard path:

```text
OpenShift AI dashboard -> Settings -> Environment setup -> Connection types
```

The page displays connection types available for the current project.

## Viewing And Previewing

Prerequisite:

- The operator is logged in to OpenShift AI with administrator privileges.

Workflow:

1. Open Settings -> Environment setup -> Connection types.
2. Optionally use the connection type Options menu and choose Preview.
3. Review the form as it appears to users.

## Creating A Connection Type

Prerequisites:

- The operator is logged in to OpenShift AI with administrator privileges.
- The required and optional environment variables are known.

Creation fields:

- name
- resource name
- optional description
- at least one category label
- enablement choice for whether users can select the type
- form fields and section headings

Important behavior:

- A resource name is generated from the connection type name.
- The resource name can be edited before creation.
- The resource name cannot be changed after creation.
- Default category labels include `database`, `model registry`,
  `object storage`, and `URI`.
- New categories can be typed into the category field.
- Category labels are descriptive and help users sort connection types in the
  dashboard.
- Connection name and description fields are included by default; do not add
  duplicate fields for those.
- A model-serving compatible type can automatically add fields required for the
  corresponding model serving method.
- Preview the user form before saving.

Verification:

- The new connection type appears on the Settings -> Environment setup ->
  Connection types page.

## Duplicating A Connection Type

Use duplication when:

- creating a new type from an existing type
- tailoring a pre-installed type
- creating versions of a specific connection type

Workflow:

1. Open the Connection types page.
2. Find the type to duplicate.
3. Optionally preview the related user form.
4. Use the Options menu and choose Duplicate.
5. Edit the populated form for the new use case.
6. Preview the form.
7. Save.

Verification:

- The duplicated connection type appears on the Connection types page.

## Editing A Connection Type

Important behavior:

- Pre-installed connection types cannot be edited.
- Edits do not apply to existing connections that users previously created.
- If previous versions need to be tracked, duplicate the type instead of
  editing it.

Prerequisites:

- The operator is logged in to OpenShift AI with administrator privileges.
- The connection type exists.
- The connection type is not pre-installed.

Verification:

- The edited connection type appears on the Connection types page.
- The preview matches the expected user form.

## Enabling Or Disabling A Connection Type

Enablement controls whether the type is available when users create a
connection.

Important behavior:

- Disabling a connection type does not affect existing connections created from
  that type.
- A type can be pre-installed or administrator-created.

Workflow:

1. Open the Connection types page.
2. Find the connection type.
3. Use the Enable column toggle.

Verification:

- Enabled types appear as options when users add a connection to a project
  resource such as a workbench or model server.
- Disabled types do not appear in the available connection type list for new
  user connections.

## Deleting A Connection Type

Important behavior:

- Pre-installed connection types cannot be deleted.
- Pre-installed types can be disabled when they should not be visible to users.
- Custom connection types can be deleted.

Prerequisites:

- The operator is logged in to OpenShift AI with administrator privileges.
- The connection type exists.
- The connection type is not pre-installed.

Workflow:

1. Open the Connection types page.
2. Find the connection type.
3. Optionally preview the user form.
4. Use the Options menu and choose Delete.
5. Type the connection type name in the confirmation form.
6. Delete.

Verification:

- The connection type is no longer displayed in the Connection types list.

## Out Of Scope For This Chapter

This chapter does not define:

- backing Kubernetes resource schema for connection types
- GitOps representation of connection type templates
- secret schema for user-created connections
- how each project resource consumes connection values
- enterprise naming or versioning policy
- migration workflow for existing user-created connections

Use component-specific skills and active schema checks for those areas.
