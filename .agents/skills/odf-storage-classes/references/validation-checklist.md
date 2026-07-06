# Validation Checklist

Use this checklist before finalizing ODF storage-class content.

## Source Alignment

- Links use ODF documentation from the active baseline.
- Generic OCP storage statements are delegated to `ocp-storage`.
- RHOAI dashboard visibility is delegated to `rhoai-storage-classes`.

## Storage-Class Review

- The change states whether it needs block, file, or object storage.
- Operator-owned default storage classes are not modified casually.
- Any custom storage class is backed by official docs and live schema checks.
- Object-storage class consumption routes to ObjectBucketClaims when the demo
  needs per-project buckets.

## Validation Commands

Run only after the OpenShift safety guard passes:

```bash
oc get storageclass
oc get storageclass <name> -o yaml
```

Check:

- provisioner
- reclaim policy
- volume binding mode
- default class annotation
- ODF ownership or generated status
