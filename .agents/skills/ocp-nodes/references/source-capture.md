# Source Capture

## Captured Source

- Product: Red Hat OpenShift Container Platform
- Baseline: use the active OpenShift version in `docs/PLATFORM_BASELINE.md`
- Source title: Nodes
- Documentation category: Configure > Postinstallation configuration > Nodes
- User-provided source URL:
  https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html-single/nodes/index
- Multi-page source URL used for extraction:
  https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/nodes/index
- Retrieved: 2026-06-10

## Sections Captured

- Overview of nodes
- Working with pods
- Automatically scaling pods with the Custom Metrics Autoscaler Operator
- Controlling pod placement onto nodes (scheduling)
- Using jobs and daemon sets
- Working with nodes
- Working with containers
- Working with clusters
- Remote worker nodes on the network edge
- Worker nodes for single-node OpenShift clusters
- Node metrics dashboard
- Manage secure signatures with sigstore

## Important Subsections Captured

- Node, pod, container, and autoscaling overview
- Scheduler profiles: `LowNodeUtilization`, `HighNodeUtilization`, and
  `NoScoring`
- Pod affinity and anti-affinity
- Node affinity
- Node overcommitment
- Taints and tolerations
- Node selectors, including cluster-wide and project-wide selectors
- Pod topology spread constraints
- Descheduler and secondary scheduler
- Viewing nodes, pods on nodes, and node CPU/memory usage
- Evacuating pods on nodes
- Updating node labels
- Marking nodes unschedulable or schedulable
- Deleting nodes
- Modifying nodes, control-plane schedulability, SELinux booleans, kernel
  arguments, swap memory, and parallel image pulls
- Maximum pods per node
- Node Tuning Operator
- Node remediation, fencing, maintenance, and rebooting
- Boot image management and garbage collection
- Node metrics dashboard indicators

## Related Official Sources To Check Before Deep Changes

- OpenShift Container Platform 4.20 documentation landing page:
  https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/
- OpenShift Container Platform 4.20 Machine management documentation:
  https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/machine_management/
- OpenShift Container Platform 4.20 Machine configuration documentation:
  https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/machine_configuration/
- OpenShift Container Platform 4.20 Specialized hardware and driver enablement:
  https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/specialized_hardware_and_driver_enablement/

## Source Boundaries

- This source is authoritative for OCP 4.20 node, pod placement, and node
  operation guidance.
- This source references machine management and machine configuration topics,
  but those areas should get dedicated `ocp-*` skills before they become demo
  implementation authority.
- This source does not define RHOAI GPU hardware profiles, Kueue queues,
  DataScienceCluster component resource settings, or NVIDIA GPU Operator
  behavior.
- Recheck this source whenever `docs/PLATFORM_BASELINE.md` moves to a new OCP
  version.
