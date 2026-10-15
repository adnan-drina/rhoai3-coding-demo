---
name: ocp-gitops-operator
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: ocp
  docs-version: "4.22"
  skill-group: "OpenShift Platform"
description: >
  Use when reviewing or changing how this repo installs and configures Red Hat
  OpenShift GitOps: the Subscription and gitops-1.21 channel patch in
  gitops/bootstrap/overlays/operator, the openshift-gitops ArgoCD CR, AppProject
  rhoai-demo, controller cluster-admin binding and rhoai-gitops-admins group in
  gitops/bootstrap/overlays/demo, Dex OpenShift SSO and RBAC policy, custom
  health checks, or component Applications under gitops/applications.
  Do NOT use for manifest authoring rules (read .agents/rules/gitops.md), for
  moving Applications (use gitops-move-applications), or for reviewing a
  GitOps diff (use review-gitops-change).
---

# OpenShift GitOps operator

Thin skill: repo decisions and pitfalls here, product behavior in the linked
Red Hat OpenShift GitOps 1.21 sections. Authoring rules for Applications live
in `.agents/rules/gitops.md`; the bootstrap is run by
`stages/010-openshift-ai-platform-foundation/deploy.sh`.

## When to use

- A change touches `gitops/bootstrap/` (operator channel, ArgoCD CR, AppProject,
  controller RBAC, Argo CD admin group).
- Argo CD access, SSO group mapping, health assessment or controller sizing is
  in question.
- A component Application is added as `gitops/applications/<NNN>-<component>.yaml`.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Operator from `redhat-operators`, `installPlanApproval: Automatic`, channel `gitops-1.21` set by an overlay patch (the base holds a placeholder channel and is never applied alone); minimum `1.21.5` in the operator policy | `gitops/bootstrap/base/subscription.yaml`, `gitops/bootstrap/overlays/operator/patch-channel.yaml`, `check_operator_policy` in `scripts/lib.sh` | [Installing the GitOps Operator using CLI][install-cli] |
| Two-phase bootstrap: overlay `operator`, wait for the CSV, then overlay `demo` (needs the Argo CD CRDs) | `stages/010-openshift-ai-platform-foundation/deploy.sh`, `gitops/bootstrap/overlays/demo/kustomization.yaml` | [Installing OLM Operators using GitOps][olm] |
| Default `openshift-gitops` instance reused; `resourceTrackingMethod: annotation` | `gitops/bootstrap/overlays/demo/argocd-instance.yaml` | [Annotation-based resource tracking][tracking] |
| Controller sized 4Gi request / 8Gi limit after a Stage 070 OOMKill | `gitops/bootstrap/overlays/demo/argocd-instance.yaml` | [Argo CD CR properties][cr-props] |
| Custom Lua health for PVC (`Pending` is healthy under WaitForFirstConsumer), OLM Subscription and MLflow | `gitops/bootstrap/overlays/demo/argocd-instance.yaml` (`extraConfig`) | [Argo CD CR properties][cr-props] |
| Demo posture: application controller bound to `cluster-admin` (least privilege is backlog) | `gitops/bootstrap/overlays/demo/argocd-cluster-admin.yaml` | [Default permissions of an Argo CD instance][default-perms] |
| SSO through Dex with OpenShift OAuth, `scopes: '[groups]'`; `system:cluster-admins`, `cluster-admins` and `rhoai-gitops-admins` map to `role:admin`; read-only local account `rhdh` (apiKey) for Developer Hub | `gitops/bootstrap/overlays/demo/argocd-instance.yaml`, `gitops/bootstrap/overlays/demo/argocd-admin-group.yaml` | [Dex role mappings][dex-roles], [Argo CD RBAC][rbac] |
| One AppProject `rhoai-demo` for every Application | `gitops/bootstrap/overlays/demo/argocd-project.yaml` | [Setting up an Argo CD instance][instance] |
| One Application per component, destination namespace `openshift-gitops`, Server-Side Diff by annotation; the Stage 060 Applications have no automated sync | `gitops/applications/`, `.agents/rules/gitops.md` | [Synchronizing your application][sync] |
| Stage deploy scripts select, apply, sync and wait through `stage-apps.sh` (no `argocd` CLI) | `scripts/stage-apps.sh` | [Creating an application by using the oc tool][app-oc] |

## Procedure

1. Change the channel only together with the `channels` and `minimum` entries
   in `check_operator_policy` in `scripts/lib.sh` and the `openshift_gitops`
   pin in `.agents/references/red-hat-doc-map.yaml`.
2. Change the ArgoCD CR in Git, never the generated `argocd-cm` or
   `argocd-rbac-cm`; the operator reconciles them.
3. Validate statically, then live after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   scripts/validate-stage-flow.sh
   oc get subscription openshift-gitops-operator -n openshift-operators -o jsonpath='{.spec.channel} {.status.installedCSV}{"\n"}'
   oc get argocd openshift-gitops -n openshift-gitops -o jsonpath='{.spec.resourceTrackingMethod}{"\n"}'
   oc get applications.argoproj.io -n openshift-gitops
   ```

## Pitfalls

- Never `oc apply -k gitops/bootstrap/base`: its channel is a placeholder.
- An `oc apply` of a whole Application can drop annotations and delegated
  fields; edit live Applications by patch and move them with the
  `gitops-move-applications` procedure.
- After a group membership change, sign out of Argo CD and in again to refresh
  the Dex token (`docs/TROUBLESHOOTING.md#argo-cd-applications-missing-after-openshift-sso-login`).
- Synced at a new revision can still apply stale manifests; hard refresh
  (`docs/TROUBLESHOOTING.md#argo-cd-reports-synced-but-the-cluster-has-stale-manifests`).
- Merge-patching `.operation` inherits partial-sync filters and skips hooks
  (`docs/TROUBLESHOOTING.md#manually-triggered-sync-finishes-in-seconds-and-skips-hooks`).
- A new z-stream on `gitops-1.21` installs automatically; a new minor needs a
  reviewed channel change.

## Official documentation (OpenShift GitOps 1.21)

| Topic | Section |
|---|---|
| Install | [Installing Red Hat OpenShift GitOps][install], [Using the CLI][install-cli] |
| Instance | [Setting up an Argo CD instance][instance], [Argo CD CR properties][cr-props], [Annotation-based tracking][tracking] |
| Access | [Configuring Argo CD RBAC][rbac], [SSO using Dex][dex], [Dex role mappings][dex-roles], [Local users][local-users] |
| Cluster configuration | [Default permissions][default-perms], [Installing OLM Operators][olm], [Creating an application with oc][app-oc], [Synchronizing][sync] |
| OCP 4.22 entry point | [About Red Hat OpenShift GitOps][ocp-gitops] |

## Related skills

`review-gitops-change`, `gitops-move-applications`, `ocp-authentication-identity-providers`,
`ocp-security-rbac-scc`, `rhoai-self-managed-installation`.

[install]: https://docs.redhat.com/en/documentation/red_hat_openshift_gitops/1.21/html-single/installing_gitops/index#installing-openshift-gitops
[install-cli]: https://docs.redhat.com/en/documentation/red_hat_openshift_gitops/1.21/html-single/installing_gitops/index#installing-gitops-operator-using-cli_installing-openshift-gitops
[instance]: https://docs.redhat.com/en/documentation/red_hat_openshift_gitops/1.21/html-single/argo_cd_instance/index#setting-up-argocd-instance
[cr-props]: https://docs.redhat.com/en/documentation/red_hat_openshift_gitops/1.21/html-single/argo_cd_instance/index#argo-cd-properties_argo-cd-cr-component-properties
[tracking]: https://docs.redhat.com/en/documentation/red_hat_openshift_gitops/1.21/html-single/argo_cd_instance/index#con-enabling-annotation-based-resource-tracking-in-argo-cd_argo-cd-cr-component-properties
[rbac]: https://docs.redhat.com/en/documentation/red_hat_openshift_gitops/1.21/html-single/access_control_and_user_management/index#configuring-argo-cd-rbac
[dex]: https://docs.redhat.com/en/documentation/red_hat_openshift_gitops/1.21/html-single/access_control_and_user_management/index#configuring-sso-for-argo-cd-using-dex
[dex-roles]: https://docs.redhat.com/en/documentation/red_hat_openshift_gitops/1.21/html-single/access_control_and_user_management/index#gitops-dex-role-mappings_configuring-sso-for-argo-cd-using-dex
[local-users]: https://docs.redhat.com/en/documentation/red_hat_openshift_gitops/1.21/html-single/access_control_and_user_management/index#managing-local-users-in-argo-cd
[default-perms]: https://docs.redhat.com/en/documentation/red_hat_openshift_gitops/1.21/html-single/declarative_cluster_configuration/index#default-permissions-of-an-argocd-instance_configuring-an-openshift-cluster-by-deploying-an-application-with-cluster-configurations
[olm]: https://docs.redhat.com/en/documentation/red_hat_openshift_gitops/1.21/html-single/declarative_cluster_configuration/index#gitops-installing-olm-operators-using-gitops_configuring-an-openshift-cluster-by-deploying-an-application-with-cluster-configurations
[app-oc]: https://docs.redhat.com/en/documentation/red_hat_openshift_gitops/1.21/html-single/declarative_cluster_configuration/index#creating-an-application-by-using-the-oc-tool_configuring-an-openshift-cluster-by-deploying-an-application-with-cluster-configurations
[sync]: https://docs.redhat.com/en/documentation/red_hat_openshift_gitops/1.21/html-single/declarative_cluster_configuration/index#synchronizing-your-application-application-with-your-git-repository_configuring-an-openshift-cluster-by-deploying-an-application-with-cluster-configurations
[ocp-gitops]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/gitops/index#about-redhat-openshift-gitops
