# Distributed Workload Operations Patterns

These examples show the intended shape for future GitOps manifests and
runbooks. Replace placeholders with verified environment values before using
them in active manifests.

## NVIDIA ResourceFlavor

Verify the node label key and value before replacing the placeholders:

```yaml
apiVersion: kueue.x-k8s.io/v1beta2
kind: ResourceFlavor
metadata:
  name: nvidia-l40s
spec:
  nodeLabels:
    <verified-node-label-key>: <verified-node-label-value>
  tolerations:
    - key: HasGPU
      operator: Exists
      effect: NoSchedule
```

Schema checks:

```bash
oc explain resourceflavor.spec
oc get nodes --show-labels
```

## NVIDIA ClusterQueue

Set quotas to match real node capacity and intended workload concurrency:

```yaml
apiVersion: kueue.x-k8s.io/v1beta2
kind: ClusterQueue
metadata:
  name: rhoai-demo-nvidia
spec:
  namespaceSelector: {}
  resourceGroups:
    - coveredResources:
        - cpu
        - memory
        - nvidia.com/gpu
      flavors:
        - name: nvidia-l40s
          resources:
            - name: cpu
              nominalQuota: 8
            - name: memory
              nominalQuota: 32Gi
            - name: nvidia.com/gpu
              nominalQuota: 1
```

Review rule: if users can request a resource, include it in both
`coveredResources` and `flavors[].resources`.

## Project LocalQueue

```yaml
apiVersion: kueue.x-k8s.io/v1beta2
kind: LocalQueue
metadata:
  name: rhoai-demo-nvidia
  namespace: <project_namespace>
spec:
  clusterQueue: rhoai-demo-nvidia
```

Readonly checks:

```bash
oc get localqueues -n <project_namespace>
oc describe localqueue rhoai-demo-nvidia -n <project_namespace>
```

## Troubleshooting Status Checks

```bash
oc get workload -n <project_namespace>
oc describe workload <workload_name> -n <project_namespace>
oc get raycluster -n <project_namespace>
oc describe raycluster <raycluster_name> -n <project_namespace>
oc get pods -n redhat-ods-applications
```

Look first at `status.conditions.message` on `Workload` and `RayCluster`
resources. For user notebook `403` failures against `rayclusters.ray.io`,
verify that notebook `TokenAuthentication` uses the intended OpenShift token
and server, then confirm the user is in `rhods-users`.

## RDMA MachineConfig Fragment

Use only when RDMA is explicitly in scope and the environment supports it. This
change restarts worker nodes.

```yaml
apiVersion: machineconfiguration.openshift.io/v1
kind: MachineConfig
metadata:
  labels:
    machineconfiguration.openshift.io/role: worker
  name: 02-worker-container-runtime
spec:
  config:
    ignition:
      version: 3.2.0
    storage:
      files:
        - contents:
            inline: |
              [crio.runtime]
              default_ulimits = [
                "memlock=-1:-1"
              ]
          mode: 420
          overwrite: true
          path: /etc/crio/crio.conf.d/10-custom
```

## RDMA PyTorchJob NCCL Environment

Adapt interface names to the validated network configuration:

```yaml
env:
  - name: NCCL_SOCKET_IFNAME
    value: net1
  - name: NCCL_IB_HCA
    value: mlx5_1
  - name: NCCL_DEBUG
    value: INFO
```

Expected evidence is an NCCL pod log entry showing the RDMA network path.
