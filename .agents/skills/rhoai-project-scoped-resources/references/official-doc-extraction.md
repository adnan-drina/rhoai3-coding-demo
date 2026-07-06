# Official Doc Extraction

This extraction is derived from the official RHOAI 3.4 chapter captured in
`source-capture.md`.

## Project-Scoped Resource Model

OpenShift AI users can access global resources in all OpenShift AI projects.
Project-scoped resources are visible only within projects where the user has
access permissions.

Cluster administrators can create these project-scoped resource types in any
OpenShift AI project:

| Resource type | Resource to search/copy | Display-name field documented in the chapter |
|---------------|-------------------------|----------------------------------------------|
| Workbench image | `ImageStream` | `metadata.annotations.opendatahub.io/notebook-image-name` |
| Hardware profile | `HardwareProfile` | `spec.displayName` |
| KServe model-serving runtime | `Template` whose `objects.kind` is `ServingRuntime` | `objects.metadata.annotations.openshift.io/display-name` |

All resource names must be unique within a project.

Users with project access can also create project-scoped resources for their
own project by using the user-facing project workflow described in separate
RHOAI documentation. This skill focuses on cluster-administrator creation.

## Prerequisites

Official prerequisites:

- access to the OpenShift console as a cluster administrator
- `disableProjectScoped` dashboard configuration option set to `false`

The project-scoped feature is controlled by dashboard configuration. Do not
assume it is enabled unless `disableProjectScoped: false` is present or the
active dashboard configuration/defaults confirm project-scoped resource support.

## Trusted YAML Sources

The official workflow tells administrators to copy YAML from a trusted source,
such as:

- an existing resource
- a Git repository
- documentation

The chapter gives a console workflow for copying from existing resources:

1. In the Administrator perspective, open Home -> Search.
2. Select the relevant project.
3. To search global OpenShift AI resources only, select
   `redhat-ods-applications`.
4. Search for the relevant resource type:
   - `ImageStream` for workbench images
   - `HardwareProfile` for hardware profiles
   - `Template` for serving runtimes, then find templates where
     `objects.kind` is `ServingRuntime`
5. Open the resource YAML and copy it.

## Creating The Project-Scoped Resource

After copying trusted YAML:

1. Select the target project.
2. Open the Import YAML page.
3. Paste the YAML.
4. Set `metadata.namespace` to the target project.
5. If needed, edit `metadata.name` so the name is unique in the target project.
6. Optionally edit the display name using the documented field for the
   resource type.
7. Create the resource.

Project display-name fields:

- workbench image:
  `metadata.annotations.opendatahub.io/notebook-image-name`
- hardware profile: `spec.displayName`
- serving runtime template:
  `objects.metadata.annotations.openshift.io/display-name`

## Verification

Verify as a regular OpenShift AI user:

- workbench images and hardware profiles appear when creating a workbench in
  the specified project
- serving runtimes appear during model deployment in the specified project

Use the workbench and deploying models documentation for user-facing
verification details.

## Unresolved Items

This chapter does not define:

- full `HardwareProfile` schema
- full `ImageStream` dashboard discovery labels and annotations
- full `Template` structure for KServe `ServingRuntime`
- exact `OdhDashboardConfig` path for `disableProjectScoped`
- GitOps sync ordering for project-scoped resources
- policy for when a resource should be global versus project-scoped

Use related official docs, active CRD/schema inspection, and repo GitOps policy
before authoring those details.
