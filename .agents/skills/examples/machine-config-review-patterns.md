# Machine Configuration Review Patterns

## MachineConfig Review Worksheet

```text
Resource: MachineConfig/<name>
Target pool or role: worker, master, or custom pool
Purpose: file, systemd, kernel, extension, firmware, access, or other host config
Official source section:
Expected disruption: none, reload, restart, drain, reboot, or unknown
Review:
- API version verified
- target pool verified
- control plane impact ruled out or explicitly approved
- Ignition and field shape verified
- rollback or removal behavior documented
- MCP status check documented
- MCD log check documented
Decision: keep, adjust, or block until official source and rollout are clear
```

## MachineConfig Shape

Use this only as a review shape. Do not apply it without the exact official
example, Ignition schema version, field placement, and target pool verified.

```yaml
apiVersion: machineconfiguration.openshift.io/v1
kind: MachineConfig
metadata:
  name: <machine-config-name>
  labels:
    machineconfiguration.openshift.io/role: <pool-role>
spec:
  config:
    ignition:
      version: <verified-ignition-version>
```

## KubeletConfig Review Shape

```yaml
apiVersion: machineconfiguration.openshift.io/v1
kind: KubeletConfig
metadata:
  name: <kubelet-config-name>
spec:
  machineConfigPoolSelector:
    matchLabels:
      pools.operator.machineconfiguration.openshift.io/<pool-name>: ""
  kubeletConfig:
    <verified-kubelet-setting>: <verified-value>
```

## ContainerRuntimeConfig Review Shape

```yaml
apiVersion: machineconfiguration.openshift.io/v1
kind: ContainerRuntimeConfig
metadata:
  name: <container-runtime-config-name>
spec:
  machineConfigPoolSelector:
    matchLabels:
      pools.operator.machineconfiguration.openshift.io/<pool-name>: ""
  containerRuntimeConfig:
    <verified-crio-setting>: <verified-value>
```

## PinnedImageSet Review Shape

```yaml
apiVersion: machineconfiguration.openshift.io/v1
kind: PinnedImageSet
metadata:
  name: <pool>-pinned-images
  labels:
    machineconfiguration.openshift.io/role: <pool-role>
spec:
  pinnedImages:
    - name: <fully-qualified-image-reference>
```

When the official OCP `PinnedImageSet` use case applies, review configured
images with:

```bash
podman manifest inspect <fully-qualified-image-reference>
```

## Node Disruption Policy Review Note

```text
Node disruption policies are configured on MachineConfiguration/cluster in the
openshift-machine-config-operator namespace, not on a MachineConfig. They can
reduce disruption for selected changes, but the MCO does not prove that the
policy can be safely applied. Document the target path or unit, expected action,
and rollback behavior before applying.
```

## Rendered Machine Config Pruning

```bash
oc adm prune renderedmachineconfigs list --in-use=false --pool-name=worker
oc adm prune renderedmachineconfigs --pool-name=worker
```

The prune command without `--confirm` is a dry run. Add `--confirm` only after
the output is reviewed and the user approves deletion:

```bash
oc adm prune renderedmachineconfigs --pool-name=worker --count=2 --confirm
```

## Image Mode Review Note

```text
Image mode for OpenShift is an advanced path for custom layered RHCOS images.
Before using it, verify registry access, pull secrets, build behavior, target
MCP, MachineOSConfig shape, MachineOSBuild status, and documented limitations.
Prefer normal MCO-managed MachineConfig, KubeletConfig, and
ContainerRuntimeConfig resources when they satisfy the requirement.
```
