# Validation Checklist

Use this checklist before finalizing MCG or NooBaa content.

## Source Alignment

- Links use ODF documentation from the active baseline.
- Standalone MCG is selected only when object storage is the requirement.
- Full StorageCluster/Ceph decisions are delegated to `odf-storagecluster`.

## Live Checks

Run only after the OpenShift safety guard passes:

```bash
oc get noobaa -n openshift-storage
oc get pods -n openshift-storage
oc get route s3 -n openshift-storage
oc get storageclass openshift-storage.noobaa.io
```

## Security

- NooBaa admin credentials are not committed.
- Generated bucket credentials are not committed.
- Example endpoints do not include real tokens or access keys.

## Handoff

- Project buckets route to `odf-object-bucket-claims`.
- RHOAI user-facing object-store workflow routes to
  `rhoai-s3-object-storage-data`.
- Generic OCP route or networking issues route to future OCP networking or
  ingress skills once created.
