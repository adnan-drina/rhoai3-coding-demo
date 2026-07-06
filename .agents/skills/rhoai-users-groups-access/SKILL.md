---
name: rhoai-users-groups-access
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when documenting, reviewing, or operating Red Hat OpenShift AI user and
  group access: OpenShift AI user versus administrator permissions, default
  access behavior, restricting access through OpenShift groups, adding users to
  RHOAI user/admin groups, session/logout caveats, LDAP group sync
  requirements, revoking access, stopping user-owned basic workbenches, backing
  up PVC data, and cleanup of user PVCs and ConfigMaps. For the dashboard-only
  workflow that selects existing administrator and user groups, use
  rhoai-access-group-selection. Do NOT use for OIDC central auth service setup,
  general OpenShift RBAC design, project-level access management (use
  rhoai-project-workflows), service accounts, or live destructive cleanup
  without explicit confirmation.
---

# RHOAI Users Groups Access

Use this skill to manage and document OpenShift AI user and group access for
the active baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior details.
Official Red Hat documentation is product authority. This skill adapts the
official user/group management guidance to this repo's demo governance model.

## Access Model

OpenShift AI users are authenticated through OpenShift. By default, all
OpenShift-authenticated users can access OpenShift AI. Users with OpenShift
`cluster-admin` permissions have administrator access in OpenShift AI.

To restrict access, define OpenShift groups for:

- OpenShift AI users
- OpenShift AI administrators

Then select those groups in the OpenShift AI dashboard using
`rhoai-access-group-selection`. Do not model backing CR fields for the
dashboard setting unless the active product documentation or CRD schema
explicitly exposes them.

## Demo Policy

For this repo:

- Prefer explicit OpenShift groups for demo access instead of relying on
  `system:authenticated`.
- Use descriptive group names such as `rhoai-users` and `rhoai-admins` unless
  the environment already provides identity-provider groups.
- Treat `cluster-admin` as required for group membership changes, custom
  workbench resources, ConfigMaps, and PVC cleanup.
- If LDAP backs the identity provider, require LDAP group sync into OpenShift
  before using those groups in OpenShift AI.
- Require users to log out of active OpenShift AI/Jupyter sessions after
  permission changes.
- Treat PVC, ConfigMap, project, and workbench cleanup as destructive.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Decide whether the task is:
   - viewing OpenShift AI group members
   - adding users to OpenShift AI access groups
   - selecting OpenShift AI user/admin groups in the dashboard
     with `rhoai-access-group-selection`
   - revoking access
   - deleting a user and cleaning up user-owned resources
4. Use `examples/user-group-access-patterns.md` for command and review
   patterns.
5. For live work, follow the OpenShift safety guard in `AGENTS.md`.
6. Validate with `references/validation-checklist.md`.

## Deletion Guard

Before removing a user or their resources:

- stop user-owned basic workbenches
- remove the user from OpenShift AI groups or identity-provider groups
- back up PVC-backed data
- delete user PVCs, ConfigMaps, and projects only with explicit approval
- verify the user can no longer access OpenShift AI

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/user-group-access-patterns.md`
