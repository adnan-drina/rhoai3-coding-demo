# Stage 120: GPU-as-a-Service

**Theme:** AI Platform Foundation
**Concept:** Make scarce GPU capacity available as a governed, self-service
platform capability.

---

## Why This Matters

Before teams can build or serve AI models, the platform must make scarce GPU
capacity available in a controlled way. A GPU worker costs materially more than
a CPU worker, and demand will always exceed supply once multiple teams start
building AI workloads.

The enterprise problem is not just "add a GPU node." Platform teams need to
decide who can use GPUs, how much capacity each team can consume, which work
gets admitted first, and how to shut capacity down when the demo or project is
idle. Data scientists should not have to understand node taints, tolerations,
device-plugin labels, or queue objects to get started.

This stage turns the GPU into a platform service. OpenShift Machine API creates
the worker capacity. Node Feature Discovery publishes hardware facts about the
nodes. The NVIDIA GPU Operator installs the NVIDIA runtime stack and exposes
GPU capacity to Kubernetes. Red Hat build of Kueue turns that capacity into
quota-controlled queues. Red Hat OpenShift AI hardware profiles present those
queues as simple dashboard choices: CPU Default, GPU Shared, GPU Priority, and
GPU Reserved.

---

## What Enables It

This stage builds the GPU-as-a-Service layer on top of the Stage 110 base
platform.

### GPU Worker Capacity

The demo uses one AWS `g6e.2xlarge` GPU worker by default. This instance type
provides one NVIDIA L40S GPU with 48 GB of GPU memory. The MachineSet is tracked
in GitOps so a fresh environment can create the GPU worker consistently.

Default node count is one GPU worker. Operators can manually scale the GPU
MachineSet to zero between sessions to control cost; the Argo CD Application
ignores `MachineSet.spec.replicas` drift so intentional scale-down is not
self-healed back to one.

### Hardware Discovery (NFD Operator)

The Node Feature Discovery Operator installs the OpenShift hardware-discovery
layer. Its `NodeFeatureDiscovery` instance publishes node feature labels from
hardware sources such as PCI devices. In this stage, NFD is the discovery
prerequisite that lets accelerator-aware operators and scheduling policy rely
on verified node metadata instead of hand-maintained labels.

NFD does not provide GPU capacity by itself. It hands discovered hardware
context to the accelerator stack; the NVIDIA GPU Operator and its GPU Feature
Discovery/device-plugin components expose the `nvidia.com/gpu` scheduling
resource and NVIDIA-specific GPU labels used by Kueue placement.

### NVIDIA GPU Enablement

The NVIDIA GPU Operator installs the driver stack, container toolkit, GPU
feature discovery, DCGM exporter, and device plugin. The stage configures GPU
time-slicing so one physical L40S is advertised as four schedulable
`nvidia.com/gpu` units.

Time-slicing is a demo and development density mechanism. It shares compute
without memory isolation. It is useful for showing multiple self-service
profiles on a single card, but it is not presented as strict production
isolation.

### Queue-Based GPU Governance

Red Hat build of Kueue provides admission control and quota. This stage enables
RHOAI integration with the standalone Kueue operator by patching the shared
`DataScienceCluster` to `kueue.managementState: Unmanaged` via an Argo CD Sync
hook Job (`job-enable-dsc-kueue`) that uses a dedicated ServiceAccount and
ClusterRole in `redhat-ods-applications`. The GPU `ResourceFlavor` uses the
GPU Feature Discovery label (`nvidia.com/gpu.present: "true"`) and GPU-only
taint, so users do not need to know node placement details.

This stage creates:

- one CPU `ResourceFlavor`
- one GPU `ResourceFlavor` targeting GPU-labeled nodes and tolerating the GPU
  taint
- four `ClusterQueue` objects
- four `LocalQueue` objects in `demo-sandbox`
- one Kueue `WorkloadPriorityClass` (`gpu-high-priority`, value 1000) for future priority experiments

The `cq-gpu-shared` and `cq-gpu-priority` queues share a `gpu-pool` cohort,
enabling future fair-sharing and borrowing between them. The
`cq-gpu-reserved-demo` queue has no cohort — true isolation for the demo team.
The `cq-cpu-default` queue provides `cpu: 40`, `memory: 128Gi` — sized for
Stage 230's CPU model plane (Qwen3 reranker, granite-30m, MiniLM embedding
InferenceServices, plus the Enterprise RAG Workbench).

The initial queue design is intentionally non-preemptive because RHOAI
workbenches are not suspendable. The "GPU Priority" profile is a dedicated
quota lane, not a preemption demonstration.

### RHOAI Hardware Profiles

Hardware profiles turn queue and resource choices into dashboard-friendly
options. Users select a profile; RHOAI adds the queue binding to the workload.
The low-level scheduling authority remains in Kueue `ResourceFlavor` and
`LocalQueue` resources.

| Hardware profile | Backing queue | GPU quota | User-facing intent |
|---|---|---:|---|
| CPU Default | `lq-cpu-default` | 0 | CPU-only workbench or small job |
| GPU Shared - 1x NVIDIA | `lq-gpu-shared` | 2 | Shared GPU capacity when available |
| GPU Priority - 1x NVIDIA | `lq-gpu-priority` | 1 | Dedicated higher-importance lane |
| GPU Reserved - Demo Team | `lq-gpu-reserved-demo` | 1 | Reserved demo-team capacity |

---

## Architecture

```text
AWS GPU MachineSet (g6e.2xlarge, 1x L40S, default replicas=1)
   |
   v
NFD Operator -> NodeFeatureDiscovery -> node hardware feature labels
   |
   v
NVIDIA GPU Operator -> driver, toolkit, GFD, DCGM, device plugin
   |
   v
time-slicing: 1 physical GPU -> 4 schedulable nvidia.com/gpu units
   |
   v
Red Hat build of Kueue -> ResourceFlavor -> ClusterQueue -> LocalQueue
   |
   v
RHOAI Hardware Profiles -> CPU Default / GPU Shared / GPU Priority / GPU Reserved
   |
   v
Data scientist selects governed capacity from the RHOAI dashboard
```

Stage 210 uses this capacity to prove vLLM model serving with Nemotron and
capture a lightweight serving baseline. Stage 220 exposes validated model
access through Models-as-a-Service.

---

## Demo

![Stage 120 walkthrough](docs/assets/demos/stage-120/stage-120-demo.gif)

| Screenshot | What it shows |
|------------|---------------|
| ![Workbench form](../docs/assets/demos/stage-120/01-create-workbench-form.png) | Create workbench form with deployment size section |
| ![Hardware profiles](../docs/assets/demos/stage-120/02-hardware-profiles-dropdown.png) | Hardware profile dropdown showing GPU options |
| ![GPU selected](../docs/assets/demos/stage-120/03-gpu-shared-selected.png) | GPU Shared Time-Slicing profile selected |
| ![MachineSet](../docs/assets/demos/stage-120/04-machineset-gpu-node.png) | GPU MachineSet managing the g5.2xlarge node |
| ![Kueue](../docs/assets/demos/stage-120/05-kueue-clusterqueues.png) | Kueue ClusterQueues for GPU quota management |

---

## References

| Source | Role |
|---|---|
| [RHOAI 3.4 - Working with accelerators](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_accelerators/index) | NVIDIA GPU enablement and hardware profiles |
| [RHOAI 3.4 - Managing workloads with Kueue](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_openshift_ai/managing-workloads-with-kueue) | Kueue integration posture |
| [RHOAI 3.4 - Managing distributed workloads](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_openshift_ai/managing-distributed-workloads_managing-rhoai) | ResourceFlavor, ClusterQueue, LocalQueue concepts |
| [OCP 4.20 - Machine management](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html-single/machine_management/index) | AWS MachineSet management |
| [OCP 4.20 - Node Feature Discovery](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html-single/specialized_hardware_and_driver_enablement/index#psap-node-feature-discovery-operator) | NFD Operator, `NodeFeatureDiscovery`, and hardware feature labels |
| [redhat-cop/gitops-catalog - gpu-operator-certified](https://github.com/redhat-cop/gitops-catalog/tree/main/gpu-operator-certified) | GitOps operator/instance reference pattern |
| [redhat-cop/gitops-catalog - nfd](https://github.com/redhat-cop/gitops-catalog/tree/main/nfd) | GitOps NFD reference pattern |
| `docs/PLATFORM_BASELINE.md` | Active product version targets |
