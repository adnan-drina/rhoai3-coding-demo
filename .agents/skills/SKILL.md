---
name: odf-storagecluster
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "odf"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Data Foundation"
description: >
  Use when documenting, reviewing, or rebuilding Red Hat OpenShift Data
  Foundation deployment posture for the demo: ODF planning, architecture,
  AWS deployment, StorageSystem, StorageCluster, standalone Multicloud Object
  Gateway selection, updates, monitoring, troubleshooting, must-gather, and
  NooBaa database backup handoff. Do NOT use for project-level bucket
  requests (use odf-object-bucket-claims), MCG S3 endpoint operation (use
  odf-multicloud-gateway), generic OpenShift storage concepts (use
  ocp-storage), or RHOAI workbench S3 consumption (use rhoai-s3-object-storage-data).
---

# ODF StorageCluster

Use this skill to keep ODF platform decisions aligned with the pinned baseline
in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Before authoring StorageCluster, StorageSystem, install, update, monitoring, or
troubleshooting content:

1. Read `docs/PLATFORM_BASELINE.md` and confirm the ODF and OCP versions.
2. Read `.agents/rules/odf.md`.
3. Read `references/source-capture.md` for the official sources used here.
4. Use `references/official-doc-extraction.md` for supported ODF behavior.
5. Use `references/validation-checklist.md` before finishing a change.

## Demo Posture

- The default demo target is minimum ODF: standalone Multicloud Object Gateway
  for S3-compatible object storage.
- Full StorageCluster/Ceph block and file storage is an explicit design choice,
  not the default. Use it only when a demo step needs ODF-provided RWO/RWX PVCs
  beyond the underlying OpenShift storage classes.
- On AWS, use the AWS ODF deployment guide for supported install paths and
  validation signals.
- Use ODF 4.20 documentation with OCP 4.20. Do not lift ODF 4.21 procedures
  into the active baseline unless the platform baseline is upgraded.
- Keep ODF Operator channel and update approval strategy in Git through the
  operator lifecycle pattern from `project-red-hat-operator-gitops`. ODF
  same-channel updates normally use automatic approval when the official ODF
  update docs and active environment allow it.

## Workflow

1. Identify whether the task is platform deployment, object-only deployment,
   storage class review, or application bucket consumption.
2. If object-only storage is enough, route implementation detail to
   `odf-multicloud-gateway`.
3. If PVC-facing ODF block/file storage is needed, review ODF architecture and
   AWS deployment sources before proposing StorageCluster content.
4. For ODF upgrades, verify OCP/ODF compatibility, storage health, and data
   resilience before changing Subscription channel or approval strategy in Git.
5. For any live validation, use readonly checks where possible and follow the
   OpenShift safety guard in `AGENTS.md`.
6. For troubleshooting, start with ODF status, pod health, dashboards, and ODF
   must-gather. Do not run unsupported Ceph commands unless Red Hat docs or
   support explicitly require them.

## Related Skills

- `odf-multicloud-gateway` for standalone MCG, NooBaa, S3 routes, backing
  stores, and bucket classes.
- `odf-object-bucket-claims` for project-level buckets and generated
  connection Secrets.
- `odf-storage-classes` for ODF storage class behavior.
- `ocp-storage` for generic OpenShift PV/PVC and StorageClass behavior.
- `rhoai-s3-object-storage-data` for RHOAI user workflows consuming S3.
- `project-red-hat-operator-gitops` for GitOps-native ODF Operator
  Subscription lifecycle, channel overlays, and approval strategy.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/storagecluster-review-patterns.md`
