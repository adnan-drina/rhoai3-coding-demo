---
name: odf-object-bucket-claims
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "odf"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Data Foundation"
description: >
  Use when documenting, reviewing, or rebuilding Red Hat OpenShift Data
  Foundation ObjectBucketClaim workflows for the demo: project-scoped S3
  buckets, generated ConfigMaps and Secrets, OBC lifecycle, application
  consumption, RHOAI object-store handoff, and NooBaa-backed bucket claims.
  Do NOT use for MCG service administration (use odf-multicloud-gateway),
  full StorageCluster decisions (use odf-storagecluster), generic OCP storage
  concepts (use ocp-storage), or RHOAI user-facing S3 workflow instructions
  (use rhoai-s3-object-storage-data).
---

# ODF ObjectBucketClaims

Use this skill when the demo needs project-scoped S3-compatible buckets from
ODF/NooBaa.

## Source Grounding

1. Confirm the active ODF version in `docs/PLATFORM_BASELINE.md`.
2. Read `.agents/rules/odf.md`.
3. Use `references/source-capture.md` for source provenance.
4. Use `references/official-doc-extraction.md` for supported behavior.
5. Use `references/validation-checklist.md` before finalizing OBC content.

## Scope

- `ObjectBucketClaim` resources for project-scoped bucket requests.
- Generated ConfigMaps and Secrets that expose bucket endpoint and
  credentials.
- Handoff from GitOps-created OBCs to RHOAI components that consume S3.
- Demo examples that use `openshift-storage.noobaa.io` only after validating
  that the storage class exists.

## Boundaries

- Do not commit generated OBC Secrets or NooBaa credentials.
- Do not use this skill to administer NooBaa or MCG backing stores; use
  `odf-multicloud-gateway`.
- Do not use this skill for generic RHOAI S3 usage instructions; use
  `rhoai-s3-object-storage-data`.

## Workflow

1. Verify ODF/MCG is present and the object storage class exists.
2. Define the project namespace that owns the bucket.
3. Create a minimal OBC manifest using official schema and live `oc explain`
   verification when needed.
4. Consume generated ConfigMap and Secret through workload references, not by
   copying credential values into Git.
5. Validate OBC phase, generated bucket data, and application consumption.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/object-bucket-claim-pattern.md`
