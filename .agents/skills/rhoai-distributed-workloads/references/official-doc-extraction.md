# Official Doc Extraction

This extraction is derived from the official RHOAI 3.4 chapter captured in
`source-capture.md`.

## Prerequisites

Before installing distributed workloads components:

- User is logged in to OpenShift with the `cluster-admin` role and can access
  the data science cluster.
- Red Hat OpenShift AI is installed.
- Red Hat build of Kueue Operator is installed on the OpenShift cluster.
- cert-manager Operator is installed.
- Sufficient resources are available. The chapter calls out 1.6 vCPU and 2 GiB
  memory in addition to minimum OpenShift AI resources for distributed workload
  infrastructure.
- For GPU use, GPU support is enabled in OpenShift AI.
- For NVIDIA GPU use, follow NVIDIA GPU enablement docs.
- For AMD GPU use, follow AMD GPU integration docs.

Red Hat supports accelerators within the same cluster only.

Starting with RHOAI 2.19, Red Hat supports RDMA for NVIDIA GPUs only, allowing
NVIDIA GPU communication through NVIDIA GPUDirect RDMA over Ethernet or
InfiniBand.

## CA Bundle Behavior

If self-signed certificates are used and added to a central CA bundle, no
additional distributed-workloads configuration is required. The central bundles
are automatically available in workload pods at:

| Bundle | Mount paths |
|--------|-------------|
| Cluster-wide CA bundle | `/etc/pki/tls/certs/odh-trusted-ca-bundle.crt`, `/etc/ssl/certs/odh-trusted-ca-bundle.crt` |
| Custom CA bundle | `/etc/pki/tls/certs/odh-ca-bundle.crt`, `/etc/ssl/certs/odh-ca-bundle.crt` |

## DataScienceCluster Component States

Set component `managementState` values in `spec.components` based on the launch
surface:

| Component | Pipelines only | Workbenches only | Pipelines and workbenches |
|-----------|----------------|------------------|---------------------------|
| `dashboard` | `Managed` | `Managed` | `Managed` |
| `aipipelines` | `Managed` | `Removed` | `Managed` |
| `kueue` | `Unmanaged` | `Unmanaged` | `Unmanaged` |
| `ray` | `Managed` | `Managed` | `Managed` |
| `trainingoperator` | `Managed` | `Managed` | `Managed` |
| `workbenches` | `Removed` | `Managed` | `Managed` |

Important behavior:

- `kueue` must be `Unmanaged` so the Red Hat build of Kueue Operator manages
  Kueue.
- `ray` enables the Ray framework for model tuning.
- `trainingoperator` enables Kubeflow Training Operator model tuning.
- Components with `Managed` state become ready after the Operator reconciles
  them.

## Verification Signals

Verify pods or deployments for:

- `kubeflow-training-operator` in `redhat-ods-applications`.
- `kuberay-operator` in `redhat-ods-applications`.
- `kueue-controller-manager` in `openshift-kueue-operator`.
- `openshift-kueue-operator` in `openshift-kueue-operator`.

When the pods are `Running`, they are ready to use.

## Next Step

After installation, configure distributed workloads through the official
managing distributed workloads documentation. This includes queue and workload
policy that is outside this install skill.

## Unresolved Items

This chapter does not define:

- Red Hat build of Kueue Operator Subscription details.
- cert-manager Subscription details.
- Kueue ClusterQueue, LocalQueue, ResourceFlavor, or admission policy.
- RayCluster, TrainingJob, or KFP workload examples.
- GPU Operator installation details.

Use the relevant official component documentation before implementing those
objects.
