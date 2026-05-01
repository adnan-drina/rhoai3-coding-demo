# Step 02: GPU Infrastructure For Private AI

## Why This Matters

Private AI requires more than a private model. It requires compute capacity that the organization can operate, observe, secure, and share. For large language models, that usually means GPU-backed infrastructure.

This step shows the accelerator layer behind the private AI story. If regulated workloads cannot use unmanaged public AI services, the organization needs a reliable way to run inference on its own platform.

## What This Step Adds

Step 02 prepares OpenShift to schedule and operate GPU workloads:

```text
GPU infrastructure
+-- Node Feature Discovery Operator and instance
+-- NVIDIA GPU Operator
+-- NVIDIA ClusterPolicy
+-- DCGM metrics integration
+-- AWS GPU MachineSets for NVIDIA L4 worker nodes
```

The result is not just "there are GPUs." The result is platform-managed accelerator capacity that model-serving workloads can consume in later steps.

## What To Notice In The Demo

Show that GPU nodes are discovered, labeled, and managed by operators. Show that NVIDIA device plugins and drivers are installed through the platform instead of by hand. Show that GPU telemetry is available for operations teams.

Connect this to the private AI requirement: if a model runs inside the platform, the platform must be able to manage the hardware it depends on.

## How Red Hat And Open Source Make It Work

Node Feature Discovery detects hardware features and labels nodes. The NVIDIA GPU Operator automates driver, device plugin, DCGM, and runtime integration. OpenShift then schedules workloads against those resources using Kubernetes-native controls.

This turns GPUs from manually managed infrastructure into a reusable platform capability.

## Red Hat Products Used

- **Red Hat OpenShift** is the platform that schedules GPU workloads and exposes accelerator capacity to model-serving components.
- **Red Hat OpenShift AI** consumes this GPU capacity through model-serving runtimes and hardware profiles in later steps.
- **OpenShift monitoring** gives platform teams visibility into node and workload health, which is critical when GPU capacity becomes a shared service.

## Open Source Projects To Know

- [Node Feature Discovery](https://kubernetes-sigs.github.io/node-feature-discovery/stable/get-started/index.html) labels Kubernetes nodes based on hardware capabilities.
- [NVIDIA GPU Operator](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/index.html) automates the NVIDIA software stack needed for GPU workloads.
- [DCGM Exporter](https://github.com/NVIDIA/dcgm-exporter) exposes GPU telemetry for monitoring.

## Why This Is Worth Knowing

GPU capacity is expensive and scarce. Enterprises need to manage it centrally, observe it, and make it available through governed services. That is what enables the later MaaS pattern: one centrally served private model can support many teams and tools.

For regulated organizations, this is also part of sovereignty and control. Private inference is only credible if the organization can operate the underlying compute.

## Where This Fits In The Full Platform

| Later step | What it gets from Step 02 |
|------------|---------------------------|
| Step 03 | GPU capacity for local vLLM model serving |
| Step 04 | Private model endpoints used by developer workspaces |
| Step 05 | Private MaaS model used by MTA Developer Lightspeed |
| Step 06 | Model capabilities that can be published through the portal |

## Deploy And Validate

Operational commands are kept here for workshop operators.

```bash
./steps/step-02-gpu-infra/deploy.sh
./steps/step-02-gpu-infra/validate.sh
```

Manifests: [`gitops/step-02-gpu-infra/base/`](../../gitops/step-02-gpu-infra/base/)

## References

- [NVIDIA GPU Operator on OpenShift](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/openshift/contents.html)
- [OpenShift 4.20 hardware accelerators](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/hardware_accelerators/nvidia-gpu-architecture)
- [Red Hat OpenShift AI](https://www.redhat.com/en/products/ai/openshift-ai)

## Next Step

[Step 03: Governed Models-as-a-Service](../step-03-llm-serving-maas/README.md) exposes private and external models through a governed API layer.
