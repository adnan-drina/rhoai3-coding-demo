---
name: odf-multicloud-gateway
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "odf"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Data Foundation"
description: >
  Use when documenting, reviewing, or rebuilding Red Hat OpenShift Data
  Foundation Multicloud Object Gateway and NooBaa guidance for the demo:
  standalone MCG, S3-compatible endpoint, NooBaa health, backing stores,
  bucket classes, object service dashboards, endpoint scaling, NooBaa database
  backup, and RHOAI object-storage platform handoff. Do NOT use for
  project-level ObjectBucketClaim manifests (use odf-object-bucket-claims),
  full StorageCluster/Ceph decisions (use odf-storagecluster), or RHOAI
  workbench S3 user workflows (use rhoai-s3-object-storage-data).
---

# ODF Multicloud Object Gateway

Use this skill for the demo's default ODF object-storage posture: standalone
Multicloud Object Gateway with NooBaa and S3-compatible access.

## Source Grounding

1. Confirm the active ODF version in `docs/PLATFORM_BASELINE.md`.
2. Read `.agents/rules/odf.md`.
3. Use `references/source-capture.md` for source provenance.
4. Use `references/official-doc-extraction.md` for supported behavior.
5. Use `references/validation-checklist.md` before finalizing MCG content.

## Demo Posture

- MCG is the default ODF starting point for the demo because RHOAI workflows
  commonly need S3-compatible object storage.
- Standalone MCG is preferred until the demo has a clear requirement for
  ODF-provided block or file storage.
- ObjectBucketClaims are the normal project-facing mechanism for bucket
  consumption.
- NooBaa admin credentials and generated bucket credentials are secrets and
  must never be committed.

## Scope

- Standalone MCG and NooBaa health.
- S3 route and endpoint discovery.
- BackingStore and BucketClass concepts.
- Object dashboard monitoring and NooBaa-related troubleshooting.
- NooBaa database backup handoff.

## Workflow

1. Confirm that the task is about the shared MCG/NooBaa service, not a single
   project bucket.
2. Validate NooBaa and object service health before authoring downstream
   GitOps assumptions.
3. Route project bucket manifests to `odf-object-bucket-claims`.
4. Route RHOAI user consumption to `rhoai-s3-object-storage-data`.
5. When troubleshooting, check object dashboard state, NooBaa phase, routes,
   events, and ODF must-gather.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/mcg-review-patterns.md`
