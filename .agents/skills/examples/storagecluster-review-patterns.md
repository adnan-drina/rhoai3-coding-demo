# StorageCluster Review Patterns

Use these examples as review patterns, not as a complete install runbook.

## Object-Only Default

For the RHOAI demo, first ask whether S3-compatible object storage is enough.
If yes, use standalone MCG and route implementation detail to
`odf-multicloud-gateway`.

## Full StorageCluster Justification

Document a full StorageCluster only when the demo requires ODF-provided block
or file storage, for example:

- Ceph RBD-backed RWO PVCs are required by a demo workload.
- CephFS-backed RWX PVCs are required by a shared data workflow.
- ODF storage classes are intentionally showcased as part of the demo concept.

## Readonly Validation Commands

Run only after the repo OpenShift safety guard has verified the target cluster.

```bash
oc get csv -n openshift-storage
oc get pods -n openshift-storage
oc get storageclass
oc get storagecluster -n openshift-storage
oc get noobaa -n openshift-storage
```

## Must-Gather Pattern

Use the active ODF version image from official docs. For ODF 4.20:

```bash
oc adm must-gather \
  --image=registry.redhat.io/odf4/odf-must-gather-rhel9:v4.20 \
  --dest-dir=tmp/must-gather-odf
```
