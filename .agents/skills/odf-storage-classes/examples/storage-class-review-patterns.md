# Storage-Class Review Patterns

## Identify ODF Classes

```bash
oc get storageclass
```

Common ODF class names can include:

- `ocs-storagecluster-ceph-rbd`
- `ocs-storagecluster-cephfs`
- `openshift-storage.noobaa.io`

Verify actual names from the live cluster. Do not assume they exist until ODF
has been installed and validated.

## Inspect One Class

```bash
oc get storageclass <name> -o yaml
```

Review the provisioner, parameters, reclaim policy, volume binding mode, and
default-class annotation before referencing the class in GitOps content.

## RHOAI Handoff

When making a storage class visible or friendly in OpenShift AI, use
`rhoai-storage-classes` for the dashboard-specific resource and UX guidance.
