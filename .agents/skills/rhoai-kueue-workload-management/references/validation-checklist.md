# Validation Checklist

Use this checklist before approving Kueue workload-management changes.

## Source Review

- Product links use the active baseline in `docs/PLATFORM_BASELINE.md`.
- `Managed` Kueue is treated as deprecated embedded Kueue.
- `Unmanaged` is used for Red Hat build of Kueue Operator integration.
- Embedded Kueue and Red Hat build of Kueue Operator are not installed together.
- Namespace queue enforcement uses `kueue.openshift.io/managed=true`.
- Workloads use `kueue.x-k8s.io/queue-name` when queue enforcement applies.
- Full quota and queue schemas are sourced from Red Hat build of Kueue docs or
  active CRD verification.

## Integration Review

Run only after following the OpenShift safety guard in `AGENTS.md`:

```bash
oc get datasciencecluster default-dsc -n redhat-ods-operator -o yaml
oc get pods -n openshift-kueue-operator
oc get clusterqueues
oc get localqueues -A
```

Check:

- Red Hat build of Kueue Operator pods are running.
- `spec.components.kueue.managementState` is `Unmanaged`.
- default or custom queue names are intentional.
- default `ClusterQueue` exists when expected.
- relevant project namespaces have `kueue.openshift.io/managed=true`.

## Dashboard Review

Run only after following the OpenShift safety guard in `AGENTS.md`:

```bash
oc get odhdashboardconfig odh-dashboard-config -n redhat-ods-applications -o yaml
oc get ns <project-namespace> -o jsonpath='{.metadata.labels.kueue\.openshift\.io/managed}{"\n"}'
oc get localqueues -n <project-namespace>
```

Check:

- `spec.dashboardConfig.disableKueue` is `false` when users should select
  Kueue-enabled options in the dashboard.
- new dashboard-created projects are labeled for Kueue management.
- existing projects and `oc`-created projects are labeled manually when needed.
- a default `LocalQueue` exists for managed namespaces.

## Workload Review

For Kueue-managed namespaces, check queue labels on enforced workload types:

```bash
oc get notebooks -n <project-namespace> --show-labels
oc get inferenceservices -n <project-namespace> --show-labels
oc get rayclusters -n <project-namespace> --show-labels
oc get rayjobs -n <project-namespace> --show-labels
oc get pytorchjobs -n <project-namespace> --show-labels
```

Check:

- `InferenceService`, `Notebook`, `PyTorchJob`, `RayCluster`, and `RayJob`
  objects have `kueue.x-k8s.io/queue-name` when required.
- dashboard-created workloads use hardware profiles that specify a local queue.
- Kueue-enabled hardware profiles do not use node selectors or tolerations for
  placement.
- workbench local queues are associated with non-preemptive cluster queues.

## Migration Review

Before migrating from embedded Kueue:

- confirm `managementState` is `Managed`
- decide whether to preserve `kueue-manager-config`
- plan workload interruption or no-interruption tradeoffs
- set embedded Kueue to `Removed`
- verify `KueueReady` Status `False` with Reason `Removed`
- verify embedded Kueue deployments are gone
- install Red Hat build of Kueue Operator
- set `managementState` to `Unmanaged`
- label existing namespaces
- submit a test workload

## Troubleshooting Review

For webhook errors:

- verify Kueue pods are running
- review Kueue pod logs for webhook server startup

For default local queue errors:

- verify `LocalQueue` exists in the user's project
- define or fix the default local queue
- provide the correct queue name to the user

For wrong local queue errors:

- verify the queue exists in the same namespace as the workload
- verify the workload or cluster configuration spells the queue name correctly

For image-pull timeout failures:

- inspect pod events
- consider `OnFailure` restart policy for Kueue-managed resources
- verify `waitForPodsReady` support in the active `Kueue` CR before changing it

## GitOps Review

- Kueue Operator, `DataScienceCluster`, `OdhDashboardConfig`, namespace labels,
  quota resources, hardware profiles, and workloads are ordered explicitly.
- Auto-created `LocalQueue` and `ClusterQueue` resources are either accepted as
  bootstrap output or replaced by reviewed GitOps-managed resources.
- README and operations notes distinguish Kueue integration from full quota
  design.
- Demo claims about fairness, prioritization, or GPU utilization match the
  implemented queue configuration.

## Fail Conditions

- `managementState: Managed` is used for new work.
- Embedded Kueue and Red Hat build of Kueue Operator coexist.
- A namespace is labeled for Kueue but workloads lack the queue label.
- Dashboard Kueue is enabled before Kueue Operator and quotas are ready.
- Kueue-enabled hardware profiles use node selectors or tolerations for node
  placement.
- Full `ResourceFlavor`, `ClusterQueue`, `LocalQueue`, or `Kueue` CR fields
  are invented without official docs or CRD verification.
