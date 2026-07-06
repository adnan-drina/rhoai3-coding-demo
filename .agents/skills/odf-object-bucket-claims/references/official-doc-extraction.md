# Official Doc Extraction

## ObjectBucketClaim Purpose

- An ObjectBucketClaim requests an object bucket from an object storage class.
- OBCs are appropriate for per-project S3-compatible buckets in the demo.
- OBCs can be attached to application deployments through ODF workflows.
- OBCs have lifecycle and deletion behavior that must be considered before
  treating demo data as persistent.

## Generated Connection Material

The OBC workflow produces connection material for applications, commonly a
ConfigMap and Secret associated with the claim.

Treat generated Secrets as credentials:

- Do not commit generated Secret data.
- Do not paste generated credentials into README files.
- Reference generated Secrets from workloads at runtime.

## Demo Example Boundary

The Red Hat Developer article shows a developer-focused OBC pattern using:

- `apiVersion: objectbucket.io/v1alpha1`
- `kind: ObjectBucketClaim`
- `spec.generateBucketName`
- `spec.storageClassName: openshift-storage.noobaa.io`

Before using this pattern in active GitOps, verify that the OBC CRD and storage
class exist in the active cluster:

```bash
oc get crd objectbucketclaims.objectbucket.io
oc get storageclass openshift-storage.noobaa.io
oc explain objectbucketclaim.spec
```

## RHOAI Handoff

- Use OBCs to provision buckets for model artifacts, AI Pipelines, MLflow,
  evaluation evidence, and other object-store-backed demo workflows.
- Use `rhoai-s3-object-storage-data` for user-facing RHOAI instructions on
  consuming S3-compatible object stores.
