# Source Capture

## Captured Source

- Product: Red Hat OpenShift Container Platform
- Baseline: use the active OpenShift version in `docs/PLATFORM_BASELINE.md`
- Source title: Storage
- Documentation category: Configure > Postinstallation configuration > Storage
- User-provided source URL:
  https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html-single/storage/index
- Multi-page source URL used for extraction:
  https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/storage/index
- Retrieved: 2026-06-10

## Sections Captured

- OpenShift Container Platform storage overview
- Understanding ephemeral storage
- Understanding persistent storage
- Configuring persistent storage
- Persistent storage using local storage
- Using Container Storage Interface (CSI)
- Generic ephemeral volumes
- Expanding persistent volumes
- Dynamic provisioning
- Detach volumes after non-graceful node shutdown

## Important Subsections Captured

- Storage types: ephemeral and persistent storage
- PV/PVC lifecycle: provisioning, binding, use, release, reclaim policy, manual
  reclaim, and reclaim-policy changes
- Persistent volumes: types, capacity, access modes, phase, mount options
- Persistent volume claims: storage classes, access modes, resources, claims as
  volumes, usage statistics, and Volume Attributes Classes
- Block volume support
- fsGroup and SELinux change-policy behavior for reducing pod timeouts
- AWS Elastic Block Store storage classes, PVCs, volume format, per-node volume
  limits, and KMS encryption
- Azure, Azure File, Cinder, Fibre Channel, FlexVolume, GCE Persistent Disk,
  iSCSI, NFS, OpenShift Data Foundation, VMware vSphere, and other provider
  handoff points
- Local Storage Operator, HostPath Provisioner, and LVM Storage
- CSI architecture, supported CSI drivers, dynamic provisioning, inline
  ephemeral volumes, snapshots, volume group snapshots, cloning, volume
  populators, CSI migration, and driver-specific operator workflows
- Dynamic provisioning plugins, StorageClass object definition, annotations,
  and default storage class changes

## Related Official Sources To Check Before Deep Changes

- OpenShift Container Platform 4.20 documentation landing page:
  https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/
- OpenShift Container Platform 4.20 API reference, Storage APIs:
  https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/storage_apis/
- OpenShift Data Foundation documentation pinned in `docs/PLATFORM_BASELINE.md`

## Source Boundaries

- This source is authoritative for OCP 4.20 storage concepts and OCP storage
  APIs, but provider-specific storage details can still require the referenced
  provider or operator documentation.
- This source references OpenShift Data Foundation, but it is not the authority
  for ODF StorageCluster, Ceph, NooBaa, object bucket claims, or ODF disaster
  recovery behavior. Use the relevant `odf-*` skill.
- This source does not define RHOAI dashboard behavior for storage class
  visibility, cluster default PVC size, project storage forms, or workbench
  storage UX.
- Recheck this source whenever `docs/PLATFORM_BASELINE.md` moves to a new OCP
  version.
