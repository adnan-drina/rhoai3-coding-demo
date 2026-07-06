# Official Documentation Extraction

## Machine Config Operator Scope

The Machine Config Operator manages operating-system and runtime configuration
for OpenShift nodes. The official Machine configuration guide covers host-level
changes such as systemd, CRI-O, kubelet, kernel, NetworkManager, certificates,
files, extensions, and RHCOS image layering.

Use this posture:

- MCO-managed changes are platform changes, not application changes.
- Many changes trigger node drain, reboot, CRI-O reload, or pool rollout.
- Rendered machine configs represent merged desired state for a pool.
- Machine config pool status is the first health signal after a change.
- Configuration drift, degraded pools, and Machine Config Daemon errors can
  block upgrades or leave nodes inconsistent.

## MachineConfig And MachineConfigPool

`MachineConfig` resources define host-level configuration. They are selected by
machine config pool role labels or pool-specific labels and rendered by the MCO
into pool-specific desired configurations.

Review principles:

- target the smallest appropriate pool
- do not change control plane pools without explicit planning
- verify generated rendered configs and MCP status after changes
- inspect MCD logs when a node becomes degraded
- prefer official examples for files, systemd units, kernel arguments,
  extensions, firmware, and access changes
- do not hand-author unsupported Ignition fields or schema versions

## Node Disruption Policies

Some machine config changes cause node drains and reboots by default. The
official docs describe node disruption policies on the singleton
`MachineConfiguration` object in the `openshift-machine-config-operator`
namespace.

Important constraints:

- `MachineConfiguration` and `MachineConfig` are different objects.
- Node disruption policies can reduce disruption for selected file, systemd,
  SSH key, and registry configuration changes.
- The MCO validates policy formatting but does not prove that a policy can be
  applied safely.
- Some machine configuration changes always require a reboot regardless of the
  policy.
- `Reboot` and `None` actions cannot be combined with other actions because
  they override them.

For the demo, do not introduce custom node disruption policies unless the
benefit and rollout behavior are documented in `docs/OPERATIONS.md`.

## KubeletConfig

Use `KubeletConfig` for supported kubelet parameter changes. The custom
resource targets a machine config pool through a pool selector and causes the
MCO to generate machine configs.

Review principles:

- verify each kubelet setting in the official docs or cluster schema
- target only the intended machine config pool
- understand that kubelet changes can roll nodes
- do not use kubelet settings to work around application-level problems
- inspect generated machine configs and MCP status after creation

## ContainerRuntimeConfig

Use `ContainerRuntimeConfig` for supported CRI-O configuration. The official
docs describe settings such as log level, overlay size, and default runtime.

Review principles:

- one `ContainerRuntimeConfig` per machine config pool should contain the
  intended configuration for that pool
- edit an existing CR for ongoing changes instead of creating a new CR for
  every change
- create new CRs mainly for different pools or temporary changes
- OpenShift has a documented cluster limit for generated container runtime
  configs; avoid creating disposable CRs
- deleting the CR is the documented way to revert its generated changes

## PinnedImageSet

`PinnedImageSet` preloads images onto nodes in a target machine config pool.
The official docs describe this as useful for slow, unreliable, or disconnected
registry access and for reducing update or application deployment risk.

Review principles:

- use `PinnedImageSet` only when the official OCP documented use case applies,
  such as unreliable registry access or update/deployment risk reduction
- include only fully qualified image references that can be inspected
  successfully
- target the correct machine config pool through labels
- verify node storage capacity before assuming preloading will succeed
- remember that pinned images are not removed by image garbage collection
- avoid mutable tags for release-critical or demo-critical content if a
  `PinnedImageSet` is explicitly justified

## Boot Image Management

Boot image management controls how boot images are managed for new machines.
Treat boot image changes as cluster infrastructure work. Pair this topic with
`ocp-machine-management` when the task also changes MachineSets or cloud
machine lifecycle.

## Rendered Machine Config Pruning

Rendered machine configs can accumulate over time. The official docs provide
`oc adm prune renderedmachineconfigs` for listing and pruning unused rendered
configs.

Use this posture:

- list or dry-run before any delete operation
- prune only configs that are not in use
- use `--pool-name` for scoped review when appropriate
- use `--confirm` only after explicit approval
- do not treat pruning as a fix for an unknown degraded-state root cause

## Image Mode For OpenShift

Image mode for OpenShift supports custom layered RHCOS images. The official
docs distinguish on-cluster image mode from out-of-cluster image mode.

Review principles:

- use image mode only when standard MCO configuration is insufficient
- verify registry, pull secret, build, and pool requirements
- understand `MachineOSConfig` and `MachineOSBuild` behavior before authoring
  resources
- one `MachineOSConfig` per associated machine config pool is the normal
  documented shape
- documented limitations include multi-architecture constraints, scale-up
  reboot behavior, and node disruption policy limitations for custom layered
  image nodes

For this demo, treat image mode as advanced platform work, not a default path.

## Machine Config Daemon Metrics And Logs

Machine Config Daemon runs on nodes and applies the desired configuration. Use
MCD metrics, pod logs, MCP conditions, and must-gather output to diagnose MCO
rollout problems.

Important signals include:

- drain errors
- pivot errors
- degraded update state
- kubelet state problems
- reboot errors
- pool update progress and degraded conditions

Do not clear or bypass MCO errors without understanding the failed node action.
