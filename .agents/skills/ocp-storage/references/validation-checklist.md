# Validation Checklist

Use this checklist when reviewing OCP storage guidance, manifests, or
operations notes.

## Source And Baseline

- The OpenShift baseline is read from `docs/PLATFORM_BASELINE.md`.
- The storage source URL points to the matching OCP documentation version.
- Provider-specific settings are backed by the relevant OCP section, provider
  docs, or live schema verification.
- ODF behavior is deferred to pinned ODF docs and `odf-*` skills.
- RHOAI dashboard storage behavior is deferred to `rhoai-storage-classes`,
  `rhoai-cluster-pvc-size`, or the relevant RHOAI skill.

## Manifest Review

- `PersistentVolumeClaim` manifests specify intended access mode, requested
  capacity, and storage class behavior.
- If `storageClassName` is omitted, the default StorageClass has been verified.
- `StorageClass` manifests use documented provisioners and parameters.
- `reclaimPolicy`, `allowVolumeExpansion`, and `volumeBindingMode` are
  intentional.
- RWX expectations are not assigned to RWO block storage.
- Block volume usage includes `volumeMode: Block` only where intended.
- Snapshot, clone, or volume-populator resources use documented API groups and
  driver-supported features.

## Live Read-Only Checks

Run these only after the live-cluster guard is satisfied:

```bash
oc get storageclass
oc get storageclass -o yaml
oc get pv
oc get pvc -A
oc get csidriver
oc get volumesnapshotclass
oc get co storage
```

For AWS-backed demo clusters, also verify the actual provisioner and default
storage class instead of assuming a name:

```bash
oc get storageclass -o custom-columns=NAME:.metadata.name,PROVISIONER:.provisioner,DEFAULT:.metadata.annotations.storageclass\\.kubernetes\\.io/is-default-class,VOLUME_BINDING:.volumeBindingMode,EXPAND:.allowVolumeExpansion
```

## Storage Operations Review

- PVC expansion is attempted only when the StorageClass and driver support it.
- Volume detach after non-graceful node shutdown is treated as an incident
  procedure.
- Local storage and LVM Storage changes include node placement, data locality,
  deletion, and recovery considerations.
- Snapshots are not described as full backup or disaster recovery unless the
  storage backend and application consistency model support that claim.

## Fail Conditions

Stop and correct the work if any of these are true:

- A StorageClass, provisioner, access mode, or CSI feature is invented.
- A manifest assumes RWX behavior from AWS EBS or another RWO block device.
- ODF resources are authored from OCP storage docs instead of ODF docs.
- A live storage mutation is proposed without the environment guard and user
  approval.
- A README claims durable storage, backup, or recovery behavior without a
  matching manifest or official source.
