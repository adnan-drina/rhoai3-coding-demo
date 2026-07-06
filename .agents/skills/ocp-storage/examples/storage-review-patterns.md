# Storage Review Patterns

## PVC Review Worksheet

```text
Resource: PersistentVolumeClaim/model-cache
Namespace: <namespace>
Storage class: verify with `oc get storageclass`
Access mode: confirm RWO/RWX requirement against workload behavior
Capacity: confirm requested size and growth path
Expansion: verify StorageClass `allowVolumeExpansion`
Reclaim behavior: inspect StorageClass/PV reclaim policy
Decision: keep, adjust, or defer to ODF/RHOAI storage skill
```

## StorageClass Shape

Use this only as a field-placement reminder. Verify provisioner and parameters
against the official docs and the live cluster before applying.

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: <storage-class-name>
provisioner: <documented-provisioner>
parameters: {}
reclaimPolicy: Delete
allowVolumeExpansion: true
volumeBindingMode: WaitForFirstConsumer
```

## PVC Shape

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: <claim-name>
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 20Gi
  storageClassName: <verified-storage-class>
```

## AWS Demo Storage Note

```text
For the AWS-hosted demo, verify the active EBS CSI StorageClass before creating
PVCs. Treat AWS EBS as block storage suitable for RWO claims. Do not present it
as shared RWX storage; use an officially supported file/object storage provider
or a future ODF-backed design for that requirement.
```

## Snapshot Review Note

```text
CSI snapshots require driver support. Verify VolumeSnapshotClass availability,
driver support, and workload consistency before using snapshots as a demo
capability. Do not describe snapshots as complete backup or disaster recovery
unless the storage backend and application consistency model support that claim.
```
