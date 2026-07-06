# Validation Checklist

Use this checklist before accepting distributed workload user documentation,
notebooks, training manifests, pipeline snippets, or demo scripts.

## Source Alignment

- Product links use the active baseline in `docs/PLATFORM_BASELINE.md`.
- The official Working with distributed workloads source is recorded when the
  workflow is introduced.
- Installation and component state are checked with
  `rhoai-distributed-workloads`.
- Kueue integration, namespace enforcement, dashboard Kueue behavior, and
  default queue behavior are checked with `rhoai-kueue-workload-management`.
- Administrator quota, `ResourceFlavor`, `ClusterQueue`, `LocalQueue`, and
  RDMA work are checked with `rhoai-distributed-workload-operations`.
- GPU prerequisites are checked with `rhoai-nvidia-gpu-accelerators`.

## Environment Preparation

- Workbench image is appropriate for the workload and includes needed SDKs or
  packages.
- Hardware profile requests match available project quota and accelerator
  policy.
- Storage is attached when data or checkpoints must be shared.
- RWX storage is used when the workload requires shared multi-node access.
- OpenShift token and server values are not stored in notebooks or Git.
- Training image selection matches workload type, accelerator framework, and
  Python version.
- Custom images do not require uncommitted credentials or ad hoc package
  installation at demo time.

## Ray And CodeFlare Review

- CodeFlare SDK is available in the selected workbench image or intentionally
  installed for the session.
- Namespace/project values match the active project.
- LocalQueue is specified when no default LocalQueue exists.
- RayCluster and Workload status are checked after cluster creation.
- Jobs are stopped and clusters are deleted when no longer needed.
- Disconnected workflows do not depend on internet-only notebooks, packages,
  images, or registries.

## Training Operator Review

- `PyTorchJob` resources use `apiVersion: kubeflow.org/v1`.
- Training scripts are mounted or otherwise provided through a reviewed
  mechanism such as a `ConfigMap`.
- Master and Worker replica counts match the intended topology.
- GPU resource keys match the active accelerator policy; default demo key is
  `nvidia.com/gpu`.
- NCCL, DDP, or FSDP examples are adapted intentionally and not copied without
  resource review.
- Jobs are monitored through `oc get pytorchjobs` and pod logs.
- Jobs are deleted when no longer needed.

## Kubeflow Trainer V2 Review

- `TrainJob` resources use `apiVersion: trainer.kubeflow.org/v1alpha1`.
- `runtimeRef` points to an available `ClusterTrainingRuntime` or
  `TrainingRuntime`.
- `resourcesPerNode`, `numNodes`, and command values match target resources.
- Suspend, resume, and delete workflows are documented when used.
- SDK-based jobs confirm SDK availability in the selected workbench image.
- Fine-tuning examples record OSFT or SFT parameter choices and training data
  format assumptions.

## Checkpointing Review

- PVC or S3-compatible checkpointing is selected intentionally.
- PVC size and access mode are sufficient for the model and topology.
- S3-compatible object storage data connection exists before S3 checkpointing
  is used.
- S3 lifecycle or cleanup ownership is documented.
- `save_steps` and `save_total_limit` values balance recovery granularity,
  throughput, and storage capacity.
- Per-pod model cache requirements are documented for large models.
- Training pod local storage is monitored during long runs.

## Monitoring And Troubleshooting Review

- Dashboard path Observe & monitor -> Workload metrics is used for project
  metrics and workload status.
- AI pipeline workloads are not described as included in distributed workload
  metrics.
- Workload statuses are interpreted correctly: Pending, Inadmissible,
  Admitted, Running, Evicted, Succeeded, and Failed.
- Kueue alerts are reviewed from OpenShift Console Observe -> Alerting when
  troubleshooting queue health.
- Ray troubleshooting checks Workload and RayCluster condition messages.
- LocalQueue errors check default queue, explicit `local_queue`, spelling, and
  namespace.
- Credential errors check the notebook `TokenAuthentication` token and server.
- Large image-pull failures account for Kueue's documented default wait before
  failing a workload.

## Optional Read-Only Checks

Run only after following the OpenShift safety guard in `AGENTS.md`:

```bash
oc get rayclusters -n <namespace>
oc get workloads -n <namespace>
oc get localqueues -n <namespace>
oc get pytorchjobs -n <namespace>
oc get trainjobs -n <namespace>
oc get pods -n <namespace>
```

Schema checks:

```bash
oc explain raycluster.spec
oc explain workload.status.conditions
oc explain pytorchjob.spec
oc explain trainjob.spec
oc explain trainjob.spec.runtimeRef
```

## Fail Conditions

Stop and correct the work if any of these are true:

- Tokens or API servers are committed or saved in notebooks.
- Training examples request GPU resources that the project quota cannot admit.
- A LocalQueue is assumed but neither default queue nor explicit queue exists.
- AI pipeline workloads are counted as distributed workload metrics.
- A `PyTorchJob` or `TrainJob` example uses an API version not supported by the
  active baseline.
- S3 checkpointing is used without cleanup ownership.
- Large-model training ignores per-pod model cache and checkpoint storage
  requirements.
- RDMA/RoCE behavior is claimed without administrator-side implementation.
