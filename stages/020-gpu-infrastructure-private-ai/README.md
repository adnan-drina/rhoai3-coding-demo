# Stage 020: GPU Infrastructure For Private AI

## Why This Matters

The [Red Hat GPU-as-a-Service for AI at scale](https://www.redhat.com/en/blog/gpu-service-ai-scale-practical-strategies-red-hat-openshift-ai) article frames the problem well: GPUs are scarce, expensive, and operationally different from ordinary compute. A serious AI platform cannot treat GPU access as a collection of hand-built node selectors. It needs a shared operating model for allocation, quota, queueing, autoscaling signals, and observability.

This stage turns the earlier GPU infrastructure step into a demo-scale GPU-as-a-Service foundation. The goal is not to simulate hundreds of users or a large fleet of accelerators. The goal is to show the control-plane building blocks that platform teams use when GPU capacity becomes a governed service for AI workloads.

## Architecture

![Stage 020 layered capability map](../../docs/assets/architecture/stage-020-capability-map.svg)

## What This Stage Adds

- Hardware discovery through Node Feature Discovery, deployed from [`gitops/stages/020-gpu-infrastructure-private-ai/base/nfd/`](../../gitops/stages/020-gpu-infrastructure-private-ai/base/nfd/), so OpenShift can label nodes based on accelerator capabilities.
- NVIDIA GPU enablement through the NVIDIA GPU Operator and `ClusterPolicy`, deployed from [`gitops/stages/020-gpu-infrastructure-private-ai/base/gpu-operator/`](../../gitops/stages/020-gpu-infrastructure-private-ai/base/gpu-operator/).
- AWS GPU MachineSet automation for NVIDIA L4 worker capacity, created by the GitOps-managed job in [`gitops/stages/020-gpu-infrastructure-private-ai/base/jobs/aws-gpu-machineset.yaml`](../../gitops/stages/020-gpu-infrastructure-private-ai/base/jobs/aws-gpu-machineset.yaml).
- Red Hat build of Kueue, a `Kueue` cluster instance, and queue resources in [`gitops/stages/020-gpu-infrastructure-private-ai/base/kueue/`](../../gitops/stages/020-gpu-infrastructure-private-ai/base/kueue/).
- The queue-enabled `maas` project placeholder, labeled for Red Hat OpenShift AI dashboard visibility and Kueue management before Stage 030 deploys private model resources.
- A demo `ResourceFlavor`, `ClusterQueue`, and `LocalQueue` for the `maas` project, with nominal quota for two NVIDIA L4 GPUs plus CPU, memory, and pod capacity.
- Kueue-aware NVIDIA L4 hardware profiles that use `spec.scheduling.type: Queue` and the `private-model-serving` local queue.
- OpenShift Custom Metrics Autoscaler Operator and `KedaController` as the autoscaling building block for future metric-driven GPU optimization.
- GPUaaS observability through the existing DCGM dashboard and an additional GPUaaS dashboard covering GPU capacity, GPU utilization, memory usage, Kueue queue state, and quota status.

The stage keeps the original direct node-scheduling hardware profiles from Stage 010 for compatibility, but the new queue-based profiles are the Red Hat OpenShift AI 3.4-aligned path for governed GPU access.

## What To Notice In The Demo

Show the shift from "we have GPU nodes" to "we have a GPU service." The GPU nodes are still visible, but the more important objects are the queue and quota resources:

1. `ResourceFlavor` maps the NVIDIA L4 node class to labels and tolerations.
2. `ClusterQueue` defines the GPU, CPU, memory, and pod budget for private model serving.
3. `LocalQueue` exposes that capacity inside the `maas` project.
4. Queue-based hardware profiles make Red Hat OpenShift AI users select a queue-backed allocation strategy instead of embedding node selectors and tolerations in the workload path.
5. OpenShift Custom Metrics Autoscaler/KEDA is present as the production autoscaling integration point, but this first pass does not bind it to the private model deployments.

This demo intentionally uses one private model-serving project. It does not attempt to create artificial contention across many tenants. The architecture still shows the operating model that would scale to multiple projects, queues, cohorts, and quota policies.

## How Red Hat And Open Source Make It Work

Red Hat OpenShift provides the Kubernetes scheduling, node lifecycle, monitoring, RBAC, and Operator Lifecycle Manager foundation. Node Feature Discovery labels accelerator-capable nodes. The NVIDIA GPU Operator manages drivers, the device plugin, container toolkit, and DCGM telemetry.

Red Hat OpenShift AI 3.4 integrates with Kueue through **Red Hat build of Kueue**, not through the deprecated embedded Kueue component. OpenShift AI is configured with `DataScienceCluster.spec.components.kueue.managementState: Unmanaged`, which tells OpenShift AI to integrate with the externally managed Red Hat build of Kueue Operator. The dashboard is also configured to show Kueue support. On OpenShift 4.20, this demo follows the Red Hat catalog's current `stable-v1.3` Kueue channel.

Kueue provides queue-based admission, quota accounting, and workload visibility. OpenShift Custom Metrics Autoscaler, the Red Hat-supported KEDA path for OpenShift, is installed as the autoscaling foundation. In production, KEDA can consume metrics such as queue backlog, idle workload state, or Prometheus signals and drive scaling decisions. In this demo, it is deliberately not attached to the main private model-serving deployments until the metric behavior is validated in a live OpenShift AI 3.4 environment.

## Red Hat Products Used

- **Red Hat OpenShift** provides the application platform, machine management, scheduling, RBAC, monitoring, and operator lifecycle.
- **Red Hat OpenShift AI** consumes the GPUaaS foundation through model serving, hardware profiles, dashboard integration, and Kueue-aware workload management.
- **Red Hat build of Kueue** provides the supported queueing and quota control plane for OpenShift AI workload management.
- **OpenShift Custom Metrics Autoscaler Operator** provides the Red Hat-supported KEDA integration for metric-driven autoscaling.
- **Red Hat OpenShift GitOps** reconciles the GPUaaS desired state through Argo CD.

## Open Source Projects To Know

- [Node Feature Discovery](https://kubernetes-sigs.github.io/node-feature-discovery/stable/get-started/index.html) labels Kubernetes nodes based on hardware capabilities.
- [NVIDIA GPU Operator](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/index.html) automates the NVIDIA software stack needed for GPU workloads.
- [DCGM Exporter](https://github.com/NVIDIA/dcgm-exporter) exposes GPU telemetry for monitoring.
- [Kueue](https://kueue.sigs.k8s.io/) provides Kubernetes-native workload queueing, quota, and admission primitives.
- [KEDA](https://keda.sh/) provides event-driven autoscaling patterns that OpenShift supports through the Custom Metrics Autoscaler Operator.

## Trust Boundaries

This stage does not process source code or prompts by itself. It prepares the private compute path that later stages use for local model serving. The governance boundary here is operational: GPU access is expressed through OpenShift projects, Kueue queues, quotas, hardware profiles, and GitOps-managed platform state.

## Why This Is Worth Knowing

GPU-as-a-Service is not only a scale story. Even in a small demo, the same concepts matter: scarce accelerators need admission control, workload integration, quota visibility, and telemetry. Without that layer, private model serving becomes a one-off deployment tied to a particular node class. With it, private model serving becomes a platform service that can be governed and extended.

The important lesson is that GPU capacity should be exposed through productized platform controls. Red Hat OpenShift AI hardware profiles give users a consumable interface. Red Hat build of Kueue gives administrators the queue and quota model behind that interface. Monitoring and autoscaling signals provide the feedback loop for optimization.

## Where This Fits In The Full Platform

| Later stage | What it gets from Stage 020 |
|------------|-----------------------------|
| Stage 030 | GPU capacity, queue labels, and hardware profile context for local model serving |
| Stage 040 | Private model endpoints whose GPU footprint can be observed and governed |
| Stage 070 | Private model endpoints used by developer workspaces |
| Stage 080 | Private MaaS model used by Red Hat Developer Lightspeed for MTA |
| Stage 090 | Platform capabilities that can be published through the developer portal |

## Deploy And Validate

Operational commands are kept here for workshop operators.

```bash
./stages/020-gpu-infrastructure-private-ai/deploy.sh
./stages/020-gpu-infrastructure-private-ai/validate.sh
```

Manifests: [`gitops/stages/020-gpu-infrastructure-private-ai/base/`](../../gitops/stages/020-gpu-infrastructure-private-ai/base/)

## References

- [GPU-as-a-Service for AI at scale: Practical strategies with Red Hat OpenShift AI](https://www.redhat.com/en/blog/gpu-service-ai-scale-practical-strategies-red-hat-openshift-ai)
- [Red Hat OpenShift AI 3.4: Managing workloads with Kueue](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_openshift_ai/managing-workloads-with-kueue)
- [Red Hat OpenShift AI 3.4: Working with hardware profiles](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/working_with_accelerators/working-with-hardware-profiles_accelerators)
- [Red Hat OpenShift AI 3.4: Managing distributed workloads](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_openshift_ai/managing-distributed-workloads_managing-rhoai)
- [OpenShift 4.20: Red Hat build of Kueue](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html-single/ai_workloads/)
- [OpenShift 4.20: Custom Metrics Autoscaler Operator](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/nodes/automatically-scaling-pods-with-the-custom-metrics-autoscaler-operator)
- [NVIDIA GPU Operator on OpenShift](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/openshift/contents.html)

## Next Stage

[Stage 030: Private Model Serving](../030-private-model-serving/README.md) deploys the private model serving resources that consume GPU capacity.
