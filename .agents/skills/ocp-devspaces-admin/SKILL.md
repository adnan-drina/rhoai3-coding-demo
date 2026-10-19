---
name: ocp-devspaces-admin
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: ocp_devspaces
  docs-version: "3.30"
  skill-group: "OpenShift Platform"
description: >
  Use when changing or reviewing the Dev Spaces 3.30 administration choices in
  this demo: CheCluster devspaces fields (per-workspace 20Gi gp3-csi storage,
  persistUserHome, idling disabled, 1200 s start timeout, running-workspace
  and container caps, allowedSources, Open VSX URL, metrics), pre-provisioned
  wksp-* projects, per-namespace editor configurations, the GitLab OAuth
  integration written by 070-gitlab, workspace RBAC and network policies. Do
  NOT use for the operator install or upgrades (use ocp-devspaces-install),
  devfiles, mounted Secrets and extensions inside a workspace (use
  ocp-devspaces-user-guide), or workspace lifecycle operations (use
  manage-devspaces).
---

# Dev Spaces administration

Thin skill: repo decisions and pitfalls here, field reference in the linked
Dev Spaces 3.30 topics. Detailed record:
`gitops/stages/070-advanced-app-platform/070-devspaces/README.md` (How, Alignment).

## When to use

- A change touches `070-devspaces/checluster.yaml`, `vscode-editor-configurations.yaml`,
  the `wksp-*` namespaces in `070-namespaces`, or the workspace network policies.
- Workspaces do not get storage, are idled, cannot start from a URL, or lose
  GitLab OAuth.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| `pvcStrategy: per-workspace`, `claimSize: 20Gi`, `storageClass: gp3-csi`, `persistUserHome.enabled: true` (default is `per-user`) | `gitops/stages/070-advanced-app-platform/070-devspaces/checluster.yaml` | [Storage strategy][storage], [Persistent home][home], [CheCluster fields][fields] |
| `secondsOfInactivityBeforeIdling: -1`, `startTimeoutSeconds: 1200` for unattended agent runs and a large image | same | [CheCluster fields][fields] |
| `maxNumberOfRunningWorkspacesPerUser: 3`; `containerResourceCaps` 6 CPU / 12Gi | same | [Multiple running workspaces][multi], [CheCluster fields][fields] |
| `allowedSources.urls` is an `.invalid` placeholder in Git; `070-gitlab` writes the GitLab group URLs and `gitServices`; Argo CD ignores both | same; `gitops/stages/070-advanced-app-platform/070-gitlab/README.md` | [Restrict allowed URLs][allowed] |
| GitLab OAuth Secret `gitlab-oauth-config` with the documented labels and annotations, created by the `070-gitlab` hub | `gitops/stages/070-advanced-app-platform/070-gitlab/` | [GitLab OAuth app][gitlabapp], [Apply the GitLab Secret][gitlabsecret] |
| `pluginRegistry.openVSXURL: https://open-vsx.org`; `metrics.enable: true` | `070-devspaces/checluster.yaml` | [Alternative extension registry][openvsx], [Server metrics][metrics] |
| Persona projects `wksp-ai-developer`, `wksp-ai-admin`, `wksp-kubeadmin` pre-provisioned (labels `part-of: che.eclipse.org`, `component: workspaces-namespace`, annotation `che.eclipse.org/username`); `autoProvision: true` for others | `gitops/stages/070-advanced-app-platform/070-namespaces/namespaces.yaml` | [Provision projects in advance][preprov] |
| Editor settings per persona project: ConfigMap `vscode-editor-configurations` (label `workspaces-config`) | `070-devspaces/vscode-editor-configurations.yaml` | [Apply IDE settings][editorcfg] |
| Persona RoleBindings `wksp-edit-<user>` (ClusterRole `edit`) | `070-devspaces/workspaces.yaml` | [Grant permissions][roles] |
| Workspace egress: NetworkPolicy `migration-workspace-maas-egress`, AdminNetworkPolicy `workspace-allow-kapi-egress` (API server, TCP 6443) | `070-devspaces/migration-workspace-maas-egress-networkpolicy.yaml`, `070-devspaces/workspace-api-egress-adminnetworkpolicy.yaml` | [Network policies][netpol] |

## Procedure

1. Edit the CheCluster in Git; never patch fields that `070-gitlab` owns.
2. Validate after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   ./stages/070-advanced-app-platform/validate.sh          # "Existing identity and Dev Spaces"
   ./stages/070-advanced-app-platform/validate.sh --static
   ```

   The former admission dry-run checker `check-workspace-creation.py` is in
   git history at `82092e01`.

3. Read-only checks:

   ```bash
   oc get checluster devspaces -n openshift-devspaces -o jsonpath='{.spec.devEnvironments.storage}{"\n"}{.spec.devEnvironments.allowedSources}{"\n"}'
   oc get ns -l app.kubernetes.io/component=workspaces-namespace
   ```

## Pitfalls

- A per-user RWO claim cannot attach to two running workspaces; that is why
  the repo uses `per-workspace`:
  `docs/TROUBLESHOOTING.md#factory-workspace-failedmount-while-coolstore-inventory-service-is-running`.
- `gitServices.gitlab[].endpoint` is deprecated in favour of the Secret
  annotation ([CheCluster fields][fields]); keep both until removed.
- A running workspace keeps an expired GitLab token until restarted:
  `docs/TROUBLESHOOTING.md#stage-070-running-workspace-retains-an-expired-gitlab-credential`.
- Injected DevWorkspace attributes cause drift; Argo CD ignores them
  (`docs/TROUBLESHOOTING.md#stage-070-stays-outofsync-after-a-successful-workspace-sync`).
- Namespace-wide Secret writers remain in `wksp-ai-developer` (README
  Alignment table, "Least privilege").

## Official documentation (Dev Spaces 3.30)

| Topic | Section |
|---|---|
| Central configuration | [How it works][cfg], [CheCluster fields][fields], [DWO custom resources][dwocr] |
| Projects | [How namespaces are organized][projects], [Provision in advance][preprov] |
| Workspace policies | [Limit per user][limituser], [Multiple running][multi], [Allowed URLs][allowed], [Container run][containers] |
| Storage | [Requirements][storagereq], [Storage strategy][storage], [Sizes][sizes], [Persistent home][home] |
| Networking and TLS | [Network policies][netpol], [Untrusted TLS][tls] |
| Identity and RBAC | [Grant permissions][roles], [Restrict users][authz] |
| Git OAuth | [GitLab OAuth app][gitlabapp], [Apply the GitLab Secret][gitlabsecret] |
| Editors and extensions | [Apply IDE settings][editorcfg], [Alternative registry][openvsx] |
| Observe | [Server metrics][metrics], [Collect logs][logs] |

## Related skills

`ocp-devspaces-install`, `ocp-devspaces-user-guide`, `manage-devspaces`,
`ocp-security-rbac-scc`, `rhdh-git-integration`.

[cfg]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/configure-con_understanding_the_checluster_custom_resource
[fields]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/configure-ref_checluster_custom_resource_fields
[dwocr]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/configure-ref_devworkspace_operator_custom_resources
[projects]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/configure-con_configuring_projects
[preprov]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/configure-proc_provisioning_projects_in_advance
[limituser]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/configure-proc_limiting_workspaces_per_user
[multi]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/configure-proc_enabling_multiple_workspaces_simultaneously
[allowed]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/configure-proc_configuring_allowed_urls_for_cde
[containers]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/configure-proc_enabling_container_run_capabilities
[storagereq]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/configure-con_storage_requirements
[storage]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/configure-proc_configuring_storage_strategy
[sizes]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/configure-proc_configuring_storage_sizes
[home]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/configure-con_persistent_user_home
[netpol]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/configure-proc_configuring_network_policies
[tls]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/configure-proc_importing_untrusted_tls_certificates
[roles]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/secure-proc_configuring_cluster_roles_for_users
[authz]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/secure-proc_configuring_advanced_authorization
[gitlabapp]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/integrate-proc_setting_up_the_gitlab_authorized_application
[gitlabsecret]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/integrate-proc_applying_the_gitlab_authorized_application_secret
[editorcfg]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/extend-proc_applying_editor_configurations
[openvsx]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/extend-proc_configuring_open_vsx_registry_url
[metrics]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/observe-proc_enabling_devspaces_metrics
[logs]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/observe-ref_collecting_logs_using_dsc
