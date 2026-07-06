# Official Documentation Extraction

This extraction is derived from the official RHOAI 3.4 guide captured in
`source-capture.md`.

## Concept Model

Distributed workloads let data scientists run jobs on multiple OpenShift worker
nodes in parallel. The user-facing value is faster training and data processing,
support for larger datasets, support for more complex models, and queue-based
scheduling when required resources are available.

Infrastructure components named by the guide:

- CodeFlare SDK
- Kubeflow Training Operator
- Kubeflow Training Operator Python SDK
- KubeRay Operator
- Red Hat build of Kueue Operator
- cert-manager Operator

Component selection:

- Ray-based distributed workloads use `kueue` and `ray`.
- Training Operator-based distributed workloads use `trainingoperator` and
  `kueue`.
- Both workload families can use Kueue and supported accelerators.
- CUDA training images are used for NVIDIA GPUs.
- ROCm-based training images are used for AMD GPUs.

Launch surfaces:

- Jupyter notebooks
- Microsoft Visual Studio Code files
- AI pipelines

The guide notes that AI pipeline workloads are not managed by the distributed
workloads feature and are not included in distributed workloads metrics.

## Preparing The Training Environment

Before distributed training or tuning, users prepare:

- a workbench with a suitable workbench image
- OpenShift cluster authentication credentials
- a suitable training image, either a base image supplied with OpenShift AI or
  a custom training image

Workbench prerequisites:

- enough worker nodes with supported accelerators
- Red Hat build of Kueue Operator installed and configured
- required OpenShift AI distributed training components installed
- distributed training resources configured
- supported accelerators configured

Workbench creation review points:

- choose a workbench image appropriate to the workload
- choose a hardware profile with suitable CPU, memory, and accelerator
  requests and limits
- attach or create storage for sharing data between the workbench and training
  runs
- use RWX storage when the workload requires shared multi-node access

## Authentication

Users can retrieve OpenShift API server and token values from the OpenShift
Console Copy login command flow.

Security constraints from the guide:

- token and server values are security credentials
- do not save token and server details in notebook files
- do not store token and server details in Git
- the token expires after 24 hours

Users can authenticate either by setting values in notebook code for supported
SDK authentication flows or by running `oc login --token=<token>
--server=<server>`.

## Training Images

Base training images are optimized with tools and libraries needed for
distributed training jobs. The official guide identifies default base image
families:

- Ray CUDA
- Ray ROCm
- KFTO CUDA
- KFTO ROCm

If preinstalled packages are insufficient, users can:

- install additional libraries after launching a default image for ad hoc use
- create a custom image that includes required libraries or packages

Custom image review points:

- select a base image by training type, accelerator framework, and Python
  version
- build with Podman or another supported container workflow
- push to a registry, optionally the integrated OpenShift image registry
- avoid committing registry credentials

## RoCE And RDMA

The guide includes RoCE networking and RDMA sections for distributed LLM and
multi-node PyTorch workloads. Treat these as advanced network acceleration
topics that require administrator setup and environment support.

Use `rhoai-distributed-workload-operations` for administrator-side RDMA
resources and readiness. Use this skill only to review whether a user workload
expects RDMA/RoCE behavior and whether that expectation has been implemented.

## Ray-Based Workloads

Ray workloads can be launched from Jupyter notebooks by using the CodeFlare
SDK. The official guide covers:

- downloading CodeFlare demo notebooks
- running demo notebooks
- managing Ray clusters from notebooks

Key CodeFlare concepts:

- authenticate to OpenShift
- define a cluster configuration with namespace and queue context
- create or apply a remote Ray cluster
- inspect cluster details and status
- run distributed jobs against the Ray cluster
- stop or delete the Ray cluster when finished

Queue behavior:

- if a default LocalQueue is not configured, the user must specify a local queue
  in the cluster configuration
- a LocalQueue name must exist in the target namespace

Disconnected environments require the relevant images, notebooks, dependencies,
and registries to be available without internet access.

## Training Operator PyTorchJob Workloads

Training Operator workflows can run distributed PyTorch training jobs.

Official resource shape:

- `apiVersion: kubeflow.org/v1`
- `kind: PyTorchJob`
- `spec.pytorchReplicaSpecs`
- `Master` replica spec
- `Worker` replica spec for multi-node training

Official script patterns include:

- NCCL/RCCL communication
- Distributed Data Parallel
- Fully Sharded Data Parallel

The official guide notes that `backend="nccl"` is used for both NVIDIA GPUs and
AMD GPUs; on AMD, the ROCm environment uses RCCL for communication.

Operational workflow:

- create a training script
- create a `ConfigMap` for the script
- create the `PyTorchJob`
- monitor `pytorchjobs`
- check pod logs
- delete the job when finished

## Training Operator SDK

The Training Operator SDK simplifies distributed training job creation.

The official guide covers:

- configuring a training job with the SDK
- running the job
- job-related `TrainingClient` API methods

Use SDK examples as workflow patterns. Verify active SDK package availability
inside the selected workbench image before relying on them.

## Kubeflow Trainer v2

Kubeflow Trainer v2 uses training runtimes and `TrainJob` resources.

Runtime concepts:

- `ClusterTrainingRuntime`: cluster-scoped runtime template
- `TrainingRuntime`: custom runtime resource
- `runtimeRef`: connects a `TrainJob` to a runtime

Official resource shape:

- `apiVersion: trainer.kubeflow.org/v1alpha1`
- `kind: TrainJob`
- `spec.runtimeRef`
- `spec.trainer`
- `spec.trainer.command`
- `spec.trainer.numNodes`
- `spec.trainer.resourcesPerNode`
- `spec.podTemplateOverrides`
- `spec.suspend` when starting a job suspended

Workflow operations:

- create a `TrainJob`
- create a `TrainJob` by using the CLI
- suspend a training job
- resume a training job
- delete a training job
- create a `TrainJob` by using the SDK
- configure JIT checkpointing with a PVC
- disable progress tracking when needed

## Fine-Tuning

The guide includes fine-tuning workflows for Kubeflow Training and Kubeflow
Trainer v2. It covers:

- configuring fine-tuning jobs
- OSFT training parameters
- SFT training parameters
- example fine-tuning notebooks
- training data format
- running fine-tuning jobs
- deleting fine-tuning jobs

Example resource patterns use `resources_per_node` or `resourcesPerNode` and
must be updated for the resources available in the target environment. For AMD
accelerators, examples change `nvidia.com/gpu` to `amd.com/gpu`; this demo
defaults to `nvidia.com/gpu`.

If a gated Hugging Face model is used, tokens must be injected securely and not
committed.

## Checkpointing

Kubeflow Trainer v2 checkpointing options:

- PersistentVolumeClaim
- S3-compatible object storage

PVC checkpointing:

- checkpoints are saved directly to a persistent volume mounted to training
  pods
- simpler setup
- useful when a shared PVC is already available

S3-compatible checkpointing:

- checkpoints are saved to fast local storage first
- checkpoints are uploaded to S3-compatible storage in the background
- upload does not block GPU training
- supported provider examples include AWS S3, MinIO, Ceph RGW, and IBM Cloud
  Object Storage
- requires a Red Hat OpenShift AI data connection for S3-compatible object
  storage

Periodic checkpoint guidance:

- avoid setting `save_steps` too low
- frequent checkpoint saves can slow training throughput
- with PVC storage, `save_total_limit` controls how many checkpoints remain on
  the PVC
- with S3 storage, `save_total_limit` controls local `emptyDir` retention only;
  uploaded S3 checkpoints remain until cleaned up separately
- use S3 lifecycle policies or object deletion for cleanup

Storage planning:

- monitor local storage on training pods with `df` and `du`
- FSDP has predictable consolidation peaks of about two times final checkpoint
  size
- DDP stores final checkpoints primarily on rank 0, creating uneven storage
  pressure
- DeepSpeed ZeRO-3 can have significant consolidation peaks and requires
  additional storage planning

Known limitations:

- training pods do not share a model cache, so each pod can download the full
  pretrained model independently
- very large models require enough per-pod local or mounted storage
- TorchElastic graceful shutdown can be too short for very large checkpointing
  operations

## Monitoring

Dashboard path:

```text
Observe & monitor -> Workload metrics
```

Project metrics include:

- CPU cores currently used by all distributed workloads in the selected project
- memory in GiB currently used by distributed workloads
- top CPU-consuming distributed workloads
- top memory-consuming distributed workloads
- distributed workload resource metrics table with current resource usage and
  workload status

Distributed workload status view includes:

- Pending
- Inadmissible
- Admitted
- Running
- Evicted
- Succeeded
- Failed

Kueue alerts are available from the OpenShift Console Administrator
perspective under Observe -> Alerting. Alert rules called out by the guide
include:

- `KueuePodDown`
- `LowClusterQueueResourceUsage`
- `ResourceReservationExceedsQuota`
- `PendingWorkloadPods`

## User Troubleshooting

Ray cluster suspended:

- inspect `Workload.status.conditions.message`
- inspect `RayCluster.status.conditions.message`
- inspect `ClusterQueue` quota
- reduce requested resources or ask the administrator for more quota

Ray cluster failed:

- a brief initial failed state can resolve during reconciliation
- if failure persists, inspect pod events

Kueue webhook error:

- Kueue pod might not be running
- contact administrator

Ray cluster remains Starting:

- inspect `Workload.status.conditions.message`
- inspect `RayCluster.status.conditions.message`

Default LocalQueue not found:

- either provide `local_queue="<local_queue_name>"` in cluster configuration or
  ask the administrator to create a default LocalQueue

Provided LocalQueue does not exist:

- check LocalQueue spelling
- check namespace/project value
- ensure the LocalQueue exists in the target namespace

Cannot create Ray cluster or submit jobs:

- likely wrong OpenShift credentials in the notebook `TokenAuthentication`
  section
- retrieve token and server from Copy login command and authenticate again

Kueue terminates pod before image pull completes:

- Kueue waits for workload pods to become provisioned and running
- default wait is 5 minutes
- if a large image is still pulling after the wait period, Kueue fails the
  workload and terminates related pods
- inspect pod events and ask the administrator for assistance if needed

## Out Of Scope For This Guide

This guide does not define:

- component installation and activation through `DataScienceCluster`
- queue and quota object ownership
- complete RDMA administrator setup
- GPU Operator installation
- full AI pipeline implementation
- production registry and image governance
- complete model evaluation workflow
