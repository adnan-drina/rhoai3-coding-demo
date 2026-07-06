# Validation Checklist

Use this checklist when reviewing OCP machine-configuration guidance,
MCO-managed manifests, image mode plans, rendered machine config pruning, or
Machine Config Daemon troubleshooting notes.

## Source And Baseline

- The OpenShift baseline is read from `docs/PLATFORM_BASELINE.md`.
- The Machine configuration source URL points to the matching OCP documentation
  version.
- API versions, fields, labels, and rollout behavior are verified against
  official docs, `oc explain`, CRDs, or the active cluster.
- Machine lifecycle concerns are reviewed with `ocp-machine-management`.
- Node scheduling, drain, taint, label, and workload placement concerns are
  reviewed with `ocp-nodes`.
- GPU and RHOAI capacity intent is reviewed with
  `rhoai-nvidia-gpu-accelerators`.

## Manifest Review

- `MachineConfig`, `KubeletConfig`, `ContainerRuntimeConfig`, and
  `PinnedImageSet` resources use `machineconfiguration.openshift.io/v1` only
  when supported by the active docs and target cluster.
- `MachineConfiguration` resources use `operator.openshift.io/v1` only when
  supported by the active docs and target cluster.
- `MachineOSConfig` and `MachineOSBuild` use the exact API shape from active
  docs or cluster schema before use.
- The target machine config pool is explicit and intentional.
- Control plane pools are not changed without explicit approval and `ocp-etcd`
  review.
- File, systemd, kubelet, CRI-O, kernel, extension, firmware, and image-layering
  changes are copied from official examples or verified schema, not invented.
- The expected disruption is documented: none, service reload, service restart,
  drain, reboot, image build, CRI-O reload, or pool rollout.
- Rollback or removal behavior is documented before applying a change.
- GitOps resources do not conflict with operator-generated rendered machine
  configs.

## Live Read-Only Checks

Run these only after the live-cluster guard is satisfied:

```bash
oc get mcp
oc get machineconfig
oc get kubeletconfig
oc get containerruntimeconfig
oc get pinnedimageset
oc get machineosconfig
oc get machineosbuild
oc get machineconfiguration cluster -n openshift-machine-config-operator -o yaml
oc get co machine-config
oc get pods -n openshift-machine-config-operator
```

For focused diagnostics:

```bash
oc describe mcp <pool-name>
oc get mcp <pool-name> -o yaml
oc get machineconfig <name> -o yaml
oc logs <machine-config-daemon-pod> -n openshift-machine-config-operator -c machine-config-daemon --tail=100
```

For rendered machine config review:

```bash
oc adm prune renderedmachineconfigs list --in-use=false --pool-name=<pool-name>
oc adm prune renderedmachineconfigs --pool-name=<pool-name>
```

The second command is a dry run unless `--confirm` is added.

## Live Operation Review

- The repo environment guard is satisfied before live commands.
- Any change that can drain, reboot, reload CRI-O, modify kubelet behavior, or
  affect MCP status has explicit user approval.
- The target MCP has enough spare capacity for disruption during the live demo.
- Workload disruption, storage attachment, PDBs, and active RHOAI capacity are
  understood before rolling worker pools.
- Rendered machine config pruning uses dry-run output first and `--confirm`
  only after approval.
- Image mode work has verified registry, pull secret, build, and MCP behavior.
- MCO degraded state is investigated before new machine config changes are
  applied.

## Fail Conditions

Stop and correct the work if any of these are true:

- A machine configuration field is invented or copied from a different OCP
  version without verification.
- A control plane pool change is proposed without explicit approval and etcd
  review.
- A `MachineConfig` targets all workers when a narrower pool is required.
- A node disruption policy is proposed as safe without evidence from the
  official docs and cluster behavior.
- `ContainerRuntimeConfig` CRs are created repeatedly instead of consolidating
  changes for the target pool.
- A `PinnedImageSet` is used without a documented OCP use case, or includes
  mutable or unaudited images for critical demo behavior.
- Rendered machine configs are pruned without dry-run output.
- Image mode is used when standard MCO configuration would satisfy the need.
