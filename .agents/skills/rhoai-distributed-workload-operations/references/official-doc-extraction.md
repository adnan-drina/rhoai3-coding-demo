# Official Doc Extraction

Use this reference when authoring or reviewing distributed workload quota,
RDMA, and troubleshooting content.

## Component Purpose

Distributed workloads such as `PyTorchJob`, `RayJob`, and `RayCluster` are
created and managed by their workload operators. Kueue provides queueing and
admission control so those workloads run only when cluster-wide quotas allow
them.

The official chapter covers administrator operations after the distributed
workload components and Kueue integration are available:

- Kueue quota resources for sharing capacity across projects
- example ResourceFlavor and ClusterQueue patterns
- RDMA setup for NVIDIA GPUDirect RDMA
- Ray and Kueue administrator troubleshooting signals

## Prerequisites

Before creating distributed workload quota resources, confirm:

- cluster-admin access
- `oc` CLI availability
- Red Hat build of Kueue Operator installed and activated
- required distributed workload components installed
- a project with a running workbench image that includes CodeFlare SDK, such
  as the Standard Data Science workbench image
- at least 1.6 vCPU and 2 GiB memory for the distributed workload
  infrastructure beyond the base OpenShift AI footprint
- physical resources available in the cluster
- GPU support enabled in OpenShift AI if GPU-backed distributed workloads are
  requested

OpenShift AI 3.4 documents NVIDIA and AMD GPU accelerators for distributed
workloads. This repo defaults to NVIDIA only unless the user asks for AMD.

## Quota Resource Workflow

Use Kueue resources for quota management:

1. Verify or create a `ResourceFlavor`.
2. Verify or create a `ClusterQueue`.
3. Verify or create a project `LocalQueue` that points to the intended
   `ClusterQueue`.
4. Check `LocalQueue` status in the project namespace.

If Kueue is enabled in the OpenShift AI dashboard, dashboard-created projects
can already have a default `LocalQueue`. Review or modify the existing queue
before creating a duplicate.

## Kueue Resource Shapes

The official chapter uses these API objects:

| Kind | API version | Scope | Notes |
|------|-------------|-------|-------|
| `ResourceFlavor` | `kueue.x-k8s.io/v1beta1` | cluster | Describes the flavor applied to requested resources; examples may use node labels and tolerations. |
| `ClusterQueue` | `kueue.x-k8s.io/v1beta1` | cluster | Defines namespace selection, covered resources, flavors, and nominal quotas. |
| `LocalQueue` | `kueue.x-k8s.io/v1beta1` | namespace | Points a project namespace to a `ClusterQueue`. |

For NVIDIA queues, include `nvidia.com/gpu` in `coveredResources` and in the
flavor `resources` list. If a user can request a resource, the `ClusterQueue`
must specify a quota for it, even when the quota is `0`.

The official examples include NVIDIA-only and mixed NVIDIA/AMD scenarios
without shared cohorts. OpenShift AI 3.4 does not support shared cohorts.

## Demo Queue Policy

For this demo:

- use `nvidia.com/gpu` as the accelerator resource
- verify node labels before setting `ResourceFlavor.spec.nodeLabels`
- keep `nominalQuota` values aligned with real node capacity and intended
  workload concurrency
- avoid AMD resource flavors and queues unless the demo scope changes
- avoid shared cohorts for this baseline

## RDMA Scope

The official RDMA section is for NVIDIA GPUDirect RDMA. Treat it as advanced
infrastructure, not a default demo setting.

Before authoring RDMA manifests, confirm:

- multiple worker nodes with supported NVIDIA GPUs
- compatible NVIDIA accelerated networking
- installed distributed training components
- configured distributed training resources
- NVIDIA GPU support enabled through Node Feature Discovery and NVIDIA GPU
  Operator
- NVIDIA `ClusterPolicy` has RDMA enabled when RDMA is in scope
- NVIDIA Network Operator design is approved
- optional SR-IOV Network Operator design is approved if SR-IOV modes are used

The official chapter also uses the Machine Configuration Operator to increase
the CRI-O pinned-memory limit for non-root users. This is disruptive because
worker nodes restart to apply the machine configuration.

RDMA verification includes:

- checking that required Operator pods are running
- setting NCCL environment variables in a `PyTorchJob`
- checking pod logs for NCCL using an InfiniBand/RDMA network path

## Troubleshooting Signals

Use the documented condition fields first:

| Symptom | Primary signal | Likely direction |
|---------|----------------|------------------|
| Ray cluster suspended | `Workload.status.conditions.message` reports insufficient quota or missing flavor | Verify `ResourceFlavor`, `ClusterQueue`, requested resources, and quota. |
| Ray cluster failed | Ray head or worker pods are not running after reconciliation | Check pod events and `Workload.status.conditions.message`. |
| Ray cluster stays `Starting` and no pods are created | `Workload.status.conditions.message` and `RayCluster.status.conditions.message` | Verify KubeRay pod health and logs. |
| User cannot create Ray cluster or submit jobs with a `403` on `rayclusters.ray.io` | Notebook `TokenAuthentication` is using the wrong OpenShift credentials | Use the correct token and server for the intended user and confirm membership in `rhods-users`. |

If the problem is not covered by the official chapter or release notes, route
the issue to Red Hat Support with collected evidence.

## Verification Commands

These commands are examples for documentation and review. Run live commands
only after applying the OpenShift safety guard in `AGENTS.md`.

```bash
oc get resourceflavors
oc get clusterqueues
oc get localqueues -n <project_namespace>
oc describe workload <workload_name> -n <project_namespace>
oc get raycluster -n <project_namespace>
oc describe raycluster <raycluster_name> -n <project_namespace>
oc get pods -n redhat-ods-applications
oc logs <kuberay_pod_name> -n redhat-ods-applications
oc explain resourceflavor.spec
oc explain clusterqueue.spec
oc explain localqueue.spec
```
