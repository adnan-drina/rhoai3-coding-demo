# Stage 020: GPU Infrastructure For Private AI

## Why This Matters

The workshop story starts with a platform team building a trusted AI development environment for enterprise developers. Stage 010 established the Red Hat OpenShift AI foundation. Stage 020 adds the private compute layer that makes the rest of the story credible: GPU capacity that can be discovered, scheduled, governed, observed, and consumed through platform abstractions.

For this demo, GPUs are not just infrastructure. They are the foundation for private model serving, where sensitive source code and prompts can stay inside the OpenShift platform boundary. If GPU access is handled as a collection of hand-built node selectors, every private model deployment becomes a special case. If GPU access is exposed as a governed platform service, the same environment can support model serving, developer workspaces, modernization workflows, and future AI workloads with clearer operational control.

This stage uses a demo-scale GPU-as-a-Service pattern aligned with Red Hat guidance: accelerator discovery, GPU node lifecycle, queue-based admission, quota, Red Hat OpenShift AI hardware profiles, autoscaling readiness, and observability. The demo does not simulate a large organization with many competing teams. It shows the control-plane building blocks that make governed private AI compute possible.

## Architecture

![Stage 020 layered capability map](../../docs/assets/architecture/stage-020-capability-map.svg)

## What This Stage Adds

Stage 020 creates a demo-scale GPU-as-a-Service foundation for the private model-serving path.

- Hardware discovery through Node Feature Discovery, deployed from [`gitops/stages/020-gpu-infrastructure-private-ai/base/nfd/`](../../gitops/stages/020-gpu-infrastructure-private-ai/base/nfd/), so OpenShift can label nodes based on accelerator capabilities.
- NVIDIA GPU enablement through the NVIDIA GPU Operator and `ClusterPolicy`, deployed from [`gitops/stages/020-gpu-infrastructure-private-ai/base/gpu-operator/`](../../gitops/stages/020-gpu-infrastructure-private-ai/base/gpu-operator/).
- AWS GPU MachineSet automation for NVIDIA L4 worker capacity, created by the GitOps-managed job in [`gitops/stages/020-gpu-infrastructure-private-ai/base/jobs/aws-gpu-machineset.yaml`](../../gitops/stages/020-gpu-infrastructure-private-ai/base/jobs/aws-gpu-machineset.yaml).
- Red Hat build of Kueue, a cluster-level `Kueue` instance, and queue resources in [`gitops/stages/020-gpu-infrastructure-private-ai/base/kueue/`](../../gitops/stages/020-gpu-infrastructure-private-ai/base/kueue/).
- The `maas` project placeholder, labeled for Red Hat OpenShift AI dashboard visibility and Kueue management before Stage 030 deploys private model resources.
- A demo `ResourceFlavor`, `ClusterQueue`, and `LocalQueue` for private model serving, sized for the current environment with two NVIDIA L4 GPUs plus CPU, memory, and pod quota.
- Queue-based NVIDIA L4 hardware profiles that use `spec.scheduling.type: Queue` and the `private-model-serving` local queue.
- OpenShift Custom Metrics Autoscaler Operator and a `KedaController` as the supported autoscaling foundation for future metric-driven optimization.
- GPUaaS observability through the existing DCGM dashboard and a GPUaaS dashboard covering GPU capacity, utilization, memory usage, Kueue queue state, and quota status.

The stage keeps the direct node-scheduling hardware profiles from Stage 010 for compatibility, but the preferred path for this storyline is the queue-based profile. In Red Hat OpenShift AI 3.4, node placement for queue-managed workloads should come from the Kueue `ResourceFlavor`, not from hardware-profile node selectors and tolerations.

## What To Notice In The Demo

The main demo point is the shift from "we installed GPU nodes" to "we created the private AI compute service that later stages consume."

The GPU nodes are still important, but the higher-value proof points are the abstractions around them. `ResourceFlavor` maps the NVIDIA L4 node class to its labels and tolerations. `ClusterQueue` defines the shared quota for private model serving. `LocalQueue` exposes that quota inside the `maas` project. Red Hat OpenShift AI hardware profiles give users a consumable choice in the dashboard without asking them to understand taints, labels, node pools, or scheduler internals.

That is the same message Red Hat emphasizes for GPU-as-a-Service: platform teams need to reduce shadow IT, fragmented accelerator pools, idle GPU capacity, and tenant isolation risk while giving approved AI workloads a governed path to scarce compute. In our storyline, those controls are what let private model serving become a reusable platform capability instead of a one-off deployment.

The demo intentionally stays small. It uses one private model-serving project and does not create artificial contention across many tenants. The operating model is still visible: more teams would mean more projects, more local queues, shared or separate cluster queues, adjusted quotas, and observability-driven tuning.

## How Red Hat And Open Source Make It Work

Red Hat OpenShift provides the Kubernetes platform substrate: cluster identity, RBAC, machine management, scheduling, networking, monitoring, and Operator Lifecycle Manager. Node Feature Discovery identifies accelerator-capable nodes. The NVIDIA GPU Operator manages the driver stack, device plugin, container toolkit, and DCGM telemetry needed for GPU workloads.

Red Hat OpenShift AI provides the AI platform layer. In this stage it consumes the GPUaaS foundation through dashboard integration and hardware profiles. In Stage 030, private model-serving workloads use the queued GPU path by applying the `kueue.x-k8s.io/queue-name=private-model-serving` label.

Red Hat OpenShift AI 3.4 integrates with Kueue through **Red Hat build of Kueue**, not through the deprecated embedded Kueue component. This repository configures `DataScienceCluster.spec.components.kueue.managementState: Unmanaged`, which tells OpenShift AI to integrate with the externally managed Red Hat build of Kueue Operator. It also enables Kueue support in the dashboard and labels the `maas` namespace with `kueue.openshift.io/managed=true` so queue enforcement applies to supported workload types.

OpenShift Custom Metrics Autoscaler, the Red Hat-supported KEDA path for OpenShift, is installed as the autoscaling building block. In production, KEDA can use Prometheus or Kueue signals such as backlog or idle workload state to scale workloads or nodes. In this demo, it is deliberately not attached to the private model deployments. That keeps the first pass focused on the GPUaaS foundation while leaving a clear extension point for demand-driven scaling.

## Red Hat Products Used

- **Red Hat OpenShift** provides the application platform, Kubernetes scheduling, machine management, RBAC, monitoring, networking, and operator lifecycle.
- **Red Hat OpenShift AI** provides the AI platform integration point through hardware profiles, dashboard configuration, Kueue-aware workload management, and later private model serving.
- **Red Hat build of Kueue** provides the supported queueing and quota control plane used by Red Hat OpenShift AI 3.4.
- **OpenShift Custom Metrics Autoscaler Operator** provides the Red Hat-supported KEDA integration for custom-metric and event-driven autoscaling patterns.
- **Red Hat OpenShift GitOps** reconciles the GPUaaS desired state through Argo CD.

## Open Source Projects To Know

- [Node Feature Discovery](https://kubernetes-sigs.github.io/node-feature-discovery/stable/get-started/index.html) labels Kubernetes nodes based on hardware capabilities so accelerator-aware scheduling can work from observable node facts.
- [NVIDIA GPU Operator](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/index.html) automates the NVIDIA software stack required for GPU workloads on Kubernetes.
- [DCGM Exporter](https://github.com/NVIDIA/dcgm-exporter) exposes GPU health, utilization, and memory metrics for monitoring.
- [Kueue](https://kueue.sigs.k8s.io/) provides Kubernetes-native workload queueing, quota accounting, and admission control.
- [KEDA](https://keda.sh/) provides event-driven autoscaling patterns that OpenShift supports through the Custom Metrics Autoscaler Operator.

## Trust Boundaries

This stage does not process source code or prompts. It prepares the private compute boundary that later stages use for local model serving.

The trust boundary in Stage 020 is operational governance: GPU access is mediated by OpenShift projects, RBAC, Kueue queues, quotas, hardware profiles, and GitOps-managed platform state. Private local models in later stages keep prompts and code inside the OpenShift platform boundary. Governed external models introduced later remain centrally controlled, but prompts are still processed by the external provider.

## Why This Is Worth Knowing

GPU-as-a-Service is not only a hyperscale concern. The same design questions appear in a small private AI deployment: who can use accelerators, which workloads get admitted first, how quota is expressed, how idle capacity is detected, and how administrators know whether expensive hardware is being used well.

The reusable lesson is that GPU capacity should be exposed through productized platform controls. Red Hat OpenShift supplies the infrastructure foundation. Red Hat OpenShift AI gives users a dashboard-level consumption model. Red Hat build of Kueue gives administrators the queue and quota model behind that interface. Monitoring and autoscaling signals provide the feedback loop for optimization.

This stage is also the point where the workshop starts to show why private AI coding assistance is a platform concern. A private model is useful only if the organization can operate the compute behind it consistently.

## Where This Fits In The Full Platform

| Later stage | What it gets from Stage 020 |
|------------|-----------------------------|
| Stage 030 | GPU capacity, Kueue queue context, and hardware profile selection for private model serving |
| Stage 040 | Private model endpoints whose GPU footprint can be observed and governed through the platform |
| Stage 070 | Private model endpoints consumed from controlled developer workspaces |
| Stage 080 | Private MaaS model capacity for Red Hat Developer Lightspeed for MTA |
| Stage 090 | Platform capabilities that can be published through the developer portal |

## Deploy And Validate

Operational commands are kept here for workshop operators.

```bash
./stages/020-gpu-infrastructure-private-ai/deploy.sh
./stages/020-gpu-infrastructure-private-ai/validate.sh
```

Manifests: [`gitops/stages/020-gpu-infrastructure-private-ai/base/`](../../gitops/stages/020-gpu-infrastructure-private-ai/base/)

## References

- [Unlocking AI innovation: GPU-as-a-Service with Red Hat](https://www.redhat.com/en/blog/unlocking-ai-innovation-gpu-service-red-hat)
- [GPU-as-a-Service for AI at scale: Practical strategies with Red Hat OpenShift AI](https://www.redhat.com/en/blog/gpu-service-ai-scale-practical-strategies-red-hat-openshift-ai)
- [Red Hat OpenShift AI 3.4: Managing workloads with Kueue](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_openshift_ai/managing-workloads-with-kueue)
- [Red Hat OpenShift AI 3.4: Working with hardware profiles](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/working_with_accelerators/working-with-hardware-profiles_accelerators)
- [Red Hat OpenShift AI 3.4: Managing distributed workloads](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_openshift_ai/managing-distributed-workloads_managing-rhoai)
- [OpenShift 4.20: Red Hat build of Kueue](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html-single/ai_workloads/)
- [OpenShift 4.20: Custom Metrics Autoscaler Operator](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/nodes/automatically-scaling-pods-with-the-custom-metrics-autoscaler-operator)
- [NVIDIA GPU Operator on OpenShift](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/openshift/contents.html)

## Next Stage

[Stage 030: Private Model Serving](../030-private-model-serving/README.md) deploys the private model serving resources that consume the queue-backed GPU capacity.
