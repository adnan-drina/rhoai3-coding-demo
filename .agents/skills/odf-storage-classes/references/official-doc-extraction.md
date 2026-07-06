# Official Doc Extraction

## ODF Storage-Class Model

- ODF exposes storage services through storage classes.
- ODF storage capabilities include block, shared or distributed file, and
  object storage.
- ODF deployments commonly create storage classes for Ceph block, CephFS, and
  NooBaa object storage.

## Operator Ownership

- The ODF operator installs default storage classes depending on the platform
  and deployment.
- Operator-owned default storage classes are controlled by ODF and should not
  be deleted or modified as normal demo configuration.
- Custom storage classes must follow the ODF managing-storage guidance and live
  schema checks.

## Review Fields

When reviewing ODF storage classes, inspect these fields without inventing
values:

```bash
oc get storageclass
oc get storageclass <name> -o yaml
```

Review:

- `provisioner`
- `reclaimPolicy`
- `volumeBindingMode`
- `parameters`
- annotations that mark a default storage class

## Demo Handoff

- Use `odf-storage-classes` to decide which ODF classes exist and what they
  provide.
- Use `rhoai-storage-classes` to decide what OpenShift AI users can see in the
  dashboard.
- Use `odf-object-bucket-claims` when the ODF object storage class is consumed
  through an ObjectBucketClaim.
