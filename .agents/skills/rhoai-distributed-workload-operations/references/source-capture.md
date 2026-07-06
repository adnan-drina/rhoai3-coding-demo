# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product baseline | `docs/PLATFORM_BASELINE.md` |
| Chapter title | Chapter 9. Managing distributed workloads |
| Chapter URL | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_openshift_ai/managing-distributed-workloads_managing-rhoai |
| Documentation category | Administer |
| Retrieved date | 2026-06-10 |
| Sections used | 9.1 Configuring quota management for distributed workloads; 9.2 Example Kueue resource configurations for distributed workloads; 9.3 Configuring a cluster for RDMA; 9.4 Troubleshooting common problems with distributed workloads for administrators |

## Supporting Red Hat Sources

| Source | Role |
|--------|------|
| `docs/PLATFORM_BASELINE.md` | Active product baseline and documentation category index |
| Red Hat build of Kueue documentation linked from the official chapter | Supplemental object behavior for Kueue resources only after Red Hat OpenShift AI chapter constraints are applied |
| OpenShift documentation linked from the official chapter | Supplemental OpenShift operator, MachineConfig, and CLI references |

## Source Boundaries

- Product configuration truth: official Red Hat OpenShift AI 3.4 chapter above.
- Demo policy: NVIDIA-first queue and accelerator usage for this repository.
- Verification: readonly `oc get`, `oc describe`, `oc explain`, and CRD checks
  listed in this skill.
- Not authoritative: upstream Kueue, KubeRay, NCCL, or NVIDIA docs unless this
  skill labels them as supplemental and ties them back to the official Red Hat
  chapter.

## Unresolved Or Environment-Specific Items

- Exact `ResourceFlavor.spec.nodeLabels` for the active AWS GPU nodes.
  Verification: `oc get nodes --show-labels` after the environment is active.
- Exact CPU and memory `nominalQuota` values for demo queues.
  Verification: match requested workloads, node capacity, and live cluster
  capacity before enabling queues.
- Whether the active AWS demo environment should enable RDMA.
  Verification: confirm supported NVIDIA GPUs, compatible accelerated
  networking, NVIDIA Network Operator design, and business need before adding
  RDMA manifests.
