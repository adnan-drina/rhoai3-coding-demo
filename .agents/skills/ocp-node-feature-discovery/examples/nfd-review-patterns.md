# NFD Review Patterns

These examples are review patterns, not copy-paste manifests. Verify exact API
fields and operand image values against the official docs and active cluster
schema before committing GitOps resources.

## NodeFeatureDiscovery Instance Shape

```yaml
apiVersion: nfd.openshift.io/v1
kind: NodeFeatureDiscovery
metadata:
  name: nfd-instance
spec:
  operand:
    image: <verified-nfd-operand-image>
  workerConfig:
    configData: |
      core:
        sources:
          - all
        noPublish: false
```

Review points:

- `operand.image` must be explicit when the custom resource is created
  manually or through GitOps rather than being fully populated by OLM.
- `sources: all` is the documented default posture, but keep it explicit only
  when the implementation benefits from clear GitOps intent.
- `noPublish: false` is required when the deployment should actually publish
  feature labels.

## NodeFeatureRule Pattern

```yaml
apiVersion: nfd.openshift.io/v1
kind: NodeFeatureRule
metadata:
  name: example-rule
spec:
  rules:
    - name: example rule
      labels:
        example-custom-feature: "true"
      matchFeatures:
        - feature: kernel.loadedmodule
          matchExpressions:
            veth:
              op: Exists
        - feature: pci.device
          matchExpressions:
            vendor:
              op: In
              value:
                - "8086"
```

Review points:

- Replace example labels with project-owned names.
- Verify every `feature` source and `matchExpressions` key against observed NFD
  features or official examples.
- Account for the documented relabeling delay before treating labels as
  missing.
- Add taints only when workload tolerations and scheduling intent are already
  documented.

## GPU Label Review Handoff

Use NFD to answer "what hardware features did the node expose?" Use the NVIDIA
GPU Operator and RHOAI skills to answer "is GPU capacity usable by workloads?"

Read-only checks:

```bash
oc get nodes --show-labels | grep feature.node.kubernetes.io
oc describe node <gpu-node-name> | grep -E 'feature.node.kubernetes.io|nvidia.com/gpu'
```

Expected review distinction:

- `feature.node.kubernetes.io/...` labels come from NFD feature discovery.
- `nvidia.com/gpu` allocatable resource comes from NVIDIA device plugin
  integration, not from NFD alone.

## NVIDIA-Only Overlay Pattern

The Red Hat CoP catalog includes an `only-nvidia` instance overlay that narrows
PCI discovery to accelerator-relevant classes and publishes only the vendor
label. Use this as a review pattern, not as an unverified manifest:

```yaml
apiVersion: nfd.openshift.io/v1
kind: NodeFeatureDiscovery
metadata:
  name: nfd-instance
spec:
  topologyUpdater: false
  workerConfig:
    configData: |
      core:
        sleepInterval: 60s
      sources:
        pci:
          deviceClassWhitelist:
            - "0200"
            - "03"
            - "12"
          deviceLabelFields:
            - "vendor"
```

Review points:

- Confirm whether `operand.image` must be explicit in the active OCP version
  before committing GitOps.
- Verify the active CRD field name for topology updater settings.
- Confirm generated node labels before using them in selectors.
- Keep this separate from `nvidia.com/gpu` resource validation.

## Topology Updater Review

Only enable NFD Topology Updater when the implementation needs topology-aware
resource reporting. When enabled, review `NodeResourceTopology` objects before
using their data in workload-placement guidance:

```bash
oc get noderesourcetopology -A
oc get noderesourcetopology <node-name> -o yaml
```
