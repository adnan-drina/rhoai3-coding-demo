---
name: odf-multicloud-gateway
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: odf
  docs-version: "4.22"
  skill-group: "OpenShift Data Foundation"
description: >
  Use when operating or reviewing the demo's shared S3 service: the standalone
  Multicloud Object Gateway (NooBaa), its health, S3 endpoint and route, the
  default pv-pool backing store and bucket class, NooBaa database backup, and
  capacity limits. Do NOT use for project ObjectBucketClaim manifests (use
  odf-object-bucket-claims), the ODF install or upgrade (use
  odf-storagecluster), or RHOAI workbench S3 user workflows (use
  rhoai-s3-object-storage-data).
---

# ODF Multicloud Object Gateway

Thin skill: repo decisions and pitfalls here, product behavior in the linked
ODF 4.22 sections. Install-side facts live in
`gitops/stages/010-openshift-ai-platform-foundation/010-odf/README.md`.

## When to use

- NooBaa is not `Ready`, OBCs stay `Pending`, or S3 clients cannot connect.
- Someone proposes a new BackingStore, BucketClass, namespace bucket, or
  endpoint scaling.
- Planning how much object data the demo can hold, or how to back it up.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| MCG is the only ODF service; it is the S3 store for models, workbenches, pipelines, MLflow and GitLab | `gitops/stages/010-openshift-ai-platform-foundation/010-odf/storagecluster.yaml` | [Deploy standalone MCG][aws-mcg] |
| Default `pv-pool` BackingStore and default BucketClass are operator-created and not in Git | not in Git (see the 010-odf README "Not in Git") | [Managing hybrid and multicloud resources][mcg] |
| No custom BackingStore, BucketClass, namespace bucket, or bucket policy | — | [Managing hybrid and multicloud resources][mcg] |
| No committed NooBaa admin or bucket credentials; consumers read generated Secrets in-cluster | `gitops/stages/010-openshift-ai-platform-foundation/010-sandbox-storage/` | [Object Bucket Claim][obc] |

## Procedure

1. Run the OpenShift safety guard from `AGENTS.md`, then check read-only:

   ```bash
   oc get noobaa noobaa -n openshift-storage -o jsonpath='{.status.phase}{"\n"}'
   oc get backingstore,bucketclass -n openshift-storage
   oc get pods -n openshift-storage
   oc get storageclass openshift-storage.noobaa.io
   ```

2. The standalone-MCG verification in the [AWS guide][aws-mcg-create] expects
   `noobaa-operator`, `noobaa-core`, two `noobaa-db-pg-cluster` instances,
   `noobaa-endpoint` and `cnpg-controller-manager` Running.
3. Before adding any MCG resource to Git, read the matching chapter of
   [Managing hybrid and multicloud resources][mcg], check the schema with
   `oc explain`, record the decision in the 010-odf README, and keep it in
   the `010-odf` Application.
4. For durable data, follow [Backup and recovery of the NooBaa DB][noobaa-db]
   before relying on the demo store; the demo does not configure it today.

## Pitfalls

- Capacity is the `pv-pool` on `gp3-csi`: finite, single-zone, no replication.
  Large model artifacts fill it; check usage before adding buckets.
- The S3 endpoint consumers use comes from each OBC's ConfigMap
  (`BUCKET_HOST`, port 443, HTTPS); do not hard-code a route host in Git.
- `noobaa-admin` credentials are break-glass only; never copy them into Git,
  READMEs, or connection Secrets.

## Official documentation (ODF 4.22)

| Topic | Section |
|---|---|
| Standalone MCG deployment and verification | [Deploy standalone MCG][aws-mcg], [Creating a standalone MCG][aws-mcg-create] |
| Backing stores, bucket classes, namespace buckets, endpoints, security | [Managing hybrid and multicloud resources][mcg] |
| Bucket claims | [Object Bucket Claim][obc] |
| NooBaa DB backup | [Backup and recovery of the MCG metadata database][noobaa-db] |
| Monitoring and diagnostics | [Monitoring ODF][monitor], [must-gather][mustgather] |

## Related skills

`odf-storagecluster`, `odf-object-bucket-claims`, `rhoai-s3-object-storage-data`.

[aws-mcg]: https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.22/html-single/deploying_openshift_data_foundation_using_amazon_web_services/index#deploy-standalone-multicloud-object-gateway
[aws-mcg-create]: https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.22/html-single/deploying_openshift_data_foundation_using_amazon_web_services/index#creating-standalone-multicloud-object-gateway_rhodf
[mcg]: https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.22/html/managing_hybrid_and_multicloud_resources/index
[obc]: https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.22/html/managing_hybrid_and_multicloud_resources/object-bucket-claim
[noobaa-db]: https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.22/html-single/managing_and_allocating_storage_resources/index#enabling-automatic-backup-of-multicloud-object-gateway-metadata-database_rhodf
[monitor]: https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.22/html-single/monitoring_openshift_data_foundation/index
[mustgather]: https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.22/html-single/troubleshooting_openshift_data_foundation/index#downloading-log-files-and-diagnostic-information_rhodf
