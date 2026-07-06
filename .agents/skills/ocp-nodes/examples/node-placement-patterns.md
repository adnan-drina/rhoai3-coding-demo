# Node Placement Patterns

## Node Inventory Snapshot

```text
Purpose: understand where demo workloads can run before adding placement rules.
Commands: guarded `oc get nodes -o wide`, `oc get nodes --show-labels`,
`oc describe node <node>`, and `oc adm top nodes`.
Decision: record node roles, capacity, allocatable resources, labels, taints,
and pressure conditions before writing selectors or affinity.
```

## Node Affinity Shape

Use this only as a field-placement reminder. Verify the target labels before
using this in active manifests.

```yaml
spec:
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
          - matchExpressions:
              - key: <verified-node-label>
                operator: In
                values:
                  - <verified-value>
```

## Toleration Shape

Use tolerations only when a matching taint is intentionally present.

```yaml
spec:
  tolerations:
    - key: <taint-key>
      operator: Equal
      value: <taint-value>
      effect: NoSchedule
```

## Topology Spread Shape

```yaml
spec:
  topologySpreadConstraints:
    - maxSkew: 1
      topologyKey: topology.kubernetes.io/zone
      whenUnsatisfiable: DoNotSchedule
      labelSelector:
        matchLabels:
          app.kubernetes.io/name: <app-name>
```

## Node Maintenance Note

```text
Before cordon, drain, reboot, or deletion:
- confirm the target cluster with the repo environment guard
- inspect pods on the node
- identify storage-backed workloads and disruption budgets
- confirm whether the node is control-plane, worker, GPU, or single-node
  OpenShift
- record the official OCP procedure used
```
