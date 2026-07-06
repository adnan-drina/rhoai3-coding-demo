# Validation Checklist

Use this checklist when reviewing ODF platform setup, StorageCluster content, or
standalone MCG installation decisions.

## Baseline

- `docs/PLATFORM_BASELINE.md` pins ODF and OCP versions.
- All official links use the pinned ODF version.
- Any ODF 4.21 or later troubleshooting detail is rejected or explicitly marked
  as future-baseline content.

## Platform Decision

- The change states whether it needs standalone MCG only or full
  StorageCluster/Ceph.
- Full StorageCluster/Ceph is justified by a real block or file storage need.
- Object-only needs route to `odf-multicloud-gateway`.

## Live Validation

Only run live commands after the OpenShift safety guard in `AGENTS.md` passes.
Prefer readonly checks:

```bash
oc get csv -n openshift-storage
oc get pods -n openshift-storage
oc get storageclass
oc get storagecluster -n openshift-storage
oc get noobaa -n openshift-storage
```

## Troubleshooting

- Diagnostics start with pod status, events, dashboard health, and ODF alerts.
- Must-gather uses the active ODF version image.
- No unsupported Ceph command is added without official Red Hat instruction.
- No generated credentials, kubeconfig, or NooBaa admin secrets are committed.
