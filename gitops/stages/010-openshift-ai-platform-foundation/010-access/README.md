# Demo sandbox access (`010-access`)

This Application creates the shared data science project `demo-sandbox` ("AI Coding Sandbox"), the
`rhoai-developers` group and the project RoleBindings for administrators and developers. Its S3 connections come
from `010-sandbox-storage`. Platform engineers and the
two demo personas (`ai-admin` in `rhods-admins`, `ai-developer` in `rhoai-developers`) use the project. Later stages
deploy workloads into it.

| | |
|---|---|
| Argo CD Application | `010-access` ([manifest](../../../applications/010-access.yaml)) |
| Deployed by | [`stages/010-openshift-ai-platform-foundation/deploy.sh`](../../../../stages/010-openshift-ai-platform-foundation/deploy.sh) (deploy-order 3). Group membership comes from [`stages/010-openshift-ai-platform-foundation/deploy.sh`](../../../../stages/010-openshift-ai-platform-foundation/deploy.sh), a separate manual step |
| Validated by | [`validate.sh`](../../../../stages/010-openshift-ai-platform-foundation/validate.sh) (project label, `rhods-admins-admin` binding, persona group membership, optional persona `can-i` checks) |
| Sync | Automated, prune and self-heal; `CreateNamespace`, `SkipDryRunOnMissingResource`, `RespectIgnoreDifferences`; Server-Side Diff via annotation; `ignoreDifferences` on the Group's `/users` and one Namespace label |
| Depends on | `010-rhoai-platform` (the `Auth` CR names `rhoai-developers` and creates `rhods-admins`) |
| Used by | `010-sandbox-storage` (namespace), Stage 020 Kueue (`kueue.openshift.io/managed` label), Stages 030-130 workloads and personas in `demo-sandbox` |

## Why

OpenShift AI projects are namespaces that the dashboard lists. Access is granted per project with roles: Admin can edit
the project and manage access, and Contributor can edit workbenches, connections and storage [1]. Contributor matches
the OpenShift `edit` cluster role, which can change most objects but not roles or bindings. Admin matches `admin` [2].
The `Auth` CR in `010-rhoai-platform` lists `rhoai-developers` as a user group, and the documentation requires such
groups to exist [3]. Declaring the group, project and bindings in Git makes the persona permissions reviewable.
Credentials and membership stay out of Git.

## What

| Kind | Name | Namespace | Wave | Purpose |
|---|---|---|---|---|
| Namespace | `demo-sandbox` | (cluster) | 0 | Label `opendatahub.io/dashboard: "true"` (shown as a project), `kueue.openshift.io/managed: "true"` (Stage 020 queue enforcement); display name "AI Coding Sandbox" |
| Group | `rhoai-developers` | (cluster) | 0 | Developer group; `users` comes from `stages/010-openshift-ai-platform-foundation/deploy.sh` (ignored by Argo CD) |
| RoleBinding | `rhoai-developers-edit` | `demo-sandbox` | 0 | `rhoai-developers` gets ClusterRole `edit` (project Contributor) |
| RoleBinding | `rhods-admins-admin` | `demo-sandbox` | 0 | `rhods-admins` gets ClusterRole `admin` (project Admin) |

There are no hooks.

Not in Git:

| Object | Owner |
|---|---|
| Group `rhods-admins` | RHOAI operator (from the `Auth` CR); membership from `stages/010-openshift-ai-platform-foundation/deploy.sh` |
| Group `rhoai-developers` `users` | `stages/010-openshift-ai-platform-foundation/deploy.sh` (`oc adm groups add-users`) |
| Identity provider and users | The cluster's existing OAuth provider; `stages/010-openshift-ai-platform-foundation/deploy.sh` changes neither |

## How

- **Ordering.** All four objects are in wave 0; the RoleBindings name groups, which need not exist first.
- **`ignoreDifferences`.** The `rhoai-developers` Group has `/users` ignored because membership is runtime data from
  the identity provider. The `demo-sandbox` Namespace has the label `evalhub.trustyai.opendatahub.io/tenant` ignored.
  The comment says Stage 050 sets it, but Stage 050 now removes that label (see findings).
  `RespectIgnoreDifferences=true` keeps a sync from clearing either field [4].
- **Project RBAC.** Developers get `edit`, not `admin`, so they cannot change bindings in the project. Administrators
  get `admin` on this project only. The dashboard admin role does not give access to individual project namespaces,
  as the RoleBinding comment explains.
- **Storage.** The project's S3 connections (Models, Workbench) are declared by `010-sandbox-storage`. The earlier
  `demo-sandbox-bucket` claim and the `demo-sandbox-s3` connection built by `stages/010-openshift-ai-platform-foundation/deploy.sh` were retired on 2026-10-14.
- **Cluster-specific values.** Persona user names come from the local `.env` (`RHOAI_ADMIN_USER`,
  `RHOAI_DEVELOPER_USER`), never from Git.

## Validation

`validate.sh` checks the following:

- the dashboard label on `demo-sandbox`;
- `rhods-admins-admin` binds `admin`;
- each configured persona is a member of its group.

With `RHOAI_ADMIN_KUBECONFIG` and `RHOAI_DEVELOPER_KUBECONFIG`, it also checks real persona sessions with
`oc auth can-i update deployments.apps -n demo-sandbox`.

```bash
oc get ns demo-sandbox --show-labels; oc get rolebinding -n demo-sandbox rhoai-developers-edit rhods-admins-admin
oc get group rhods-admins rhoai-developers
```

## Alignment with official guidance

| Topic | Official guidance (link) | This repository | Status |
|---|---|---|---|
| Project roles | Admin manages project and access; Contributor edits workbenches, connections and storage [1] | `admin` for `rhods-admins`, `edit` for `rhoai-developers` | Aligned |
| OpenShift default roles | `admin`: modify any resource except quota; `edit`: most objects, not roles or bindings [2] | Used as documented | Aligned |
| User groups | Groups must exist before they are selected; group membership managed in the OpenShift console [3] | Group in Git; membership by `oc adm groups add-users` from `stages/010-openshift-ai-platform-foundation/deploy.sh` | Aligned (CLI equivalent) |
| Connection lifecycle | Connections are Kubernetes Secrets with standard annotations [5] | Declared by `010-sandbox-storage`; none here | Aligned |

## References

1. Working on projects, Manage access to projects (Default project roles). Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_on_projects/managing-access-to-projects_projects
2. Authentication and authorization, Using RBAC to define and apply permissions (Default cluster roles). OpenShift Container Platform 4.22. https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/authentication_and_authorization/using-rbac
3. Manage users and groups (Add users to OpenShift AI user groups; Select admin and user groups). Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/managing_openshift_ai/managing-users-and-groups
4. Sync Options, Respect Ignore Difference Configs (upstream). Argo CD. https://argo-cd.readthedocs.io/en/stable/user-guide/sync-options/
5. Working on projects, Use connections (Using the connections API). Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_on_projects/using-connections_projects
