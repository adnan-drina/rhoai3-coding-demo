# Official Documentation Extraction

## Machine API Scope

Machine management covers OpenShift infrastructure objects that create and
maintain machines. Do not confuse these with Kubernetes `Node` behavior:

- Machine API manages provider-backed machines when supported by the
  installation type.
- MachineSets manage groups of compute machines.
- Machines eventually correspond to nodes, but node labels, scheduling, and
  workload placement belong in `ocp-nodes`.
- Some tasks are automated and some are manual; not all documented tasks are
  available in every installation type.

For the demo, always verify that the target cluster has Machine API resources
before assuming MachineSets are available.

## Compute MachineSets

Use compute MachineSets to create purpose-specific worker pools, such as GPU
workers or infrastructure workers. A compute MachineSet can define provider
configuration, replicas, labels, taints, and template metadata.

Review principles:

- clone or compare against an existing cluster MachineSet before creating a new
  one
- keep provider-specific fields aligned with the target infrastructure
- verify failure domains, zones, subnets, security groups, IAM/profile
  references, image references, and tags
- verify labels and taints with `ocp-nodes` before relying on them for
  scheduling
- use official GPU MachineSet labeling guidance for cluster autoscaler handling
  when the MachineSet is intended for GPU workers
- do not invent provider spec fields or assume examples are portable across
  clouds

For AWS demo work, use the AWS compute MachineSet chapter as the starting
point. Keep exact GPU instance selection aligned with the active
`rhoai-nvidia-gpu-accelerators` skill and the live environment plan.

For demo.redhat.com GPU workers, the Red Hat CoP GPU Operator catalog provides
a useful pattern for deriving a GPU MachineSet from an existing AWS worker
MachineSet. Use that pattern to identify transformation steps, but preserve the
provider-specific fields from the live cluster and commit the reviewed result
as GitOps desired state by default.

## Scaling And Modification

Manual scaling changes the number of replicas for a compute MachineSet. The
official docs distinguish scaling from broader MachineSet modification.

Use this posture:

- scaling to zero can be valid for expensive or limited-use specialized
  hardware when autoscaler behavior and workload impact are understood
- modification beyond replica count needs provider-specific review
- changes to a MachineSet template usually affect future machines rather than
  rewriting already-created machines
- deletion and replacement need explicit planning so the cluster does not lose
  required capacity

Treat manual scale, modification, and deletion as live-environment operations
unless the change is only a proposed GitOps desired state.

## Machine Lifecycle And Deletion

Machines have phases and ownership relationships that should be inspected
before deletion or replacement. Deleting a machine is not the same as deleting a
node by itself, and cloud provider state can be involved.

Before deleting or replacing a machine:

- inspect the Machine, Node, MachineSet, and owning resources
- verify workload disruption and PodDisruptionBudget impact
- check storage attachment and application state
- verify whether autoscaler or MachineHealthCheck controllers might also act
- confirm replacement capacity and failure-domain balance

## Autoscaling

Cluster autoscaling coordinates with MachineAutoscaler resources to scale
MachineSets. Use autoscaling for elastic worker capacity only after confirming:

- ClusterAutoscaler exists and its global limits match demo intent
- MachineAutoscaler min/max replica bounds are correct
- the target MachineSet has the required labels and annotations
- GPU or specialized-hardware MachineSets have the required autoscaler labeling
- scale-down behavior does not remove capacity required for active demos
- scale-to-zero is intentionally designed and validated

For RHOAI GPU capacity, pair this section with `rhoai-nvidia-gpu-accelerators`
and environment resource-management skills.

## Infrastructure MachineSets

Infrastructure MachineSets can isolate infrastructure workloads from
application workloads. Use them only when the demo design explicitly requires
dedicated infrastructure capacity. Verify labels, taints, tolerations, and
cluster workload placement before claiming infrastructure isolation.

## User-Provisioned Infrastructure

Customized user-provisioned infrastructure installations can lack compute
MachineSets. Do not assume Machine API workflows are available in every cluster.
For user-provisioned infrastructure, use the official manual procedures and
record which parts are outside normal GitOps automation.

## Control Plane Machines

ControlPlaneMachineSet automates management and recovery of control plane
machines on supported platforms. In OCP 4.20, support includes AWS, Google
Cloud, Microsoft Azure, Nutanix, and VMware vSphere, with activation behavior
depending on cloud provider and upgrade history.

Control plane machine work is high risk:

- do not create or activate a control plane machine set casually
- review provider-specific configuration before activation
- coordinate with etcd health and `ocp-etcd`
- treat replacement as a planned control plane operation
- use MachineHealthCheck cautiously for control plane machines because multiple
  unhealthy control plane machines can indicate etcd or scaling problems that
  need manual intervention

## Machine Health Checks

MachineHealthCheck detects unhealthy machines and can trigger remediation.
Before enabling or changing one:

- confirm selector scope so it targets only intended machines
- confirm unhealthy conditions and timeouts
- confirm remediation behavior for the platform
- ensure it does not fight with planned scaling, replacement, or maintenance
- use conservative behavior around control plane machines

MachineHealthCheck is useful for resilience, but it is not a replacement for
capacity planning, clean node operations, or platform incident handling.
