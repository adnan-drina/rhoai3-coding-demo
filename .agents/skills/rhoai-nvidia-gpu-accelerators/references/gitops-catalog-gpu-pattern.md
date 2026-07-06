# Red Hat CoP GPU Operator GitOps Pattern

Use this reference when rebuilding NVIDIA GPU infrastructure for the
demo.redhat.com AWS environment.

## Source Role

The Red Hat Community of Practice GitOps Catalog is a pattern source, not
product support authority. Use official Red Hat documentation, installed OLM
package metadata, live MachineSet shape, and active CRDs for product fields.

Captured sources:

- https://github.com/redhat-cop/gitops-catalog/tree/main/gpu-operator-certified
- https://github.com/redhat-cop/gitops-catalog/tree/main/gpu-operator-certified/instance/components/aws-gpu-machineset
- https://raw.githubusercontent.com/redhat-cop/gitops-catalog/main/gpu-operator-certified/instance/components/aws-gpu-machineset/job.sh
- https://raw.githubusercontent.com/redhat-cop/gitops-catalog/main/gpu-operator-certified/instance/components/aws-gpu-machineset/job.yaml
- https://raw.githubusercontent.com/redhat-cop/gitops-catalog/main/gpu-operator-certified/instance/base/cluster-policy.yaml

Capture date: 2026-06-10.

## Reusable Catalog Shape

The catalog item uses the same operator pattern we want for this repo:

```text
gpu-operator-certified/
  operator/
    base/
      namespace.yaml
      operator-group.yaml
      subscription.yaml
    overlays/
      stable/
      v25.3/
      ...
  instance/
    base/
      cluster-policy.yaml
      device-plugin-config.yaml
    components/
      aws-gpu-machineset/
      monitoring-dashboard/
      time-sliced*/
      mig-*/
    overlays/
      aws/
      aws-time-sliced-2/
      default/
      ...
```

Reusable ideas:

- GPU Operator namespace and single-namespace OperatorGroup are separated from
  the Subscription.
- Operator base uses a placeholder channel and overlays patch the Subscription
  channel.
- Instance base owns the NVIDIA `ClusterPolicy` and device-plugin ConfigMap.
- Optional behavior is modeled as Kustomize Components.
- AWS overlay composes `instance/base` plus the `aws-gpu-machineset`
  component.
- Time-slicing and MIG are explicit opt-in components, not default behavior.

## AWS MachineSet Component

The CoP `aws-gpu-machineset` component is designed for AWS OpenShift clusters
and states it has been tested on demo.redhat.com.

The component packages an Argo CD sync-hook Job that:

- checks for `kube-system/aws-creds` to detect AWS
- uses `registry.redhat.io/openshift4/ose-cli`
- clones an existing worker MachineSet
- changes the instance type
- sets the generated MachineSet replicas to `0`
- adds the template label `node-role.kubernetes.io/gpu`
- adds the MachineSet and template label `cluster-api/accelerator=nvidia-gpu`
- adds the taint `nvidia-gpu-only:NoSchedule`
- creates MachineAutoscaler resources with default bounds `0..4`

## Project Reuse Decision

Reuse the transformation logic, not the unreviewed generated state.

Default rhoai3-demo posture:

- instance type: `g6e.2xlarge`
- default node count: `1`
- GPU count: one NVIDIA L40S GPU per node, time-sliced to four schedulable
  `nvidia.com/gpu` units for the demo
- accelerator resource: `nvidia.com/gpu`
- taint: `nvidia-gpu-only:NoSchedule`
- autoscaler lower bound: normally `1` for active demo readiness unless the
  environment shutdown flow intentionally scales to zero
- autoscaler upper bound: explicit environment decision; do not inherit `4`
  without cost and quota review

Preferred implementation:

1. Inspect an existing worker MachineSet in the target demo.redhat.com cluster.
2. Generate or author a cluster-specific GPU MachineSet manifest in Git.
3. Preserve provider-specific fields from the live worker MachineSet.
4. Change only reviewed GPU fields: instance type, replicas, labels, taints,
   and autoscaler bounds.
5. Apply through Argo CD as tracked desired state.

An Argo CD hook generator can be used only as an explicit bootstrap exception
for throwaway demo.redhat.com environments. If used, review its RBAC with
`ocp-security-rbac-scc` and capture the generated MachineSet and
MachineAutoscaler back into Git when the environment becomes a maintained demo.

## ClusterPolicy Handoff

The catalog `ClusterPolicy` includes daemonset toleration for the
`nvidia-gpu-only` taint. If this project changes the taint key or effect, update
the NVIDIA `ClusterPolicy`, hardware profiles, workload tolerations, and
validation checks together.

The catalog enables advanced GPU Operator features such as MIG-related
components in some overlays. For this demo, keep MIG and time slicing disabled
unless a future step explicitly introduces GPU partitioning as a concept.

## Do Not Copy Blindly

- Do not keep the catalog default `g4dn.4xlarge`; the demo policy is
  `g6e.2xlarge`.
- Do not inherit MachineAutoscaler `0..4` without cost, quota, and readiness
  review.
- Do not commit broad generated RBAC or hook Jobs without security review.
- Do not use remote Kustomize references to the CoP catalog in committed
  GitOps.
- Do not create RHOAI hardware profiles until nodes report
  `nvidia.com/gpu` capacity and allocatable values.
