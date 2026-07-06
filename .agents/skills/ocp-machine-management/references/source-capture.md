# Source Capture

## Captured Source

- Product: Red Hat OpenShift Container Platform
- Baseline: use the active OpenShift version in `docs/PLATFORM_BASELINE.md`
- Source title: Machine management
- Documentation category: Configure > Postinstallation configuration > Machine
  management
- User-provided source URL:
  https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html-single/machine_management/index
- Multi-page source URL used for extraction:
  https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/machine_management/index
- Retrieved: 2026-06-10

## Sections Captured

- Overview of machine management
- Managing compute machines with the Machine API
- Manually scaling a compute machine set
- Modifying a compute machine set
- Machine phases and lifecycle
- Deleting a machine
- Applying autoscaling to an OpenShift Container Platform cluster
- Creating infrastructure machine sets
- Managing user-provisioned infrastructure manually
- Managing control plane machines
- Deploying machine health checks

## Important Subsections Captured

- Machine API overview
- Compute machine management
- Control plane machine management
- Cluster autoscaling and machine autoscaling
- Machine health checks
- Creating compute machine sets on AWS, Azure, Azure Stack Hub, Google Cloud,
  IBM Cloud, IBM Power Virtual Server, Nutanix, RHOSP, VMware vSphere, and bare
  metal
- AWS compute MachineSet examples and provider-specific fields
- Labeling GPU machine sets for the cluster autoscaler
- Provider-specific failure domains and reliability guidance
- Manual scaling, modification, phase review, deletion, and replacement
- User-provisioned infrastructure machine additions
- ControlPlaneMachineSet support, activation, provider support, replacement,
  and health-check behavior

## Related Official Sources To Check Before Deep Changes

- OpenShift Container Platform 4.20 documentation landing page:
  https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/
- OpenShift Container Platform 4.20 Machine API reference:
  https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/machine_apis/
- OpenShift Container Platform 4.20 Nodes guide:
  https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html-single/nodes/index
- OpenShift Container Platform 4.20 Specialized hardware and driver
  enablement:
  https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/specialized_hardware_and_driver_enablement/

## Supporting Pattern Sources

- Red Hat CoP GPU Operator catalog:
  https://github.com/redhat-cop/gitops-catalog/tree/main/gpu-operator-certified
- Red Hat CoP AWS GPU MachineSet component:
  https://github.com/redhat-cop/gitops-catalog/tree/main/gpu-operator-certified/instance/components/aws-gpu-machineset

These are implementation pattern sources only. They do not replace OCP Machine
management documentation or live provider-spec verification.

## Source Boundaries

- This source is authoritative for OCP 4.20 Machine API, MachineSet,
  ControlPlaneMachineSet, autoscaling, and MachineHealthCheck behavior.
- This source includes GPU MachineSet autoscaler labeling, but it does not
  replace NVIDIA GPU Operator, Node Feature Discovery, or RHOAI hardware-profile
  documentation.
- This source does not define pod scheduling behavior after nodes exist; use
  `ocp-nodes` for selectors, affinity, taints, tolerations, and node
  operations.
- This source does not define RHOAI model-serving capacity policy or GPU
  workload placement.
- The CoP AWS GPU MachineSet component is useful for demo.redhat.com
  transformation logic, but the default project posture is reviewed
  Git-tracked MachineSet desired state.
- Recheck this source whenever `docs/PLATFORM_BASELINE.md` moves to a new OCP
  version.
