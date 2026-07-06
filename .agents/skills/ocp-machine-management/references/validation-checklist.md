# Validation Checklist

Use this checklist when reviewing OCP machine-management guidance, MachineSet
manifests, autoscaler resources, or machine lifecycle runbooks.

## Source And Baseline

- The OpenShift baseline is read from `docs/PLATFORM_BASELINE.md`.
- The Machine management source URL points to the matching OCP documentation
  version.
- Machine API fields are verified against official docs or `oc explain`.
- Provider-specific fields are copied from the matching provider chapter or
  live cluster shape, not invented.
- Node scheduling is reviewed with `ocp-nodes`.
- GPU and RHOAI capacity intent is reviewed with
  `rhoai-nvidia-gpu-accelerators`.

## Manifest Review

- `MachineSet` manifests use `machine.openshift.io/v1beta1` only when supported
  by the active docs and target cluster.
- Namespace is `openshift-machine-api` unless official docs and live cluster
  state show otherwise.
- Provider spec matches the target infrastructure provider.
- AWS MachineSet fields such as instance type, AMI/image reference, subnets,
  security groups, IAM/profile references, block devices, placement, and tags
  are verified against an existing MachineSet or official example.
- Replica count, labels, taints, and failure-domain spread are intentional.
- GPU MachineSet autoscaler labels are present when cluster autoscaling is
  expected to manage GPU worker capacity.
- MachineSet template labels and taints are paired with `ocp-nodes` placement
  review.
- MachineAutoscaler min/max bounds match the intended capacity range.
- ClusterAutoscaler global limits allow the MachineAutoscaler behavior.
- For the rhoai3-demo default GPU pool, instance type is `g6e.2xlarge`,
  desired replicas start at `1`, MachineSet labels include
  `cluster-api/accelerator=nvidia-gpu`, node template labels include
  `node-role.kubernetes.io/gpu`, and the taint/toleration handoff is reviewed
  with `rhoai-nvidia-gpu-accelerators`.
- If a generated MachineSet is created by a hook Job, it is captured back into
  Git or explicitly documented as a disposable bootstrap exception.

## Live Read-Only Checks

Run these only after the live-cluster guard is satisfied:

```bash
oc get machinesets -n openshift-machine-api
oc get machines -n openshift-machine-api
oc get machinehealthchecks -n openshift-machine-api
oc get machineautoscalers -A
oc get clusterautoscaler -A
oc get controlplanemachineset -n openshift-machine-api
oc get nodes -o wide
```

For provider-shape comparison:

```bash
oc get machineset <name> -n openshift-machine-api -o yaml
oc describe machine <name> -n openshift-machine-api
oc describe node <node-name>
```

## Live Operation Review

- Scaling, deleting, replacing, or modifying machines has explicit user
  approval.
- The repo environment guard is satisfied before live commands.
- Active workloads, storage attachment, PDBs, and RHOAI demo capacity are
  understood before machine deletion or scale-down.
- Control plane machine changes are reviewed with `ocp-etcd`.
- MachineHealthCheck behavior is paused, scoped, or reviewed when planned
  maintenance could otherwise trigger remediation.
- User-provisioned infrastructure differences are documented before assuming
  MachineSet automation.

## Fail Conditions

Stop and correct the work if any of these are true:

- A MachineSet provider spec is invented or copied from the wrong cloud
  provider.
- A GPU worker MachineSet is authored without the RHOAI/NVIDIA handoff.
- MachineAutoscaler or ClusterAutoscaler bounds can remove required demo
  capacity unexpectedly.
- Control plane machine work is proposed without etcd and cluster operator
  health review.
- A machine lifecycle operation is proposed without the environment guard and
  user approval.
