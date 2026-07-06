# Distributed Workload Workflow Patterns

These examples are review patterns. Verify active CRDs, installed components,
queue names, image tags, storage classes, SDK availability, and project quota
before copying anything into GitOps, notebooks, or demo scripts.

## User Authentication Pattern

```text
server: value from Copy login command
token: value from Copy login command
```

Review points:

- Treat both values as credentials.
- Do not save them in notebook files.
- Do not commit them to Git.
- Tokens expire after 24 hours.

## Ray/CodeFlare Queue Pattern

```python
from codeflare_sdk import Cluster, ClusterConfiguration

cluster = Cluster(
    ClusterConfiguration(
        namespace="<project-name>",
        local_queue="<local-queue-name>",
    )
)
```

Review points:

- Confirm the selected workbench image includes CodeFlare SDK.
- Provide `local_queue` when no default LocalQueue exists.
- Check `Workload.status.conditions.message` and
  `RayCluster.status.conditions.message` when the Ray cluster does not start.

## Training Operator PyTorchJob Review Shape

```yaml
apiVersion: kubeflow.org/v1
kind: PyTorchJob
metadata:
  name: <job-name>
  namespace: <project-name>
spec:
  pytorchReplicaSpecs:
    Master:
      replicas: 1
    Worker:
      replicas: <worker-count>
```

Review points:

- Mount or provide the training script through a reviewed mechanism.
- Set CPU, memory, and `nvidia.com/gpu` requests and limits to values the
  LocalQueue can admit.
- Monitor with `oc get pytorchjobs -n <project-name>` and pod logs.

## Kubeflow Trainer V2 TrainJob Review Shape

```yaml
apiVersion: trainer.kubeflow.org/v1alpha1
kind: TrainJob
metadata:
  name: <job-name>
  namespace: <project-name>
spec:
  runtimeRef:
    name: <runtime-name>
    kind: ClusterTrainingRuntime
  trainer:
    command: ["torchrun", "/workspace/train.py"]
    numNodes: 2
    resourcesPerNode:
      requests:
        nvidia.com/gpu: 1
      limits:
        nvidia.com/gpu: 1
```

Review points:

- Confirm the runtime exists before submitting the job.
- Use `TrainingRuntime` only when a reviewed project or custom runtime exists.
- Use `spec.suspend` only when the workflow needs explicit suspend/resume
  behavior.

## Checkpointing Decision Pattern

| Backend | Good fit | Watchpoints |
|---------|----------|-------------|
| PVC | simpler shared storage | capacity, RWX availability, `save_total_limit` |
| S3-compatible storage | portable, asynchronous upload | data connection, lifecycle cleanup, local `emptyDir` pressure |

Review points:

- Avoid very frequent `save_steps` because checkpoint writes can slow training.
- With S3, uploaded checkpoints remain until cleaned up separately.
- Plan per-pod model cache storage for large models.

## Monitoring Pattern

```text
OpenShift AI dashboard -> Observe & monitor -> Workload metrics
```

Review points:

- Use Project metrics for CPU and memory usage.
- Use Distributed workload status for Pending, Inadmissible, Admitted, Running,
  Evicted, Succeeded, or Failed states.
- Do not include AI pipeline workloads in distributed workload metrics.

## User Troubleshooting Pattern

```bash
oc get workloads -n <project-name>
oc get rayclusters -n <project-name>
oc get localqueues -n <project-name>
oc get pods -n <project-name>
```

Review points:

- Suspended or Starting Ray clusters usually require condition-message review.
- LocalQueue errors usually mean missing default queue, wrong queue name, or
  wrong namespace.
- Forbidden RayCluster errors usually point to wrong notebook credentials.
- Slow image pulls can exceed the Kueue wait period and fail the workload.
