# Official Doc Extraction

This extraction is derived from the official RHOAI 3.4 chapter captured in
`source-capture.md`.

## Purpose

Kueue lets OpenShift AI manage AI and machine learning workloads at scale using
quota management, resource allocation, and prioritized scheduling. In OpenShift
AI, Kueue can schedule:

- distributed training jobs: `RayJob`, `RayCluster`, `PyTorchJob`
- workbenches: `Notebook`
- model serving: `InferenceService`

Kueue validation and queue enforcement apply only to workloads in namespaces
with:

```text
kueue.openshift.io/managed=true
```

Benefits described by Red Hat:

- prevents resource conflicts and prioritizes workload processing
- manages quotas across teams and projects
- provides consistent scheduling across workload types
- improves GPU and specialized hardware utilization

## Embedded Kueue Deprecation

Starting with OpenShift AI 2.24, embedded Kueue for managing distributed
workloads is deprecated. Kueue is now provided through the Red Hat build of
Kueue Operator.

Rules:

- do not install embedded Kueue and Red Hat build of Kueue Operator on the same
  cluster
- OpenShift AI does not automatically migrate existing workloads
- cluster administrators must manually migrate from embedded Kueue to Red Hat
  build of Kueue Operator when needed

## DataScienceCluster Management States

Configure how OpenShift AI interacts with Kueue through
`DataScienceCluster.spec.components.kueue.managementState`.

| State | Meaning |
|-------|---------|
| `Unmanaged` | Supported state for using Kueue with OpenShift AI. RHOAI integrates with an existing Kueue installation managed by the Red Hat build of Kueue Operator. The Red Hat build of Kueue Operator must be installed and running. When enabled, the OpenShift AI Operator creates a default `Kueue` CR if one does not exist. |
| `Managed` | Deprecated embedded Kueue mode. Not compatible with the Red Hat build of Kueue Operator. Environments using this state must migrate to `Unmanaged`. |
| `Removed` | Disables Kueue in OpenShift AI. If previously `Managed`, RHOAI uninstalls embedded Kueue. If previously `Unmanaged`, RHOAI stops checking the external integration but does not uninstall the Red Hat build of Kueue Operator. Empty `managementState` also functions as `Removed`. |

## Queue Enforcement

Enable Kueue validation and queue enforcement for a project by labeling the
namespace:

```text
kueue.openshift.io/managed=true
```

The legacy `kueue-managed` label is supported for backward compatibility, but
`kueue.openshift.io/managed=true` is the recommended label.

When a project is enabled for Kueue management, the validating webhook requires
new or updated workloads to include:

```text
kueue.x-k8s.io/queue-name=<LocalQueue name>
```

The webhook enforces the queue label on:

- `InferenceService`
- `Notebook`
- `PyTorchJob`
- `RayCluster`
- `RayJob`

OpenShift AI creates a default cluster-scoped `ClusterQueue` if one does not
already exist and a namespace-scoped `LocalQueue` for the namespace if one does
not already exist. These default resources are created with
`opendatahub.io/managed=false`, so cluster administrators can change or delete
them after creation.

## Restrictions

When Kueue manages OpenShift AI workloads:

- namespaces must have `kueue.openshift.io/managed=true` for validation and
  queue enforcement
- dashboard-created workloads such as workbenches and model servers must use a
  hardware profile that specifies a local queue
- when a hardware profile specifies a local queue, OpenShift AI automatically
  applies the `kueue.x-k8s.io/queue-name` label to workloads that use it
- Kueue-enabled hardware profiles cannot contain node selectors or tolerations
  for node placement
- node placement should be handled through local queues associated with queues
  configured with appropriate resource flavors
- workbenches are not suspendable workloads and can only use a local queue
  associated with a non-preemptive cluster queue
- the default cluster queue that OpenShift AI creates is non-preemptive

## Workflow By Persona

Cluster administrator:

1. Install the Red Hat build of Kueue Operator.
2. Activate Kueue integration by setting `managementState` to `Unmanaged` in
   `DataScienceCluster`.
3. Configure quotas through Red Hat build of Kueue resources.
4. Enable Kueue in the dashboard by setting
   `OdhDashboardConfig.spec.dashboardConfig.disableKueue` to `false`.

OpenShift AI administrator:

1. Create Kueue-enabled hardware profiles.

ML engineer or data scientist:

1. For dashboard-created workloads, select a Kueue-enabled hardware profile.
2. For CLI or SDK workloads, add `kueue.x-k8s.io/queue-name` to the workload
   YAML and set it to the target `LocalQueue` name.

## Activating Kueue Integration

Prerequisites:

- cluster administrator privileges
- OpenShift 4.19 or later
- cert-manager Operator for Red Hat OpenShift installed and configured
- OpenShift CLI installed
- Red Hat build of Kueue Operator installed

Activate the integration by setting `managementState` to `Unmanaged` in the
`default-dsc` DataScienceCluster in the operator namespace. The default
operator namespace is `redhat-ods-operator`.

Default queue names:

```bash
oc patch datasciencecluster default-dsc --type='merge' \
  -p '{"spec":{"components":{"kueue":{"managementState":"Unmanaged"}}}}' \
  -n <operator-namespace>
```

Custom queue names:

```bash
oc patch datasciencecluster default-dsc --type='merge' \
  -p '{"spec":{"components":{"kueue":{"managementState":"Unmanaged","defaultClusterQueueName":"<example-cluster-queue>","defaultLocalQueueName":"<example-local-queue>"}}}}' \
  -n <operator-namespace>
```

Verification:

- Red Hat build of Kueue pods run in `openshift-kueue-operator`
- default `ClusterQueue` exists

## Dashboard Enablement

Enable Kueue in the dashboard so users can select Kueue-enabled options during
workload creation:

```text
OdhDashboardConfig.spec.dashboardConfig.disableKueue=false
```

When Kueue is enabled in the dashboard:

- new projects created from the dashboard are automatically enabled for Kueue
  management
- OpenShift AI labels those namespaces with
  `kueue.openshift.io/managed=true`
- OpenShift AI creates a default `LocalQueue` if one does not exist
- the `LocalQueue` is created with `opendatahub.io/managed=false`

Existing projects and projects created with `oc` must be labeled manually:

```bash
oc label namespace <project-namespace> kueue.openshift.io/managed=true --overwrite
```

Verification:

- namespace label returns `true`
- `LocalQueue` exists in the project namespace
- a test workload such as a `Notebook` includes the
  `kueue.x-k8s.io/queue-name` label

## Troubleshooting Signals

`failed to call webhook` for Kueue:

- likely cause: Kueue pod might not be running
- check Kueue pod and logs for webhook server startup

`Default Local Queue ... not found`:

- likely cause: no default local queue is defined and no local queue is
  specified in the cluster configuration
- check for `LocalQueue` in the user project, create one if needed, and provide
  queue details to the user

`local_queue provided does not exist`:

- likely cause: local queue name is wrong, default local queue is wrong, queue
  is missing, or queue is in another namespace
- check `LocalQueue` resources in the project and verify the user's namespace
  and queue name

Pod terminated before image pull:

- default Kueue wait for all workload pods to become provisioned and running is
  5 minutes
- if a large image is still pulling after that period, Kueue can fail the
  workload and terminate pods
- resolution options: add an `OnFailure` restart policy for Kueue-managed
  resources or configure `waitForPodsReady` in the `Kueue` CR installed in
  `openshift-kueue-operator`

## Migration From Embedded Kueue

Migration is required when
`DataScienceCluster.spec.components.kueue.managementState` is `Managed`.

Skip migration when the state is `Removed` or `Unmanaged`.

Migration workflow:

1. Optional: preserve `kueue-manager-config` by annotating it
   `opendatahub.io/managed=false`.
2. Set `spec.components.kueue.managementState` to `Removed` to uninstall
   embedded Kueue.
3. Verify `KueueReady` has Status `False` and Reason `Removed`.
4. Verify embedded Kueue deployments such as `kueue-controller-manager` are no
   longer present in the OpenShift AI applications namespace.
5. Install the Red Hat build of Kueue Operator.
6. Set `spec.components.kueue.managementState` to `Unmanaged`, optionally with
   custom queue names.
7. Label existing project namespaces with
   `kueue.openshift.io/managed=true`.
8. Verify Kueue is healthy and workloads continue to be processed.

## Unresolved Items

This chapter does not define:

- complete `ResourceFlavor`, `ClusterQueue`, or `LocalQueue` schemas
- quota design for this demo
- full hardware profile schema for local queue integration
- production migration sequencing for running workloads
- exact `Kueue` CR schema for `waitForPodsReady`

Use the Red Hat build of Kueue documentation, hardware profile docs, active CRD
schema, and repo GitOps policy before authoring those details.
