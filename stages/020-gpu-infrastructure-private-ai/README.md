# Stage 020: GPU Infrastructure for Private AI

## Why This Matters

Before teams can build or serve AI models, the platform must make scarce GPU capacity available in a controlled way. A GPU worker costs materially more than a CPU worker, and demand will always exceed supply once multiple teams start building AI workloads.

The enterprise problem is not just "add a GPU node." Platform teams need to decide who can use GPUs, how much capacity each team can consume, which work gets admitted first, and how to shut capacity down when the demo or project is idle. Data scientists should not have to understand node taints, tolerations, device-plugin labels, or queue objects to get started.

This stage turns the GPU into a platform service. Data scientists select a hardware profile from the RHOAI dashboard; the platform handles node placement, taint toleration, quota enforcement, and admission control transparently.

## Architecture

```
AWS GPU MachineSet (g6e.2xlarge, 1x L40S each, replicas=2)
   │
   ▼
NFD Operator → NodeFeatureDiscovery → node hardware feature labels
   │
   ▼
NVIDIA GPU Operator → driver, toolkit, GFD, DCGM, device plugin
   │
   ▼
device plugin: 1 physical GPU → 1 schedulable nvidia.com/gpu unit (no time-slicing)
   │
   ▼
Red Hat build of Kueue → ResourceFlavor → ClusterQueue → LocalQueue
   │
   ▼
RHOAI Hardware Profiles → CPU Default / GPU Reserved
   │
   ▼
Data scientist selects governed capacity from the RHOAI dashboard
```

Stage 030 uses this capacity to serve a private LLM. Stage 040 exposes validated model access through Models-as-a-Service.

## Demo

### Hardware Profile Selection

The workbench creation form exposes GPU capacity as simple dropdown choices — no node taints or tolerations required.


### GPU MachineSet

The AWS GPU MachineSets, managed by OpenShift Machine API and tracked in GitOps: the default RTX PRO 6000 (`g7e.2xlarge`) pool with one MachineSet per zone, and the L40S (`g6e.2xlarge`) pool. A Machine API MachineSet launches in exactly one subnet and never retries another zone, so per-zone MachineSets are how the platform reaches whichever zone has capacity.

![GPU MachineSet](images/04-machineset-gpu-node.png)

### Kueue ClusterQueues

The CPU queue supports workbenches; `cq-gpu-rtxpro6000` (two RTX PRO 6000 units) and `cq-gpu-reserved-demo` (two L40S units) provide exclusive GPUs for model-serving consumers, each through its own LocalQueue in `demo-sandbox`, `internal-models` and `evaluated-models`.


## What This Stage Adds

The GPU-as-a-Service layer on top of the Stage 010 base platform.

- **GPU pools** — the default pool is AWS `g7e.2xlarge` (one NVIDIA RTX PRO 6000 Blackwell Server Edition, 96 GB, FP8 and NVFP4 tensor cores), one MachineSet per `us-east-2` zone, chosen by the 2026-10-13 serving study; the former `g6e.2xlarge` (one NVIDIA L40S, 48 GB) pool stays declared at zero, and dormant per-zone `p5.4xlarge` (H100) MachineSets record the capacity probe. All use 200 GB gp3 encrypted EBS root volumes and the `nvidia-gpu-only:NoSchedule` taint; the Argo CD Application ignores `MachineSet.spec.replicas` drift so operators scale to zero between sessions for cost control
- **Node Feature Discovery** — NFD Operator (`stable` channel, Automatic approval) publishes hardware feature labels; GPU Feature Discovery within the GPU Operator adds NVIDIA-specific labels used for Kueue placement
- **NVIDIA GPU Operator** — certified operator (`v26.7` channel, CSV `gpu-operator-certified.v26.7.1`, driver 595.91.07 supports Blackwell) installs driver stack, container toolkit, GFD, DCGM exporter, and device plugin; each GPU is one schedulable `nvidia.com/gpu` unit with no time-slicing
- **Red Hat build of Kueue** — standalone operator (`stable-v1.4` channel, Automatic approval); integration enabled by patching the shared DSC to `kueue.managementState: Unmanaged` via an Argo CD Sync hook Job; the existing Red Hat cert-manager installation is reused as a prerequisite
- **Queue topology** — one CPU ResourceFlavor and one ResourceFlavor per GPU type, each selecting only its own pool by the MachineSet label `cluster-api/accelerator` (`gpu-l40s`, `gpu-rtxpro6000`) and tolerating the GPU taint; one ClusterQueue per GPU type (`cq-gpu-reserved-demo` for L40S, `cq-gpu-rtxpro6000`) because a hardware profile names one LocalQueue and Kueue picks the first fitting flavor inside a ClusterQueue
- **RHOAI Hardware Profiles** — CPU Default, NVIDIA L40S and NVIDIA RTX PRO 6000 Queue-type profiles turn queue and resource choices into dashboard-friendly dropdown selections; the flavor, not the profile, places the workload (RHOAI 3.5, Manage workloads with Kueue)

## What To Notice And Why It Matters

- **Two cards, one model per card** — this project uses exclusive cards to leave memory available for its selected model weights and inference runtime; it does not demonstrate GPU time-slicing
- **CPU queue sizing** — `cq-cpu-default` provides cpu: 40, memory: 128Gi, sized for the CPU model plane (reranker, embedding InferenceServices, workbenches)
- **MachineSet is cluster-specific** — carries AMI, subnet, and cluster labels; must be regenerated from the cluster's own worker pool on each new environment via `generate-gpu-machineset.sh`
- **DSC patch mechanism** — Stage 020 does not own a second DataScienceCluster; it patches the Stage 010 shared owner through a dedicated ServiceAccount and ClusterRole

## How Red Hat And Open Source Make It Work

OpenShift Machine API creates GPU worker capacity from a declarative MachineSet. Node Feature Discovery publishes hardware facts. The NVIDIA GPU Operator installs the driver stack and exposes GPU capacity to Kubernetes. The Red Hat build of Kueue turns that capacity into quota-controlled queues with admission control and fair sharing. Red Hat OpenShift AI hardware profiles present those queues as simple dashboard choices so data scientists never interact with node-level scheduling primitives.

## Trust Boundaries

| Boundary | Control |
|----------|---------|
| GPU access | Taint `nvidia-gpu-only:NoSchedule` ensures only workloads with explicit toleration (via Kueue ResourceFlavor) land on GPU nodes |
| Quota enforcement | Kueue ClusterQueues bound by nominal quota — workloads exceeding quota are queued, not rejected silently |
| Isolation | `cq-gpu-reserved-demo` has no cohort; its GPU allocation cannot be borrowed by other queues |
| Cost control | MachineSet replicas can be scaled to zero manually; GitOps ignores the drift |
| DSC patch authority | Hook Job uses a scoped ServiceAccount and ClusterRole in `redhat-ods-applications` |

## Red Hat Products Used

| Product | Version/Channel |
|---------|-----------------|
| Red Hat OpenShift Container Platform | 4.22 (Machine API) |
| Red Hat OpenShift AI Self-Managed | stable-3.5 (hardware profiles, Kueue integration) |
| Node Feature Discovery Operator | stable (CSV nfd.4.22.0-202609212027) |
| NVIDIA GPU Operator (certified) | v26.7 (CSV gpu-operator-certified.v26.7.1) |
| Red Hat build of Kueue | stable-v1.4 (CSV kueue-operator.v1.4.2) |

## Open Source Projects To Know

| Project | Role |
|---------|------|
| Kueue | Kubernetes-native job queuing and quota management |
| NVIDIA GPU Operator | Driver stack, device plugin, DCGM exporter |
| Node Feature Discovery | Hardware label publisher |
| NVIDIA GPU Feature Discovery | GPU-specific label publisher (within GPU Operator) |

## Deploy And Validate

```bash
# Generate cluster-specific GPU MachineSet (required on each new environment)
RHOAI_GPU_MACHINESET_REPLICAS=2 \
  ./stages/020-gpu-infrastructure-private-ai/generate-gpu-machineset.sh --source "$RHOAI_SOURCE_WORKER_MACHINESET" --write

# Review and publish the generated environment overlay, then deploy its exact revision
./stages/020-gpu-infrastructure-private-ai/deploy.sh

# Native readiness (requires two Ready exclusive GPU workers)
./stages/020-gpu-infrastructure-private-ai/validate.sh --readiness

# Read-only native CUDA validator and per-node DCGM checks
./stages/020-gpu-infrastructure-private-ai/validate.sh --functional
```

Global hardware profiles require their named LocalQueue in each consuming project. This stage creates those queues in `demo-sandbox`; other projects need an explicit queue setup before selecting these profiles. See [Operations](../../docs/OPERATIONS.md#stage-020) for queue admission and GPU dashboard acceptance.

Administrators can open **Observe → Dashboards** in the OpenShift console and select **NVIDIA DCGM Exporter Dashboard** to inspect GPU temperature, power, clocks, utilization, framebuffer memory and tensor activity. Use the AI administrator account for cluster GPU metrics. Idle GPUs may correctly report zero utilization; this stage does not generate load just to populate charts.

## References

| Source | Role |
|--------|------|
| [RHOAI 3.5 - Working with accelerators](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_accelerators/index) | NVIDIA GPU enablement and hardware profiles |
| [RHOAI 3.5 - Managing workloads with Kueue](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/managing_openshift_ai/managing-workloads-with-kueue) | Kueue integration posture |
| [RHOAI 3.5 - Managing distributed workloads](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/managing_openshift_ai/managing-distributed-workloads_managing-rhoai) | ResourceFlavor, ClusterQueue, LocalQueue concepts |
| [OCP 4.22 - Machine management](https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/machine_management/index) | AWS MachineSet management |
| [OCP 4.22 - Node Feature Discovery](https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/specialized_hardware_and_driver_enablement/index) | NFD Operator and hardware feature labels |

## Next Stage

[Stage 030: Private Model Serving](../030-private-model-serving/) proves that a real LLM can be served on this governed GPU capacity — turning accelerator infrastructure into a working model endpoint before MaaS governance is introduced.

Operator installation uses native Automatic approval on the selected channels. Historical CSVs shown here are qualified baselines, not immutable future installation pins. See the [fresh deployment policy](../../docs/migration/035-operator-automatic-policy.md) for compatible-version checks, rolling-channel limits and the standard cluster-credential prerequisite.
