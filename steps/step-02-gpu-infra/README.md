# Step 02: GPU Infrastructure For Private AI

> Compatibility note: this step path is retained for existing links. New docs and automation should use [Stage 020](../../stages/020-gpu-infrastructure-private-ai/README.md).

## Why This Matters

Private AI depends on more than choosing a model that can run locally. The platform also needs accelerator capacity that can be provisioned, observed, shared, and recovered by operations teams. For the LLMs in this demo, that means GPU-backed OpenShift worker nodes.

This step establishes the infrastructure layer behind the private model path. When source code or modernization context should stay inside the platform boundary, the organization needs a repeatable way to run inference on infrastructure it controls.

## Architecture

![Step 02 layered capability map](../../docs/assets/architecture/step-02-capability-map.svg)

## What This Step Adds

- Hardware discovery through Node Feature Discovery, deployed from [`gitops/step-02-gpu-infra/base/nfd/`](../../gitops/step-02-gpu-infra/base/nfd/), so OpenShift can label nodes based on accelerator capabilities.
- NVIDIA GPU enablement through the NVIDIA GPU Operator and `ClusterPolicy`, deployed from [`gitops/step-02-gpu-infra/base/gpu-operator/`](../../gitops/step-02-gpu-infra/base/gpu-operator/).
- DCGM metrics integration so GPU health and utilization can be observed alongside other platform signals.
- AWS GPU MachineSet automation for NVIDIA L4 worker capacity, created by the GitOps-managed job in [`gitops/step-02-gpu-infra/base/jobs/aws-gpu-machineset.yaml`](../../gitops/step-02-gpu-infra/base/jobs/aws-gpu-machineset.yaml).

The capability added is centrally managed accelerator capacity. Later steps consume it through model-serving workloads rather than requiring each application team to build its own GPU stack.

## What To Notice In The Demo

Show that GPU nodes become part of the OpenShift scheduling model. Nodes are discovered and labeled, the NVIDIA software stack is operator-managed, and GPU metrics are available for operational visibility.

Connect this to the private AI requirement. Keeping inference inside the platform boundary is only credible when the platform can also manage the hardware dependency behind that inference path.

## How Red Hat And Open Source Make It Work

OpenShift provides the Kubernetes scheduling, node management, monitoring, and operator lifecycle foundation. Node Feature Discovery labels nodes based on detected hardware features. The NVIDIA GPU Operator manages the NVIDIA drivers, device plugin, container toolkit, and DCGM telemetry components needed for GPU workloads.

Red Hat OpenShift AI consumes that accelerator layer later through hardware profiles and model-serving workloads. The result is a reusable GPU platform service rather than manually configured infrastructure tied to one model deployment.

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
