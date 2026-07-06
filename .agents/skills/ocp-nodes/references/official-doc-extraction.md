# Official Documentation Extraction

## Node And Pod Model

OpenShift nodes provide the compute substrate for pods and containers. Use this
skill to reason about node inventory, resource pressure, scheduling, placement,
and day-2 node operations.

For demo documentation, distinguish:

- node capacity and allocatable resources
- pod resource requests and limits
- scheduler placement rules
- node labels and taints
- Machine/MachineSet lifecycle, which belongs in a future machine-management
  skill
- RHOAI hardware profiles and GPU enablement, which belong in `rhoai-*` skills

## Scheduling And Placement

The official docs cover several placement mechanisms. Use the least powerful
mechanism that satisfies the need:

- scheduler profile for cluster-wide scheduler behavior
- pod affinity and anti-affinity for placement relative to other pods
- node affinity for placement onto nodes with matching labels
- taints and tolerations to repel or permit workloads
- node selectors for direct node-label selection
- topology spread constraints to spread pods across topology domains
- descheduler to evict pods based on policy
- secondary scheduler only when a workload needs a distinct scheduling path

Do not combine many placement mechanisms casually. A pod with strict affinity,
selectors, and missing tolerations can remain pending even when capacity exists.

## Scheduler Profiles

The official docs define scheduler profiles such as:

- `LowNodeUtilization`: spreads pods evenly across nodes and provides default
  scheduler behavior
- `HighNodeUtilization`: packs pods onto fewer nodes to increase utilization,
  with increased risk if a node fails
- `NoScoring`: lowers scheduling latency by disabling scoring plugins, which
  can sacrifice better placement decisions

Changing the cluster `Scheduler` object is a cluster-wide operation. Use it
only with explicit approval, official docs, and validation of workload impact.

## Labels, Selectors, Taints, And Tolerations

For GitOps manifests:

- verify node labels on the target cluster before using `nodeSelector` or node
  affinity
- verify taints before adding tolerations
- do not invent GPU or hardware labels; use `ocp-node-feature-discovery` once
  created and `rhoai-nvidia-gpu-accelerators` for NVIDIA GPU intent
- avoid hard-coding node names unless a procedure explicitly requires it
- prefer topology and role labels over node names for portable demo manifests

For live operations:

- label changes can affect scheduling immediately
- taint changes can repel future pods and, depending on effect, evict running
  pods
- cordon/drain changes should be planned with workload disruption in mind

## Node Operations

The official docs cover listing nodes, listing pods on a node, viewing resource
usage, evacuating pods, marking nodes unschedulable or schedulable, deleting
nodes, and rebooting nodes.

Treat these as live platform operations:

- `cordon` and `uncordon` affect future scheduling
- `drain` evacuates pods and can disrupt workloads
- deleting a node is not the same as deleting a cloud machine or Machine API
  object
- rebooting nodes that run routers, critical infrastructure, or storage-backed
  workloads needs additional planning
- single-node OpenShift has special constraints because draining the only node
  can remove application availability

Do not run node maintenance commands from a skill alone. Pair with `env-*`
skills and the repo safety guard.

## Node Management And Tuning

The Nodes guide includes node modification, control-plane schedulability,
SELinux booleans, kernel arguments, swap memory, parallel image pulls, maximum
pods per node, Node Tuning Operator, boot image management, and garbage
collection.

Use this posture:

- control-plane schedulability is not normal demo placement; document any
  exception explicitly
- kernel arguments and Node Tuning Operator changes can trigger node-level
  disruption and must be backed by official docs
- maximum pods per node changes affect density, kubelet behavior, and network
  scale assumptions
- swap use should not be enabled just to mask missing resource requests
- garbage collection and image pull tuning are node operations, not application
  fixes

## Autoscaling, Jobs, Daemon Sets, And Containers

The Nodes guide covers:

- HPA, VPA, and Custom Metrics Autoscaler concepts
- Jobs and daemon sets for task automation and per-node pods
- container operations such as logs, exec, copy, and port-forward
- cluster-level maintenance patterns

For this demo, use these mechanisms only when they are the correct OpenShift
primitive. Do not use daemon sets as a shortcut for operator-managed platform
components, and do not use autoscaling language without metrics and validation.

## Metrics And Troubleshooting

Use the Node metrics dashboard and read-only CLI checks to identify:

- node readiness and conditions
- CPU and memory pressure
- OOM kills
- image pull failures
- kubelet and CRI-O reserved resource pressure
- pod distribution across nodes
- pending pods caused by scheduling constraints

Pair metrics findings with the relevant skill: `ocp-storage` for volume
attachment or PVC issues, `ocp-observability` for monitoring configuration,
and `rhoai-*` skills for OpenShift AI workload behavior.
