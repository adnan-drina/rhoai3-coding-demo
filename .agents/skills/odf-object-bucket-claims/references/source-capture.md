# Source Capture

## Baseline

- Product family: Red Hat OpenShift Data Foundation
- Product version: repository baseline in `docs/PLATFORM_BASELINE.md`
- Active ODF baseline while authored: 4.20
- Active OCP baseline while authored: 4.20
- Retrieved: 2026-06-10

## Official Sources

- Managing hybrid and multicloud resources:
  https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.20/html/managing_hybrid_and_multicloud_resources/index
- ObjectBucketClaim chapter:
  https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.20/html/managing_hybrid_and_multicloud_resources/object-bucket-claim
- Managing and allocating storage resources:
  https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.20/html-single/managing_and_allocating_storage_resources/index

## Supporting Red Hat Article

- Red Hat OpenShift Data Foundation for developers and data scientists:
  https://developers.redhat.com/articles/2024/07/31/red-hat-openshift-data-foundation-developers-and-data-scientists

Use the article for the lightweight developer/data-scientist OBC example and
for narrative context. Verify API fields against official docs and live CRDs
before using them in active GitOps.

## Sections Used

- ObjectBucketClaim lifecycle and application attachment.
- Viewing object buckets and deleting ObjectBucketClaims.
- ODF object storage class handoff.
- Supporting article examples for generated OBC ConfigMaps, Secrets, endpoint
  discovery, and S3 credential consumption.

## Source Boundaries

- This skill does not define every MCG backing-store or bucket-class feature.
- This skill does not make generated Secrets safe to commit.
- Recheck all source URLs whenever the ODF baseline changes.
