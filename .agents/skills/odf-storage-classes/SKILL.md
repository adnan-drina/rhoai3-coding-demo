---
name: odf-storage-classes
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: odf
  docs-version: "4.22"
  skill-group: "OpenShift Data Foundation"
description: >
  Use when deciding which storage class a demo workload should use, reviewing
  the ODF-provided openshift-storage.noobaa.io class, or evaluating a proposal
  for ODF Ceph RBD/CephFS classes, custom pools, reclaim policy, or binding
  mode. Do NOT use for generic OpenShift storage semantics (use ocp-storage),
  RHOAI dashboard storage-class visibility (use rhoai-storage-classes), project
  ObjectBucketClaims (use odf-object-bucket-claims), or MCG administration (use
  odf-multicloud-gateway).
---

# ODF Storage Classes

Thin skill: repo decisions and pitfalls here, product behavior in the linked
ODF 4.22 sections.

## When to use

- A manifest sets `storageClassName` and you must choose one.
- Someone proposes RWX storage, Ceph RBD/CephFS classes, or a custom ODF class.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| ODF provides exactly one class: `openshift-storage.noobaa.io` (provisioner `openshift-storage.noobaa.io/obc`, reclaim `Delete`), for OBCs only | operator-owned; listed in `gitops/stages/010-openshift-ai-platform-foundation/odf/README.md` | [Storage classes][sc] |
| Block storage (PVCs, including the MCG database) uses the cluster's AWS EBS CSI class `gp3-csi`, not ODF | `gitops/stages/010-openshift-ai-platform-foundation/odf/storagecluster.yaml` | — (cluster-provided) |
| No `ocs-storagecluster-ceph-rbd` or `ocs-storagecluster-cephfs` classes exist, because there is no Ceph cluster | — | [Deploy standalone MCG][aws-mcg] |
| RHOAI dashboard storage-class display is configured by the RHOAI skill, not here | — | see `rhoai-storage-classes` |

## Procedure

1. Object data → OBC on `openshift-storage.noobaa.io` (`odf-object-bucket-claims`).
2. RWO PVC → the cluster default CSI class; check with
   `oc get storageclass` after the OpenShift safety guard in `AGENTS.md`.
3. RWX or Ceph-backed need → this is an ODF topology change, not a class
   change: take it to `odf-storagecluster` and record the decision in the
   010-odf README before any manifest.
4. Before referencing any class in Git, inspect it:
   `oc get storageclass <name> -o yaml` (provisioner, reclaimPolicy,
   volumeBindingMode, default-class annotation).

## Pitfalls

- ODF default storage classes are operator-owned and cannot be deleted or
  modified ([Storage classes][sc]); create a custom class instead
  ([Creating storage classes and pools][sc-create]) — only once Ceph exists.
- `Delete` reclaim on the NooBaa class removes bucket data with the claim.
- Do not reference Ceph class names from ODF examples; they do not exist here.

## Official documentation (ODF 4.22)

| Topic | Section |
|---|---|
| Storage class model, default class ownership | [Storage classes][sc] |
| Custom classes and pools | [Creating storage classes and pools][sc-create] |
| Why there is no Ceph here | [Deploy standalone MCG][aws-mcg] |

## Related skills

`ocp-storage`, `rhoai-storage-classes`, `odf-object-bucket-claims`, `odf-storagecluster`.

[sc]: https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.22/html-single/managing_and_allocating_storage_resources/index#storage-classes_rhodf
[sc-create]: https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.22/html-single/managing_and_allocating_storage_resources/index#creating-storage-classes-and-pools_rhodf
[aws-mcg]: https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.22/html-single/deploying_openshift_data_foundation_using_amazon_web_services/index#deploy-standalone-multicloud-object-gateway
