# Validation Checklist

Use this checklist before accepting documentation, runbook, or implementation
work for OpenShift AI administrator and user group selection.

## Source Review

- Product links use the active baseline in `docs/PLATFORM_BASELINE.md`.
- The official chapter URL uses the active `/3.4/` baseline path.
- The work is limited to selecting existing OpenShift groups in the OpenShift
  AI dashboard.
- Group creation, membership, LDAP sync, user cleanup, and PVC backup are
  delegated to `rhoai-users-groups-access`.
- Central OIDC setup is delegated to `rhoai-central-authentication-service`.

## Access Model Review

- Default all-authenticated OpenShift access is documented when relevant.
- Default OpenShift AI administrator access for OpenShift `cluster-admin`
  users is documented when relevant.
- The selected administrator groups already exist in OpenShift.
- The selected user groups already exist in OpenShift.
- `system:authenticated` is used only when unrestricted access is the explicit
  intent.
- If access should be restricted, `system:authenticated` is not selected as a
  user group.

## Dashboard Procedure Review

- The runbook uses the official path:

  ```text
  OpenShift AI dashboard -> Settings -> User management
  ```

- Administrator groups are selected under administrator groups.
- User groups are selected under user groups.
- Multiple groups are added by repeating the text-box selection.
- The procedure ends with saving changes.
- No undocumented CR fields or annotations are used to represent the dashboard
  setting.

## Verification Review

Validate with representative users:

- an administrator-group member can log in and see Settings
- a user-group member can log in
- a user-group member can access components such as projects and workbenches
- a user outside the selected groups is denied access when restricted access is
  intended

Optional read-only OpenShift checks, after following the safety guard in
`AGENTS.md`:

```bash
oc get groups
oc describe group <rhoai-admin-group>
oc describe group <rhoai-user-group>
```

## Fail Conditions

- The runbook claims restricted access while `system:authenticated` still
  grants access.
- The selected groups do not exist in OpenShift.
- A non-administrator is expected to edit dashboard user management.
- The change uses undocumented dashboard backing fields.
- Verification checks only administrator access and skips normal user access.
