# MachineSet Review Patterns

## AWS Compute MachineSet Review Worksheet

```text
Resource: MachineSet/<name>
Namespace: openshift-machine-api
Purpose: GPU worker, infrastructure worker, or general compute
Provider: AWS
Source: official OCP Machine management guide plus existing cluster MachineSet
Review:
- instance type verified
- AMI/image reference verified
- IAM/profile reference verified
- subnet and security groups verified
- availability zone and failure-domain spread verified
- labels and taints reviewed with ocp-nodes
- autoscaler labels reviewed when scale-to-zero or GPU autoscaling is intended
- RHOAI GPU intent reviewed with rhoai-nvidia-gpu-accelerators
Decision: keep, adjust, or block until provider spec is verified
```

## MachineSet Shape

Use this only as a review shape. Do not apply it without official provider
fields from the active docs and live cluster comparison.

```yaml
apiVersion: machine.openshift.io/v1beta1
kind: MachineSet
metadata:
  name: <machineset-name>
  namespace: openshift-machine-api
spec:
  replicas: 1
  selector:
    matchLabels:
      machine.openshift.io/cluster-api-cluster: <cluster-id>
      machine.openshift.io/cluster-api-machineset: <machineset-name>
  template:
    metadata:
      labels:
        machine.openshift.io/cluster-api-cluster: <cluster-id>
        machine.openshift.io/cluster-api-machineset: <machineset-name>
    spec:
      providerSpec:
        value:
          apiVersion: machine.openshift.io/v1beta1
          kind: AWSMachineProviderConfig
          instanceType: <verified-instance-type>
```

## Autoscaler Review Note

```text
Before enabling autoscaling:
- verify ClusterAutoscaler exists and global limits allow the target capacity
- verify MachineAutoscaler min/max for the MachineSet
- verify GPU MachineSet labels required by the official docs when applicable
- confirm scale-down will not remove capacity during live demo flows
```

## Live Scale Guard Note

```text
Scaling a MachineSet up or down is a live platform operation. Confirm the
target cluster with the repo environment guard, inspect active workloads, and
record the official OCP procedure before changing replicas.
```
