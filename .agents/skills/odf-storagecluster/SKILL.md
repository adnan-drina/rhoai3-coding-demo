---
name: odf-storagecluster
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: odf
  docs-version: "4.22"
  skill-group: "OpenShift Data Foundation"
description: >
  Use when reviewing, changing, upgrading, or troubleshooting the OpenShift Data
  Foundation install of this demo: the odf-operator Subscription channel, the
  standalone-MCG StorageCluster, the choice between object-only MCG and full
  Ceph block/file storage, ODF/OpenShift version matching, monitoring, and
  must-gather. Do NOT use for project bucket requests (use
  odf-object-bucket-claims), MCG/NooBaa service operation (use
  odf-multicloud-gateway), generic OpenShift storage (use ocp-storage), or
  RHOAI workbench S3 consumption (use rhoai-s3-object-storage-data).
---

# ODF StorageCluster

Thin skill: repo decisions and pitfalls here, product behavior in the linked
ODF 4.22 sections. The component README is the detailed record:
`gitops/stages/010-openshift-ai-platform-foundation/odf/README.md`.

## When to use

- A change touches `gitops/stages/010-openshift-ai-platform-foundation/odf/`.
- Someone proposes Ceph RBD/CephFS storage, an ODF upgrade, or a new ODF consumer.
- ODF or NooBaa is unhealthy and you need the first diagnostics.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Standalone Multicloud Object Gateway only; no Ceph, no `storageDeviceSets` | `odf/storagecluster.yaml` (`spec.multiCloudGateway.reconcileStrategy: standalone`) | [Deploy standalone MCG][aws-mcg] |
| No StorageSystem object; the StorageCluster is the top-level resource (no `odf.openshift.io` StorageSystem API on this cluster) | `odf/storagecluster.yaml` | [Creating a standalone MCG][aws-mcg-create] |
| MCG database on `gp3-csi` (AWS EBS CSI, RWOP) — a cluster-specific value | `odf/storagecluster.yaml` (`dbStorageClassName`) | [Deploy standalone MCG][aws-mcg] (RWOP prerequisite) |
| Channel `stable-4.22` matching the OpenShift minor, approval `Automatic` | `odf/subscription.yaml`; minimum `4.22.5` in `scripts/platform/check-operator-policy.py` | [Updating ODF][update] |
| OwnNamespace OperatorGroup in `openshift-storage` | `odf/operator-group.yaml` | [Installing the ODF Operator][aws-install] |
| `OCSInitialization/ocsinit`, NooBaa, BackingStore, BucketClass and the `openshift-storage.noobaa.io` StorageClass stay operator-owned (not in Git) | comment in `odf/kustomization.yaml` | [Architecture][arch] |
| `SkipDryRunOnMissingResource` on every object; StorageCluster at wave 2 | `odf/kustomization.yaml` | — (Argo CD behavior) |

The version is pinned once, in `.agents/references/red-hat-doc-map.yaml`
(`products.odf.docs_version`), and the checker verifies it against the
Subscription channel.

## Procedure

1. Object storage only? Stay on MCG and route bucket work to
   `odf-object-bucket-claims`. Full StorageCluster/Ceph needs a real RWO/RWX
   requirement that the cluster's default CSI storage cannot meet, a recorded
   decision in the component README, and the [AWS dynamic-device
   procedure][aws-dynamic].
2. Upgrade: change the channel in `odf/subscription.yaml` to the new OpenShift
   minor, the minimum in `check-operator-policy.py`, and `docs_version` in the
   doc map together; run `python3 scripts/shared/check-doc-links.py`; re-read
   the [release notes][relnotes] and [Updating ODF][update].
3. Validate (after the OpenShift safety guard in `AGENTS.md`):
   `./stages/010-openshift-ai-platform-foundation/validate.sh`, or by hand:

   ```bash
   oc get storagecluster ocs-storagecluster -n openshift-storage -o jsonpath='{.status.phase}{"\n"}'
   oc get noobaa noobaa -n openshift-storage -o jsonpath='{.status.phase}{"\n"}'
   oc get csv -n openshift-storage
   ```

4. Diagnose: pods and events in `openshift-storage`, the ODF dashboards
   ([Monitoring][monitor]), then [must-gather][mustgather] with the image tag
   that matches the installed ODF minor.

## Pitfalls

- The AWS guide's standalone-MCG verification lists `rook-ceph-operator`
  among expected pods while its own section 2.5 says it is absent in
  standalone mode; do not treat its absence as a failure.
- The default backing store is a `pv-pool` on `gp3-csi`: finite, single-zone,
  not an HA design.
- Do not run Ceph commands; Red Hat supports them only when support or the
  documentation instructs it ([Troubleshooting][ts]).
- `dbStorageClassName` must change on any non-AWS cluster.

## Official documentation (ODF 4.22)

| Topic | Section |
|---|---|
| Standalone MCG on AWS | [Deploy standalone Multicloud Object Gateway][aws-mcg] |
| Operator install | [Installing the ODF Operator][aws-install] |
| Full internal-mode cluster | [Deploy using dynamic storage devices][aws-dynamic] |
| Planning and architecture | [Planning your deployment][plan], [Architecture][arch] |
| Updates | [Updating OpenShift Data Foundation][update] |
| Monitoring | [Monitoring OpenShift Data Foundation][monitor] |
| Diagnostics | [must-gather][mustgather], [alerts and errors][ts] |
| Release notes | [4.22 release notes][relnotes] |

## Related skills

`odf-multicloud-gateway`, `odf-object-bucket-claims`, `odf-storage-classes`,
`ocp-storage`, `rhoai-s3-object-storage-data`.

[aws-mcg]: https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.22/html-single/deploying_openshift_data_foundation_using_amazon_web_services/index#deploy-standalone-multicloud-object-gateway
[aws-mcg-create]: https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.22/html-single/deploying_openshift_data_foundation_using_amazon_web_services/index#creating-standalone-multicloud-object-gateway_rhodf
[aws-install]: https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.22/html-single/deploying_openshift_data_foundation_using_amazon_web_services/index#installing-openshift-data-foundation-operator-using-the-operator-hub_rhodf
[aws-dynamic]: https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.22/html-single/deploying_openshift_data_foundation_using_amazon_web_services/index#deploy-using-dynamic-storage-devices-aws
[plan]: https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.22/html-single/planning_your_deployment/index
[arch]: https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.22/html-single/red_hat_openshift_data_foundation_architecture/index
[update]: https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.22/html-single/updating_openshift_data_foundation/index
[monitor]: https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.22/html-single/monitoring_openshift_data_foundation/index
[mustgather]: https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.22/html-single/troubleshooting_openshift_data_foundation/index#downloading-log-files-and-diagnostic-information_rhodf
[ts]: https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.22/html-single/troubleshooting_openshift_data_foundation/index#troubleshooting-alerts-and-errors-in-openshift-data-foundation
[relnotes]: https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.22/html/4.22_release_notes/index
