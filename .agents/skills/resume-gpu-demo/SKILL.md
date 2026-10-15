---
name: resume-gpu-demo
metadata:
  author: rhoai3-coding-demo
  version: 1.2.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Demo Environment"
description: >
  Resume the Stage 020/030 GPUaaS and private model-serving path after GPU
  nodes were intentionally scaled to zero, the demo environment was shut down,
  or private models are pending after GPU capacity returns. Use when the user
  asks to start the demo after shutdown, recover from zero GPU nodes, bring
  private model serving back online, check Kueue/GPU state after restart, or
  prepare the GPU-backed stages for validation. Do NOT use for unrelated
  OpenShift troubleshooting, non-GPU stages, or manifest review.
---

# Resume GPU Demo

This skill makes "resume from zero GPU nodes" a first-class workflow for the demo. GPU lifecycle is part of the Stage 020 `deploy.sh`; prefer it over hand-running `oc scale`. The former `resume-gpu-demo.sh` wrapper was folded into it.

## When To Use

- GPU MachineSets were scaled to `0` to save cost.
- The demo environment was stopped and later started again.
- Private model pods are `Pending`, `SchedulingGated`, or not ready after GPU capacity returns.
- The user asks whether Kueue, GPU nodes, or private model serving survived a restart.

## Primary Commands

Run these after the OpenShift safety guard in `AGENTS.md`. After a full shutdown, reconcile Stage 020 first, then start GPU capacity:

```bash
stages/020-gpu-infrastructure-private-ai/deploy.sh             # re-applies the Stage 020 components at the reviewed revision
stages/020-gpu-infrastructure-private-ai/deploy.sh --gpus 1    # start one GPU worker in the default pool
stages/020-gpu-infrastructure-private-ai/validate.sh
stages/040-governed-models-as-a-service/validate.sh
```

What `deploy.sh --gpus N` does:

1. Selects the one reviewed GPU MachineSet of the pool (`GPU_POOL=rtxpro6000`, the default, in `GPU_ZONE`, default `us-east-2a`; or `GPU_POOL=l40s`) and checks Stage 020 owns it.
2. Scales it to `N` (1 or 2); Argo CD ignores the live replica count.
3. Waits for GPU nodes with allocatable `nvidia.com/gpu`.
4. Waits for the NVIDIA `ClusterPolicy` to return to `ready`.

`--gpus 0` parks every GPU pool, so no forgotten pool keeps billing; private model pods become unavailable.

## Useful Variants

Check state without changing anything:

```bash
stages/020-gpu-infrastructure-private-ai/validate.sh
```

Scale GPU capacity down to save cost:

```bash
stages/020-gpu-infrastructure-private-ai/deploy.sh --gpus 0
```

Two workers, or the L40S pool (Stage 050 candidate queue `lq-gpu-reserved-demo`):

```bash
stages/020-gpu-infrastructure-private-ai/deploy.sh --gpus 2
GPU_POOL=l40s stages/020-gpu-infrastructure-private-ai/deploy.sh --gpus 1
```

## Expected Evidence

After a successful resume:

- GPU MachineSet desired replicas match ready replicas.
- GPU nodes are `Ready` and advertise allocatable `nvidia.com/gpu`.
- `ResourceFlavor`, `ClusterQueue`, and `LocalQueue` exist.
- Kueue `Workload` objects exist for the private models.
- The served private model (`qwen3-8-27b` in `internal-models`) is `Ready=True`.
- Stage 020 and Stage 040 validation pass, or only known metric warnings remain.

## Recovery Notes

- Machines stuck `Stopped` after a cloud shutdown/start cycle never recover: scale the GPU MachineSet to 0, delete the stopped Machines, then run `deploy.sh --gpus N` again so new Machines are provisioned.
- Node labels and taints come from the MachineSet template; a replaced node gets them on creation (`docs/TROUBLESHOOTING.md#gpu-nodes-do-not-appear`).

## Notes

- Kueue persists across restarts, but it does not create cloud GPU nodes by itself.
- GPU capacity is a platform lifecycle action; Kueue is the admission and quota control plane.
- Do not scale GPU nodes down unless the user asks for cost-saving or shutdown.
- Models are served in the `internal-models` namespace.
