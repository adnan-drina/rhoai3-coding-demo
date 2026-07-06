# Official Doc Extraction

This extraction is derived from the official RHOAI 3.4 chapter captured in
`source-capture.md`.

## Application Tiles

If an application is installed in the OpenShift cluster, an OpenShift AI
administrator can add a tile for that application to the OpenShift AI dashboard
so OpenShift AI users can access it from the Applications pages.

Prerequisites:

- OpenShift AI administrator privileges
- `spec.dashboardConfig.enablement` set to `true` in dashboard configuration;
  the documented default is `true`

Official resource:

- API group and kind: `dashboard.opendatahub.io/v1`, `OdhApplication`
- default namespace: `redhat-ods-applications`
- documented labels:
  - `app: odh-dashboard`
  - `app.kubernetes.io/part-of: odh-dashboard`

Documented `OdhApplication` spec fields include:

| Field | Purpose |
|-------|---------|
| `enable.validationConfigMap` | ConfigMap used by the dashboard enablement flow |
| `img` | SVG icon for the tile |
| `getStartedLink` | Get-started URL |
| `route` | Route name for the application |
| `routeNamespace` | Namespace containing the route |
| `displayName` | Tile display name |
| `kfdefApplications` | Related KfDef applications list |
| `support` | Support text |
| `csvName` | Related CSV name, if any |
| `provider` | Application provider |
| `docsLink` | Documentation URL |
| `quickStart` | Quick start identifier |
| `getStartedMarkDown` | Markdown content for the information panel |
| `description` | Tile summary |
| `category` | Support category such as Self-managed, Partner managed, or Red Hat managed |

Verification:

- application appears on the Applications Enabled page after users enable it
- the tile opens the intended route and information panel

## Preventing Application Additions

By default, OpenShift AI administrators can add applications to the dashboard
Applications Enabled page.

The documented control is:

```text
OdhDashboardConfig.spec.dashboardConfig.enablement
```

Set `enablement` to `false` to disable the ability for dashboard users to add
applications to the dashboard. The docs note that the default Start basic
workbench tile remains enabled by default and must be controlled separately.

## Disabling Connected Applications

The official chapter describes disabling connected applications by uninstalling
the related Operator from the `redhat-ods-applications` project after deleting
required Operator resources or instances.

Prerequisites:

- logged in to the OpenShift web console
- member of the OpenShift `cluster-admins` group
- target service installed or configured
- target application or component is enabled and visible on the Enabled page

Important boundary:

- uninstalling an Operator does not remove all CRDs or managed resources
- applications deployed by the Operator can continue to run
- configured off-cluster resources can continue to exist
- remaining CRDs, managed resources, applications, and off-cluster resources
  require manual cleanup

Expected dashboard effect:

- after the Operator is removed, the application is no longer available for
  users and is marked Disabled on the Enabled page; this can take a few minutes

## Application Information And Support Labels

The dashboard Exploring applications page can show available applications.
Application tiles can include:

- support-level labels such as Red Hat-managed, Partner managed, or
  Self-managed
- information panels with quick-start and documentation links

The documented dashboard configuration fields are:

| Field | `true` means | documented default |
|-------|--------------|--------------------|
| `spec.dashboardConfig.disableInfo` | hide application information panels | `false` |
| `spec.dashboardConfig.disableISVBadges` | hide support-level labels | `false` |

Use these fields when the demo needs a simpler Applications page or when
support-level labeling should be visible for audience context.

## Default Basic Workbench Application

The OpenShift AI dashboard includes the Start basic workbench application by
default.

To hide this tile, the chapter instructs administrators to edit the dashboard
configuration and set the notebook controller `enabled` value to `false`.

Verification:

- in the OpenShift AI dashboard, click Applications Enabled
- the Start basic workbench tile is no longer listed

Because the chapter's prose references the notebook controller section rather
than a full YAML example, verify the active schema before GitOps authoring:

```bash
oc explain odhdashboardconfig.spec.notebookController
```

## Unresolved Items

This chapter does not define:

- full CRD schema for every `OdhApplication` field
- complete GitOps lifecycle for dashboard application tiles
- validation ConfigMap contents for each application
- enterprise policy for which third-party or self-managed applications should
  be surfaced in the dashboard
- cleanup plan for CRDs, managed resources, application workloads, or
  off-cluster resources after Operator uninstall

Use active CRD schema, component-specific docs, and project governance before
implementing those areas.
