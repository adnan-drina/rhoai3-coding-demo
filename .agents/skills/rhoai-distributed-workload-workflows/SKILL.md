---
name: rhoai-distributed-workload-workflows
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when documenting, reviewing, or authoring Red Hat OpenShift AI data
  scientist workflows for distributed workloads: preparing workbenches and
  training images, authenticating to OpenShift from notebooks, running
  Ray-based workloads with CodeFlare SDK, running distributed workloads from AI
  pipelines or disconnected environments, creating Kubeflow Training Operator
  PyTorchJob workloads, using the Training Operator SDK, running Kubeflow
  Trainer v2 TrainJob workloads, configuring training runtimes, fine-tuning
  with OSFT or SFT, configuring PVC or S3 checkpointing, monitoring distributed
  workload metrics and status, and troubleshooting user-facing Ray, Kueue, and
  training job failures. Do NOT use for distributed workload component
  installation (use rhoai-distributed-workloads), Kueue integration and
  namespace enforcement (use rhoai-kueue-workload-management), administrator
  ResourceFlavor/ClusterQueue/LocalQueue/RDMA operations (use
  rhoai-distributed-workload-operations), GPU enablement (use
  rhoai-nvidia-gpu-accelerators), Kubeflow Spark Operator SparkApplication
  resources (use rhoai-kubeflow-spark-operator), or live cluster changes
  without the OpenShift safety guard.
---

# RHOAI Distributed Workload Workflows

Use this skill for OpenShift AI user workflows that run distributed data
processing, distributed training, and model fine-tuning jobs on the active
product baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product workflow details.
Official Red Hat documentation is product authority. This skill adapts the
official Working with distributed workloads guide to this repo's demo workflow
and GitOps review model.

## Scope

This skill covers:

- distributed workload concepts and user-facing benefits
- CodeFlare SDK, KubeRay, Kueue, Kubeflow Training Operator, Training Operator
  SDK, and Kubeflow Trainer v2 workflow boundaries
- preparing a workbench for distributed training
- OpenShift server/token authentication from notebooks and CLI sessions
- base training images and custom training image handling
- Ray-based workloads from Jupyter notebooks, AI pipelines, and disconnected
  environments
- Training Operator `PyTorchJob` training scripts and resource patterns
- Training Operator SDK job configuration, execution, and job API methods
- Kubeflow Trainer v2 `TrainJob`, training runtimes, suspend/resume/delete
  workflows, SDK usage, and fine-tuning workflows
- PVC and S3-compatible checkpointing for Kubeflow Trainer v2
- distributed workload project metrics, status, and Kueue alerts
- user troubleshooting for Ray, Kueue webhook, LocalQueue, credentials, and
  slow image-pull failures

Use other skills for adjacent work:

- `rhoai-distributed-workloads` for installing distributed workload components
  and setting `DataScienceCluster` component states
- `rhoai-kueue-workload-management` for Kueue integration, namespace queue
  enforcement, default queue behavior, dashboard Kueue flags, and hardware
  profile restrictions
- `rhoai-distributed-workload-operations` for administrator quota resources,
  `ResourceFlavor`, `ClusterQueue`, `LocalQueue`, RDMA setup boundaries, and
  administrator troubleshooting
- `rhoai-workbench-image-import` and `rhoai-workbenches-custom-images` for
  custom workbench image handling
- `rhoai-nvidia-gpu-accelerators` for accelerator enablement and this demo's
  NVIDIA-first GPU posture
- `rhoai-storage-classes` and `rhoai-connection-types` for storage and
  S3-compatible object storage connection context
- `rhoai-s3-object-storage-data` for workbench Boto3 object storage access,
  endpoint formatting, and S3-compatible object operations
- `rhoai-kfp-pipeline-authoring` for AI pipeline implementation details
- `rhoai-kubeflow-spark-operator` for Spark data processing applications and
  `SparkApplication` resources
- `rhoai-model-customization-training` for Training Hub algorithm selection,
  MLflow tracking handoff, and Kubeflow Trainer fine-tuning context
- `rhoai-model-evaluation` for evaluation workflows and evidence after
  training or fine-tuning

## Demo Policy

For this repo:

- Treat this skill as the user workflow layer. Installation, queue policy, and
  quota/RDMA resources remain in adjacent install/admin skills.
- Prefer NVIDIA/CUDA training examples for the active demo unless the user
  explicitly asks for AMD coverage.
- Use `nvidia.com/gpu` in demo workload examples unless the active accelerator
  policy changes.
- Never store OpenShift tokens, API servers, Hugging Face tokens, S3
  credentials, or registry credentials in notebooks, Git, or committed
  manifests.
- Use workbench/project service accounts only where the official workflow and
  active RBAC allow them; otherwise use explicit user token authentication.
- Treat AI pipeline workloads as launch surfaces for distributed data science
  jobs, not as distributed workloads metrics entries; the official guide says
  AI pipeline workloads are not managed by the distributed workloads feature
  and are not included in distributed workload metrics.
- Use checkpointing for long-running training jobs. Choose PVC for simpler
  shared storage and S3-compatible object storage when portability and
  asynchronous upload are needed.
- For very large models, document local model-cache and checkpoint storage
  needs before promising a training workflow.
- Use dashboard workload metrics and Kueue status to explain queueing and
  resource pressure to demo audiences.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/source-capture.md` and
   `references/official-doc-extraction.md`.
3. Confirm prerequisites with:
   - `rhoai-distributed-workloads`
   - `rhoai-kueue-workload-management`
   - `rhoai-distributed-workload-operations`
   - `rhoai-nvidia-gpu-accelerators`
4. Decide whether the task is:
   - workbench or training image preparation
   - Ray/CodeFlare notebook workflow
   - AI pipelines distributed workload launch
   - Training Operator `PyTorchJob`
   - Training Operator SDK
   - Kubeflow Trainer v2 `TrainJob`
   - fine-tuning workflow
   - checkpointing
   - monitoring
   - user troubleshooting
5. Use `examples/distributed-workload-workflow-patterns.md` for focused review
   patterns.
6. Validate with `references/validation-checklist.md`.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/distributed-workload-workflow-patterns.md`
