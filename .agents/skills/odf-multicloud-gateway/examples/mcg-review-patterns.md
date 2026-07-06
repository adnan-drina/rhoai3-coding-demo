# MCG Review Patterns

## Readiness Checks

Run only after the repo OpenShift safety guard verifies the target cluster.

```bash
oc get noobaa -n openshift-storage
oc get pods -n openshift-storage
oc get route s3 -n openshift-storage
oc get storageclass openshift-storage.noobaa.io
```

## Admin Credentials Boundary

The Red Hat Developer article shows that NooBaa admin credentials can be
retrieved from the `noobaa-admin` Secret. Treat that as an operational break
glass pattern, not normal GitOps desired state. Do not copy the secret values
into this repository.

## Project Bucket Handoff

After MCG is healthy, create project buckets through ObjectBucketClaims and
consume generated Secrets/ConfigMaps from workloads:

- Use `odf-object-bucket-claims` for the OBC manifest.
- Use `rhoai-s3-object-storage-data` for RHOAI data-scientist usage.
