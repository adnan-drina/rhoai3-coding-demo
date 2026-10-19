# OpenShift Dev Spaces (`070-devspaces`)

This Application installs Red Hat OpenShift Dev Spaces 3.30 and the workspace side of the developer platform: the operator, the `CheCluster`, the persona workspace namespaces, the standing `coolstore-inventory-service` workspace, and governed MaaS model access for workspaces. Developers in Stages 110–130 open their IDE here. Developer Hub templates create new workspaces against this instance, and Stage 130 migration runs use its per-run identity and model-profile contract.

| | |
|---|---|
| Argo CD Application | `070-devspaces` ([manifest](../../../applications/070-devspaces.yaml)) |
| Deployed by | `stages/070-advanced-app-platform/deploy.sh` → `stage-apps.sh deploy 070` (deploy-order 3) |
| Validated by | `stages/070-advanced-app-platform/validate.sh` (operator, "Existing identity and Dev Spaces" and credential checks); `validate.sh --static` (authoring tests) |
| Sync | Automated, `prune: true`, `selfHeal: true`; `CreateNamespace`, `SkipDryRunOnMissingResource`, `RespectIgnoreDifferences`, `ClientSideApplyMigration=false`; compare-option `ServerSideDiff=true`; retry 10 times with backoff |
| Depends on | `070-namespaces` (deploy-order 1), `070-identity` (deploy-order 2); Stage 040 (`maas-default-gateway` and the `devspaces-coding-models` subscription); `gp3-csi` storage class |
| Used by | `070-gitlab` (GitLab OAuth Secret, CheCluster Git service and allowed sources, workspace remotes), `070-pipelines` (migration-run provisioner, Sonar token mirror), `070-rhdh` (workspace links in templates), Stages 110, 120 and 130 |

## Why

Dev Spaces gives each developer a managed, browser-based workspace on OpenShift, so source code and AI assistance stay inside the cluster [1][2]. The 3.30 guide supports installing it through Argo CD: Subscription, `CheCluster` v2 and Kustomization in Git, reconciled by GitOps [1]. The repository follows that model.

The operator, the instance and the workspace contract form one Application because they change together: a CheCluster change, a namespace RBAC change or a new MaaS credential shape all affect the same workspaces. GitLab-specific values (OAuth application, Git endpoint, allowed source URLs) are produced later by `070-gitlab`, because GitLab must exist before they can be minted.

## What

### Operator and instance

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| Subscription | `devspaces` | `openshift-operators` | Channel `stable`, `installPlanApproval: Automatic`, no `startingCSV` (wave 2), as in the GitOps guide [1]. OLM adds the DevWorkspace operator dependency in the same namespace |
| ServiceAccount, Role, RoleBinding | `job-wait-devspaces-webhook` | `openshift-devspaces` | Read deployments, services and endpoints (wave 8) |
| Job (Sync hook) | `job-wait-devspaces-webhook` | `openshift-devspaces` | Waits for the operator rollout and webhook endpoints before the CheCluster (wave 9; `BeforeHookCreation,HookSucceeded`) |
| CheCluster | `devspaces` | `openshift-devspaces` | The Dev Spaces instance (wave 10; see How) |

### Persona namespaces and workspaces

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| RoleBinding | `wksp-edit-<user>` | each persona namespace | ClusterRole `edit` for the persona user (wave 3) |
| ConfigMap | `vscode-editor-configurations` | each persona namespace | Code - OSS settings, recommendations and the Kilo Code model default (wave 17) |
| DevWorkspace | `coolstore-inventory-service` | `wksp-ai-developer`, `wksp-ai-admin` | Standing catalog workspace, `started: false`, UDI image pinned by digest, Kilo Code VSIX via `DEFAULT_EXTENSIONS`, remote patched by `070-gitlab` (wave 10) |
| ServiceAccount, ClusterRole, ClusterRoleBinding | `job-repair-devworkspace-sync-options` | `openshift-devspaces` / cluster | `get`/`patch` on DevWorkspaces (wave 17) |
| Job (Sync hook) | `job-repair-devworkspace-sync-options` | `openshift-devspaces` | Resets the Argo sync-option annotation on the two standing workspaces (wave 19) |

### Model access for workspaces

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| ServiceAccount | `devspace-maas-key-provisioner` / `devspace-maas-key-provisioner-admin` | `wksp-ai-developer` / `wksp-ai-admin` | MaaS key owner per persona, so MaaS attributes usage to each persona (wave 17; `maas-keys/developer`, `maas-keys/admin`) |
| Role, RoleBinding | `devspace-maas-key-secret-manager[-admin]` | each persona namespace | Secret create; get/patch/update on its two key Secrets |
| Role, RoleBinding | `devspace-maas-gateway-reader` | `openshift-ingress` | `get` Gateways, to read the MaaS hostname (both provisioners) |
| Role, RoleBinding | `devspace-maas-key-reader[-admin]` / `devspace-maas-key-workspace-readers[-admin]` | each persona namespace | That namespace's workspace service accounts read its two key Secrets by name |
| Role, RoleBinding | `devspace-ai-tools-init-reader` / `devspace-ai-tools-init-admin-readers` | `wksp-ai-developer` | `ai-admin`'s workspace service accounts read the shared init ConfigMap |
| ConfigMap | `workspace-maas-model-endpoint[-admin]` | each persona namespace | OpenAI path on the MaaS gateway (`/v1`), mounted into the key Job |
| ConfigMap | `devspace-ai-tools-init` | `wksp-ai-developer` | `init-ai-tools.sh`: the workspace postStart bootstrap for Kilo Code, OpenCode and the Stage 130 Hermes worker configuration |
| ConfigMap (generated) | `migration-model-profiles` | `wksp-ai-developer` | `model-profiles.json`, the one model runtime profile table; mounted read-only at `/etc/rhoai3/model-profiles` with `mount-on-start` |
| ConfigMap (generated) | `stage070-secret-writer-<hash>` | `wksp-ai-developer` | `secret_writer.py`, the typed Secret writer |
| Job (not a hook) | `provision-devspace-maas-api-keys[-admin]` | each persona namespace | Mints or keeps MaaS keys and writes `maas-devspace-api-keys` and `workspace-maas-credentials` (wave 18; `Force=true,Replace=true` recreate it on each sync [12]) |
| NetworkPolicy | `migration-workspace-maas-egress` | `wksp-ai-developer` | Egress for workspace pods: DNS, Dev Spaces, MaaS/ingress, RHOAI, MTA, same namespace, and TCP 80/443 (wave 20) |
| AdminNetworkPolicy | `workspace-allow-kapi-egress` | cluster | Allows workspace namespaces to reach the API server on control-plane nodes, TCP 6443 (wave 19, priority 50) |

### Migration-run contract (Stage 130)

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| ServiceAccount | `migration-run-provisioner` | `app-platform-build` | Identity of the platform Tekton Task that creates and retires per-run resources (wave 17) |
| Role, RoleBinding | `migration-run-resource-manager` | `wksp-ai-developer` | Secrets, ConfigMaps, Services, ServiceAccounts, Deployments, Roles, RoleBindings: full lifecycle; subject in `app-platform-build` so no workspace pod can use it |
| ClusterRole, ClusterRoleBinding | `migration-run-provisioner-container-build` | cluster | `use` on SCC `container-build` only, so the provisioner can grant it to per-run worker Roles |
| Role, RoleBinding | `workspace-sonar-credentials-writer` | `wksp-ai-developer`, `wksp-ai-admin` | Secret get/create/update/patch for `app-platform-build/project-provisioner`, which mirrors project-scoped Sonar tokens (wave 13) |
| ValidatingAdmissionPolicy, Binding | `migration-workspace-run-name` | cluster | On CREATE, a DevWorkspace that sets `MIGRATION_RUN_NAME` must be named exactly that (waves 10–11, `Deny`) |
| Secret | `migration-fixture-credentials` | `wksp-ai-developer` | Public specimen demo identities, never mounted; copied per run by the provisioner (wave 17) |

The namespaces `openshift-devspaces`, `wksp-ai-developer`, `wksp-ai-admin` and `wksp-kubeadmin` come from `070-namespaces`.

Not in Git: the GitLab OAuth Secret `gitlab-oauth-config`, the CheCluster `gitServices` and real `allowedSources` URLs, and the workspace Git remotes (all written by `070-gitlab`); the MaaS key Secrets (written by the key Job); per-workspace PVCs and workspace service accounts (created by the DevWorkspace Operator). Two test scripts in this folder, `outcome-board-hooks.test.py` and `run-budgets-hooks.test.py`, are not rendered; Stage 130's `validate.sh` runs them.

## How

**Installation.** The Subscription lives in `openshift-operators` (AllNamespaces) with `Automatic` approval on `stable`, as the 3.30 GitOps guide shows [1]. `check_operator_policy` in `scripts/lib.sh` (run by Stage 070 `deploy.sh`) refuses another channel or an offered version outside the qualified 3.30 line (minimum 3.30.2). The webhook-wait hook then holds the CheCluster until the operator, which runs in `openshift-operators`, answers admission calls; its Role there reads only the `devspaces-operator` Deployment and Service. Until 2026-10-15 the Subscription lived in `openshift-devspaces` with Manual approval and its own approver hook; `docs/OPERATIONS.md` records the move.

**CheCluster choices** (field reference [3]):

- `storage.pvcStrategy: per-workspace`, 20 Gi on `gp3-csi`, with `persistUserHome.enabled: true`. One volume per workspace lets factory workspaces run beside `coolstore-inventory-service` without sharing an RWO claim.
- `secondsOfInactivityBeforeIdling: -1` disables idling, because agent workers run unattended for long periods. `startTimeoutSeconds: 1200` allows the large tooling image and the postStart bootstrap.
- `maxNumberOfRunningWorkspacesPerUser: 3`; `containerResourceCaps` caps containers at 6 CPU / 12 Gi.
- `allowedSources.urls` starts as an `.invalid` placeholder; `070-gitlab` replaces it with the GitLab workload and platform groups. Only those sources can start a workspace.
- `pluginRegistry.openVSXURL: https://open-vsx.org`; `defaultNamespace.autoProvision: true` for other users.

**Persona namespaces.** The three `wksp-*` namespaces (from `070-namespaces`) carry the documented pre-provisioning labels and username annotation [4], so Dev Spaces uses them instead of `<username>-devspaces`. Editor settings are per-namespace `vscode-editor-configurations` ConfigMaps, the documented per-project form [5].

**MaaS credentials.** Each persona namespace has its own key Job and key owner (`maas-keys/base`, overlays `developer` and `admin`), so MaaS usage is attributed per persona; the Stage 040 `devspaces-coding-models` subscription lists both owners. The key Job reads the Gateway hostname, authenticates to the MaaS API with its own service-account token, and creates keys on the `devspaces-coding-models` subscription. An existing key is kept only if the API confirms the same owner and subscription and an `active` status; any other answer stops the Job without revoking anything. Keys go into `maas-devspace-api-keys` and into `workspace-maas-credentials`, an env-mounted Secret with `MAAS_API_KEY`, `MAAS_API_BASE_URL` and the canonical model ID [6]. `secret_writer.py` creates or merge-patches each Secret without a `last-applied-configuration` copy. `ai-admin` workspaces read the same Secrets across namespaces, so both personas share one key owner.

**Workspace bootstrap.** `coolstore-inventory-service` runs `init-ai-tools.sh` from the ConfigMap at postStart, through the Kubernetes API. The AdminNetworkPolicy allows that API path; the namespaced policy cannot, because the API server runs on host network.

**Cross-component writes.** `070-gitlab`'s integration hub (wave 14 of that Application) writes the GitLab OAuth Secret with the labels and annotations the guide requires [7], patches the CheCluster `gitServices` and `allowedSources`, and patches the workspaces' `origin` remote. `070-pipelines` runs the migration-run provisioner and the project enrollment that mirror per-run and Sonar credentials into `wksp-ai-developer`.

**ignoreDifferences.** DevWorkspace `spec.started` (user lifecycle) and the `HOST_USERS` env, `devworkspace-config` and `scc` attributes that Dev Spaces injects; CheCluster `allowedSources.urls` and the GitLab endpoint (owned by `070-gitlab`); the two `coolstore-inventory-service` remotes (owned by `070-gitlab`).

Operations: [Stage 070 Dev Spaces](../../../../docs/OPERATIONS.md#stage-070--dev-spaces-devspaces-component). Failures: [workspace does not start](../../../../docs/TROUBLESHOOTING.md#red-hat-openshift-dev-spaces-workspace-does-not-start), [workspace tools unavailable](../../../../docs/TROUBLESHOOTING.md#stage-070-workspace-tools-or-mta-ai-are-unavailable).

## Validation

`validate.sh` (live, read-only):

- `devspaces installed revision` = `devspacesoperator.v3.30.2` and `devspacesoperator.v3.30.2 succeeded`.
- `Dev Spaces Active`, `Dev Spaces per-workspace storage`, `Dev Spaces GitLab OAuth configured`.
- `wksp-ai-developer standing workspace uses GitLab` and the same for `wksp-ai-admin`.
- `Scoped integration Secret openshift-devspaces/gitlab-oauth-config exists`.
- `stages/070-advanced-app-platform/validate.sh`: `no_retained_secret_annotation` for `openshift-devspaces`, `wksp-ai-developer` and `wksp-ai-admin`; `idle_bootstrap_cannot_write_credentials` includes `openshift-devspaces`; `no_credential_annotation:openshift-devspaces/gitlab-oauth-config`.

`validate.sh --static`: the stage renders, its components are disjoint, and the scripts parse. The former offline tests (`tests/*.test.py`) and the admission dry-run checker `check-workspace-creation.py` are in git history at `82092e01`.

By hand:

```bash
oc get checluster devspaces -n openshift-devspaces -o jsonpath='{.status.chePhase} {.status.cheVersion}{"\n"}'
oc get devworkspace -n wksp-ai-developer
```

## Alignment with official guidance

| Topic | Official guidance | This repository | Status |
|---|---|---|---|
| GitOps installation | Subscription, CheCluster v2 and Kustomization in Git, reconciled by Argo CD [1] | Same | Aligned |
| Subscription namespace | Subscription in `openshift-operators` (AllNamespaces); "Do not place the Subscription in the `openshift-devspaces` namespace" [1] | Same | Aligned |
| Channel and approval | `stable`, `Automatic` in the example [1] | Same; the operator policy check holds the qualified minimum | Aligned |
| PVC strategy | Default `per-user`; `per-workspace` gives one PVC per workspace [3] | `per-workspace`, 20 Gi, `gp3-csi` | Deviation (justified: concurrent factory workspaces) |
| Home persistence | `persistUserHome` requires `per-user` or `per-workspace` [3] | Enabled with `per-workspace` | Aligned |
| Idling | Default 1800 s; `-1` disables [3] | `-1` | Deviation (justified: unattended agent runs) |
| Start timeout | Default 300 s [3] | 1200 s | Deviation (justified: large image and bootstrap) |
| Allowed sources | `allowedSources.urls` restricts which URLs can start a workspace [3] | Restricted to two GitLab groups, set by `070-gitlab` | Aligned |
| Pre-provisioned projects | Labels `part-of: che.eclipse.org`, `component: workspaces-namespace`, annotation `che.eclipse.org/username` [4] | All three present; `autoProvision` stays `true` for other users | Aligned |
| Editor configuration | ConfigMap `vscode-editor-configurations` with `workspaces-config` labels in the user project, or in `openshift-devspaces` to replicate [5] | Per persona project | Aligned |
| Default extensions | `DEFAULT_EXTENSIONS` lists local VSIX paths, which a postStart command may download [8] | Kilo Code 7.4.8 VSIX downloaded to `/tmp` at postStart | Aligned (no checksum on the download) |
| Mounted credentials | `mount-to-devworkspace` Secrets restart running workspaces when applied unless annotated `mount-on-start` [6] | `migration-model-profiles` uses `mount-on-start`; `workspace-maas-credentials` and `devspace-ai-tools-init` do not | Gap: a credential or init-script change can restart running workspaces |
| GitLab OAuth | Secret `gitlab-oauth-config` with the `oauth-scm-configuration` labels and annotations, keys `id`/`secret` [7]; app callback `/api/oauth/callback`, Confidential, scopes `api write_repository openid` [9] | Written by `070-gitlab` exactly so; CheCluster `gitServices.gitlab[].endpoint` also set | Aligned; the endpoint field is deprecated in favor of the annotation [3] |
| Tooling image | Use the release's UDI | `udi-rhel9:3.29.1` digest under Dev Spaces 3.30.2 | Gap: image one minor behind the operator |
| Least privilege | `get`/`list` on Secrets reveals them; workload creators inherit namespace SA rights [10] | Provisioner SA outside the workspace namespace; key reader by name; key and Sonar writers namespace-wide | Partly aligned (namespace-wide Secret writers remain) |
| API egress | AdminNetworkPolicy `nodes` peer for host-network destinations [11] | `workspace-allow-kapi-egress` to control-plane nodes, TCP 6443 | Aligned |

## References

1. Deploy using GitOps and Argo CD, Red Hat OpenShift Dev Spaces 3.30. https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/install-proc_deploying_devspaces_using_gitops
2. Red Hat OpenShift Dev Spaces 3.30 documentation. https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30
3. CheCluster custom resource fields, Red Hat OpenShift Dev Spaces 3.30. https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/configure-ref_checluster_custom_resource_fields
4. Provision projects in advance, Red Hat OpenShift Dev Spaces 3.30. https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/configure-proc_provisioning_projects_in_advance
5. Apply editor configurations, Red Hat OpenShift Dev Spaces 3.30. https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/extend-proc_applying_editor_configurations
6. Mount Secrets, Red Hat OpenShift Dev Spaces 3.30. https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/develop-proc_mounting_secrets
7. Connect OpenShift Dev Spaces to your GitLab OAuth application, Red Hat OpenShift Dev Spaces 3.30. https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/integrate-proc_applying_the_gitlab_authorized_application_secret
8. Configure default extensions, Red Hat OpenShift Dev Spaces 3.30. https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/extend-proc_configuring_default_extensions
9. Set up the GitLab authorized application, Red Hat OpenShift Dev Spaces 3.30. https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/integrate-proc_setting_up_the_gitlab_authorized_application
10. Role Based Access Control Good Practices, Kubernetes (upstream). https://kubernetes.io/docs/concepts/security/rbac-good-practices/
11. Admin network policy, 2.4 "Egress nodes and networks peer for AdminNetworkPolicy", OpenShift Container Platform 4.22. https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/network_security/admin-network-policy
12. Sync Options (`Replace`, `Force`, `RespectIgnoreDifferences`), Argo CD (upstream). https://argo-cd.readthedocs.io/en/stable/user-guide/sync-options/
13. [Stage 070 README](../../../../stages/070-advanced-app-platform/README.md)
