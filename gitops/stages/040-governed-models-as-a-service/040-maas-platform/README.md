# MaaS platform enablement (`040-maas-platform`)

This Application turns Models-as-a-Service (MaaS) on in OpenShift AI. It enables the AIGateway, MaaS and OGX (GenAI Studio) components and the related dashboard features, configures attributed MaaS usage telemetry, admits the native MaaS namespaces to the Gateway, and grants `rhods-admins` administration of the MaaS tenant namespace. It also ships two custom cost dashboards on the OpenShift AI Observability page (the serving-health alerts moved to `040-local-models`, the GPU utilization ServiceMonitor to `020-nvidia-gpu-operator`). Platform administrators and every later MaaS consumer (models, access policies, GenAI Studio, Stage 050 and 070) depend on it.

| | |
|---|---|
| Argo CD Application | `040-maas-platform` ([manifest](../../../applications/040-maas-platform.yaml)) |
| Deployed by | `stages/040-governed-models-as-a-service/deploy.sh` (deploy-order 4). `deploy.sh` re-runs the Sync hooks of this component once if `genAiTracing` is still not `true` after the stage is reconciled |
| Validated by | `stages/040-governed-models-as-a-service/validate.sh` → `stages/040-governed-models-as-a-service/validate.sh` ("Current native KServe/AIGateway/OGX components and feature flags"; namespace admission labels); `preflight.sh` (exact RBAC of the namespace-label helper; Stage 010 field delegation) |
| Sync | Automated, `prune: true`, `selfHeal: true`; `CreateNamespace`, `SkipDryRunOnMissingResource`, `ServerSideDiff`, `RespectIgnoreDifferences`; compare-option `ServerSideDiff=true`; no `ignoreDifferences` |
| Depends on | `010-rhoai-platform` (DataScienceCluster `default-dsc` and `odh-dashboard-config`, with `/spec/components/aigateway`, `/spec/components/ogx` and the dashboard fields delegated); `040-maas-database` (namespace `models-as-a-service`, database); `040-gateway-governance` (Gateway and Kuadrant) |
| Used by | `040-local-models`, `040-external-models`, `040-model-access`, `040-genai-studio`; Stage 050 and 070 MaaS consumers; platform administrators (Observability page) |

## Why

The MaaS guide enables MaaS through the DataScienceCluster: `spec.components.aigateway.managementState: Managed` and `spec.components.aigateway.modelsAsAService.managementState: Managed`. In 3.5 this replaces the deprecated `kserve.modelsAsService` path [1]. The vLLM-on-MaaS dashboard feature requires `spec.dashboardConfig.vLLMDeploymentOnMaaS: true` [1]. Usage telemetry and its attribution fields are set on the tenant configuration (section 1.18.3) [1].

The DataScienceCluster and `OdhDashboardConfig` belong to `010-rhoai-platform`. Stage 010 delegates the fields Stage 040 needs through `ignoreDifferences`, and this component's Sync-hook Job sets them. That keeps one owner per object, as the repository's component rules require, while each stage owns its own feature switches. Native controllers create the `MaaSTenantConfig` (`default-tenant`). The Job sets only its telemetry fields and leaves ownership with the controller.

The cost dashboards ship here because MaaS showback is a platform function that platform administrators use, not model configuration.

## What

### `010-access/`

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| RoleBinding | `rhods-admins-maas-admin` | `models-as-a-service` | ClusterRole `admin` for Group `rhods-admins` in the MaaS tenant namespace (wave 3) |

### `jobs/`: MaaS enablement and namespace admission

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| ServiceAccount | `prepare-maas-route-access` | `redhat-ods-applications` | Namespace-label Job identity (wave 8) |
| ClusterRole, ClusterRoleBinding | `prepare-maas-route-access` | (cluster) | `get`/`patch` on Namespaces `redhat-ods-applications` and `redhat-ai-gateway-infra` only (wave 8) |
| Job | `prepare-maas-route-access` | `redhat-ods-applications` | `Sync` hook, wave 15 (after `job-enable-dsc-maas` creates the AIGateway namespace; AIGateway readiness does not depend on route admission), `BeforeHookCreation,HookSucceeded`. Waits for both namespaces and adds `maas-gateway-access=true` (UID and resourceVersion guarded merge patch) |
| ServiceAccount | `job-enable-dsc-maas` | `redhat-ods-applications` | Enablement Job identity (wave 13) |
| ClusterRole, ClusterRoleBinding | `job-enable-dsc-maas` | (cluster) | `get`/`patch` DataScienceCluster `default-dsc`; `get` AIGateway `default-aigateway`, OGX `default-ogx`, MaaS Config `default`, Ingress config `cluster` (wave 13) |
| Role, RoleBinding | `job-enable-dsc-maas` | `redhat-ods-applications` | `get`/`patch` OdhDashboardConfig `odh-dashboard-config` (wave 13) |
| Role, RoleBinding | `job-enable-maas-telemetry` | `models-as-a-service` | `get`/`patch` MaaSTenantConfig `default-tenant` (wave 13) |
| Job | `job-enable-dsc-maas` | `redhat-ods-applications` | `Sync` hook, wave 14, `BeforeHookCreation,HookSucceeded`, 20 min deadline. See How |

### `observability/`: custom dashboards

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| PersesDashboard | `dashboard-5-cost-per-token-admin` | `redhat-ods-monitoring` | "Cost per token" tab: vLLM token counters per model and MaaS `authorized_hits_total`/`authorized_calls_total` per user and subscription, priced with editable variables |
| PersesDashboard | `dashboard-6-tokenomics-break-even-admin` | `redhat-ods-monitoring` | "Tokenomics · break-even (live)" tab: worker cost of serving private models (showback offer catalog) against token throughput and a reference external model's list price |

The two dashboard YAML files are generated by [`stages/040-governed-models-as-a-service/showback/generate-dashboards.sh --write`](../../../../stages/040-governed-models-as-a-service/showback/README.md); edit the generator, not the YAML (`--check` compares them). Neither dashboard sets a sync wave.

### `monitoring/` (moved)

Moved on 2026-10-14 to `040-local-models` (`monitoring/`): the vLLM serving rules and their RoleBinding target `internal-models`.

### Objects not in Git

| Object | Owner |
|---|---|
| `default-dsc` component fields `aigateway`, `ogx` | Set by `job-enable-dsc-maas`; object owned by `010-rhoai-platform` |
| `odh-dashboard-config` fields `dashboardConfig.*` and `genAiStudioConfig` | Set by `job-enable-dsc-maas`; object owned by `010-rhoai-platform` |
| `MaaSTenantConfig default-tenant` (`spec.telemetry` set by the Job) | MaaS controller (owner reference to Config `default`) |
| Namespace `redhat-ai-gateway-infra`, `maas-api` Deployment, AIGateway/OGX operands | OpenShift AI operator |
| Label `maas-gateway-access=true` on `redhat-ods-applications`, `redhat-ai-gateway-infra` | `prepare-maas-route-access` Job |

## How

- **Enablement Job (`job-enable-dsc-maas`).** In order, it:
  1. Merge-patches `default-dsc` to set `aigateway` Managed, `modelsAsAService` Managed, `batchGateway` Removed and `ogx` Managed, and reads the two states back.
  2. Merge-patches `odh-dashboard-config` to set `genAiStudio`, `genAiTracing`, `modelAsService`, `vLLMDeploymentOnMaaS`, `externalModels`, `llmdTemplates`, `guardrails`, `agentConfigManagement`, `promptManagement` and `aiAssetCustomEndpoints` to `true`, and reads them back.
  3. Sets `genAiStudioConfig.aiAssetCustomEndpoints` to `externalProviders: false` with `clusterDomains: [<cluster-domain>]`, read from `ingresses.config.openshift.io/cluster`. Playground custom endpoints may then target the MaaS hostname but not third-party providers.
  4. Waits up to about 8 minutes each for `default-aigateway` and `default-ogx` to report a current generation and `Ready`.
  5. Checks that `default-tenant` has exactly one owner, MaaS Config `default`, and no Argo CD tracking id. It then patches `spec.telemetry` with a UID and resourceVersion guard.
- **Telemetry choices.** The Job sets `enabled: true`, `captureOrganization: true`, `captureUser: true`, `captureGroup: false` and `captureModelUsage: true`. The guide's default for `captureUser` is `false`, for privacy and to keep Prometheus small with many users [1]. The demo turns it on so the Usage dashboard, the Cost per token tab and the Usage page's CSV export can attribute tokens to a user.
- **Field delegation.** `preflight.sh` refuses to deploy unless `010-rhoai-platform` delegates `/spec/components/aigateway`, `/spec/components/ogx` and the dashboard fields. Stage 010's Application also delegates `/spec/dashboardConfig/aiAssetCustomEndpoints` and `/spec/genAiStudioConfig`, but the preflight does not check those two. Because the Job runs only when a sync runs it [3], `deploy.sh` forces a hook sync of this component if `genAiTracing` is not `true`.
- **Namespace admission.** The Gateway in `040-gateway-governance` admits route namespaces only when they carry `maas-gateway-access=true`. `redhat-ods-applications` and `redhat-ai-gateway-infra` are operator-owned, so the `prepare-maas-route-access` Job adds only that label.
- **GPU utilization ServiceMonitor.** Moved to `020-nvidia-gpu-operator` (`rhoai-monitoring/`) on 2026-10-14.
- **Custom dashboards.** The guide says the built-in dashboards show a curated subset of metrics and points to Prometheus queries or external tools for anything else [2]. The two custom PersesDashboards follow the `dashboard-*` naming in `redhat-ods-monitoring` that, according to the generator's header comment, the Observability page renders as tabs (not described in the guide; the UI was not checked for this README). Prices and GPU cost are dashboard variables, not invoices. The Tokenomics default GPU price (2.24 $/h) is labelled as an AWS g6e.2xlarge (one L40S). The default model now runs on g7e.2xlarge (RTX PRO 6000).
- **Serving alerts.** Moved to `040-local-models` (`monitoring/`) with their RoleBinding, next to the models they watch.
- **Secrets.** None. The Job reads no Secret.
- **Cluster-specific values.** The ingress domain written to `genAiStudioConfig` is read at runtime by the Job.

## Validation

`stages/040-governed-models-as-a-service/validate.sh` requires the following:

- `default-dsc` is current and `Ready`.
- `aigateway`, `ogx` and `kserve` are `Managed`, and each component CR is current, `Ready` and in phase `Ready`.
- `modelsAsAService` is `Managed`.
- Nine dashboard flags are `true`. `aiAssetCustomEndpoints` is not checked.
- `maas-gateway-access=true` is set on `models-as-a-service`, `internal-models`, `external-models`, `redhat-ai-gateway-infra` and `redhat-ods-applications`.

`preflight.sh` checks the namespace-label helper's exact ClusterRole and ClusterRoleBinding. Telemetry, dashboards, alerts and the ServiceMonitor have no automated check in this component's validation.

By hand:

```bash
oc get datasciencecluster default-dsc -o jsonpath='{.spec.components.aigateway}{"\n"}'
oc get maastenantconfigs default-tenant -n models-as-a-service -o jsonpath='{.spec.telemetry}{"\n"}'
```

## Alignment with official guidance

| Topic | Official guidance (link) | This repository | Status |
|---|---|---|---|
| Enable MaaS | `aigateway` and `aigateway.modelsAsAService` `Managed` in the DSC (section 1.6) [1] | Set by the Sync-hook Job on delegated Stage 010 fields | Aligned (by Job, because Stage 010 owns the DSC) |
| vLLM on MaaS (Technology Preview) | `dashboardConfig.vLLMDeploymentOnMaaS: true` [1] | Set by the Job | Aligned |
| User workload monitoring for usage metrics | Required. Without it the deployment is `Degraded` (section 1.2) [1] | Enabled by `030-private-model-serving` (`cluster-monitoring-config`), not this component | Aligned |
| Telemetry attribution | `captureUser` default `false` for privacy and cardinality; `captureGroup` default `false`; `captureOrganization` and `captureModelUsage` default `true` (section 1.18.3) [1] | `captureUser: true`, others at default | Deviation (justified: per-user showback is a demo goal; user identities appear in metrics) |
| Collect metrics from user workloads | Label the workload's pod template `monitoring.opendatahub.io/scrape=true`; do not label operator-managed workloads (section 12.3) [2] | Label on a demo-owned ServiceMonitor for the operator-managed DCGM exporter | Deviation (justified: avoids changing operator-managed pods; mitigates a recorded 3.5.1 product gap) |
| Custom dashboards | Built-in dashboards show a curated subset; use Prometheus or external tools for more (section 12.2.6) [2] | Two PersesDashboards rendered as Observability tabs | Deviation (justified: demo showback; not a documented extension point) |
| Monitoring access | Users who monitor metrics have `monitoring-rules-view` (section 2.6.1) [4] | RoleBinding in `internal-models` for `rhoai-developers` and `rhods-admins` | Aligned |
| Job RBAC scope | Least privilege (repository rule) | Every Job rule is limited by `resourceNames` | Aligned |

## References

1. Govern LLM access with Models-as-a-Service, sections 1.2, 1.6 "MaaS configuration" and 1.18.3 "Enable telemetry for Models-as-a-Service", Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/govern_llm_access_with_models-as-a-service/index
2. Managing OpenShift AI, "Managing observability", 12.2.6 "Metrics beyond the built-in dashboards" and 12.3 "Collect metrics from user workloads", Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/managing_openshift_ai/managing-observability_managing-rhoai
3. Sync waves and hooks, "Hook lifecycle and cleanup", Argo CD (upstream). https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/
4. Managing and monitoring models, 2.6.1 "Configure monitoring for the model serving platform" and 2.7.3.3 "vLLM metrics", Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_and_monitoring_models/index
