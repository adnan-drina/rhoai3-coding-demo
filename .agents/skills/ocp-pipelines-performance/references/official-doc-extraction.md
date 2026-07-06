# Official Doc Extraction

Use this extraction to keep OpenShift Pipelines performance and resource
management content grounded in official Red Hat sources. When implementation
needs exact CR fields, verify the active cluster schema with `oc explain` or
`oc get crd` before authoring GitOps manifests.

## Performance Benchmarks

Red Hat benchmark results (OpenShift Pipelines 1.13, no significant difference
from 1.12):

- Cluster: 3-node OpenShift Container Platform on AWS `m6a.2xlarge` nodes
- Up to 60 simple test pipelines ran concurrently without significant failures
  or delays
- Beyond 60 concurrent pipelines, the following metrics increased:
  - number of failed pipeline runs
  - average duration of a pipeline run
  - pod creation latency
  - work queue depth
  - number of pending pods
- Results depend on the test configuration; production results will vary

## High-Availability Mode

Enable HA mode through the `TektonConfig` CR to improve controller throughput:

```yaml
apiVersion: operator.tekton.dev/v1alpha1
kind: TektonConfig
metadata:
  name: config
spec:
  pipeline:
    performance:
      disable-ha: false
      buckets: 5          # range: 5–10
      replicas: 3         # must be > 2 and <= buckets
```

Effect: reduces pipeline execution times and the delay from creating a
`TaskRun` CR to the start of the pod executing the task run. Higher numbers
for buckets and replicas are generally beneficial. Monitor for CPU and memory
exhaustion on nodes.

## Resource Consumption Model

Each task runs as a pod; each step runs as a container within that pod.

Default behavior:

- Step resource requests default to `BestEffort` (zero) or to the minimums
  set through `LimitRange` in the project.
- When `LimitRange` minimum values are set, OpenShift Pipelines uses those
  minimums instead of zero.

Step resource configuration:

```yaml
spec:
  steps:
  - name: <step_name>
    computeResources:
      requests:
        memory: 2Gi
        cpu: 600m
      limits:
        memory: 4Gi
        cpu: 900m
```

LimitRange example:

```yaml
apiVersion: v1
kind: LimitRange
metadata:
  name: <limit_container_resource>
spec:
  limits:
  - max:
      cpu: "600m"
      memory: "2Gi"
    min:
      cpu: "200m"
      memory: "100Mi"
    default:
      cpu: "500m"
      memory: "800Mi"
    defaultRequest:
      cpu: "100m"
      memory: "100Mi"
    type: Container
```

## Mitigating Extra Resource Consumption

OpenShift Pipelines requests the maximum CPU, memory, and ephemeral storage of
any single step for the pod, setting all other step requests to zero. With
`LimitRange`, init containers use the max limit and each container uses the
min, which can over-allocate total pod memory.

Example: a task with two steps and a LimitRange `min: 500Mi`, `max: 1Gi`
results in a total pod memory request of 2Gi. A task with ten steps under the
same LimitRange results in a 5Gi total memory request.

Mitigation strategies:

- Reduce the number of steps by grouping into one bigger step using script
  blocks and a shared image.
- Distribute independent steps across multiple tasks to lower per-task
  requests.

## Step-Level Compute Resource Overrides in PipelineRun

Override step compute resources in referenced tasks without modifying the
original Task definition using `spec.taskRunSpecs[*].stepSpecs`:

```yaml
apiVersion: tekton.dev/v1
kind: PipelineRun
metadata:
  name: example-run
spec:
  taskRunSpecs:
    - pipelineTaskName: ecosystem-cert-preflight-checks
      stepSpecs:
        - name: app-check
          computeResources:
            requests:
              memory: 4Gi
            limits:
              memory: 4Gi
```

Fields:

- `pipelineTaskName`: the task name defined in the Pipeline
- `stepSpecs[].name`: the step within the task
- `computeResources`: CPU and memory allocation for the step

To guarantee allocation, set identical values for `requests` and `limits`.

Step-level overrides differ from task-level compute resources:

- **Step-level override**: allocates resources to a specific step
- **Task-level compute resources**: distributes resources evenly across all
  steps in a task

## PriorityClass-Based Resource Quota

When direct per-pipeline quota is not available, use `PriorityClass` scoping:

Step 1 — Create a PriorityClass:

```yaml
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: pipeline1-pc
value: 1000000
description: "Priority class for pipeline1"
```

Step 2 — Create a scoped ResourceQuota:

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: pipeline1-rq
spec:
  hard:
    cpu: "1000"
    memory: 200Gi
    pods: "10"
  scopeSelector:
    matchExpressions:
    - operator: In
      scopeName: PriorityClass
      values: ["pipeline1-pc"]
```

Step 3 — Reference in PipelineRun:

```yaml
apiVersion: tekton.dev/v1
kind: PipelineRun
metadata:
  generateName: petclinic-run-
spec:
  pipelineRef:
    name: maven-build
  taskRunTemplate:
    podTemplate:
      priorityClassName: pipeline1-pc
  workspaces:
  - name: local-maven-repo
    emptyDir: {}
  - name: source
    volumeClaimTemplate:
      spec:
        accessModes:
          - ReadWriteOnce
        resources:
          requests:
            storage: 200M
```

Verify quota usage:

```bash
oc describe quota
```

Since OpenShift Pipelines 1.17, the priority class applies to all pods created
for a task, including the affinity assistant pod.

ResourceQuota error mitigation: when pods fail with `failed quota: <name> must
specify cpu, memory`, either specify a `LimitRange` for the namespace
(recommended) or explicitly define requests and limits for all containers.

## Pod Eviction Protection via PodDisruptionBudget

Labels on a `PipelineRun` propagate to `TaskRun` resources and their pods.
A `PodDisruptionBudget` targeting those labels prevents voluntary eviction.

PDB configuration (one-time per namespace):

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: tekton-protect
  namespace: ci
spec:
  minAvailable: 1
  selector:
    matchLabels:
      pdb: protect
```

Apply to PipelineRun:

```yaml
apiVersion: tekton.dev/v1
kind: PipelineRun
metadata:
  name: infra-change
  namespace: ci
  labels:
    pdb: protect
spec:
  pipelineRef:
    name: infra-change-pipeline
```

Verification:

```bash
oc get pdb tekton-protect -n ci
oc adm drain <node-name> --ignore-daemonsets   # drain pauses while pod runs
```

## Multicluster Support (Technology Preview)

Multicluster support is a Technology Preview feature. Not supported with Red
Hat production SLAs. Not recommended for production use.

### Architecture

Hub-and-spoke model:

- **Hub cluster**: manages pipeline run definitions and statuses; schedules
  runs to spoke clusters via Kueue/MultiKueue; does not execute workloads
- **Spoke clusters**: full OpenShift Pipelines installation; execute runs
  scheduled from the hub; report status back; auto-cleanup after completion

Key hub cluster components:

- Kueue with MultiKueue enabled
- Tekton Kueue plugin
- proxy-aee service (log/status streaming from spokes)
- syncer-service (secret synchronization hub-to-spoke)

### Hub Cluster Configuration

Prerequisites: OpenShift Pipelines Operator installed, `cluster-admin` access,
`oc` CLI, spoke kubeconfig files.

1. Install Red Hat Build of Kueue (RHBoK) operator 1.3+
2. Create Kueue CR with Tekton integration:

```yaml
apiVersion: kueue.openshift.io/v1
kind: Kueue
metadata:
  name: cluster
spec:
  config:
    integrations:
      externalFrameworks:
      - group: tekton.dev
        resource: pipelineruns
        version: v1
      frameworks:
      - BatchJob
      - Pod
      - Deployment
    multiKueue:
      externalFrameworks:
      - group: tekton.dev
        resource: pipelineruns
        version: v1
  logLevel: Normal
  managementState: Managed
  operatorLogLevel: Normal
```

3. Create RBAC for Kueue controller to manage PipelineRuns:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: kueue-tekton-permissions
rules:
- apiGroups: ["tekton.dev"]
  resources: ["pipelineruns", "pipelineruns/status"]
  verbs: ["create", "delete", "get", "list", "patch", "update", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: kueue-tekton-permissions-binding
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: kueue-tekton-permissions
subjects:
- kind: ServiceAccount
  name: kueue-controller-manager
  namespace: openshift-kueue-operator
```

4. Create spoke kubeconfig secrets in `openshift-kueue-operator` namespace:

```bash
export KUEUE_NAMESPACE=openshift-kueue-operator
oc create secret generic <spoke_secret_name> \
  -n ${KUEUE_NAMESPACE} \
  --from-file=kubeconfig=<path_to_spoke_kubeconfig>
```

5. Create NetworkPolicy allowing egress from Kueue pods:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: kueue-allow-egress-external
  namespace: openshift-kueue-operator
spec:
  podSelector:
    matchLabels:
      app.openshift.io/name: kueue
  policyTypes:
  - Egress
  egress:
  - ports:
    - port: 443
      protocol: TCP
    - port: 80
      protocol: TCP
```

6. Create Kueue resources (ResourceFlavor, ClusterQueue, LocalQueue,
   AdmissionCheck, MultiKueueConfig, MultiKueueCluster):

```yaml
apiVersion: kueue.x-k8s.io/v1beta2
kind: ResourceFlavor
metadata:
  name: default-flavor
---
apiVersion: kueue.x-k8s.io/v1beta2
kind: ClusterQueue
metadata:
  name: cluster-queue
spec:
  namespaceSelector: {}
  resourceGroups:
  - coveredResources: ["cpu", "memory", "tekton.dev/pipelineruns"]
    flavors:
    - name: default-flavor
      resources:
      - name: cpu
        nominalQuota: 9
      - name: memory
        nominalQuota: 36Gi
      - name: tekton.dev/pipelineruns
        nominalQuota: 10
  admissionChecksStrategy:
    admissionChecks:
    - name: sample-multikueue
---
apiVersion: kueue.x-k8s.io/v1beta2
kind: LocalQueue
metadata:
  namespace: default
  name: pipelines-queue
spec:
  clusterQueue: cluster-queue
---
apiVersion: kueue.x-k8s.io/v1beta2
kind: AdmissionCheck
metadata:
  name: sample-multikueue
spec:
  controllerName: kueue.x-k8s.io/multikueue
  parameters:
    apiGroup: kueue.x-k8s.io
    kind: MultiKueueConfig
    name: multikueue-config
---
apiVersion: kueue.x-k8s.io/v1beta2
kind: MultiKueueConfig
metadata:
  name: multikueue-config
spec:
  clusters:
  - <spoke_cluster_name_1>
  - <spoke_cluster_name_2>
---
apiVersion: kueue.x-k8s.io/v1beta2
kind: MultiKueueCluster
metadata:
  name: <spoke_cluster_name_1>
spec:
  clusterSource:
    kubeConfig:
      locationType: Secret
      location: <spoke_secret_name_1>
```

7. Enable multicluster in TektonConfig:

```bash
oc patch tektonconfig config --type=merge -p '{
  "spec": {
    "scheduler": {
      "disabled": false,
      "multi-cluster-disabled": false,
      "multi-cluster-role": "Hub"
    }
  }
}'
```

8. Optional: if Tekton Results is enabled, disable the watcher and retention
   policy agent to prevent conflicts with spoke-executed runs:

```bash
oc patch tektonconfig config --type=merge -p '{
  "spec": {
    "result": {
      "options": {
        "deployments": {
          "tekton-results-watcher": {
            "spec": { "replicas": 0 }
          },
          "tekton-results-retention-policy-agent": {
            "spec": { "replicas": 0 }
          }
        }
      }
    }
  }
}'
```

### Spoke Cluster Configuration

Prerequisites: OpenShift Pipelines Operator installed on each spoke,
`cluster-admin` access, `oc` CLI, hub cluster configured.

1. Install Red Hat Build of Kueue operator 1.3+ (same Kueue CR as hub)
2. Create service account and RBAC for MultiKueue (`multikueue-sa`):
   - ClusterRole with permissions for batch jobs, pods, secrets, Kueue
     workloads, and Tekton pipelineruns/taskruns
   - ClusterRoleBinding binding the service account
3. Create NetworkPolicy allowing egress from Kueue pods (same as hub)
4. Create Kueue resources (ResourceFlavor, ClusterQueue with
   `tekton.dev/pipelineruns` nominalQuota: 1, LocalQueue)
5. Enable multicluster in TektonConfig:

```bash
oc patch tektonconfig config --type=merge -p '{
  "spec": {
    "scheduler": {
      "disabled": false,
      "multi-cluster-disabled": false,
      "multi-cluster-role": "Spoke"
    }
  }
}'
```

6. Generate kubeconfig for hub cluster authentication:
   - Create a long-lived token secret for the service account
   - Retrieve token, CA cert, and server URL
   - Generate kubeconfig file and provide to hub cluster administrator

### Verification

On the hub cluster:

```bash
# ClusterQueue status
oc get clusterqueues cluster-queue -o jsonpath="{range .status.conditions[?(@.type == 'Active')]}CQ - Active: {@.status} Reason: {@.reason} Message: {@.message}{'\n'}{end}"

# AdmissionCheck status
oc get admissionchecks sample-multikueue -o jsonpath="{range .status.conditions[?(@.type == 'Active')]}AC - Active: {@.status} Reason: {@.reason} Message: {@.message}{'\n'}{end}"

# MultiKueueCluster status (per spoke)
oc get multikueuecluster <spoke_cluster_name> -o jsonpath="{range .status.conditions[?(@.type == 'Active')]}MC - Active: {@.status} Reason: {@.reason} Message: {@.message}{'\n'}{end}"
```

All checks should show `Active: True`.

Test pipeline run:

```yaml
apiVersion: tekton.dev/v1
kind: PipelineRun
metadata:
  generateName: test-multicluster-
  namespace: default
  labels:
    kueue.x-k8s.io/queue-name: pipelines-queue
spec:
  managedBy: kueue.x-k8s.io/multikueue
  pipelineSpec:
    tasks:
    - name: test-task
      taskSpec:
        steps:
        - name: echo
          image: registry.access.redhat.com/ubi9/ubi-minimal:latest
          script: |
            #!/bin/sh
            echo "Multicluster test successful"
```

### Creating Pipeline Runs in a Multicluster Environment

Required labels and fields:

- `metadata.labels.kueue.x-k8s.io/queue-name: pipelines-queue`
- `spec.managedBy: kueue.x-k8s.io/multikueue` (optional; webhook adds
  automatically if omitted)

Pipeline definitions can use:

- Embedded pipeline specifications
- Remote resolvers (HTTP, Git, Bundle)
- Pipelines as Code (PAC) with `managedBy` field; syncer-service handles
  secret synchronization automatically

Cannot use:

- `pipelineRef`/`taskRef` with the cluster resolver
- `tekton.dev/v1beta1` API version

### Kueue Resource Reference

| Resource | Purpose |
|----------|---------|
| `ResourceFlavor` | Defines available resource types |
| `ClusterQueue` | Manages cross-namespace quotas and admission checks |
| `LocalQueue` | Namespace-scoped queue referencing a ClusterQueue |
| `AdmissionCheck` | Condition workloads must satisfy before admission |
| `MultiKueueConfig` | Lists spoke clusters available for scheduling |
| `MultiKueueCluster` | Connection details for a spoke cluster (kubeconfig secret) |

All Kueue resources use `apiVersion: kueue.x-k8s.io/v1beta2`.

### Known Limitations

Web console:

- Stop action does not work for spoke-executing pipeline runs
- Cancel action may be disabled or unavailable
- Workaround: cancel directly on spoke cluster via
  `oc patch pipelinerun <name> -n <ns> --type merge -p '{"spec":{"status":"Cancelled"}}'`
- Logs/status display may have delays if proxy service is unavailable

CLI (`tkn`):

- `tkn taskrun list` returns no results on hub
- `tkn pipelinerun describe` fails with "failed to find get taskruns"
- `tkn pipelinerun logs` fails with "taskruns.tekton.dev not found"
- `tkn pipelinerun cancel` does not work
- `tkn pipeline start` creates runs without `managedBy` field
- On spoke clusters, `tkn pipelinerun list` only works during active execution

Other:

- Pipeline run name must not exceed 45 characters
- Namespaces must be pre-created on spoke clusters
- LocalQueue must exist in matching namespace on each spoke
- Only `tekton.dev/v1` API version supported
- Only pipeline runs and associated ConfigMaps/Secrets are synchronized
