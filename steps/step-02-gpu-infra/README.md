# Step 02: GPU Infrastructure
**"GPU-accelerated compute"** — Deploy NFD and the NVIDIA GPU Operator to enable GPU hardware, then provision GPU worker nodes for model serving workloads.

## Overview

Models need GPUs. This step deploys the hardware detection and driver stack that makes NVIDIA GPUs available to OpenShift workloads, then provisions the GPU worker nodes that will run the LLM inference services in subsequent steps.

### What Gets Deployed

```text
GPU Infrastructure
├── NFD Operator + Instance      → Hardware feature detection on nodes
├── GPU Operator + ClusterPolicy → NVIDIA driver, DCGM, device plugin
├── DCGM Dashboard ConfigMap     → GPU metrics in OpenShift Console
└── GPU MachineSets (AWS)        → 2x g6e.2xlarge with NVIDIA L4
```

Manifests: [`gitops/step-02-gpu-infra/base/`](../../gitops/step-02-gpu-infra/base/)

<details>
<summary>Deploy</summary>

```bash
./steps/step-02-gpu-infra/deploy.sh
./steps/step-02-gpu-infra/validate.sh
```

</details>

## References

- [NVIDIA GPU Operator on OpenShift](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/openshift/contents.html)
- [OCP 4.20 Hardware Accelerators](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/hardware_accelerators/nvidia-gpu-architecture)

## Next Steps

- **Step 03**: [LLM Serving + MaaS](../step-03-llm-serving-maas/README.md) — Deploy models with tier-based access and rate limiting
