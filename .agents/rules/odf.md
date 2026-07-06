---
name: odf
skill-group: OpenShift Data Foundation
skill-prefix: odf-
applies-to:
  - "docs/PLATFORM_BASELINE.md"
  - "docs/**/*.md"
  - "gitops/**/*.yaml"
  - "gitops/**/*.yml"
  - "scripts/**/*"
  - ".agents/skills/odf-*/**"
---

# ODF Guidance

Use this rule for OpenShift Data Foundation storage guidance. Keep detailed
procedures in `odf-*` skills and use official ODF documentation for the active
version in `docs/PLATFORM_BASELINE.md`.

## Source Rules

- Use ODF documentation from the pinned baseline, currently ODF 4.20.
- Do not use a newer ODF documentation version for product configuration unless
  `docs/PLATFORM_BASELINE.md` is updated first.
- Use Red Hat articles and rh-brain only for narrative context and examples;
  official ODF docs remain the product configuration authority.
- Do not invent StorageCluster, NooBaa, BackingStore, BucketClass, OBC,
  StorageClass, or Ceph fields. Use official docs plus `oc explain` or CRD
  checks when a field is unclear.

## Demo Storage Posture

- Start with the minimum ODF footprint needed for the RHOAI demo:
  standalone Multicloud Object Gateway, NooBaa, and ObjectBucketClaims.
- Use full ODF StorageCluster/Ceph block and file storage only when a demo stage
  explicitly needs ODF-provided RWO/RWX PVCs beyond the underlying OpenShift
  storage classes.
- Manage ODF Operator lifecycle through GitOps: keep the Subscription channel
  and approval strategy in Git, keep ODF version compatibility aligned with the
  OCP baseline, and validate storage health before and after upgrades.
- Treat generated OBC Secrets as credentials. Never commit generated bucket
  credentials.
- Live `oc` or `kubectl` commands that inspect or mutate the cluster must
  follow the OpenShift safety guard in `AGENTS.md`.

## Skills

- Use `.agents/skills/odf-storagecluster/SKILL.md` for ODF deployment posture,
  StorageCluster, StorageSystem, AWS install, monitoring, update, and
  troubleshooting guidance.
- Use `.agents/skills/odf-multicloud-gateway/SKILL.md` for MCG, NooBaa,
  S3 endpoint, backing store, bucket class, and standalone object-storage
  guidance.
- Use `.agents/skills/odf-object-bucket-claims/SKILL.md` for project-scoped
  ObjectBucketClaim creation, generated ConfigMaps/Secrets, and application
  consumption patterns.
- Use `.agents/skills/odf-storage-classes/SKILL.md` for ODF-provided block,
  file, object storage classes, reclaim behavior, binding behavior, and
  storage-class review.
- Use `.agents/skills/ocp-storage/SKILL.md` for generic OpenShift storage
  concepts and API behavior.
- Use `.agents/skills/rhoai-s3-object-storage-data/SKILL.md` when the task is
  about RHOAI users consuming an S3-compatible object store from a workbench.
