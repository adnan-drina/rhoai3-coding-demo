# Source Capture

## Captured Source

- Product: Red Hat OpenShift Container Platform
- Baseline: use the active OpenShift version in `docs/PLATFORM_BASELINE.md`
- Source title: etcd
- Documentation category: Configure > Postinstallation configuration > etcd
- Source URL:
  https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html-single/etcd/index
- Retrieved: 2026-06-10

## Sections Captured

- How etcd works
- Understanding etcd performance
- Storage practices for etcd
- Cluster latency requirements for etcd
- Validating the hardware for etcd
- Leader election and log replication of etcd
- Node scaling for etcd
- Effects of disk latency on etcd
- Monitoring consensus latency for etcd
- Moving etcd to a different disk
- Defragmenting etcd data
- Setting tuning parameters for etcd
- OpenShift Container Platform timer tunables for etcd
- Determining the size of the etcd database and understanding its effects
- Increasing the database size for etcd
- Measuring network jitter between control plane nodes
- How etcd peer round trip time affects performance
- Determining Kubernetes API transaction rate for your environment
- Backing up and restoring etcd data
- Replacing an unhealthy etcd member
- Disaster recovery
- About etcd encryption
- Supported encryption types
- Enabling etcd encryption
- Disabling etcd encryption
- Guidance for clusters that span data centers

## Related Official Sources To Check Before Deep Changes

- OpenShift Container Platform 4.20 documentation landing page:
  https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/
- OpenShift Container Platform 4.20 release notes:
  https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/release_notes/
- OpenShift lifecycle and support scope, when support posture matters:
  https://access.redhat.com/support/policy/updates/openshift

## Source Boundaries

- This source is authoritative for OCP 4.20 etcd operations and guidance.
- This source is not a replacement for Red Hat Support during production
  disaster recovery, quorum loss, storage corruption, or multi-site design
  review.
- RHOAI skills still decide RHOAI component behavior; this skill only covers
  OpenShift etcd and control plane considerations that affect the demo.
- ODF storage and disaster-recovery behavior needs separate `odf-*` skills
  after the ODF baseline is pinned.
- Recheck this source whenever `docs/PLATFORM_BASELINE.md` moves to a new OCP
  version.
