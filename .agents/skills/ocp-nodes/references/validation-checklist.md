# Validation Checklist

Use this checklist when reviewing OCP node guidance, pod placement manifests,
or node operations notes.

## Source And Baseline

- The OpenShift baseline is read from `docs/PLATFORM_BASELINE.md`.
- The Nodes source URL points to the matching OCP documentation version.
- Node, pod, scheduler, and workload API fields are verified with official docs
  or `oc explain`.
- MachineSet, Machine API, MachineConfig, NFD, GPU, and RHOAI behavior is
  deferred to the relevant dedicated skill.

## Manifest Review

- Node placement rules use labels that exist on the target cluster.
- Tolerations match taints that exist or are intentionally introduced.
- `nodeSelector`, node affinity, pod affinity, anti-affinity, and topology
  spread constraints are not over-constraining the pod.
- Placement rules avoid hard-coded node names unless the official procedure or
  demo design requires a fixed node.
- Scheduler profile or secondary scheduler usage is explicitly justified.
- Resource requests and limits support the intended scheduling behavior.
- GPU placement is reviewed with `rhoai-nvidia-gpu-accelerators` and future
  `ocp-node-feature-discovery`.

## Live Read-Only Checks

Run these only after the live-cluster guard is satisfied:

```bash
oc get nodes -o wide
oc describe node <node-name>
oc get pods -A -o wide --field-selector spec.nodeName=<node-name>
oc adm top nodes
oc adm top pods -A
oc get events -A --sort-by=.lastTimestamp
```

For placement troubleshooting:

```bash
oc describe pod <pod-name> -n <namespace>
oc get nodes --show-labels
oc get nodes -o custom-columns=NAME:.metadata.name,TAINTS:.spec.taints
oc get scheduler cluster -o yaml
```

## Live Operation Review

- Node cordon, drain, reboot, deletion, tuning, or schedulability changes have
  explicit user approval.
- Workload disruption is understood before draining or rebooting a node.
- Single-node OpenShift constraints are called out when applicable.
- Control-plane scheduling changes are treated as exceptional and documented.
- Kernel argument, swap, maximum-pod, image-pull, and Node Tuning Operator
  changes have official docs and rollback planning.

## Fail Conditions

Stop and correct the work if any of these are true:

- A placement rule references labels, taints, scheduler names, or topology keys
  that are not verified.
- A pod remains pending because combined affinity, selectors, tolerations, and
  topology constraints are too strict.
- MachineSet or AWS instance lifecycle is authored from the Nodes guide alone.
- Node maintenance is proposed without the environment guard and approval.
- RHOAI GPU behavior is inferred from generic node docs instead of RHOAI/NVIDIA
  skills.
