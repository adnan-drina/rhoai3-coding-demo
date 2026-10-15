---
name: rhoai-access-group-selection
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when someone wants to pick OpenShift AI administrator or user groups in
  the dashboard (Settings > User management), asks why that screen shows
  rhods-admins and rhoai-developers, or considers system:authenticated for
  broad access in this demo. Do NOT use for the Auth CR contents, group
  creation, membership, revocation or user cleanup (use
  rhoai-users-groups-access), the identity provider (use
  ocp-authentication-identity-providers), or external OIDC (use
  rhoai-central-authentication-service).
---

# RHOAI access group selection

Thin skill: the dashboard group-selection screen only. The groups themselves,
their membership and the `Auth` CR belong to `rhoai-users-groups-access`.
Product behavior is in the linked OpenShift AI 3.5 sections.

## When to use

- A request says "select groups in Settings > User management".
- Someone proposes `system:authenticated` to open the dashboard to everyone.
- The screen shows groups that differ from what was expected.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Groups are not selected in the dashboard. Git sets them in the `Auth` resource `auth` (`services.platform.opendatahub.io/v1alpha1`); the screen reflects that state | `gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-platform/auth.yaml` | [Select admin and user groups][select-mr], [Dashboard configuration options][dash-options] |
| Admin group `rhods-admins`; user groups `rhods-admins` and `rhoai-developers`. `system:authenticated` is not listed, so the default access for all authenticated users is replaced | same file; `gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-platform/README.md` ("Auth") | [Select admin and user groups (Managing OpenShift AI)][select-mo] |
| `Auth` is owned by Argo CD Application `010-rhoai-platform` (automated sync with self-heal; `ignoreDifferences` covers only the DSC and the dashboard config) | `gitops/applications/010-rhoai-platform.yaml` | — (repo GitOps rule) |
| The dashboard `groupsConfig` field is not set; the 3.5 options table marks it read-only | `gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-platform/odhdashboardconfig.yaml` (field absent) | [Dashboard configuration options][dash-options] |

## Procedure

1. Change groups in `auth.yaml` through `rhoai-users-groups-access`, not in
   the dashboard. A dashboard edit that reaches the `Auth` resource is drift,
   and self-heal returns it to the Git value.
2. Deploy and validate with Stage 010:
   `./stages/010-openshift-ai-platform-foundation/deploy.sh`, then
   `./stages/010-openshift-ai-platform-foundation/validate.sh`.
3. Read-only check, after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get auth auth -o jsonpath='{.spec.adminGroups} {.spec.allowedGroups}{"\n"}'
   ```

   Then open Settings > User management as the admin persona and compare.

## Pitfalls

- A selected group must already exist in OpenShift ([Select admin and user
  groups][select-mo]); `rhoai-developers` comes from
  `gitops/stages/010-openshift-ai-platform-foundation/010-access/`.
- `system:authenticated` in the user groups opens the dashboard to every
  logged-in user; the demo's persona separation depends on not doing that.
- Users see a group change only after they log out of all sessions (see
  `rhoai-users-groups-access`).

## Official documentation (OpenShift AI 3.5)

| Topic | Section |
|---|---|
| Group selection screen | [Select admin and user groups (Managing resources)][select-mr] |
| Same procedure in the access chapter | [Select admin and user groups (Managing OpenShift AI)][select-mo] |
| `groupsConfig` read-only, `Auth` fields | [Dashboard configuration options][dash-options] |

## Related skills

`rhoai-users-groups-access`, `ocp-authentication-identity-providers`,
`rhoai-central-authentication-service`, `rhoai-dashboard-customization`.

[select-mr]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#selecting-admin-and-user-groups_resource-mgmt
[select-mo]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#selecting-admin-and-user-groups_managing-rhoai
[dash-options]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#ref-dashboard-configuration-options_dashboard
