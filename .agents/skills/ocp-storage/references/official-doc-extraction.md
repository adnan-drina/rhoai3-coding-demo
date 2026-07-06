# Official Documentation Extraction

## Storage Roles

OpenShift storage spans temporary pod storage and persistent workload storage.
Use this split consistently:

- Ephemeral storage is tied to the pod/container lifecycle and is managed with
  resource requests and limits that affect scheduling and eviction.
- Persistent storage uses the Kubernetes PV framework. Administrators provide
  storage and developers request it through PVCs without needing provider
  implementation details.

For the RHOAI demo, this means READMEs and operations docs should clearly
separate pod-local scratch space from PVC-backed state, model data, pipeline
artifacts, object storage, and external model endpoints.

## PV And PVC Lifecycle

Use the official lifecycle model:

- provision storage statically or dynamically
- bind PVCs to matching PVs
- mount claimed PVs into pods
- protect storage objects while they are in use
- release PVs when claims are deleted
- apply reclaim policies such as `Retain` or `Delete`
- manually reclaim only through an explicit administrative procedure

Review every PVC against these properties:

- `storageClassName`
- access mode
- requested capacity
- volume mode, when block storage is used
- reclaim behavior of the backing StorageClass/PV
- expected namespace ownership
- expansion support, if future growth is expected

## StorageClass And Dynamic Provisioning

`StorageClass` describes storage that can be requested and can pass parameters
to the dynamic provisioner. Cluster administrators or storage administrators
define StorageClass objects; users request them through PVCs.

Use this review model:

- discover actual StorageClasses on the cluster before selecting one
- verify the provisioner matches the target infrastructure or operator
- verify the default storage class annotation before relying on omitted
  `storageClassName`
- check `reclaimPolicy`, `allowVolumeExpansion`, and `volumeBindingMode`
- prefer `WaitForFirstConsumer` when topology-aware scheduling matters
- do not invent provider parameters or assume a storage class exists

For AWS, the storage guide includes AWS Elastic Block Store guidance and the
dynamic provisioner `ebs.csi.aws.com`. Treat EBS as block storage and verify the
cluster's actual EBS CSI StorageClass names before authoring manifests.

## CSI

CSI provides a standard interface for storage drivers. OpenShift installs
certain CSI driver operators, drivers, and required storage classes by default,
depending on the platform. Other supported CSI drivers, such as AWS EFS and GCP
Filestore, can require manual installation.

Use CSI guidance for:

- CSI driver/operator architecture
- supported driver and feature matrix review
- dynamic provisioning
- CSI inline ephemeral volumes
- snapshots and `snapshot.storage.k8s.io/v1` resources
- volume group snapshots
- volume cloning
- volume populators
- volume expansion and resize support
- automatic migration from selected in-tree plugins

Do not assume every CSI driver supports snapshots, cloning, resize, group
snapshots, or inline ephemeral volumes. Check the official driver support table
and live driver objects.

## Snapshots, Clones, And Populators

CSI volume snapshots represent a point-in-time state of a storage volume and
require a CSI driver that supports snapshots. OpenShift supports CSI volume
snapshots by default, but the backing CSI driver must provide snapshot support.

Use snapshots and clones carefully:

- take snapshots only when the workload can tolerate the captured state
- verify that no pods are using the PVC when the official procedure requires it
- use `VolumeSnapshotClass` for dynamic snapshot provisioning
- remember that clones reference an existing PVC as `dataSource`
- keep clones in the same namespace as the source PVC when the official
  limitations require it

## Local Storage And LVM Storage

Local storage workflows are node-sensitive and operator-specific. The storage
guide covers:

- HostPath Provisioner
- Local Storage Operator
- LVM Storage
- local volume discovery and provisioning
- local storage metrics
- deleting local storage resources
- LVM snapshots, clones, expansion, monitoring, must-gather, and
  troubleshooting

For this demo, do not use local storage as a substitute for cloud or ODF-backed
storage unless the design explicitly depends on node-local behavior and records
the operational tradeoffs.

## Expansion And Attachment Recovery

Persistent volume expansion depends on StorageClass and driver support. Before
increasing a PVC size, verify:

- the StorageClass allows expansion
- the backing CSI driver supports resize
- the filesystem or volume mode behavior is understood
- the workload can tolerate the operation

The storage guide also covers detaching volumes after non-graceful node
shutdown. Treat this as a live incident workflow, not GitOps desired state, and
pair it with `env-troubleshoot`.

## ODF Boundary

The OCP storage guide references OpenShift Data Foundation as a persistent
storage provider. Do not infer ODF implementation details from this skill.
Use `odf-storagecluster`, `odf-storage-classes`,
`odf-object-bucket-claims`, or `odf-multicloud-gateway` before authoring ODF
StorageCluster, Ceph, NooBaa, object bucket, or ODF disaster recovery content.
