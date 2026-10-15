---
name: rhoai-distributed-workload-operations
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when an administrator plans quota for Ray, PyTorchJob or TrainJob
  workloads on top of the Stage 020 Kueue queues, evaluates RDMA for
  multi-node training, or troubleshoots a user's Ray cluster as an
  administrator. Not deployed in this demo (ray, trainingoperator and trainer
  are Removed in default-dsc). Do NOT use for the Kueue integration, existing
  queues and admission errors of model servers and workbenches (use
  rhoai-kueue-workload-management), enabling the components (use
  rhoai-distributed-workloads), or user training jobs (use
  rhoai-distributed-workload-workflows).
---

# RHOAI Distributed Workload Operations

Thin skill: administrator view of distributed workloads in OpenShift AI 3.5.
**Not deployed in this demo**: no Ray, Training Operator or Trainer workloads,
no RDMA, no quota reserved for them.

## When to use

- A future stage proposes distributed training and needs quota, RDMA or Ray
  administration.
- Reviewing whether the Stage 020 queues can admit training jobs.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| `ray`, `trainingoperator`, `trainer` are `Removed` in `default-dsc` | `gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-platform/datasciencecluster.yaml` | [Manage distributed workloads][dw] |
| The only queues are the Stage 020 ones (`cq-gpu-rtxpro6000`, `cq-gpu-reserved-demo`, `cq-cpu-default`, `kueue.x-k8s.io/v1beta2`), sized for model servers and workbenches; NVIDIA only, no cohorts, no preemption | `gitops/stages/020-gpu-infrastructure-private-ai/020-gpu-quotas/queues/` | [Configure quota management][quota], [NVIDIA GPUs without shared cohort][nvidia] |
| No RDMA or accelerated networking is configured | — | [Configure a cluster for RDMA][rdma] |

## If enabled

1. Enable the components first (`rhoai-distributed-workloads`).
2. Add quota for training in Git under
   `gitops/stages/020-gpu-infrastructure-private-ai/020-gpu-quotas/queues/`
   (a ClusterQueue or more nominal quota) or in the new stage, and a
   LocalQueue in each training project. The two GPUs per ClusterQueue are
   used by model servers today; adding training without new GPU nodes
   starves them.
3. Treat RDMA as out of scope unless the nodes and network support it; the
   official prerequisites decide.
4. Validate with `./stages/020-gpu-infrastructure-private-ai/validate.sh --readiness`
   and, after the OpenShift safety guard in `AGENTS.md`, read-only:

   ```bash
   oc get clusterqueue,localqueue -A
   oc get workloads -A
   ```

## Pitfalls

- The live `Kueue` CR lists RayCluster, RayJob, PyTorchJob and TrainJob
  frameworks; the operators behind them are not installed.
- The official quota examples name other GPU models (and AMD); keep this
  repo's flavors and its one-ClusterQueue-per-GPU-type pattern
  (`gitops/stages/020-gpu-infrastructure-private-ai/020-gpu-quotas/queues/cq-gpu-rtxpro6000.yaml`).

## Official documentation (OpenShift AI 3.5)

| Topic | Section |
|---|---|
| Administration | [Manage distributed workloads][dw] |
| Quota | [Configure quota management][quota], [Example Kueue configurations][examples] |
| RDMA | [Configure a cluster for RDMA][rdma] |
| Troubleshooting | [Distributed workloads for administrators][ts] |

## Related skills

`rhoai-distributed-workloads`, `rhoai-kueue-workload-management`,
`rhoai-distributed-workload-workflows`, `rhoai-nvidia-gpu-accelerators`,
`ocp-ai-workloads`, `rhoai-troubleshoot`.

[dw]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#managing-distributed-workloads_managing-rhoai
[quota]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#configuring-quota-management-for-distributed-workloads_managing-rhoai
[examples]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#ref-example-kueue-resource-configurations_managing-rhoai
[nvidia]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#nvidia_gpus_without_shared_cohort
[rdma]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#configuring-a-cluster-for-rdma_managing-rhoai
[ts]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#troubleshooting-common-problems-with-distributed-workloads-for-administrators_managing-rhoai
