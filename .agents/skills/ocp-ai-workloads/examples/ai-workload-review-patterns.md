# AI Workload Review Patterns

These examples are review patterns, not copy-paste manifests. Verify exact API
versions, CR fields, resource names, and support posture against the official
docs and active cluster schema before committing GitOps resources.

## Kueue Cluster Configuration Shape

```yaml
apiVersion: kueue.openshift.io/v1
kind: Kueue
metadata:
  name: cluster
  namespace: openshift-kueue-operator
spec:
  managementState: Managed
  config:
    integrations:
      frameworks:
        - BatchJob
```

Review points:

- The official examples use `cluster` as the `Kueue` CR name.
- `BatchJob` is the documented default framework integration.
- Add `LeaderWorkerSet` or `JobSet` only when the corresponding operator and
  operand are installed and the namespace is Kueue-managed.
- Verify fair-sharing and gang-scheduling field placement before committing.

## Queue Topology Shape

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
    - coveredResources:
        - cpu
        - memory
        - pods
      flavors:
        - name: default-flavor
          resources:
            - name: cpu
              nominalQuota: 9
            - name: memory
              nominalQuota: 36Gi
            - name: pods
              nominalQuota: 5
---
apiVersion: kueue.x-k8s.io/v1beta2
kind: LocalQueue
metadata:
  name: user-queue
  namespace: team-namespace
spec:
  clusterQueue: cluster-queue
```

Review points:

- Add GPU resources only after `nvidia.com/gpu` capacity is verified.
- Keep `ResourceFlavor` node labels tied to observed node labels.
- Ensure team namespaces are explicitly labeled with
  `kueue.openshift.io/managed=true`.

## Queued Job Shape

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  generateName: sample-job-
  namespace: team-namespace
  labels:
    kueue.x-k8s.io/queue-name: user-queue
spec:
  parallelism: 3
  completions: 3
  template:
    spec:
      containers:
        - name: sample
          image: registry.k8s.io/e2e-test-images/agnhost:2.53
          args:
            - entrypoint-tester
            - hello
            - world
          resources:
            requests:
              cpu: "1"
              memory: 200Mi
      restartPolicy: Never
```

Review points:

- Every queued workload needs a local queue label and pod resource requests.
- Check `Workload` objects after submission before debugging pod scheduling.
- Do not use upstream example images in active demo GitOps without replacing
  them with approved project images.

## Distributed Workload Handoff

Use OCP AI workload skills for platform operators and APIs:

- `Kueue`
- `ClusterQueue`
- `ResourceFlavor`
- `LocalQueue`
- `Workload`
- `LeaderWorkerSet`
- `JobSet`

Use RHOAI skills for OpenShift AI component enablement, dashboard workflows,
distributed workload notebooks, pipelines, model serving, and llm-d.
