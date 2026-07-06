---
name: ocp-storage
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "ocp"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when documenting, reviewing, or rebuilding OpenShift Container Platform
  storage guidance from official OCP documentation: ephemeral storage,
  persistent storage, PV/PVC lifecycle, access modes, reclaim policies,
  StorageClass behavior, dynamic provisioning, provider-backed storage,
  AWS EBS storage classes and PVCs, CSI architecture and drivers, CSI snapshots,
  volume group snapshots, cloning, volume populators, generic ephemeral
  volumes, volume expansion, local storage, LVM Storage, and detach behavior
  after non-graceful node shutdown. Do NOT use for RHOAI dashboard storage
  settings; use rhoai-storage-classes or rhoai-cluster-pvc-size. Do NOT use for
  ODF Ceph, NooBaa, or StorageCluster behavior; use odf-* skills once created.
  Do NOT run live cluster operations without the env safety guard.
---

# OCP Storage

Use this skill to ground OpenShift storage documentation, GitOps review notes,
runbooks, and demo implementation planning in the official OpenShift Container
Platform Storage guide for the active baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority. This skill covers OCP storage
foundations and handoffs; it does not replace provider-specific storage docs,
ODF docs, or RHOAI component-specific storage guidance.

## Demo Storage Posture

For this AWS-hosted RHOAI demo, treat OCP storage as the platform substrate:

- Use cluster-discovered `StorageClass` objects; do not hard-code a default
  class without verifying it on the target cluster.
- Prefer CSI-backed dynamic provisioning for normal PVC-backed workloads.
- Treat AWS EBS as RWO block storage; do not imply RWX file semantics from EBS.
- Use ODF skills for Ceph, NooBaa, object buckets, RWX storage services, and
  data-service behavior once the ODF baseline is pinned.
- Keep RHOAI dashboard storage visibility and default PVC size decisions in
  RHOAI skills.
- Do not store application data, model data, or pipeline artifacts in Git.

## OCP Storage Model

Use the official docs to frame storage as:

- **Ephemeral storage**: temporary pod/container storage that does not outlive
  the pod lifecycle and affects scheduling and eviction through requests and
  limits.
- **Persistent storage**: PV/PVC-backed storage that can survive pod lifecycle
  events and abstracts provider details from application teams.
- **StorageClass**: an administrator-defined class of storage and provisioning
  parameters that users request through PVCs.
- **CSI**: the standard interface for vendor and cloud storage drivers,
  snapshots, cloning, resizing, and selected ephemeral volume workflows.
- **Dynamic provisioning**: on-demand volume creation using a StorageClass
  instead of requiring administrators to pre-create every PV.

## Workflow

1. Confirm the active OpenShift baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Identify the storage layer involved:
   - pod ephemeral storage
   - PVC/PV lifecycle
   - StorageClass and dynamic provisioning
   - CSI driver/operator behavior
   - snapshots, clones, expansion, or volume attachment recovery
   - local storage, LVM Storage, or provider-specific storage
4. For AWS demo implementation, verify live StorageClass names, provisioners,
   default annotation, reclaim policy, expansion support, and binding mode
   before writing manifests.
5. For RHOAI-facing docs, describe why the storage capability matters and map
   it to OCP/RHOAI components without duplicating provider-specific procedure
   details.
6. For any live `oc` command, use the repo environment guard and the relevant
   `env-*` skill.
7. Validate the result with `references/validation-checklist.md`.

## Related Skills

- Use `rhoai-storage-classes` for OpenShift AI dashboard storage-class
  visibility and defaults.
- Use `rhoai-cluster-pvc-size` for OpenShift AI cluster default PVC size.
- Use `rhoai-s3-object-storage-data` for RHOAI workbench access to
  S3-compatible object storage.
- Use `odf-*` skills for OpenShift Data Foundation implementation.
- Use `project-gitops-authoring` and `project-manifest-review` for GitOps
  manifests.
- Use `env-troubleshoot` for live PVC, pod, or node storage diagnostics.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/storage-review-patterns.md`
