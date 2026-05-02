---
name: resume-gpu-demo
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  rhoai-version: "3.4"
  ocp-version: "4.20"
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

This skill makes "resume from zero GPU nodes" a first-class workflow for the
demo. Prefer the repo script over hand-running many `oc` commands.

## When To Use

- GPU MachineSet was scaled to `0` to save cost.
- The demo environment was stopped and later started again.
- Stage 030 private model pods are `Pending`, `SchedulingGated`, or not ready after GPU capacity returns.
- The user asks whether Kueue, GPU nodes, or private model serving survived a restart.

## Primary Command

Run the scripted recovery path:

```bash
./scripts/resume-gpu-demo.sh resume
```

What it does:

1. Requests an Argo CD sync for Stage 020.
2. Scales the discovered GPU MachineSet to the desired replica count.
3. Waits for GPU nodes with allocatable `nvidia.com/gpu`.
4. Repairs expected GPU node labels and taints if needed.
5. Waits for NVIDIA `ClusterPolicy` to return to `ready`.
6. Validates Stage 020.
7. Requests an Argo CD sync for Stage 030.
8. Scales stale old model ReplicaSets to zero if they are still holding Kueue quota.
9. Waits for both private `LLMInferenceService` resources to become ready.
10. Validates Stage 030.

## Useful Variants

Check state without changing anything:

```bash
./scripts/resume-gpu-demo.sh status
```

Bring GPU capacity up only:

```bash
./scripts/resume-gpu-demo.sh up
```

Scale GPU capacity down to save cost:

```bash
./scripts/resume-gpu-demo.sh down
```

Use a non-default GPU node count:

```bash
./scripts/resume-gpu-demo.sh resume 2
```

## Expected Evidence

After a successful resume:

- GPU MachineSet desired replicas match ready replicas.
- GPU nodes are `Ready`.
- GPU nodes advertise allocatable `nvidia.com/gpu`.
- `ResourceFlavor`, `ClusterQueue`, and `LocalQueue` exist.
- Kueue `Workload` objects exist for private models.
- `gpt-oss-20b` and `nemotron-3-nano-30b-a3b` are `Ready=True`.
- Stage 020 and Stage 030 validation pass, or only known metric warnings remain.

## Notes

- Kueue persists across restarts, but it does not create cloud GPU nodes by itself.
- The script treats GPU capacity as a platform lifecycle action and Kueue as the admission/quota control plane.
- The stale ReplicaSet cleanup is demo-specific. It handles the known two-GPU quota rollout case where old model ReplicaSets can keep admitted Kueue reservations while new model pods wait.
- Do not scale GPU nodes down unless the user asks for cost-saving or shutdown.
