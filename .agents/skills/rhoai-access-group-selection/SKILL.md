---
name: rhoai-access-group-selection
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when documenting, reviewing, or performing the Red Hat OpenShift AI
  dashboard workflow for selecting existing OpenShift administrator and user
  groups: default all-authenticated access, default cluster-admin
  administrator behavior, Settings > User management group selection,
  system:authenticated access implications, and post-selection verification.
  Do NOT use for creating groups, adding or removing users, LDAP group sync,
  user deletion, PVC cleanup, central OIDC setup, or general OpenShift RBAC;
  use rhoai-users-groups-access or rhoai-central-authentication-service instead.
---

# RHOAI Access Group Selection

Use this skill for the OpenShift AI dashboard workflow that selects existing
OpenShift groups as OpenShift AI administrator and user groups on the active
baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior details.
Official Red Hat documentation is product authority. This skill adapts the
official Managing resources chapter to this repo's access-governance model.

## Scope

This skill covers only selection of existing groups in the OpenShift AI
dashboard:

- understanding default access for all authenticated OpenShift users
- understanding default OpenShift AI administrator access for users with
  OpenShift `cluster-admin`
- selecting one or more OpenShift groups under administrator groups
- selecting one or more OpenShift groups under user groups
- treating `system:authenticated` as broad access
- validating administrator and non-administrator access after saving

Use `rhoai-users-groups-access` for group creation, membership, LDAP sync,
revocation, user deletion, workbench shutdown, PVC backup, and cleanup.

## Demo Policy

For this repo:

- Prefer explicit groups such as `rhoai-admins` and `rhoai-users`, or
  environment-provided identity-provider groups, instead of broad access.
- Use `system:authenticated` only when unrestricted demo access is intentional
  and documented.
- Treat dashboard group selection as a manual or runbook-backed operation until
  official docs or schema verification provides an approved automation path.
- Do not model dashboard user-management settings as CR fields unless the
  active product docs or installed schema exposes them.
- Require access changes to be documented in `docs/OPERATIONS.md` when they
  become part of the active implementation.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Confirm the target administrator and user groups already exist in OpenShift.
3. Log in to OpenShift AI as a user with OpenShift AI administrator privileges.
4. Open the dashboard path:

   ```text
   OpenShift AI dashboard -> Settings -> User management
   ```

5. Select one or more OpenShift groups under administrator groups.
6. Select one or more OpenShift groups under user groups.
7. Avoid `system:authenticated` unless broad access is the documented intent.
8. Save changes.
9. Validate access with `references/validation-checklist.md`.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/group-selection-patterns.md`
