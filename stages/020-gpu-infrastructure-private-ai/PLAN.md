# Stage 020: GPU-as-a-Service - Plan

## Intent

- Stage identifier: `120`
- Stage family: `1xx AI Platform Foundation`
- Stage slug: `020-gpu-infrastructure-private-ai`
- Concept introduced: GPU capacity as a governed, self-service platform
  capability.
- Target audience: Platform engineer, MLOps engineer, data scientist
- Enterprise value: GPUs are scarce and expensive; the platform turns raw GPU
  nodes into governed capacity with quotas, queues, hardware profiles, and a
  documented scale-to-zero path.
- Depends on: `010-openshift-ai-platform-foundation`
- New components: Red Hat build of Kueue operator, NFD operator, NVIDIA GPU
  Operator, AWS GPU MachineSet, Kueue quota objects, RHOAI hardware profiles.
- Existing shared components touched: Stage 020 patches the shared
  `DataScienceCluster` to `kueue.managementState: Unmanaged` so RHOAI
  integrates with the standalone Kueue operator.
- Non-goals:
  - model serving or KServe enablement; deferred to
    `030-private-model-serving`
  - GuideLLM or performance benchmarking; deferred to the Stage 030 serving
    baseline work after endpoint readiness is repeatable
  - Models-as-a-Service governance; deferred to
    `040-governed-models-as-a-service`
  - MIG GPU partitioning
  - multi-GPU or multi-node serving
  - non-NVIDIA accelerators

## Hardware Decision

- AWS GPU instance type: `g6e.2xlarge`
- Physical GPU: one NVIDIA L40S, 48 GB GPU memory
- Default node count: one GPU worker
- Manual cost-control path: scale the GPU MachineSet to zero between demo
  sessions; Argo CD ignores `MachineSet.spec.replicas` drift for this stage.
- Time-slicing: one physical GPU advertised as four `nvidia.com/gpu` units.

The committed MachineSet is specific to the current `cluster-klvxt` AWS
environment because MachineSet provider configuration includes cluster ID, AMI,
subnet, security group, IAM profile, region, and zone values. A fresh demo
environment must regenerate this manifest from a live worker MachineSet before
Stage 020 is deployed.

Use `generate-gpu-machineset.sh` to create the replacement manifest from the
guarded target cluster. The script preserves provider-specific AWS fields from
an existing worker MachineSet and changes only the reviewed GPU intent:
instance type, replicas, labels, taint, and MachineSet identity.

## Queue / Quota / Profile Design

One CPU `ResourceFlavor` and one GPU `ResourceFlavor` are created. The GPU
ResourceFlavor targets nodes labeled by GPU feature discovery and tolerates the
GPU-only taint. Kueue-enabled hardware profiles carry no node selectors or
tolerations; placement belongs to the ResourceFlavor.

| Hardware profile | LocalQueue -> ClusterQueue | GPU nominal quota | Behavior |
|---|---|---:|---|
| `cpu-default` | `lq-cpu-default` -> `cq-cpu-default` | 0 | CPU-only self-service work |
| `gpu-shared` | `lq-gpu-shared` -> `cq-gpu-shared` | 2 | Shared GPU quota |
| `gpu-priority` | `lq-gpu-priority` -> `cq-gpu-priority` | 1 | Dedicated higher-importance lane |
| `gpu-reserved-demo` | `lq-gpu-reserved-demo` -> `cq-gpu-reserved-demo` | 1 | Reserved demo-team quota |

The queue set is non-preemptive. RHOAI workbenches are not suspendable, so this
stage demonstrates governed admission and reservation, not preemption.

## Acceptance Criteria

- [ ] README explains Why and What without runbook detail.
- [ ] Official Red Hat docs are captured for GPU enablement, hardware profiles,
  Kueue, NFD, and MachineSet management.
- [ ] Relevant Red Hat-linked GitHub reference implementations are captured.
- [ ] Argo CD Application follows project standards and uses project
  `rhoai-demo`.
- [ ] GPU MachineSet exists and has one ready worker by default.
- [ ] GPU node reports at least four allocatable `nvidia.com/gpu` units.
- [ ] NFD, NVIDIA GPU Operator, and Kueue operator CSVs are `Succeeded`.
- [ ] NVIDIA `ClusterPolicy` reports `ready`.
- [ ] Shared `DataScienceCluster` has `kueue: Unmanaged`; `kserve`
  is `Removed` before Stage 030 and may become `Managed` after Stage 030.
- [ ] Four ClusterQueues and four LocalQueues are `Active`.
- [ ] Four RHOAI hardware profiles exist and are visible to users.
- [ ] Deploy and validate scripts pass against the guarded cluster.
- [ ] Manifest and Red Hat source-alignment reviews pass.

## Source Capture

| Purpose | Source | Skill | Notes |
|---|---|---|---|
| GPU operator, ClusterPolicy, time-slicing | RHOAI accelerators guide and Red Hat CoP GitOps catalog | `rhoai-nvidia-gpu-accelerators` | NVIDIA-only demo policy; time-slicing for density |
| Hardware profiles | RHOAI working with accelerators guide | `rhoai-hardware-profiles` | Queue-backed hardware profiles in Dashboard |
| NFD operator | OCP 4.20 specialized hardware docs and CoP NFD catalog | `ocp-node-feature-discovery` | node hardware labeling |
| GPU MachineSet | OCP 4.20 machine management docs and live worker export | `ocp-machine-management` | cluster-specific AWS providerSpec |
| Kueue operator and RHOAI integration | RHOAI Kueue docs | `rhoai-kueue-workload-management` | DSC `kueue: Unmanaged` |
| Queue resources | RHOAI distributed workloads docs and live CRD schema | `rhoai-distributed-workload-operations` | `kueue.x-k8s.io/v1beta2` storage version |

## Skill Routing

- Coordinator: `project-demo-stage-authoring`
- Documentation: `project-documentation-authoring`
- GitOps: `project-gitops-authoring`, `project-red-hat-operator-gitops`
- Platform: `ocp-machine-management`, `ocp-node-feature-discovery`,
  `ocp-ai-workloads`
- RHOAI: `rhoai-nvidia-gpu-accelerators`, `rhoai-hardware-profiles`,
  `rhoai-kueue-workload-management`,
  `rhoai-distributed-workload-operations`,
  `rhoai-dsci-dsc-configuration`
- Environment: `openshift-project-safety`, `env-deploy-and-evaluate`,
  `env-manage-resources`, `env-troubleshoot`
- Review: `project-manifest-review`,
  `project-red-hat-doc-alignment-review`, `rhoai-api-tiers`

## GitOps Ownership

- Owning Application: `020-gpu-infrastructure-private-ai`
- Source path: `gitops/stages/020-gpu-infrastructure-private-ai/base`
- Project: `rhoai-demo`
- Owned resources:
  - Kueue, NFD, and NVIDIA GPU Operator install resources
  - NFD instance
  - NVIDIA `ClusterPolicy` and time-slicing ConfigMap
  - AWS GPU MachineSet
  - Kueue ResourceFlavor, ClusterQueue, LocalQueue, WorkloadPriorityClass
  - RHOAI HardwareProfile resources
- Shared resources:
  - Stage 010 creates the single `DataScienceCluster`; Stage 020 patches only
    the Kueue component field through a GitOps hook and does not render a
    competing DSC.
- Intentional drift:
  - The Argo CD Application ignores MachineSet `/spec/replicas` so operators can
    manually scale GPU nodes down to zero.

## Manifest Inventory

| Path | Kind | Source authority |
|---|---|---|
| `gitops/stages/020-gpu-infrastructure-private-ai/base/kueue/operator/` | Namespace, OperatorGroup, Subscription | RHOAI Kueue docs |
| `gitops/stages/020-gpu-infrastructure-private-ai/base/nfd/operator/` | Namespace, OperatorGroup, Subscription | OCP NFD docs and CoP catalog |
| `gitops/stages/020-gpu-infrastructure-private-ai/base/nfd/instance/base/` | NodeFeatureDiscovery | OCP NFD docs |
| `gitops/stages/020-gpu-infrastructure-private-ai/base/gpu-operator/operator/` | Namespace, OperatorGroup, Subscription | RHOAI accelerators docs and CoP catalog |
| `gitops/stages/020-gpu-infrastructure-private-ai/base/gpu-operator/instance/base/` | ClusterPolicy, time-slicing ConfigMap | NVIDIA GPU Operator defaults plus demo time-slicing |
| `gitops/stages/020-gpu-infrastructure-private-ai/base/machineset/base/` | MachineSet | OCP Machine API and live worker export |
| `gitops/stages/020-gpu-infrastructure-private-ai/base/kueue-quota/base/` | ResourceFlavor, ClusterQueue, LocalQueue, WorkloadPriorityClass | RHOAI distributed workloads docs |
| `gitops/stages/020-gpu-infrastructure-private-ai/base/hardware-profiles/base/` | HardwareProfile | RHOAI hardware profiles docs |
| `gitops/argocd/app-of-apps/020-gpu-infrastructure-private-ai.yaml` | Argo CD Application | project GitOps standards |

## Script Plan

### `deploy.sh`

- loads `.env` with exported values
- validates `RHOAI_EXPECTED_API_SERVER` against `oc whoami --show-server`
- injects `GIT_REPO_URL` and `GIT_REPO_BRANCH` into the Argo CD Application
- applies only the Argo CD Application

### `validate.sh`

- validates guard
- checks Argo CD sync and health
- checks operator CSV readiness
- checks NFD and NVIDIA ClusterPolicy readiness
- checks GPU MachineSet readiness and GPU allocatable count
- checks DSC Kueue state and accepts either pre-Stage-210 or post-Stage-210
  KServe state
- checks ClusterQueue and LocalQueue Active conditions
- checks hardware profile presence

## Operations And Troubleshooting

- `docs/OPERATIONS.md`: Stage 020 deploy, validate, manual scale-down, and fresh
  environment MachineSet regeneration guidance.
- `docs/TROUBLESHOOTING.md`: GPU MachineSet, quota, ClusterPolicy, Kueue, and
  hardware-profile failure patterns.

## Risks And Deferred Work

| Item | Type | Resolution |
|---|---|---|
| AWS GPU quota for `g6e` | risk | Provisioning fails if the sandbox lacks quota; verify before scale-up |
| GPU cost | risk | One `g6e.2xlarge` runs continuously unless manually scaled to zero |
| MachineSet portability | expected | Regenerate from a live worker MachineSet in each fresh environment |
| Kueue preemption | deferred | Stage 020 is non-preemptive; later stages can test suspendable jobs |
| model serving | deferred | Stage 030 will enable KServe/vLLM and ensure the Nemotron endpoint is ready |

## Review Log

- Source capture: complete
- Manifest review: pending
- Red Hat source-alignment review: pending
- Live deploy: succeeded on cluster-klvxt 2026-06-12; Argo CD Applications
  `010-openshift-ai-platform-foundation` and `020-gpu-infrastructure-private-ai` synced and
  healthy at GitOps revision `d9963b1`.
- Live validation: PASSED 2026-06-12 — `020-gpu-infrastructure-private-ai/validate.sh`
  23/23 after validator fix commit `c1a2a66`.
- Regression validation: PASSED 2026-06-12 — `validate.sh` 23/23 after
  Stage 030 changed KServe from `Removed` to `Managed` through the shared
  Stage 010 `DataScienceCluster` owner.
