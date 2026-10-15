# Observability operators and trace roles (`010-observability-operators`)

This Application installs the three operators that the native OpenShift AI observability stack needs: the Cluster
Observability Operator (COO), the Red Hat build of OpenTelemetry and the Tempo Operator. It also grants the two trace
roles that make the RHOAI-generated Tempo tenant usable: write access for the RHOAI collector and read access for
RHOAI administrators. [`010-rhoai-platform`](../rhoai-platform/README.md) (DSCI `spec.monitoring`) and
[`010-console-observability`](../console-observability/README.md) (UIPlugin) consume these operators.

| | |
|---|---|
| Argo CD Application | `010-observability-operators` ([manifest](../../../applications/010-observability-operators.yaml)) |
| Deployed by | [`stages/010-openshift-ai-platform-foundation/deploy.sh`](../../../../stages/010-openshift-ai-platform-foundation/deploy.sh) (deploy-order 1) |
| Validated by | [`validate.sh`](../../../../stages/010-openshift-ai-platform-foundation/validate.sh) (three CSVs `Succeeded`; `check-operator-policy.py --verify`); [`validate-foundation-services.sh`](../../../../stages/010-openshift-ai-platform-foundation/validate-foundation-services.sh) (SubjectAccessReview for the writer role; trace written and read back) |
| Sync | Automated, prune and self-heal; `CreateNamespace`, `SkipDryRunOnMissingResource`, `RespectIgnoreDifferences`; Server-Side Diff via annotation |
| Depends on | OpenShift GitOps bootstrap and the `redhat-operators` catalog. The writer binding names a service account the RHOAI operator creates later; a binding to a missing subject is valid |
| Used by | `010-rhoai-platform` (monitoring stack), `010-console-observability` (UIPlugin CRD and Perses), any later stage that creates OpenTelemetry collectors or reads RHOAI traces |

## Why

The OpenShift AI observability stack requires the Cluster Observability Operator (Prometheus and Alertmanager), the
Tempo Operator (trace backend) and the Red Hat build of OpenTelemetry (collector) to be installed before it is
enabled [1]. RHOAI then generates the operands itself. These are OLM operators with independent lifecycles, but they
form one prerequisite set, so they share one Application with one subfolder per operator.

The trace roles are needed because the RHOAI-generated `TempoMonolithic` runs in `openshift` multitenancy mode with
tenant `redhat-ods-monitoring`. Tempo's gateway authorizes each request against a virtual resource: API group
`tempo.grafana.com`, resource = tenant name, resource name `traces`. It uses `get` for reads [2] and `create` for writes
(upstream) [3]. The comment in `tempo-traces-writer-role.yaml` records that the RHOAI collector RBAC does not include
the write grant.

## What

`cluster-observability-operator/`, `opentelemetry/`, `tempo/` (one operator each):

| Kind | Name | Namespace | Wave | Purpose |
|---|---|---|---|---|
| Namespace | `openshift-cluster-observability-operator` | (cluster) | -1 | Recommended COO namespace [4]; `openshift.io/cluster-monitoring: "true"` |
| OperatorGroup | `cluster-observability-operator` | same | 0 | AllNamespaces (no `targetNamespaces`) [4] |
| Subscription | `cluster-observability-operator` | same | 0 | Channel `stable`, `Automatic` |
| Namespace | `openshift-opentelemetry-operator` | (cluster) | -1 | `openshift.io/cluster-monitoring: "true"` [5] |
| OperatorGroup | `opentelemetry-product` | same | 0 | AllNamespaces |
| Subscription | `opentelemetry-product` | same | 0 | Channel `stable`, `Automatic` [5] |
| Namespace | `openshift-tempo-operator` | (cluster) | -1 | `openshift.io/cluster-monitoring: "true"` [6] |
| OperatorGroup | `tempo-product` | same | 0 | AllNamespaces [6] |
| Subscription | `tempo-product` | same | 0 | Channel `stable`, `Automatic` [6] |

`trace-roles/`:

| Kind | Name | Namespace | Wave | Purpose |
|---|---|---|---|---|
| ClusterRole | `rhoai-monitoring-traces-writer` | (cluster) | 0 | `create` on `tempo.grafana.com` / `redhat-ods-monitoring` / `traces` |
| ClusterRoleBinding | `rhoai-monitoring-traces-writer` | (cluster) | 0 | Grants it to ServiceAccount `redhat-ods-monitoring/data-science-collector-collector` |
| ClusterRole | `rhoai-monitoring-traces-reader` | (cluster) | 0 | `get` on the same tenant resource |
| ClusterRoleBinding | `rhoai-monitoring-traces-reader` | (cluster) | 0 | Grants it to Group `rhods-admins` only |

There are no hooks.

Not in Git (OLM and operator-owned): the CSVs (live `cluster-observability-operator.v1.5.3`,
`opentelemetry-operator.v0.158.0-3`, `tempo-operator.v0.22.0-3`) and CRDs. The operands the RHOAI operator generates
from the DSCI are also not here: `MonitoringStack`, `ThanosQuerier`, `TempoMonolithic`, `OpenTelemetryCollector` and
`PersesDatasource` objects in `redhat-ods-monitoring`. The collector ServiceAccount is created by the OpenTelemetry
Operator for the RHOAI-generated collector.

### `cluster-monitoring/`: platform and user-workload monitoring configuration

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| ConfigMap | `cluster-monitoring-config` | `openshift-monitoring` | `enableUserWorkload: true`; platform Prometheus 7 d / 8 GB retention on a 40 Gi `gp3-csi` PVC. |
| ConfigMap | `user-workload-monitoring-config` | `openshift-user-workload-monitoring` | User-workload Prometheus 7 d / 5 GB retention on a 20 Gi `gp3-csi` PVC. |

## How

- **Channels and approval.** All three use the rolling `stable` channel with `Automatic` approval, which is what the
  product guides show [4][5][6]. A rolling channel can cross minor versions. The repository bounds this in
  `scripts/platform/check-operator-policy.py`: it requires `stable` and the qualified minor versions with minimums COO
  `1.5.3`, OpenTelemetry `0.158.0-2` and Tempo `0.22.0-2`. A new minor version on the channel makes deployment fail
  closed until it is qualified. `docs/PLATFORM_BASELINE.md` maps OpenTelemetry 0.158 and Tempo 0.22 to product
  release 3.11.
- **Waves.** Namespaces are in wave -1. OperatorGroups, Subscriptions and roles are in wave 0. RHOAI reads these
  operators only when the DSCI is reconciled. `010-rhoai-platform` retries until the CRDs exist.
- **Trace RBAC scope.** The reader binding is limited to `rhods-admins`, not every authenticated user. The upstream
  query RBAC example binds `system:authenticated` [2]. Read and write are separate roles, so the collector cannot read
  and administrators cannot write.
- **Credentials.** None. Tempo uses PV storage (`traces.storage.backend: pv` in the DSCI), so there is no object
  storage secret.
- **Cluster-specific values.** None.

## Validation

`validate.sh` checks each Subscription's installed CSV for `Succeeded`. It also runs `check-operator-policy.py --verify`,
which checks the channel and minimum version. `validate-foundation-services.sh` sends a SubjectAccessReview as
`system:serviceaccount:redhat-ods-monitoring:data-science-collector-collector` for `create` on the tenant resource. It
then pushes a synthetic span through the collector and reads it back from Tempo by its trace ID.

```bash
oc get csv -n openshift-cluster-observability-operator; oc get csv -n openshift-tempo-operator; oc get csv -n openshift-opentelemetry-operator
oc get clusterrolebinding rhoai-monitoring-traces-writer rhoai-monitoring-traces-reader -o wide
```

## Alignment with official guidance

| Topic | Official guidance (link) | This repository | Status |
|---|---|---|---|
| Prerequisite operators | COO, Tempo and OpenTelemetry installed before enabling RHOAI observability [1] | All three, in the same batch as the platform | Aligned |
| COO install | Namespace `openshift-cluster-observability-operator`, all namespaces, `stable`, Automatic [4]; 1.5.3 released [7] | Same; live 1.5.3 | Aligned |
| OpenTelemetry install | Namespace with the cluster-monitoring label, OperatorGroup with only `upgradeStrategy`, Subscription `opentelemetry-product` `stable` Automatic [5] | Same, except the OperatorGroup name is `opentelemetry-product` instead of `openshift-opentelemetry-operator` | Aligned (name only) |
| Tempo install | Namespace with the cluster-monitoring label, OperatorGroup with no targets, `tempo-product` `stable` Automatic [6] | Same | Aligned |
| Trace read RBAC | ClusterRole `get` on `tempo.grafana.com` tenant `traces` [2] | Reader role bound to `rhods-admins` | Aligned (narrower subject) |
| Trace write RBAC | Not in the Red Hat 3.11 docs; upstream shows `create` on the tenant `traces` [3] | Writer role bound to the RHOAI collector service account | Deviation (justified: fills a gap in the generated RHOAI collector RBAC; upstream-backed) |
| Version pinning | Rolling `stable` channel in the guides | Rolling channel with Automatic approval; the minor/minimum check runs at deploy and validate time only, so OLM may update unattended between runs (accepted for the demo) | Aligned |

## References

1. Manage observability, Enable the observability stack (prerequisites). Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/managing_openshift_ai/managing-observability_managing-rhoai
2. Configuring distributed tracing, Configuring query RBAC. Red Hat OpenShift distributed tracing platform 3.11. https://docs.redhat.com/en/documentation/red_hat_openshift_distributed_tracing_platform/3.11/html/configuring_distributed_tracing/distr-tracing-tempo-configuring#distr-tracing-tempo-configuring-query-rbac_distr-tracing-tempo-configuring
3. Tempo Operator, Multitenancy: RBAC for writing data (upstream). Grafana Tempo documentation. https://grafana.com/docs/tempo/latest/setup/operator/multitenancy/
4. Installing Red Hat OpenShift Cluster Observability Operator, Installing the Cluster Observability Operator in the web console. Cluster Observability Operator 1-latest (no 1.5-specific page is published). https://docs.redhat.com/en/documentation/red_hat_openshift_cluster_observability_operator/1-latest/html-single/installing_red_hat_openshift_cluster_observability_operator/index
5. Installing Red Hat build of OpenTelemetry (CLI). Red Hat build of OpenTelemetry 3.11. https://docs.redhat.com/en/documentation/red_hat_build_of_opentelemetry/3.11/html/installing_red_hat_build_of_opentelemetry/install-otel
6. Installing distributed tracing, Tempo Operator (CLI). Red Hat OpenShift distributed tracing platform 3.11. https://docs.redhat.com/en/documentation/red_hat_openshift_distributed_tracing_platform/3.11/html/installing_distributed_tracing/distr-tracing-tempo-installing
7. Cluster Observability Operator release notes (1.5.3). Cluster Observability Operator 1-latest. https://docs.redhat.com/en/documentation/red_hat_openshift_cluster_observability_operator/1-latest/html/red_hat_openshift_cluster_observability_operator_release_notes
