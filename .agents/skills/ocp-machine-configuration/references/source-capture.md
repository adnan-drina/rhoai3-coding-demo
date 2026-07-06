# Source Capture

## Official Source

| Field | Value |
|-------|-------|
| Product | Red Hat OpenShift Container Platform |
| Version | Repository baseline in `docs/PLATFORM_BASELINE.md` |
| Documentation category | Machine configuration |
| Source URL | https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html-single/machine_configuration/index |
| Multi-page URL | https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/machine_configuration/index |
| Retrieved | 2026-06-10 |

## Sections Captured

- Machine configuration overview
- About the Machine Config Operator
- Machine config overview
- MCO node drain behavior
- Configuration drift detection
- Machine config pool status
- Node status during updates
- MCO certificates
- Chrony configuration
- Kernel arguments, real-time kernel, journald, RHCOS extensions, firmware, and
  core user password examples
- Node disruption policies
- MCO-related custom resources
- `KubeletConfig` and `ContainerRuntimeConfig`
- Pinning images to nodes with `PinnedImageSet`
- Boot image management
- Managing unused rendered machine configs
- Image mode for OpenShift
- Machine Config Daemon metrics

## Related Official Sources

- OCP 4.20 documentation landing page:
  https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/
- OCP 4.20 Machine APIs:
  https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/machine_apis/
- OCP 4.20 Machine management:
  https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/machine_management/index
- OCP 4.20 Nodes:
  https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/nodes/index

## Source Boundaries

- This skill is about node OS and runtime configuration through MCO-managed
  resources.
- It is not product authority for cloud machines, MachineSets, or autoscaling;
  use `ocp-machine-management`.
- It is not product authority for pod scheduling, taints, drains, or generic
  node operations; use `ocp-nodes`.
- It is not product authority for RHOAI accelerator enablement; use
  `rhoai-nvidia-gpu-accelerators` and `ocp-node-feature-discovery`.
- If a field, API version, or rollout behavior is not clear in the official
  docs, verify with `oc explain`, CRD inspection, or the active cluster before
  authoring GitOps resources.
