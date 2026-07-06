# DataScienceCluster Distributed Workloads States

These snippets show the official component-state pattern. Verify prerequisites
before committing real GitOps.

## Pipelines Only

```yaml
spec:
  components:
    dashboard:
      managementState: Managed
    aipipelines:
      managementState: Managed
    kueue:
      managementState: Unmanaged
    ray:
      managementState: Managed
    trainingoperator:
      managementState: Managed
    workbenches:
      managementState: Removed
```

## Workbenches Only

```yaml
spec:
  components:
    dashboard:
      managementState: Managed
    aipipelines:
      managementState: Removed
    kueue:
      managementState: Unmanaged
    ray:
      managementState: Managed
    trainingoperator:
      managementState: Managed
    workbenches:
      managementState: Managed
```

## Pipelines And Workbenches

```yaml
spec:
  components:
    dashboard:
      managementState: Managed
    aipipelines:
      managementState: Managed
    kueue:
      managementState: Unmanaged
    ray:
      managementState: Managed
    trainingoperator:
      managementState: Managed
    workbenches:
      managementState: Managed
```

Review notes:

- `kueue` remains `Unmanaged` because the Red Hat build of Kueue Operator
  manages Kueue.
- Install or sync prerequisite Operators before enabling these component states.
- Configure queues and workload policy separately with the official managing
  distributed workloads documentation.
