# Red Hat CoP NFD GitOps Pattern

Use this reference when rebuilding Node Feature Discovery GitOps for the
rhoai3-demo NVIDIA GPU path.

## Source Role

The Red Hat Community of Practice GitOps Catalog is a pattern source, not
product support authority. Use official OCP documentation, installed OLM
package metadata, and active CRDs for supported fields and exact channel
availability.

Captured sources:

- https://github.com/redhat-cop/gitops-catalog/tree/main/nfd
- https://raw.githubusercontent.com/redhat-cop/gitops-catalog/main/nfd/operator/base/subscription.yaml
- https://raw.githubusercontent.com/redhat-cop/gitops-catalog/main/nfd/instance/base/node-feature-discovery.yaml
- https://raw.githubusercontent.com/redhat-cop/gitops-catalog/main/nfd/instance/overlays/only-nvidia/patch-node-feature-discovery.yaml
- https://raw.githubusercontent.com/redhat-cop/gitops-catalog/main/nfd/aggregate/overlays/only-nvidia/kustomization.yaml

Capture date: 2026-06-10.

## Reusable Catalog Shape

The catalog item uses the shared Red Hat Operator GitOps layout:

```text
nfd/
  operator/
    base/
      namespace.yaml
      operator-group.yaml
      subscription.yaml
    overlays/
      stable/
  instance/
    base/
      node-feature-discovery.yaml
    overlays/
      default/
      kata/
      only-nvidia/
  aggregate/
    overlays/
      default/
      kata/
      only-nvidia/
```

Reusable ideas:

- Namespace is `openshift-nfd` with cluster-monitoring label enabled.
- OperatorGroup is scoped to `openshift-nfd`.
- Subscription package is `nfd` from `redhat-operators` in
  `openshift-marketplace`.
- Operator base uses a placeholder channel and the stable overlay patches
  `spec.channel` to `stable`.
- Instance base owns a `NodeFeatureDiscovery` named `nfd-instance`.
- Aggregate overlays combine `operator/overlays/stable` with the selected
  instance overlay and use `SkipDryRunOnMissingResource=true` for first sync.

## NVIDIA-Only Overlay

The CoP `only-nvidia` instance overlay patches `NodeFeatureDiscovery` to:

- set `topologyUpdater: false`
- keep `core.sleepInterval: 60s`
- configure PCI discovery with device class whitelist values:
  - `0200`
  - `03`
  - `12`
- publish only the PCI `vendor` label field

This is a useful starting point for the demo because the project intentionally
uses NVIDIA GPUs only. It should reduce unnecessary feature-label surface while
still allowing NFD to publish accelerator-relevant PCI vendor signals.

## Project Reuse Decision

Default rhoai3-demo posture:

- curate the NFD operator and instance layout locally
- prefer an `only-nvidia` instance overlay for the NVIDIA GPU path
- keep topology updater disabled unless a later demo step requires topology or
  NUMA-aware placement
- verify `NodeFeatureDiscovery` fields with official OCP docs and live schema
- keep NFD separate from NVIDIA device-plugin capacity; NFD labels nodes, while
  the NVIDIA GPU Operator exposes `nvidia.com/gpu`

Important caveat: the CoP example omits an explicit `operand.image`. The active
OCP skill extraction says `operand.image` must be explicit when the
`NodeFeatureDiscovery` custom resource is created manually or through GitOps
unless OLM or the active Operator path safely sets it. Verify this before
committing manifests.

## Do Not Copy Blindly

- Do not use remote Kustomize references to the CoP catalog in committed
  GitOps.
- Do not assume `stable` is the only valid NFD channel; verify available
  channels from the active OLM catalog.
- Do not copy the instance CR without checking `operand.image` requirements.
- Do not enable topology updater unless the demo needs
  `NodeResourceTopology`.
- Do not use NFD labels as a substitute for checking `nvidia.com/gpu` capacity
  and allocatable values.
