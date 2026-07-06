# Validation Checklist

Use this checklist before finalizing OBC content or GitOps manifests.

## Source And Schema

- ODF baseline matches `docs/PLATFORM_BASELINE.md`.
- OBC API version and fields are verified through official docs or
  `oc explain`.
- The target object storage class exists in the active cluster.

## Secret Handling

- Generated OBC Secret data is not committed.
- Example manifests do not include real bucket credentials.
- Workloads reference generated ConfigMaps and Secrets instead of copying
  values into manifests.

## Runtime Checks

Run only after the OpenShift safety guard passes:

```bash
oc get storageclass openshift-storage.noobaa.io
oc get obc -n <namespace>
oc get configmap -n <namespace> <obc-name>
oc get secret -n <namespace> <obc-name>
```

## Handoff

- RHOAI user-facing object-store workflows route to
  `rhoai-s3-object-storage-data`.
- MCG service health and S3 route troubleshooting routes to
  `odf-multicloud-gateway`.
