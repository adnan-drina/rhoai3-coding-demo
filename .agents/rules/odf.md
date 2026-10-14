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
  - "stages/**"
  - ".agents/skills/odf-*/**"
---

# ODF Guidance

Use this rule for OpenShift Data Foundation storage guidance. Keep procedures in
`odf-*` skills; the doc map `.agents/references/red-hat-doc-map.yaml` routes ODF
books to those skills and holds the one ODF documentation version
(`products.odf.docs_version`), which must equal the Subscription channel in
`gitops/stages/010-openshift-ai-platform-foundation/odf/subscription.yaml`.

## Source Rules

- Link ODF documentation of the map's `docs_version` only; run
  `python3 scripts/shared/check-doc-links.py` after changing links or versions.
- Use Red Hat articles and rh-brain only for narrative context and examples;
  official ODF docs remain the product configuration authority.
- Do not invent StorageCluster, NooBaa, BackingStore, BucketClass, OBC,
  StorageClass, or Ceph fields. Use official docs plus `oc explain` or CRD checks when a field is unclear.

## Demo Storage Posture

- Start with the minimum ODF footprint needed for the RHOAI demo:
  standalone Multicloud Object Gateway, NooBaa, and ObjectBucketClaims.
- Use full ODF StorageCluster/Ceph block and file storage only when a demo stage
  explicitly needs ODF-provided RWO/RWX PVCs beyond the underlying OpenShift storage classes.
- Manage ODF Operator lifecycle through GitOps: keep the Subscription channel
  and approval strategy in Git, keep ODF version compatibility aligned with the OCP baseline, and validate storage health before and after upgrades.
- Treat generated OBC Secrets as credentials. Never commit generated bucket
  credentials.
- Live `oc` or `kubectl` commands that inspect or mutate the cluster must
  follow the OpenShift safety guard in `AGENTS.md`.

## Skills

The doc map routes ODF books to the four `odf-*` skills. Cross-family handoffs:
`.agents/skills/ocp-storage/SKILL.md` for generic OpenShift storage, and
`.agents/skills/rhoai-s3-object-storage-data/SKILL.md` for RHOAI users
consuming S3 from a workbench.
