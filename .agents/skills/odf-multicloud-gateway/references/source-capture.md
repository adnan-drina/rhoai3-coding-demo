# Source Capture

## Baseline

- Product family: Red Hat OpenShift Data Foundation
- Product version: repository baseline in `docs/PLATFORM_BASELINE.md`
- Active ODF baseline while authored: 4.20
- Active OCP baseline while authored: 4.20
- Retrieved: 2026-06-10

## Official Sources

- Deploying OpenShift Data Foundation using Amazon Web Services:
  https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.20/html-single/deploying_openshift_data_foundation_using_amazon_web_services/index
- Red Hat OpenShift Data Foundation architecture:
  https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.20/html-single/red_hat_openshift_data_foundation_architecture/index
- Managing hybrid and multicloud resources:
  https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.20/html/managing_hybrid_and_multicloud_resources/index
- Monitoring OpenShift Data Foundation:
  https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.20/html-single/monitoring_openshift_data_foundation/index
- Troubleshooting OpenShift Data Foundation:
  https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.20/html-single/troubleshooting_openshift_data_foundation/index

## Supporting Red Hat Article

- Red Hat OpenShift Data Foundation for developers and data scientists:
  https://developers.redhat.com/articles/2024/07/31/red-hat-openshift-data-foundation-developers-and-data-scientists

Use the article for narrative support around lightweight MCG and data-scientist
object-storage needs. Official ODF documentation remains the authority.

## Sections Used

- Standalone MCG deployment path on AWS.
- MCG architecture and S3-compatible service role.
- Managing hybrid and multicloud object resources, including backing stores,
  bucket classes, S3 endpoint access, endpoint scaling, and object policies.
- Monitoring object service and ObjectBucketClaim health.
- Troubleshooting and must-gather handoff.

## Source Boundaries

- This skill does not define per-application OBC manifests.
- This skill does not define RHOAI workbench UX for S3 consumption.
- Recheck all source URLs whenever the ODF baseline changes.
