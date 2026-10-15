---
name: rhoai-users-groups-access
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when reviewing or changing who can use OpenShift AI in this demo: the
  Auth CR (adminGroups rhods-admins, allowedGroups rhods-admins and
  rhoai-developers) in rhoai-platform/auth.yaml, the rhoai-developers Group
  and demo-sandbox RoleBindings in
  gitops/stages/010-openshift-ai-platform-foundation/access/, persona
  membership set by setup-access.sh, revoking a user, or cleaning up a
  removed user's workbench, PVC and ConfigMap. Do NOT use for the dashboard
  group-selection screen only (use rhoai-access-group-selection), the
  identity provider (use ocp-authentication-identity-providers), or project
  roles in general (use rhoai-project-workflows).
---

# RHOAI users, groups and access

Thin skill: repo decisions and pitfalls here, product procedure in the linked
OpenShift AI 3.5 sections. Detailed records:
`gitops/stages/010-openshift-ai-platform-foundation/access/README.md` and the
"Auth" part of `gitops/stages/010-openshift-ai-platform-foundation/rhoai-platform/README.md`.

## When to use

- A change touches `rhoai-platform/auth.yaml` or anything under `access/`.
- A persona cannot reach the dashboard or `demo-sandbox`.
- A user must lose access, or their resources must be removed.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Explicit groups replace the default access for every OpenShift user: `Auth` `adminGroups: [rhods-admins]`, `allowedGroups: [rhods-admins, rhoai-developers]` (API group `services.platform.opendatahub.io`; dashboard `groupsConfig` is read-only) | `rhoai-platform/auth.yaml` | [Select admin and user groups][select], [Dashboard configuration options][dash-options] |
| Groups must exist first: `rhods-admins` comes from the operator, `rhoai-developers` from Git; `users` ignored by Argo CD | `access/group-rhoai-developers.yaml`, `gitops/applications/010-access.yaml` | [Select admin and user groups][select] |
| Membership is runtime data: `setup-access.sh` adds `RHOAI_ADMIN_USER` and `RHOAI_DEVELOPER_USER` from the local `.env` (CLI equivalent of the console procedure) | `stages/010-openshift-ai-platform-foundation/setup-access.sh` | [Add users to user groups][add-users] |
| Project roles in `demo-sandbox`: `rhods-admins` get `admin`, `rhoai-developers` get `edit` | `access/rolebinding-admins-admin.yaml`, `access/rolebinding-developer-edit.yaml` | [User types][user-types] |
| Admins only may read RHOAI traces (`rhoai-monitoring-traces-reader` bound to `rhods-admins`) | `observability-operators/trace-roles/` | see `rhoai-observability` |
| Identity comes from the cluster's login provider (Keycloak realm `sso`, provider `rhbk`); not in GitOps | `stages/010-openshift-ai-platform-foundation/README.md` | see `ocp-authentication-identity-providers` |

Paths in the table are relative to `gitops/stages/010-openshift-ai-platform-foundation/` unless they start with `gitops/` or `stages/`.

## Procedure

1. Group lists change in `auth.yaml` only; new groups get a manifest under
   `access/` (or come from the identity provider) before they are listed.
2. Deploy, set membership, validate:
   `./stages/010-openshift-ai-platform-foundation/deploy.sh`,
   `./stages/010-openshift-ai-platform-foundation/setup-access.sh`,
   `./stages/010-openshift-ai-platform-foundation/validate.sh`
   (persona membership; real `can-i` checks when `RHOAI_ADMIN_KUBECONFIG` and
   `RHOAI_DEVELOPER_KUBECONFIG` are set).
3. By hand, after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get auth auth -o jsonpath='{.spec.adminGroups} {.spec.allowedGroups}{"\n"}'
   oc get group rhods-admins rhoai-developers
   oc get rolebinding -n demo-sandbox rhoai-developers-edit rhods-admins-admin
   ```

4. Removing a user follows the official order ([Remove user access][remove]):
   stop their basic workbench, revoke access, back up storage, then clean up.
   PVC, ConfigMap and project deletion is destructive: ask first.

## Pitfalls

- Permission changes apply only after the user logs out of all sessions; a
  running Jupyter session survives an OpenShift logout ([User types][user-types]).
- Removing a pointer from the `access` Application `ignoreDifferences` lets
  Argo CD wipe the `rhoai-developers` membership.
- The dashboard admin role does not grant access to project namespaces; that
  is why `demo-sandbox` has its own `admin` binding.
- An LDAP identity provider needs group sync before its groups can be used
  ([Add users to user groups][add-users]).

## Official documentation (RHOAI 3.5)

| Topic | Section |
|---|---|
| User types, custom roles | [Set up user access and identity][overview], [Platform user types][user-types], [Custom roles][custom-roles] |
| View and add users | [View users][view-users], [Add users to user groups][add-users] |
| Select groups | [Select admin and user groups][select] |
| Remove access and clean up | [Remove user access][remove], [Stop workbenches of other users][stop-wb], [Revoke workbench access][revoke], [Back up storage][backup], [Clean up after deleting users][cleanup] |
| `Auth` resource and `groupsConfig` | [Dashboard configuration options][dash-options] (Managing resources) |

## Related skills

`rhoai-access-group-selection`, `rhoai-project-workflows`, `rhoai-basic-workbenches`,
`rhoai-central-authentication-service`, `rhoai-dashboard-customization`,
`ocp-authentication-identity-providers`, `ocp-security-rbac-scc`.

[overview]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#overview-of-user-types-and-permissions_managing-rhoai
[user-types]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#platform_user_types
[custom-roles]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#custom_roles_for_project_resources
[view-users]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#viewing-data-science-users_managing-rhoai
[add-users]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#adding-users-to-user-groups_managing-rhoai
[select]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#selecting-admin-and-user-groups_managing-rhoai
[remove]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#about-deleting-users-and-resources_managing-rhoai
[stop-wb]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#stopping-basic-workbenches-owned-by-other-users_managing-rhoai
[revoke]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#revoking-user-access-to-basic-workbenches_managing-rhoai
[backup]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#backing-up-storage-data_managing-rhoai
[cleanup]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#cleaning-up-after-deleting-users_managing-rhoai
[dash-options]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#ref-dashboard-configuration-options_dashboard
