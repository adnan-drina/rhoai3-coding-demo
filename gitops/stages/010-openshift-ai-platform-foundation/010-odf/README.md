# OpenShift Data Foundation object storage (`010-odf`)

This Application installs OpenShift Data Foundation (ODF) and creates a standalone Multicloud Object Gateway (MCG,
NooBaa). The demo gets S3-compatible object storage and the `openshift-storage.noobaa.io` StorageClass for
ObjectBucketClaims (OBCs). It does not deploy Ceph block or file storage. The sandbox buckets in
[`010-sandbox-storage`](../010-sandbox-storage/README.md) consume it, and so do
later stages that need buckets.

| | |
|---|---|
| Argo CD Application | `010-odf` ([manifest](../../../applications/010-odf.yaml)) |
| Deployed by | [`stages/010-openshift-ai-platform-foundation/deploy.sh`](../../../../stages/010-openshift-ai-platform-foundation/deploy.sh) (deploy-order 1) |
| Validated by | [`validate.sh`](../../../../stages/010-openshift-ai-platform-foundation/validate.sh) (Application Synced/Healthy; `odf-operator` CSV `Succeeded`; `NooBaa/noobaa` phase `Ready`); `check-operator-policy.py --verify` |
| Sync | Automated, prune and self-heal; `CreateNamespace`, `SkipDryRunOnMissingResource`, `RespectIgnoreDifferences`; Server-Side Diff via annotation; no `ignoreDifferences` |
| Depends on | OpenShift GitOps bootstrap; the `gp3-csi` StorageClass (AWS EBS CSI, provided by the cluster) |
| Used by | `010-sandbox-storage` (OBCs `rhoai-models`, `rhoai-workbench`), Stage 050 (`050-mlflow/objectbucketclaim.yaml`, `050-model-qualification/storage/`), Stage 070 GitLab buckets (`gitops/stages/070-advanced-app-platform/070-gitlab/buckets.yaml`) |

## Why

Model artifacts, workbench exchange data, pipeline data and evaluation evidence need S3-compatible storage inside the
cluster. ODF can deploy only the Multicloud Object Gateway, without Ceph ("Deploy standalone Multicloud Object
Gateway") [1]. OBCs against `openshift-storage.noobaa.io` then create buckets with a ConfigMap and a Secret named after
the claim [2]. This is the smallest ODF footprint for the demo. Block and file storage come from the cluster's default
CSI storage. The operator and its single StorageCluster share one lifecycle, so they form one Application.

## What

| Kind | Name | Namespace | Wave | Purpose |
|---|---|---|---|---|
| Namespace | `openshift-storage` | (cluster) | 0 | ODF namespace, label `openshift.io/cluster-monitoring: "true"` |
| OperatorGroup | `openshift-storage-operatorgroup` | `openshift-storage` | 0 | `targetNamespaces: [openshift-storage]` (OwnNamespace) |
| Subscription | `odf-operator` | `openshift-storage` | 0 | Channel `stable-4.22`, `Automatic`, `redhat-operators` |
| StorageCluster | `ocs-storagecluster` | `openshift-storage` | 2 | `multiCloudGateway.reconcileStrategy: standalone`, `dbStorageClassName: gp3-csi`; no `storageDeviceSets` |

The kustomization adds `SkipDryRunOnMissingResource=true` to every object, because the StorageCluster CRD exists only
after the CSV succeeds. There are no hooks.

Not in Git (operator-owned):

- the dependent operator Subscriptions and CSVs (live `odf-operator.v4.22.5-rhodf`);
- `OCSInitialization/ocsinit`, which the operator creates and reconciles. The kustomization comment explains why it is
  not managed here;
- `NooBaa/noobaa`, `BackingStore/noobaa-default-backing-store` (type `pv-pool`) and
  `BucketClass/noobaa-default-bucket-class`;
- the NooBaa database PVCs (`noobaa-db-pg-cluster-1/2`, `gp3-csi`, `ReadWriteOncePod`);
- the `openshift-storage.noobaa.io` StorageClass (provisioner `openshift-storage.noobaa.io/obc`, reclaim `Delete`).

## How

- **Channel and approval.** The channel is `stable-4.22`, matching the OpenShift 4.22 minor. Approval is `Automatic`.
  `check-operator-policy.py` refuses other channels and versions below the qualified `4.22.5`.
- **Standalone MCG.** The documented procedure picks "Setup Multicloud Object Gateway" in the console [1]. The GitOps
  equivalent is a `StorageCluster` with `spec.multiCloudGateway.reconcileStrategy: standalone` and no device sets. On
  this cluster there is no `odf.openshift.io` StorageSystem API, so the StorageCluster is the top-level object. The
  manifest comment records the field values that were checked live.
- **`dbStorageClassName: gp3-csi`.** The documentation says to use an existing StorageClass [1]. `gp3-csi` is the AWS
  EBS CSI class on this cluster. The MCG database uses `ReadWriteOncePod`, which EBS CSI supports [1]. This is a
  cluster-specific value written in Git. A cluster on another platform needs a different class.
- **Capacity.** The default backing store is a `pv-pool` on `gp3-csi`. It has finite capacity and no replication
  across zones. That is enough for the demo, but it is not an HA production design (see the Stage 010 README).
- **Ordering.** Wave 2 puts the StorageCluster after the Subscription. Argo CD retries until the CRD exists.
  `010-sandbox-storage` OBCs wait for the StorageClass through their own waves and retries.
- **Credentials.** None in this component. OBC credentials are generated per claim in the consumer namespace.

## Validation

`validate.sh` checks the following:

- the Subscription's installed CSV is `Succeeded`;
- `noobaa` is in phase `Ready`;
- the Application is Synced and Healthy at the reviewed revision.

Check by hand:

```bash
oc get storagecluster ocs-storagecluster -n openshift-storage -o jsonpath='{.status.phase}{"\n"}'
oc get noobaa noobaa -n openshift-storage -o jsonpath='{.status.phase}{"\n"}'; oc get sc openshift-storage.noobaa.io
```

## Alignment with official guidance

| Topic | Official guidance (link) | This repository | Status |
|---|---|---|---|
| Deployment mode | "Deploy standalone Multicloud Object Gateway" [1] | StorageCluster with `reconcileStrategy: standalone`, no Ceph | Aligned |
| Install mode | Operator installed into "A specific namespace on the cluster" (`openshift-storage`) [1] | OperatorGroup targeting `openshift-storage` | Aligned |
| Version match | ODF 4.22 documentation for OpenShift 4.22 | `stable-4.22` | Aligned |
| Database storage | Use an existing StorageClass; the MCG database uses RWOP [1] | `gp3-csi`; live PVCs are RWOP | Aligned |
| Verification | NooBaa operator, core, two `noobaa-db-pg-cluster` instances, endpoint pods Running [1] | `validate.sh` checks the `NooBaa` phase, not the pods | Aligned |
| OBC consumption | `storageClassName: openshift-storage.noobaa.io`; ConfigMap and Secret named after the OBC [2] | The consumers follow this | Aligned |
| Update approval | Not prescribed in [1] | `Automatic` with the repository version policy | Deviation (justified: demo follows z-streams; the policy enforces minor and minimum version) |

## References

1. Deploying OpenShift Data Foundation using Amazon Web Services, Chapter 3: Deploy standalone Multicloud Object Gateway. Red Hat OpenShift Data Foundation 4.22. https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.22/html-single/deploying_openshift_data_foundation_using_amazon_web_services/index
2. Managing hybrid and multicloud resources, Chapter 12: Object Bucket Claim. Red Hat OpenShift Data Foundation 4.22. https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.22/html/managing_hybrid_and_multicloud_resources/object-bucket-claim
