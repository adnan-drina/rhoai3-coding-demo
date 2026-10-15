---
name: ocp-security-rbac-scc
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: ocp
  docs-version: "4.22"
  skill-group: "OpenShift Platform"
description: >
  Use when reviewing or changing RBAC, ServiceAccount permissions, SCC grants
  or pod security admission labels in this repo: demo-sandbox RoleBindings in
  Stage 010 access, the Argo CD controller cluster-admin binding, named `use`
  grants on the nonroot-v2, nested-container and container-build SCCs in Stage
  070, the anyuid binding for SWE-bench in Stage 050, per-ImageStream pull
  Roles, or pod-security.kubernetes.io namespace labels. Do NOT use for login
  and identity providers (use ocp-authentication-identity-providers), OpenShift
  AI dashboard groups (use rhoai-users-groups-access), Argo CD RBAC policy (use
  ocp-gitops-operator), or Tekton pipeline security (use ocp-pipelines-security).
---

# RBAC, service accounts and SCCs

Thin skill: repo decisions and pitfalls here, product behavior in the linked
OpenShift Container Platform 4.22 sections. RBAC, SCC and NetworkPolicy changes
are security-sensitive: include validation notes in the PR (`AGENTS.md`).

## When to use

- A change adds or edits a Role, ClusterRole, binding, ServiceAccount, SCC
  grant or pod security label.
- A pod is rejected by SCC or pod security admission, or a persona gets
  `forbidden`.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Project access by group: `rhoai-developers` get ClusterRole `edit`, `rhods-admins` get `admin`, on `demo-sandbox` only | `gitops/stages/010-openshift-ai-platform-foundation/access/rolebinding-developer-edit.yaml`, `gitops/stages/010-openshift-ai-platform-foundation/access/rolebinding-admins-admin.yaml` | [Using RBAC][rbac] |
| Demo posture: Argo CD application controller is `cluster-admin`; least privilege is backlog | `gitops/bootstrap/overlays/demo/argocd-cluster-admin.yaml` | [Using RBAC][rbac] |
| No custom SCC objects; SCCs are granted with `use` on one named built-in SCC through a Role or ClusterRole | see the next rows | [Role-based access to SCCs][scc-rbac] |
| GitLab ServiceAccount gets `nonroot-v2` in `gitlab-system` only | `gitops/stages/070-advanced-app-platform/gitlab/role-gitlab-use-nonroot.yaml` | [Default SCCs][default-sccs] |
| Only the pipeline build Task may use `nested-container` (rootless buildah in a user namespace) | `gitops/stages/070-advanced-app-platform/pipelines/operators/image-builder-scc.yaml` | [Managing SCCs][scc] |
| The migration-run provisioner may grant `container-build` (injected by Dev Spaces) to per-run worker Roles | `gitops/stages/070-advanced-app-platform/devspaces/migration-run-resources-rbac.yaml` | [Role-based access to SCCs][scc-rbac] |
| Deviation with operator approval: `anyuid` for the two SWE-bench ServiceAccounts in `evaluated-models` | `gitops/stages/050-model-evaluation/evaluation-content/swebench/rbac.yaml` | [Default SCCs][default-sccs] |
| Image pulls granted per stream (`imagestreams/layers`, one `resourceName`) | `gitops/stages/060-agent-runtime-and-agentops/openshell-runtime/images/image-pull-role.yaml` | [Using RBAC][rbac] |
| Pod security admission: `audit`/`warn` `restricted` on Stage 040 namespaces, `baseline` on `evaluated-models`; no `enforce` label is set in Git | `gitops/stages/040-governed-models-as-a-service/local-models/namespace.yaml`, `gitops/stages/050-model-evaluation/model-qualification/namespace.yaml` | [Pod security admission][psa] |
| Hook and automation identities are dedicated ServiceAccounts with namespace Roles | for example `gitops/stages/050-model-evaluation/oci-export/oci-export.yaml` | [Service accounts][sa] |

## Procedure

1. Prefer a namespaced Role and RoleBinding; grant an SCC by name with the
   `use` verb, never by adding a subject to an SCC or binding `privileged`.
2. Record any `anyuid`, `privileged` or `cluster-admin` grant as a deviation
   in the component README and `docs/OPERATIONS.md`.
3. Validate after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc auth can-i --list -n demo-sandbox --as=<persona> --as-group=rhoai-developers
   oc get pod <pod> -n <ns> -o jsonpath='{.metadata.annotations.openshift\.io/scc}{"\n"}'
   oc adm policy who-can use scc nested-container
   ```

   Impersonation is a review aid only; persona acceptance needs real logins
   (`ocp-authentication-identity-providers`).

## Pitfalls

- Passing SCC admission does not prove a user namespace works: buildah can
  still fail `unshare(CLONE_NEWUSER)`
  (`docs/TROUBLESHOOTING.md#buildah-inside-native-openshift-user-namespaces`).
  Do not add `SYS_ADMIN` or privileged access.
- `oc auth can-i` misparses some virtual resources; confirm with a
  SubjectAccessReview when a check looks wrong.
- The RHOAI dashboard admin role alone does not grant access to a project
  namespace; a project RoleBinding is required.
- `edit` cannot change roles or bindings; developers needing that is a design
  change, not a fix.

## Official documentation (OCP 4.22)

| Topic | Section |
|---|---|
| RBAC | [Using RBAC to define and apply permissions][rbac] |
| Service accounts | [Understanding and creating service accounts][sa], [Using service accounts][sa-use], [Bound service account tokens][bound] |
| SCC | [Managing security context constraints][scc], [Default SCCs][default-sccs], [Role-based access to SCCs][scc-rbac] |
| Pod security | [Understanding and managing pod security admission][psa] |

## Related skills

`ocp-authentication-identity-providers`, `rhoai-users-groups-access`,
`ocp-gitops-operator`, `ocp-pipelines-security`, `ocp-devspaces-admin`.

[rbac]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/authentication_and_authorization/index#using-rbac
[sa]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/authentication_and_authorization/index#understanding-and-creating-service-accounts
[sa-use]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/authentication_and_authorization/index#using-service-accounts
[bound]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/authentication_and_authorization/index#bound-service-account-tokens
[scc]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/authentication_and_authorization/index#managing-pod-security-policies
[default-sccs]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/authentication_and_authorization/index#default-sccs_configuring-internal-oauth
[scc-rbac]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/authentication_and_authorization/index#role-based-access-to-ssc_configuring-internal-oauth
[psa]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/authentication_and_authorization/index#understanding-and-managing-pod-security-admission
