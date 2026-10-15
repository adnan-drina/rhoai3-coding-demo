---
name: odf-object-bucket-claims
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: odf
  docs-version: "4.22"
  skill-group: "OpenShift Data Foundation"
description: >
  Use when adding, reviewing, or debugging an ObjectBucketClaim in this demo:
  project-scoped S3 buckets on openshift-storage.noobaa.io, the generated
  ConfigMap and Secret, mapping OBC output into RHOAI S3 connections, Argo CD
  prune/delete protection for bucket data, and OBC deletion behavior. Do NOT use
  for MCG/NooBaa service administration (use odf-multicloud-gateway), the ODF
  install (use odf-storagecluster), generic OpenShift storage (use ocp-storage),
  or RHOAI user-facing S3 workflows (use rhoai-s3-object-storage-data).
---

# ODF ObjectBucketClaims

Thin skill: repo decisions and pitfalls here, product behavior in the linked
ODF 4.22 sections. Copy the pattern from an existing claim in Git, not from
documentation examples.

## When to use

- A stage needs a new S3 bucket.
- An OBC stays `Pending`, or a consumer cannot read the generated credentials.
- Reviewing how bucket credentials reach a workload or an RHOAI connection.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Every bucket is an OBC on `openshift-storage.noobaa.io` | OBCs listed below | [Object Bucket Claim][obc] |
| Fixed `bucketName` (not `generateBucketName`) so buckets are predictable across rebuilds; exception: the Stage 070 GitLab buckets use `generateBucketName` | `gitops/stages/010-openshift-ai-platform-foundation/010-sandbox-storage/obc-models.yaml`; `gitops/stages/070-advanced-app-platform/070-gitlab/buckets.yaml` | [Object Bucket Claim][obc] |
| Bucket objects carry `argocd.argoproj.io/sync-options: Prune=false,Delete=false` so data outlives the Application (GitLab buckets: `Prune=false` only) | `010-sandbox-storage/obc-*.yaml`, Stage 050 OBCs | — (Argo CD behavior) |
| Generated credentials never enter Git; a hook Job copies OBC output into RHOAI connection Secrets in-cluster, with owner-UID and HTTPS/443 checks | `010-sandbox-storage/connection-job.yaml`, `role.yaml` | [Object Bucket Claim][obc] |
| RHOAI connections are Secret skeletons in Git (`opendatahub.io/connection-type-protocol: s3`), data filled at runtime and ignored by Argo CD | `010-sandbox-storage/connection-*.yaml` | see `rhoai-connection-types` |

Existing claims to copy from:

- `gitops/stages/010-openshift-ai-platform-foundation/010-sandbox-storage/obc-models.yaml`, `obc-workbench.yaml`
- `gitops/stages/050-model-evaluation/050-mlflow/objectbucketclaim.yaml`
- `gitops/stages/050-model-evaluation/050-model-qualification/storage/obc-*.yaml`
- `gitops/stages/070-advanced-app-platform/070-gitlab/buckets.yaml`

## Procedure

1. Copy the nearest existing claim; keep the namespace, a fixed `bucketName`,
   `storageClassName: openshift-storage.noobaa.io`, and the
   `Prune=false,Delete=false` sync option.
2. Consume the generated ConfigMap and Secret (both named after the claim)
   through `envFrom`/`valueFrom` or an in-cluster Job; never copy values.
3. Document the bucket in the owning component README (What table, Not in Git).
4. Validate after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get obc -n <namespace> <claim> -o jsonpath='{.status.phase}{"\n"}'   # Bound
   oc get configmap,secret -n <namespace> <claim>
   ```

## Pitfalls

- `openshift-storage.noobaa.io` has reclaim policy `Delete`: removing a claim
  removes its bucket and data. That is why the repo forbids prune and delete
  on bucket objects; read the deletion section of [Object Bucket Claim][obc]
  before deleting one by hand.
- The ConfigMap may lack `BUCKET_REGION`; the sandbox Job falls back to
  `us-east-1`.
- Generated Secrets are owned by the OBC; an OBC that already has another
  owner or tracking id is refused by `stages/010-openshift-ai-platform-foundation/deploy.sh --component 010-sandbox-storage`.

## Official documentation (ODF 4.22)

| Topic | Section |
|---|---|
| OBC lifecycle, generated ConfigMap/Secret, deletion | [Object Bucket Claim][obc] |
| The MCG service behind the claims | [Managing hybrid and multicloud resources][mcg] |
| Storage class model | [Storage classes][sc] |

## Related skills

`odf-multicloud-gateway`, `rhoai-s3-object-storage-data`, `rhoai-connection-types`.

[obc]: https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.22/html/managing_hybrid_and_multicloud_resources/object-bucket-claim
[mcg]: https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.22/html/managing_hybrid_and_multicloud_resources/index
[sc]: https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.22/html-single/managing_and_allocating_storage_resources/index#storage-classes_rhodf
