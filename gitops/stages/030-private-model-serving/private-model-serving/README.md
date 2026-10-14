# Private model serving foundation (`030-private-model-serving`)

This Application turns on the OpenShift AI model-serving and model-discovery foundations: the KServe and Model Registry
components of the shared `DataScienceCluster`, the `demo-registry` model registry, the Model Catalog and the Developer
Preview Agent Catalog with one custom agent source, and persistent storage for OpenShift platform and user-workload
Prometheus. It deploys no model and allocates no GPU. Stage 040 deploys models and writes registry records, Stage 050
reads the registry and catalog, and Stage 060 is the subject of the agent catalog cards.

| | |
|---|---|
| Argo CD Application | `030-private-model-serving` ([manifest](../../../argocd/app-of-apps/030-private-model-serving/private-model-serving.yaml)) |
| Deployed by | [`stages/030-private-model-serving/deploy.sh`](../../../../stages/030-private-model-serving/deploy.sh) (own deploy script, `demo.rhoai.io/deploy-script`; pins the Application to the published commit SHA) |
| Validated by | [`validate.sh`](../../../../stages/030-private-model-serving/validate.sh) (Application at its exact revision, DSC/KServe conditions, KServe-owned workloads, both Prometheus PVCs) and [`validate-model-discovery.sh`](../../../../stages/030-private-model-serving/validate-model-discovery.sh) (registry and catalog workloads, authenticated registry, Model Catalog and Agent Catalog APIs, dashboard flags) |
| Sync | Automated, `prune` and `selfHeal`. Server-Side Diff through the `compare-options` annotation; `RespectIgnoreDifferences=true`, `SkipDryRunOnMissingResource=true`, `CreateNamespace=true`. Retry 10 times, 5 s to 3 min backoff. |
| Depends on | `010-rhoai-platform` (the `default-dsc` and `odh-dashboard-config` objects and their delegated fields); Stage 020 readiness (checked by `deploy.sh` on first install); the `gp3-csi` StorageClass (AWS EBS CSI). |
| Used by | Stage 040 (KServe, registry records), `050-evalhub` (catalog safety-insights Role in `rhoai-model-registries`), Stage 060 (MCP catalog/registry dashboard flags, Agent Catalog cards), Stage 040/050 dashboards and alerts that need user-workload monitoring. |

## Why

Model serving in OpenShift AI 3.5 runs on KServe, which is a `DataScienceCluster` component with a `managementState` the
operator reconciles [2][7]. Model Registry and Model Catalog are one component, `modelregistry`; it must be `Managed`
before anyone can use the registry or the catalog, and its `registriesNamespace` is set to `rhoai-model-registries` [1][2].
A registry instance (`ModelRegistry` CR) is then created in that namespace [1]. The Agent Catalog is a 3.5 Developer
Preview feature for agent starter-kit discovery [5]; it is shown in the dashboard only with `agentsCatalog: true` [4].

Stage 010 creates the shared `DataScienceCluster` and dashboard configuration with these components `Removed`, so the
base platform validates on its own. This component turns them on by patching only the delegated fields. The registry,
catalog and monitoring changes have one lifecycle (serving foundation, no model), so they share one Application. Models
change often and live in Stage 040.

OpenShift monitoring keeps Prometheus data on `emptyDir` unless a persistent volume claim is configured; Red Hat highly
recommends persistent storage for production clusters [8]. On this demo the unbounded `emptyDir` time-series databases
caused worker disk-pressure evictions, so both Prometheus stacks get PVCs and retention limits [8][9][10].

## What

### `dsc-enablement/` (KServe)

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| ServiceAccount | `job-enable-dsc-kserve` | `redhat-ods-applications` | Identity of the hook Job. Wave 1. |
| ClusterRole | `job-enable-dsc-kserve` | cluster | `get`, `patch` on `datascienceclusters/default-dsc` only. Wave 1. |
| ClusterRoleBinding | `job-enable-dsc-kserve` | cluster | Binds the role to the ServiceAccount. Wave 1. |
| Job | `job-enable-dsc-kserve` | `redhat-ods-applications` | `Sync` hook, wave 2, delete policy `BeforeHookCreation,HookSucceeded`. Waits for the DSC, merge-patches `spec.components.kserve.managementState: Managed`, and reads it back. |

### `model-discovery/` (registry, catalogs, dashboard flags)

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| ServiceAccount | `enable-model-discovery` | `redhat-ods-applications` | Identity of the hook Job. Wave 1. |
| ClusterRole / ClusterRoleBinding | `enable-model-discovery` | cluster | `get`, `patch` on `default-dsc`; `get` on the `modelregistries.modelregistry.opendatahub.io` CRD. Wave 1. |
| Role / RoleBinding | `enable-model-discovery` | `redhat-ods-applications` | `get`, `patch` on `odhdashboardconfigs/odh-dashboard-config` only. Wave 1. |
| Job | `enable-model-discovery` | `redhat-ods-applications` | `Sync` hook, wave 2, `BeforeHookCreation,HookSucceeded`. Sets `modelregistry` `Managed` with `registriesNamespace: rhoai-model-registries`, sets six dashboard flags, then waits until the `ModelRegistry` CRD is `Established`. |
| ConfigMap | `agent-catalog-sources` | `rhoai-model-registries` | Wave 8. Agent Catalog source `governed-coding-agents` with two metadata-only cards (OpenCode, Hermes) that point to Stage 060. |
| Namespace | `rhoai-model-registries` | cluster | `Prune=false,Delete=false`. Registry namespace named in the DSC. |
| ModelRegistry | `demo-registry` | `rhoai-model-registries` | Wave 6, `Prune=false,Delete=false`, `SkipDryRunOnMissingResource`. Registry with the operator-generated PostgreSQL, gRPC 9090, REST 8080, authenticated route through kube-rbac-proxy on 443. |
| RoleBinding | `demo-registry-rhods-admins` | `rhoai-model-registries` | Wave 7, `Prune=false,Delete=false`. Group `rhods-admins` to the operator-created Role `registry-user-demo-registry`. |
| RoleBinding | `demo-registry-rhoai-developers` | `rhoai-model-registries` | Wave 7, `Prune=false,Delete=false`. Group `rhoai-developers` to the same Role. |

### `monitoring/` (moved)

Moved on 2026-10-14 to `010-observability-operators` (`cluster-monitoring/`), with `Prune=false,Delete=false`: it is cluster-wide platform configuration that Stages 040 and 050 also rely on.

### Objects not in Git

| Object | Created by |
|---|---|
| `Deployment` `demo-registry`, `demo-registry-postgres`; PVC `demo-registry-postgres-storage`; Secret `demo-registry-postgres-credentials`; Route `demo-registry-https`; Role `registry-user-demo-registry`; Group `demo-registry-users` | Model Registry operator, owned by the `ModelRegistry` CR |
| `ModelRegistry` component `default-modelregistry`; `Deployment` `model-catalog`, `model-catalog-postgres`; Route `model-catalog-https`; catalog Roles | OpenShift AI operator (`modelregistry` component) |
| `KServe` component `default-kserve` and its controller Deployments in `redhat-ods-applications` | OpenShift AI operator (`kserve` component) |
| Prometheus PVCs `prometheus-k8s-db-prometheus-k8s-{0,1}` (40 Gi) and `prometheus-user-workload-db-prometheus-user-workload-{0,1}` (20 Gi) | Cluster Monitoring Operator from the two ConfigMaps |
| Registry models, versions and artifacts | Stage 040 and Stage 050 helpers, through the registry API |

## How

**Ordering.** Waves 1 and 2 create the RBAC and run the two hook Jobs, so the CRD exists before the `ModelRegistry`
(wave 6). The registry RoleBindings (wave 7) reference a Role the operator creates only after the registry exists. The
agent source ConfigMap (wave 8) lands after the catalog is enabled. `SkipDryRunOnMissingResource` lets the first sync
proceed before the CRD exists [12]. Argo CD applies hooks and resources wave by wave until all are synced and healthy [11].

**Deploy script.** `deploy.sh` refuses to run unless the published branch equals the reviewed local commit, Stage 010 is
reconciled, Stage 010 delegates the fields below, any existing registry objects are already tracked by this Application,
any existing `demo-registry` spec equals Git and owns its database PVC and Secret, and the monitoring ConfigMaps are absent
or already owned by this Application. It runs `preflight-agent-catalog.py`, which only adopts an empty
`agent-catalog-sources` ConfigMap. It then applies the Application with `targetRevision` set to the commit SHA, waits for
`Synced`/`Healthy`/`Succeeded` at that SHA, and runs `validate.sh`. On a first install it runs the Stage 020 readiness
check; on an update it runs `validate-serving-update.py` so parked GPU capacity is not started.

**Delegated fields.** Stage 010's `010-rhoai-platform` Application owns `default-dsc` and `odh-dashboard-config` and lists
the fields later stages own in its `ignoreDifferences` with `RespectIgnoreDifferences=true`, so Argo CD neither reports nor
reverts them [12]. `scripts/shared/stage_apps.py delegated 010 ...` reads that list, and `deploy.sh` asserts it. This
component writes:

| Object | Field | Value | Written by | Doc default |
|---|---|---|---|---|
| `DataScienceCluster/default-dsc` | `/spec/components/kserve` | `managementState: Managed` | `job-enable-dsc-kserve` | `Removed` in the Stage 010 manifest [6] |
| `DataScienceCluster/default-dsc` | `/spec/components/modelregistry` | `managementState: Managed`, `registriesNamespace: rhoai-model-registries` | `enable-model-discovery` | namespace value as documented [2] |
| `OdhDashboardConfig/odh-dashboard-config` | `/spec/dashboardConfig/disableModelRegistry`, `disableModelCatalog` | `false` | `enable-model-discovery` | `false` [4] |
| same | `/spec/dashboardConfig/agentsCatalog` | `true` | `enable-model-discovery` | `false`, Developer Preview [4][5] |
| same | `/spec/dashboardConfig/toolCalling`, `mcpCatalog`, `mcpRegistry` | `true` | `enable-model-discovery` | `false`, Technology Preview [4] |

The KServe sub-fields shown live (`nim`, `rawDeploymentServiceConfig`, `modelsAsService`, `wva`) are operator defaults or
are set by Stage 040; this component sets only `managementState`.

**Registry configuration.** `postgres.generateDeployment: true` uses the default database the operator deploys. The 3.5
guide states this option is for evaluation, development and testing only and is not supported for production [1].
`sslMode: disable` keeps the in-namespace database connection plaintext. The REST route is disabled; the only external
route is the kube-rbac-proxy route on 443, which checks the caller's token. Groups get access through the operator-created
`registry-user-demo-registry` Role, the same Role the dashboard's registry permissions page binds [1].

**Agent catalog source.** The 3.5 docs describe custom sources only for the Model Catalog (`model-catalog-sources`
ConfigMap) [3]. The Agent Catalog source schema is taken from the upstream model-registry source code at the commit named in
the ConfigMap comment. The cards carry metadata and a README only; no image, template or credential.

**Monitoring.** `enableUserWorkload: true` turns on monitoring for user-defined projects [10]. `retention` and
`retentionSize` cap the time-series databases below the PVC size, and `volumeClaimTemplate` requests `gp3-csi` volumes
[8][9]. The storage class is AWS-specific; `deploy.sh` checks that `gp3-csi` uses the `ebs.csi.aws.com` provisioner.

**Secrets.** None in Git. The registry database Secret is generated by the registry operator. Validators use the caller's
own token in memory only.

**Cluster-specific values.** `repoURL` and `targetRevision` are set by `deploy.sh` from `.env` (`GIT_REPO_URL`) and the
published commit SHA.

## Validation

`validate.sh` requires the Application `Synced` and `Healthy` with a `Succeeded` operation at its 40-character revision;
DSC `Ready` and `KserveReady`; `kserve` and `modelregistry` `Managed`; the `default-kserve` component `Ready`,
`KServeReady` and `ModelControllerReady` with current owned Deployments; and both Prometheus resources using `gp3-csi` at
40 Gi / 20 Gi with Bound PVCs. `validate-model-discovery.sh` checks the `ModelRegistry` `Available` and
`KubeRBACProxyAvailable` conditions, its API and PostgreSQL Deployments and Bound PVC, an authenticated list call on the
registry route, the catalog component `Ready`, the dashboard flags, and that the Model Catalog and Agent Catalog APIs return
items, including exactly one `opencode` and one `hermes` card from `governed-coding-agents`.

By hand:

```bash
oc get application 030-private-model-serving -n openshift-gitops \
  -o jsonpath='{.status.sync.status} {.status.health.status} {.status.sync.revision}{"\n"}'
oc get datasciencecluster default-dsc \
  -o jsonpath='{.spec.components.kserve.managementState} {.spec.components.modelregistry.managementState}{"\n"}'
```

## Alignment with official guidance

| Topic | Official guidance (link) | This repository | Status |
|---|---|---|---|
| Enable KServe | DSC component `managementState: Managed` [6][7] | Hook Job sets `Managed` | Aligned |
| Enable Model Registry and Catalog | `modelregistry` `Managed`, `registriesNamespace: rhoai-model-registries` [2] | Same values | Aligned |
| Configuration through GitOps | Component fields belong in the DSC [6] | Set by hook Jobs into fields Stage 010 delegates, not in a DSC manifest | Deviation (justified: one shared DSC owned by Stage 010; later stages enable their own components) |
| Registry database | Default database is for evaluation, development and testing only [1] | `generateDeployment: true`, `sslMode: disable` | Deviation (justified: demo; no HA, backup or TLS to the database) |
| Registry access | Grant groups through the registry permissions (operator-created role) [1] | RoleBindings for `rhods-admins` and `rhoai-developers` to `registry-user-demo-registry` | Aligned |
| Dashboard flags | `dashboardConfig` options and defaults [4] | Registry/Catalog shown; Agent Catalog, tool calling, MCP catalog and registry enabled | Aligned (preview features: Developer/Technology Preview) |
| Agent Catalog | Developer Preview in 3.5 [5]; no documented source format [3] | Custom source from upstream schema | Deviation (justified: Developer Preview; schema pinned to an upstream commit) |
| Prometheus persistence | Persistent storage highly recommended for production [8][9] | 40 Gi / 20 Gi `gp3-csi` PVCs | Aligned |
| Retention | `retention` and `retentionSize` under the Prometheus key [8][9] | 7 d with 8 GB / 5 GB caps | Aligned |
| User-workload monitoring | `enableUserWorkload: true` in `cluster-monitoring-config` [10] | Set | Aligned |
| Ownership of cluster monitoring config | One owner per object | Owned here, not by a Stage 010 observability component | Gap (cluster-wide platform configuration lives in a serving component; see findings) |
| Argo CD sync options | Server-Side Diff by Application annotation [13]; `Prune=false`/`Delete=false` for retained objects [12] | Annotation present; registry objects retained | Aligned |

## References

1. Managing model registries, Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_model_registries/index
2. Enable the model registry component, Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/managing_model_registries/enabling-the-model-registry-component_managing-model-registries
3. Manage and govern model catalog sources, Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/manage_and_govern_model_catalog_sources/index
4. Customizing the dashboard (dashboard feature configuration options), Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/managing_resources/customizing-the-dashboard
5. Release notes, Developer Preview features, Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/developer-preview-features_relnotes
6. Installing and deploying OpenShift AI (installing components by using the CLI), Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/installing_and_uninstalling_openshift_ai_self-managed/installing-and-deploying-openshift-ai_install
7. Configuring your model-serving platform, Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/configuring_your_model-serving_platform/index
8. Storing and recording data for core platform monitoring, Monitoring stack for Red Hat OpenShift 4.22. https://docs.redhat.com/en/documentation/monitoring_stack_for_red_hat_openshift/4.22/html/configuring_core_platform_monitoring/storing-and-recording-data
9. Storing and recording data for user workload monitoring, Monitoring stack for Red Hat OpenShift 4.22. https://docs.redhat.com/en/documentation/monitoring_stack_for_red_hat_openshift/4.22/html/configuring_user_workload_monitoring/storing-and-recording-data-uwm
10. Preparing to configure the user workload monitoring stack (enabling monitoring for user-defined projects), Monitoring stack for Red Hat OpenShift 4.22. https://docs.redhat.com/en/documentation/monitoring_stack_for_red_hat_openshift/4.22/html/configuring_user_workload_monitoring/preparing-to-configure-the-monitoring-stack-uwm
11. Sync phases and waves, Argo CD (upstream). https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/
12. Sync options, Argo CD (upstream). https://argo-cd.readthedocs.io/en/stable/user-guide/sync-options/
13. Diff strategies (Server-Side Diff), Argo CD (upstream). https://argo-cd.readthedocs.io/en/stable/user-guide/diff-strategies/
