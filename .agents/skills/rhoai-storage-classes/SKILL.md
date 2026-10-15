---
name: rhoai-storage-classes
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when someone wants to enable, rename or set the default of a storage
  class in OpenShift AI (Settings > Cluster settings > Storage classes),
  choose access modes such as ReadWriteMany for workbench cluster storage, or
  asks which storage class backs workbench PVCs in this demo (gp3-csi block,
  ODF openshift-storage.noobaa.io only for buckets). Do NOT use for the
  default PVC size (use rhoai-cluster-pvc-size), S3 data access from
  workbenches (use rhoai-s3-object-storage-data), ODF storage classes and
  ObjectBucketClaims (use odf-storage-classes, odf-object-bucket-claims), or
  OpenShift storage in general (use ocp-storage).
---

# RHOAI storage classes

Thin skill. Not customized in this demo: OpenShift AI storage class settings
are left at their defaults and no GitOps object sets them. Product behavior is
in the linked OpenShift AI 3.5 sections.

## When to use

- A workbench needs shared (RWX) cluster storage.
- The storage class list in the dashboard is questioned or must change.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Block storage comes from the cluster's AWS EBS CSI class `gp3-csi`; repo-managed PVCs name it explicitly | `gitops/stages/010-openshift-ai-platform-foundation/010-odf/README.md` ("Depends on"), for example `gitops/stages/050-model-evaluation/050-mlflow/postgresql-pvc.yaml` | [Storage classes in OpenShift AI][sc-rhoai] |
| ODF is standalone Multicloud Object Gateway only: `openshift-storage.noobaa.io` serves ObjectBucketClaims, not workbench PVCs; no Ceph block or file classes, so no RWX class | `gitops/stages/010-openshift-ai-platform-foundation/010-odf/` | [Access modes][access], [Object storage endpoints][object] |
| No OpenShift AI storage class settings (enabled list, display names, access modes, default) in Git; the OpenShift AI default is not changed | none under `gitops/` | [Configure storage class settings][settings], [Configure the default storage class][default] |
| Data sharing between workbenches goes through S3 connections, not RWX volumes | `gitops/stages/010-openshift-ai-platform-foundation/010-sandbox-storage/README.md` | [Persistent storage for workbenches][persistent] |

## Procedure

1. Check the classes and what the cluster supports, after the OpenShift
   safety guard in `AGENTS.md`:

   ```bash
   oc get storageclass
   oc get pvc -n demo-sandbox -o custom-columns=NAME:.metadata.name,CLASS:.spec.storageClassName,MODES:.spec.accessModes
   ```

2. Before offering RWX, a class that supports it must exist; that needs a new
   storage backend (for example ODF file storage), which is a platform change
   with its own GitOps component and README (see `odf-storage-classes`).
3. Dashboard settings change only what OpenShift AI users see, not the
   OpenShift class ([Configure storage class settings][settings]). If one is
   changed, record it in `docs/OPERATIONS.md`, because it is not in Git.

## Pitfalls

- `ReadWriteMany` lets several workbenches write the same data; read
  [Using shared storage (RWX)][rwx] before enabling it.
- The OpenShift AI default storage class can differ from the OpenShift
  default ([Configure the default storage class][default]); check both when a
  PVC lands on an unexpected class.

## Official documentation (OpenShift AI 3.5)

| Topic | Section |
|---|---|
| Chapter | [Manage storage classes][chapter] |
| Concepts | [Persistent storage][persistent], [Storage classes in OpenShift AI][sc-rhoai], [Access modes][access], [Shared storage (RWX)][rwx] |
| Procedures | [Storage class settings][settings], [Default storage class][default] |
| Object storage | [Object storage endpoints][object] |

## Related skills

`rhoai-cluster-pvc-size`, `rhoai-s3-object-storage-data`,
`rhoai-connection-types`, `odf-storage-classes`, `odf-object-bucket-claims`,
`ocp-storage`, `rhoai-project-workflows`.

[chapter]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#managing-storage-classes
[persistent]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#about-persistent-storage_resource-mgmt
[sc-rhoai]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#storage_classes_in_openshift_ai
[access]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#access_modes
[rwx]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#using_shared_storage_rwx
[settings]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#configuring-storage-class-settings_resource-mgmt
[default]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#configuring-the-default-storage-class-for-your-cluster_resource-mgmt
[object]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#overview-of-object-storage-endpoints_resource-mgmt
