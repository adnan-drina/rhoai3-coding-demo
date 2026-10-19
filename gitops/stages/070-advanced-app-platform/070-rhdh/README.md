# Red Hat Developer Hub (`070-rhdh`)

This Application installs Red Hat Developer Hub 1.10 as the developer portal of the platform. It publishes a software catalog and two software templates (new Quarkus application, application migration) that are pinned to one reviewed platform commit in the private GitLab mirror. It signs users in through the existing Keycloak `platform` realm and shows each project's Kubernetes, Topology, Tekton and Argo CD state. Developers and the Stage 110–130 workflows start new and migration projects here.

| | |
|---|---|
| Argo CD Application | `070-rhdh` ([manifest](../../../applications/070-rhdh.yaml)) |
| Deployed by | `stages/070-advanced-app-platform/deploy.sh` → `stage-apps.sh deploy 070` (deploy-order 8, last) |
| Validated by | `stages/070-advanced-app-platform/validate.sh` (operator, portal, catalog and security checks); `validate.sh --static` (catalog renderer and template tests) |
| Sync | Automated, `prune: true`, `selfHeal: true`; `CreateNamespace`, `SkipDryRunOnMissingResource`, `RespectIgnoreDifferences`, `ClientSideApplyMigration=false`; compare-option `ServerSideDiff=true`; `ignoreDifferences` on OperatorGroup annotation `olm.providedAPIs` (OLM-owned), Subscription `startingCSV`, Secret `rhdh-secrets` `/data`, ConsoleLink `rhdh` `href`/`imageURL` |
| Depends on | `070-namespaces` (`rhdh-operator`, `rhdh`); `070-identity` (Secret `stage070-rhdh-provisioner`, a `platform`-realm client that may manage clients); `070-gitlab` (GitLab mirror of the platform repository at the synced commit, Secrets `rhdh-gitlab` and `gitlab-catalog-reader`, ConfigMap `gitlab-platform-config`, Argo CD reader token `rhdh-local-user`, from Stage 010); `070-devspaces`, `070-sonarqube` and the Coolstore enrollment in `coolstore-dev` (Routes used for links); Stage 040 (`maas-default-gateway` and `maas-gateway-internal` for migration workspaces); Stage 010 (Keycloak) |
| Used by | Developers (portal, templates, TechDocs); Stage 110–130 workflows; `070-pipelines/gitlab` enrollment (handles the GitLab issues the templates open) |

## Why

The platform needs one self-service entry point where a developer finds approved templates, documentation and the state of their project. Red Hat Developer Hub provides the catalog, the scaffolder, TechDocs and role-based access control on a supported Backstage distribution [1][2][4].

The portal is installed by its Operator and configured only through the `Backstage` custom resource, ConfigMaps and Secrets. This is the documented Operator path [1][5]. The catalog is generated at sync time from a bundle that Kustomize builds from the same checkout. The bundle name carries a content hash, so a catalog or template change is a manifest change Argo CD applies. The generator publishes only when every bundled file is byte-identical to the file in the GitLab mirror at the synced commit. Template links, skeletons and TechDocs therefore always point to one immutable revision.

Developer Hub is the last component in the deploy order. Its catalog hook needs the GitLab mirror and the scoped GitLab credentials that `070-gitlab` creates at wave 14 of its own sync. Sync waves only order resources inside one Application [8], so `stage-apps.sh deploy 070` provides the cross-component order.

## What

### `rhdh-operator/`: Operator installation

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| OperatorGroup | `rhdh-operator` | `rhdh-operator` | No target namespaces: all-namespaces mode (wave 1) |
| Subscription | `rhdh` | `rhdh-operator` | Channel `fast-1.10`, `installPlanApproval: Manual`, `startingCSV: rhdh-operator.v1.10.5`, `redhat-operators` (wave 2) |
| ServiceAccount, Role, RoleBinding | `approve-installplan` | `rhdh-operator` | `get`/`list`/`patch` InstallPlans; `get` on Subscription `rhdh` only (wave 1) |
| Job (Sync hook) | `approve-installplan` | `rhdh-operator` | Approves this operator's InstallPlan only if every CSV is on its allowlist (`rhdh-operator.v1.10.5`), then waits for that CSV (wave 2; `BeforeHookCreation,HookSucceeded`) |

The `rhdh-operator` and `rhdh` namespaces come from `070-namespaces`.

### `rhdh-instance/`: portal configuration

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| ConfigMap | `app-config-rhdh` | `rhdh` | App config: OIDC provider, RBAC, GitLab integration and discovery, Kubernetes and Argo CD plugins, file catalog location, local TechDocs, global header (wave 5) |
| ConfigMap | `dynamic-plugins-rhdh` | `rhdh` | Enables GitLab catalog and scaffolder modules, RBAC, Kubernetes, Topology; digest-pinned OCI Tekton and Argo CD plugins, mounted as the CI and CD entity tabs (wave 5) |
| ConfigMap | `rhdh-rbac-policies` | `rhdh` | `rbac-policies.csv`: `ai-developer` gets `role:default/developer` (catalog read, template use, task create/read, Kubernetes read; catalog entity/location create and delete denied) (wave 5) |
| Secret | `rhdh-secrets` | `rhdh` | Placeholder `data` only; the configure hook writes runtime values (wave 5, `ServerSideApply=true`) |
| ConfigMap | `catalog-runtime-rhdh` | `rhdh` | Sync hook (wave 5, `BeforeHookCreation`): placeholder catalog that the generator replaces |
| ServiceAccount, Secret, ClusterRole, ClusterRoleBinding | `rhdh-kubernetes-reader` (ServiceAccount, ClusterRole, ClusterRoleBinding), `rhdh-kubernetes-reader-token` | `rhdh` / cluster | Identity of the Kubernetes, Topology and Tekton plugins; read-only ClusterRole `rhdh-kubernetes-reader` (wave 5) |
| Backstage | `developer-hub` | `rhdh` | Instance (wave 18). Mounts app config, dynamic plugins, RBAC CSV, runtime catalog and `kube-root-ca.crt`; env from `rhdh-secrets` and `rhdh-gitlab`; `maxSurge: 0` rollout; `NODE_EXTRA_CA_CERTS` set to the cluster CA |
| ConsoleLink | `rhdh` | (cluster) | Application-menu entry; `href` patched by the configure hook (wave 15) |

### `jobs/` and `catalog/`, `templates/`: catalog generation and portal setup

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| ConfigMap (generated) | `rhdh-catalog-bundle-<hash>` | `rhdh` | `catalog/all.yaml`, `generate.sh`, `render_catalog.py` and every template and skeleton file (wave 7, `PruneLast`) |
| ServiceAccount, Role, RoleBinding | `job-generate-rhdh-catalog` | `rhdh` | ConfigMap create, and get/patch/update on `catalog-runtime-rhdh` only; no pod or exec access (wave 7, standing) |
| Role, RoleBinding | `job-generate-rhdh-catalog-maas-route` | `openshift-ingress` | `get` on Gateway `maas-default-gateway` and Service `maas-gateway-internal` only (wave 7) |
| ClusterRole, ClusterRoleBinding | `job-generate-rhdh-catalog` | (cluster) | `get`/`list` Routes, `get` Applications, `get` cluster Ingress config (wave 7) |
| Job | `job-generate-rhdh-catalog` | `rhdh` | Sync hook, wave 17, `BeforeHookCreation,HookSucceeded`: verifies the bundle against the GitLab mirror, renders and writes `catalog-runtime-rhdh` |
| CronJob | `refresh-rhdh-catalog` | `rhdh` | Every 5 minutes, `SKIP_IF_CURRENT=true`: converges after syncs that skip hooks; defers while `070-rhdh` has a running operation (wave 19) |
| ServiceAccount, Role, ClusterRole, bindings | `job-configure-rhdh`, `job-configure-rhdh-gitops-reader` | `rhdh`, `openshift-gitops`, cluster | Sync-hook RBAC (wave 18, deleted on success): read three named Secrets, patch `rhdh-secrets`, patch Deployments, read the operator-managed `rhdh-local-user` (Argo CD token), get/list Routes, get/patch ConsoleLinks |
| Job | `job-configure-rhdh` | `rhdh` | Sync hook, wave 18: creates or updates the `rhdh` OIDC client, writes `rhdh-secrets`, patches the ConsoleLink, restarts the portal when values changed |

`network-policy.yaml` adds NetworkPolicy `platform-ingress` in `rhdh`: ingress only from the same namespace, the OpenShift router and monitoring namespaces. Egress is unchanged.

Not in Git: the Deployment `backstage-developer-hub`, StatefulSet `backstage-psql-developer-hub`, the Route and the default app-config ConfigMaps (all owned by the Operator); Secrets `rhdh-gitlab`, `gitlab-catalog-reader`, `gitlab-publisher` and ConfigMap `gitlab-platform-config` (owned by the `070-gitlab` integration hub); Secret `stage070-rhdh-provisioner` (declared by `070-identity`).

## How

- **Installation.** The Subscription uses the documented `fast-1.10` channel in the recommended `rhdh-operator` namespace with all-namespaces mode [1]. Approval is `Manual`. This component's own `approve-installplan` hook approves the plan only if every CSV in it is on its allowlist (`rhdh-operator.v1.10.5`) and waits until that CSV is installed; its Role reaches only `rhdh-operator` InstallPlans and the `rhdh` Subscription. The validator expects exactly `rhdh-operator.v1.10.5`, so a z-stream update is a reviewed change.
- **Ordering inside the Application.** Wave 5 creates config and the placeholder catalog; wave 7 the bundle and generator RBAC; wave 17 the catalog Job; wave 18 the `Backstage` CR and the configure Job; wave 19 the refresh CronJob, so a failed refresh cannot gate setup.
- **Catalog generation.** `generate.sh` reads the synced revision from `070-rhdh` `status.operationState.syncResult.revision`. `render_catalog.py verify` reads every bundled file from the GitLab API with the read-only `gitlab-catalog-reader` token and refuses `FACTORY_BUNDLE_MISMATCH` when any byte differs. `render` substitutes the Dev Spaces, SonarQube, Coolstore, MaaS and GitLab values and refuses any unresolved placeholder. The result is stamped with `rhoai3.redhat.com/catalog-revision` and `catalog-bundle`. Template Locations of a previous revision are no longer emitted, so the catalog deletes them as orphans (`orphanStrategy: delete`); the generator has no database access.
- **Catalog sources.** Only the file location may introduce `Template` entities. The GitLab discovery provider reads `catalog-info.yaml` on `main` in the `rhoai-workloads` group every minute and may not ingest templates. Templates publish private repositories and open an enrollment issue; they do not call `catalog:register`. `orphanStrategy: delete` removes retired entities.
- **Authentication.** OIDC against `https://<keycloak-host>/realms/platform`, client `rhdh`, `auth.environment: production`, resolver `preferredUsernameMatchingUserEntityName` [3]. User entities `ai-admin` and `ai-developer` come from `catalog/all.yaml`.
- **Authorization.** RBAC is enabled with `ai-admin` as policy administrator and a CSV policy file mounted through `extraFiles`, as documented [4]. `pluginsWithPermission` adds `kubernetes`.
- **Plugins.** The Kubernetes plugin uses a ServiceAccount token and the cluster CA from `kube-root-ca.crt`; Tekton PipelineRuns, TaskRuns and Routes are custom resources [5]. Tekton and Argo CD plugins are OCI packages pinned by digest, as the plugin guide recommends [5].
- **Trust.** `NODE_EXTRA_CA_CERTS` adds the cluster CA to Node's trust store instead of disabling TLS checks [6].
- **Rollout.** `maxSurge: 0` through `spec.deployment.patch` lets only one backend run database migrations on a fresh database [6].
- **Credentials.** The configure Job exchanges the `stage070-rhdh-provisioner` client credentials for a `platform`-realm token, keeps an existing client secret and session secret or generates new ones, and writes them with the Kubernetes reader token, the Argo CD reader token and the service URLs into `rhdh-secrets` by merge patch. The Application ignores `/data` of that Secret, so syncs keep the runtime values. GitLab tokens arrive in `rhdh-gitlab` from `070-gitlab`. No value is stored in Git or in apply annotations.
- **Operations.** Day-2 notes: [Operations, Developer Hub](../../../../docs/OPERATIONS.md#stage-070--developer-hub-rhdh-component). Failure recovery: [catalog generator refusal](../../../../docs/TROUBLESHOOTING.md#rhdh-catalog-generator-refuses-factory_bundle_mismatch) and [OIDC 504](../../../../docs/TROUBLESHOOTING.md#red-hat-developer-hub-oidc-sign-in-fails-with-504-gateway-timeout).

## Validation

`validate.sh` checks for this component:

- `rhdh installed revision` and `rhdh-operator.v1.10.5 succeeded`.
- `Portal instance exists`, `Portal catalog bundle stamped`, `Portal catalog has no unresolved placeholders`, `Portal templates use private GitLab mirror`, `Developer Hub reachable`.
- `Scoped integration Secret rhdh/gitlab-publisher exists` and `rhdh/gitlab-catalog-reader exists`.
- `Stage 070 corrected security boundaries` (`stages/070-advanced-app-platform/validate.sh`): no apply annotation on `rhdh-gitlab`, `rhdh-local-user` or any Secret in `rhdh`; Developer Hub's Argo CD token equals the operator's `rhdh-local-user` token; `job-configure-rhdh` cannot read the master admin Secret; `stage070-rhdh-provisioner` can read only its `platform` client and cannot administer `sso` or `master`; `platform-ingress` is installed in `rhdh`.

`validate.sh --static` checks renders, disjoint components and script syntax. `jobs/catalog/render_catalog.test.py` (bundle coverage, hash rename, mismatch refusal, Python 3.6 compatibility, wave order) and `templates/app-migration/app-migration-template.test.py` stay beside their sources and run by hand; the former stage tests (`security-boundaries.test.py` and others) are in git history at `82092e01`.

By hand (read-only):

```bash
oc get subscription rhdh -n rhdh-operator -o jsonpath='{.status.installedCSV}{"\n"}'
oc get backstage developer-hub -n rhdh; oc get pods -n rhdh
oc get configmap catalog-runtime-rhdh -n rhdh -o jsonpath='{.metadata.annotations.rhoai3\.redhat\.com/catalog-revision}{"\n"}'
```

## Alignment with official guidance

| Topic | Official guidance | This repository | Status |
|---|---|---|---|
| Operator install | Namespace `rhdh-operator`, channel `fast` or `fast-1.10`, all-namespaces mode [1] | Same; Manual approval with exact `startingCSV` | Aligned |
| Configuration | Custom app config, dynamic plugins, extra files and env through the `Backstage` CR [6] | `appConfig`, `dynamicPluginsConfigMapName`, `extraFiles`, `extraEnvs` | Aligned |
| Guest access | `auth.environment: production` disables guest login [3] | Set | Aligned |
| User provisioning | Users must exist in the catalog; the Keycloak catalog provider imports them [3] | Two static User entities in `catalog/all.yaml` | Deviation (justified: two fixed demo personas) |
| Sign-in resolver | Default `oidcSubClaimMatchingKeycloakUserId`; `preferredUsernameMatchingUserEntityName` is a documented alternative [3] | Alternative resolver, matching the static entity names | Aligned |
| RBAC | Policy admins in `permission.rbac.admin.users`; CSV through `policies-csv-file` and `extraFiles`; list plugin IDs in `pluginsWithPermission` [4] | As documented, CSV in Git | Aligned |
| Tekton plugin | OCI package from `rhdh-plugin-export-overlays`, digest recommended; Kubernetes plugin with a ServiceAccount; Tekton custom resources [5] | Digest-pinned OCI package; `pipelineruns`, `taskruns` | Aligned |
| Kubernetes plugin RBAC | Read-only ClusterRole with named resources (for example `backstage-read-only` with Tekton `get`/`list`) [5] | ClusterRole `rhdh-kubernetes-reader`: the Backstage Kubernetes plugin's documented read rules plus Tekton runs and Routes [12] | Aligned |
| Argo CD plugin | Recommended: Community frontend with Community backend; mixing Community and Roadie plugins is not recommended [5] | Community frontend `bs_1.49.4__2.8.0` with Community backend `bs_1.49.4__1.4.0`, both digest-pinned | Aligned |
| Custom CA | Configure trust with `NODE_EXTRA_CA_CERTS` [6] | Cluster CA through `NODE_EXTRA_CA_CERTS` | Aligned |
| Database | Operator-managed local PostgreSQL by default; external PostgreSQL for production [6] | Operator-managed local PostgreSQL | Deviation (justified: single-cluster demo) |
| TechDocs | Local builder is not intended for production; use CI-built docs in object storage [7] | `builder: local` | Deviation (justified: one platform docs source, no docs pipeline) |
| Developer Lightspeed | Enabled by default; disable with the `lightspeed` flavour when no LLM is configured, which also stops the unconfigured sidecar [9] | `flavours: [{name: lightspeed, enabled: false}]` in the Backstage CR | Aligned |
| Namespace ingress | NetworkPolicy allowing the OpenShift router namespaces by `policy-group.network.openshift.io/ingress` [10] | Same, plus same-namespace and monitoring | Aligned |
| Telemetry | `analytics-provider-segment` is enabled by default; disable it with `disabled: true` in the dynamic plugins ConfigMap [11] | Disabled | Aligned |

## References

1. Installing Red Hat Developer Hub on OpenShift Container Platform, 2.1 "Install the Red Hat Developer Hub Operator", Red Hat Developer Hub 1.10. https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/installing_red_hat_developer_hub_on_openshift_container_platform/index
2. Integrating Red Hat Developer Hub with your Git provider, chapter 2 "Integrate with GitLab", Red Hat Developer Hub 1.10. https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/integrating_red_hat_developer_hub_with_your_git_provider/index
3. Authentication in Red Hat Developer Hub, 1.2, 2.2 "Disable the Guest login", 4.1 "Import users and groups from RHBK", 5.1 "Enable authentication with RHBK", Red Hat Developer Hub 1.10. https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/authentication_in_red_hat_developer_hub/index
4. Authorization in Red Hat Developer Hub, chapter 2 and 7.1 "Manage authorizations by using external files", Red Hat Developer Hub 1.10. https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/authorization_in_red_hat_developer_hub/index
5. Configuring dynamic plugins, chapter 2 "Install and configure Argo CD", chapter 5 "Enable the Tekton plugin", 6.2.3 "View Tekton PipelineRuns", Red Hat Developer Hub 1.10. https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/configuring_dynamic_plugins/index
6. Configuring Red Hat Developer Hub, chapters 6, 10 "Configure trust for corporate Certificate Authority with NODE_EXTRA_CA_CERTS", 14 and 17, Red Hat Developer Hub 1.10. https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/configuring_red_hat_developer_hub/index
7. TechDocs for Red Hat Developer Hub, chapter 2 "Configure TechDocs", Red Hat Developer Hub 1.10. https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/techdocs_for_red_hat_developer_hub/index
8. Sync phases and waves, Argo CD (upstream). https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/
9. Interacting with Red Hat Developer Lightspeed for Red Hat Developer Hub, chapter 4 and 4.3 "Disable Developer Lightspeed for RHDH by using the Operator", Red Hat Developer Hub 1.10. https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/interacting_with_red_hat_developer_lightspeed_for_red_hat_developer_hub/index
10. Network policy, 3.1.1.1 "Policy additivity" (`allow-from-router` example), OpenShift Container Platform 4.22. https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/network_security/network-policy
11. Telemetry data collection and analysis, "Disable telemetry data collection by using the Operator", Red Hat Developer Hub 1.10. https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/telemetry_data_collection_and_analysis/index#disable-telemetry-data-collection-using-the-operator_disable-telemetry-data-collection-in-rhdh
12. Kubernetes plugin configuration, "Role Based Access Control", Backstage (upstream). https://backstage.io/docs/features/kubernetes/configuration

Repository: [Stage 070 README](../../../../stages/070-advanced-app-platform/README.md), [Application manifest](../../../applications/070-rhdh.yaml), [stage validator](../../../../stages/070-advanced-app-platform/validate.sh).
