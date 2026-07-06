---
name: odf-storage-classes
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "odf"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Data Foundation"
description: >
  Use when documenting, reviewing, or rebuilding Red Hat OpenShift Data
  Foundation storage class guidance for the demo: ODF-provided block, file,
  and object storage classes, Ceph RBD, CephFS, NooBaa object storage class,
  reclaim policy, volume binding mode, custom storage class review, and
  RHOAI handoff. Do NOT use for generic OpenShift storage concepts (use
  ocp-storage), RHOAI dashboard storage class visibility (use
  rhoai-storage-classes), project ObjectBucketClaims (use
  odf-object-bucket-claims), or MCG service administration (use
  odf-multicloud-gateway).
---

# ODF Storage Classes

Use this skill for ODF-provided storage classes and their role in the demo.

## Source Grounding

1. Confirm the active ODF version in `docs/PLATFORM_BASELINE.md`.
2. Read `.agents/rules/odf.md`.
3. Use `references/source-capture.md` for source provenance.
4. Use `references/official-doc-extraction.md` for supported ODF behavior.
5. Use `references/validation-checklist.md` before finalizing storage-class
   content.

## Scope

- ODF-created and ODF-backed storage classes.
- ODF block, file, and object storage class roles.
- Reclaim policy and volume binding behavior in ODF storage-class review.
- Handoff between ODF storage classes and RHOAI dashboard visibility.

## Boundaries

- Use `ocp-storage` for generic Kubernetes and OpenShift storage semantics.
- Use `rhoai-storage-classes` for OpenShift AI dashboard storage-class
  enablement, display name, description, and access-mode UX.
- Use `odf-object-bucket-claims` for application buckets created from an
  object storage class.
- Do not delete or modify operator-owned default ODF storage classes unless
  official docs and the live cluster state explicitly support the change.

## Workflow

1. Identify whether the task needs block, file, or object storage.
2. Check whether the active cluster already provides an acceptable non-ODF
   storage class.
3. If ODF block/file is required, review ODF-managed storage class behavior
   before proposing changes.
4. If object storage is required, route project bucket creation to
   `odf-object-bucket-claims`.
5. Validate storage classes with readonly `oc get storageclass` output before
   writing GitOps assumptions.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/storage-class-review-patterns.md`
