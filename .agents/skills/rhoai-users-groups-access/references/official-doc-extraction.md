# Official Doc Extraction

This extraction is derived from the official RHOAI 3.4 chapter captured in
`source-capture.md`.

## User Types

OpenShift AI user types:

| Type | Permissions |
|------|-------------|
| User | Can access and use individual OpenShift AI components, such as workbenches and AI pipelines. |
| Administrator | Can do user actions plus configure OpenShift AI settings, access and manage workbenches, and access/manage pipeline applications for any project. |

Default behavior:

- all OpenShift users can access OpenShift AI
- OpenShift `cluster-admin` users automatically have administrator access in
  OpenShift AI

Optional restricted behavior:

- create OpenShift groups for users and administrators
- add identity-provider groups or OpenShift-created groups
- select those groups in the OpenShift AI dashboard

Some operations require `cluster-admin`, including adding/removing users from
OpenShift AI groups and managing custom user environment/storage configuration
such as Jupyter notebook resources, ConfigMaps, and PVCs.

Session caveat: OpenShift AI session management is separate from OpenShift
authentication. When permissions change, users must log out of active sessions
for changes to take effect.

## Viewing Users

Prerequisites:

- OpenShift AI user group, administrator group, or both exist
- current operator has `cluster-admin`
- OpenShift has a supported identity provider configured

Official console path:

```text
OpenShift web console -> User Management -> Groups -> <group name>
```

Examples in the Red Hat docs use names such as `rhods-admins` and
`rhods-users`.

## Adding Users To Groups

By default, all OpenShift users can access OpenShift AI. To restrict access,
define user/admin groups and add accounts to the appropriate groups.

Effects:

- user group members can access OpenShift AI dashboard components such as AI
  pipelines and Jupyter; by default they can access pipeline apps in projects
  they created
- administrator group members can access developer/admin dashboard functions
  and configure pipeline applications for any project
- users outside the selected user/admin groups cannot view the dashboard, use
  associated services, or access the Cluster settings page

If LDAP is used as the identity provider, LDAP groups must be synced into
OpenShift.

Official console path:

```text
OpenShift web console -> User Management -> Groups -> <group> -> Actions -> Add Users
```

User lists are managed in the OpenShift web console.

## Selecting OpenShift AI Groups

Default access remains all authenticated OpenShift users unless restricted.
`system:authenticated` allows all authenticated OpenShift users to access
OpenShift AI.

Prerequisites:

- logged in to OpenShift AI as a user with OpenShift AI administrator
  privileges
- target groups already exist in OpenShift

Official dashboard path:

```text
OpenShift AI dashboard -> Settings -> User management
```

Select one or more groups under:

- Red Hat OpenShift AI administrator groups
- Red Hat OpenShift AI user groups

Verification:

- administrator users can log in and see Settings
- non-administrator users can log in and use individual components such as
  projects and workbenches

## Deleting Users

Before deleting a user from OpenShift AI, Red Hat recommends backing up data on
PVCs.

Deletion workflow:

1. Stop workbenches owned by the user.
2. Revoke user access to workbenches.
3. Remove the user from the allowed group in the identity provider.
4. After deletion, delete associated configuration files from OpenShift.

OpenShift AI administrators can stop basic workbenches owned by other users
from the basic workbench Administration tab. They can stop one user's server or
all workbenches.

To revoke access when using OpenShift AI groups:

- remove the user from the OpenShift AI user/admin group in the OpenShift web
  console
- confirm the user is no longer visible in the group
- check the default workbench project (`rhods-notebooks` or custom workbench
  namespace) for `jupyter-nb-<username>-*` pods and delete stale pods if needed
- delete projects that belong to the user, if appropriate

PVC backup is especially important before deleting a user and before
uninstalling OpenShift AI.

Cleanup after deleting users:

- delete the user's PVC named `jupyter-nb-<username>` in the default workbench
  project or custom workbench namespace
- delete the user's ConfigMap named
  `jupyterhub-singleuser-profile-<username>` in the same project/namespace

Verification:

- user sees an access-needed message if they try OpenShift AI
- user's single-user profile, PVC, and ConfigMap are no longer visible

## Unresolved Items

This chapter does not define:

- exact GitOps mechanism for dashboard user-management settings
- identity-provider configuration
- LDAP sync configuration
- enterprise access-review cadence
- backup implementation for user PVC data
- project deletion policy for user-owned projects

Use official OpenShift docs, organization IAM policy, and project governance
before implementing those areas.
