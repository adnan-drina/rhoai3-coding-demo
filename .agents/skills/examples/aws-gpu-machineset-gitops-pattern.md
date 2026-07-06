# AWS GPU MachineSet GitOps Pattern

Use this pattern when creating the demo.redhat.com AWS GPU worker pool.

## Preferred Layout

```text
gitops/gpu-infrastructure/
  operator/
    base/
    overlays/<verified-channel>/
  instance/
    base/
      cluster-policy.yaml
      device-plugin-config.yaml
    components/
      aws-gpu-machineset/
        machineset.yaml
        machineautoscaler.yaml
        kustomization.yaml
    overlays/aws-l4-single/
      kustomization.yaml
```

The component should contain reviewed, Git-tracked resources. Avoid a hook Job
as the default implementation because it creates untracked resources from live
cluster state.

## MachineSet Contract

Start by exporting a current worker MachineSet from the target cluster:

```sh
oc get machineset -n openshift-machine-api
oc get machineset <worker-machineset> -n openshift-machine-api -o yaml
```

Create the GPU MachineSet by preserving provider-specific fields from the live
worker MachineSet and changing only reviewed GPU intent:

```yaml
apiVersion: machine.openshift.io/v1beta1
kind: MachineSet
metadata:
  namespace: openshift-machine-api
  labels:
    cluster-api/accelerator: nvidia-gpu
spec:
  replicas: 1
  template:
    spec:
      metadata:
        labels:
          node-role.kubernetes.io/gpu: ""
          cluster-api/accelerator: nvidia-gpu
      taints:
        - key: nvidia-gpu-only
          effect: NoSchedule
      providerSpec:
        value:
          instanceType: g6e.2xlarge
          # Preserve and revalidate image, subnet, security groups, IAM/profile,
          # placement, tags, block devices, and userDataSecret from the live
          # worker MachineSet.
```

## Autoscaler Contract

Use a MachineAutoscaler only when the cluster has a compatible
ClusterAutoscaler and the cost/readiness tradeoff is intentional:

```yaml
apiVersion: autoscaling.openshift.io/v1beta1
kind: MachineAutoscaler
metadata:
  namespace: openshift-machine-api
spec:
  minReplicas: 1
  maxReplicas: 1
  scaleTargetRef:
    apiVersion: machine.openshift.io/v1beta1
    kind: MachineSet
    name: <gpu-machineset-name>
```

Use `minReplicas: 0` only for the documented environment shutdown path. If the
demo needs burst capacity, raise `maxReplicas` only after AWS quota and budget
review.

## Validation

Run after the environment guard confirms the target cluster:

```sh
oc get machineset -n openshift-machine-api -l cluster-api/accelerator=nvidia-gpu
oc get machineautoscaler -n openshift-machine-api
oc get nodes -l node-role.kubernetes.io/gpu=
oc describe node <gpu-node> | rg -A20 'Capacity|Allocatable|nvidia.com/gpu'
```

The MachineSet, NVIDIA `ClusterPolicy`, hardware profiles, and GPU workloads
must agree on labels, taints, tolerations, and `nvidia.com/gpu` resource use.
