# Red Hat build of Kueue (`020-kueue`)

This Application installs the Red Hat build of Kueue Operator and switches the OpenShift AI Kueue integration to
`Unmanaged`, the mode in which OpenShift AI uses that operator. Kueue then admits workloads against the quotas
that `020-gpu-quotas` defines. OpenShift AI hardware profiles, workbenches and model servers in Stages 030 to 050
consume it.

| | |
|---|---|
| Argo CD Application | `020-kueue` ([manifest](../../../argocd/app-of-apps/020-gpu-infrastructure-private-ai/kueue.yaml)) |
| Deployed by | [`stages/020-gpu-infrastructure-private-ai/deploy.sh`](../../../../stages/020-gpu-infrastructure-private-ai/deploy.sh) (deploy-order 2) |
| Validated by | [`stages/020-gpu-infrastructure-private-ai/validate.sh`](../../../../stages/020-gpu-infrastructure-private-ai/validate.sh) (operator policy, `kueue-operator current CSV Succeeded`, `Kueue delegated Unmanaged with autoCreateQueues=false`, `Native Kueue Available with fresh owned controller`) |
| Sync | Automated, prune and self-heal; `SkipDryRunOnMissingResource`, `RespectIgnoreDifferences`; Server-Side Diff by compare-options annotation; retry 10, 5s to 3m |
| Depends on | Stage 010 `DataScienceCluster` `default-dsc`, which must delegate `/spec/components/kueue` (checked by `deploy.sh`); cert-manager Operator 1.20 (checked by `deploy.sh`); namespace `redhat-ods-applications` (Stage 010) |
| Used by | `020-gpu-quotas` (Kueue CRDs and controller); Stage 010 `demo-sandbox` namespace label `kueue.openshift.io/managed`; Stage 040/050 LocalQueues and model servers |

## Why

OpenShift AI 3.5 manages workloads with the Red Hat build of Kueue. The `Unmanaged` Kueue management state
requires that operator to be installed and running; the older `Managed` state is deprecated and incompatible with
it [1]. When `Unmanaged` is set, the OpenShift AI Operator creates the default `Kueue` custom resource if none
exists [1]. The Red Hat build of Kueue needs the cert-manager Operator and runs in `openshift-kueue-operator` [2].

The DSC field is changed by a Sync hook Job instead of a second `DataScienceCluster` manifest. Stage 010 owns
`default-dsc` and lists `/spec/components/kueue` in its `ignoreDifferences`, so Stage 020 can set that one subtree
without two Applications owning the same object.

## What

Operator installation:

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| Namespace | `openshift-kueue-operator` | cluster-scoped | Operator namespace, label `openshift.io/cluster-monitoring: "true"` |
| OperatorGroup | `openshift-kueue-operator` | `openshift-kueue-operator` | No `targetNamespaces` (all namespaces), `upgradeStrategy: Default` |
| Subscription | `kueue-operator` | `openshift-kueue-operator` | Channel `stable-v1.4`, `redhat-operators`, Automatic approval (sync-wave 1) |

DSC enablement (`dsc-enablement/`):

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| ServiceAccount | `job-enable-dsc-kueue` | `redhat-ods-applications` | Identity of the hook Job (sync-wave 1) |
| ClusterRole | `job-enable-dsc-kueue` | cluster-scoped | `get`/`patch` only `datascienceclusters/default-dsc`; `get` only CRD `kueues.kueue.openshift.io` (sync-wave 1) |
| ClusterRoleBinding | `job-enable-dsc-kueue` | cluster-scoped | Binds the ClusterRole to the ServiceAccount (sync-wave 1) |
| Role | `job-enable-dsc-kueue` | `openshift-kueue-operator` | `get` Subscription `kueue-operator` and CSVs (sync-wave 1) |
| RoleBinding | `job-enable-dsc-kueue` | `openshift-kueue-operator` | Binds the Role to the ServiceAccount (sync-wave 1) |
| Job | `job-enable-dsc-kueue` | `redhat-ods-applications` | Argo CD `Sync` hook, sync-wave 2, delete policy `BeforeHookCreation,HookSucceeded` |

Objects not in Git:

| Kind | Name | Owner |
|---|---|---|
| Kueue | `cluster` | Created by the OpenShift AI Operator when the DSC says `Unmanaged` (annotation `platform.opendatahub.io/instance.name: default-kueue`) |
| Deployment | `kueue-controller-manager` | Red Hat build of Kueue Operator, owned by the `Kueue` CR |
| CSV, CRDs (`kueue.x-k8s.io`, `kueue.openshift.io`) | | OLM |
| Subscription `openshift-cert-manager-operator` | namespace `cert-manager-operator` | OLM dependency resolution; not tracked by any Application |

## How

- **Installation.** Channel `stable-v1.4`, Automatic approval, no `startingCSV`.
  `scripts/platform/check-operator-policy.py` requires the 1.4 release family, at least `1.4.2`. Installed on this
  cluster: `kueue-operator.v1.4.3`.
- **cert-manager.** The component does not declare cert-manager. `deploy.sh` refuses to continue unless a
  `cert-manager-operator.v1.20.*` CSV is `Succeeded`; the `Kueue` status reports `CertManagerAvailable`.
- **Hook Job.** A `Sync` hook runs with the manifests of its wave, and its delete policy removes it after
  success and before the next run [3]. The Job waits up to 270 s for the Subscription's `installedCSV` to be `Succeeded` and the
  `kueues.kueue.openshift.io` CRD to be `Established`, then up to 180 s for `default-dsc`. It then merge-patches
  `spec.components.kueue` to `managementState: Unmanaged` and `autoCreateQueues: false`, and reads both back.
  `backoffLimit: 1`, `activeDeadlineSeconds: 600`. The image is the OpenShift CLI (`ose-cli`) pinned by digest.
  The Job follows `status.installedCSV` because Automatic approval changes the CSV name.
- **`autoCreateQueues: false`.** OpenShift AI then does not create a default ClusterQueue and LocalQueue per
  managed namespace. This is the documented choice for strict quota control; all queues come from
  `020-gpu-quotas` and the consuming stages [1].
- **Kueue CR.** Not declared here: OpenShift AI creates it [1]. On this cluster it is named `cluster` with
  frameworks Deployment, Pod, PyTorchJob, RayCluster, RayJob, SparkApplication, StatefulSet and TrainJob.
- **ignoreDifferences / delegated fields.** None on this Application. Stage 010 delegates
  `default-dsc /spec/components/kueue` to this hook.
- **Secrets.** None.
- **Cluster-specific values.** None.

## Validation

`validate.sh` checks: Subscription Automatic and current CSV `Succeeded`; `default-dsc` has kueue
`Unmanaged`, `autoCreateQueues` false, is `Ready` and current; exactly one `Kueue` CR is `Available` and
`CertManagerAvailable`, not `Degraded` or `Progressing`, with a fully ready `kueue-controller-manager` it owns.

```bash
oc get datasciencecluster default-dsc -o jsonpath='{.spec.components.kueue}{"\n"}'
oc get kueue cluster -o jsonpath='{range .status.conditions[*]}{.type}={.status} {end}{"\n"}'
```

## Alignment with official guidance

| Topic | Official guidance (link) | This repository | Status |
|---|---|---|---|
| Kueue provider | Install the Red Hat build of Kueue Operator; `Managed` is deprecated [1] | Operator installed; DSC `Unmanaged` | Aligned |
| Operator namespace and monitoring | `openshift-kueue-operator` with cluster monitoring enabled [2] | Same, label `openshift.io/cluster-monitoring: "true"` | Aligned |
| cert-manager prerequisite | cert-manager Operator installed and configured [1][2] | Verified by `deploy.sh`, not declared | Aligned |
| `Kueue` CR | Named `cluster` [2]; OpenShift AI creates a default one in `Unmanaged` mode [1] | Left to OpenShift AI | Aligned |
| Queue creation mode | `autoCreateQueues: false` for strict quota control in multitenant GPU environments [1] | `false` | Aligned |
| DSC change method | Set `managementState: Unmanaged` on `default-dsc` [1] | Sync hook Job with scoped RBAC, because Stage 010 owns the DSC | Deviation (justified: one owner per object; the field is delegated) |
| Dashboard Kueue switch | Set `disableKueue: false` in `OdhDashboardConfig` [1] | Done by Stage 010 (`odhdashboardconfig.yaml`), not here | Aligned |
| Approval | Operator from OperatorHub [2] | Automatic within `stable-v1.4` | Aligned |

## References

1. Managing workloads with Kueue, Managing OpenShift AI, Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/managing_openshift_ai/managing-workloads-with-kueue
2. Red Hat build of Kueue, AI workloads, OpenShift Container Platform 4.22. https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/ai_workloads/red-hat-build-of-kueue
3. Sync phases and waves, Argo CD (stable) (upstream). https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/
