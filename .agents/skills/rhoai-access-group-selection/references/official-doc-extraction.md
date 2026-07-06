# Official Documentation Extraction

This extraction is derived from the official RHOAI 3.4 chapter captured in
`source-capture.md`.

## Access Defaults

- By default, all users authenticated in OpenShift can access OpenShift AI.
- By default, users with OpenShift `cluster-admin` permissions are OpenShift AI
  administrators.
- A cluster administrator can define additional administrator and user groups in
  OpenShift.
- Existing OpenShift groups are selected in the OpenShift AI dashboard to
  control OpenShift AI administrator and user access.

## Prerequisites

- The operator is logged in to OpenShift AI as a user with OpenShift AI
  administrator privileges.
- The OpenShift groups that will be selected as administrator and user groups
  already exist.
- For details about creating and managing the groups, use the broader
  `rhoai-users-groups-access` skill and the related official user/group
  documentation.

## Dashboard Procedure

Official dashboard path:

```text
OpenShift AI dashboard -> Settings -> User management
```

Selection workflow:

1. Under administrator groups, select an OpenShift group.
2. Repeat the administrator-group selection when multiple groups are needed.
3. Under user groups, select an OpenShift group.
4. Repeat the user-group selection when multiple groups are needed.
5. Save the changes.

## Broad Access Setting

`system:authenticated` grants access to all OpenShift-authenticated users.

Use it only when unrestricted access is intended. For controlled demo
environments, prefer explicit administrator and user groups.

## Verification

After saving:

- administrator users can log in to OpenShift AI and see the Settings
  navigation menu
- non-administrator users can log in to OpenShift AI
- non-administrator users can access individual components such as projects and
  workbenches

If the access model is intended to be restricted, also verify that users
outside the selected groups cannot use the dashboard.

## Out Of Scope For This Chapter

This chapter does not define:

- OpenShift group creation commands
- adding or removing users from groups
- LDAP group synchronization
- backing CR fields for the dashboard selection
- central OIDC configuration
- user deletion, workbench shutdown, PVC backup, or cleanup
- GitOps automation for dashboard user-management settings
