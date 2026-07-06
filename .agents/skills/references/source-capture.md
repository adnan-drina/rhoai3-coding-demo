# Source Capture

## Baseline

- Product family: Red Hat OpenShift Data Foundation
- Product version: repository baseline in `docs/PLATFORM_BASELINE.md`
- Active ODF baseline while authored: 4.20
- Active OCP baseline while authored: 4.20
- Retrieved: 2026-06-10

## Official Sources

- Planning your deployment:
  https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.20/html-single/planning_your_deployment/index
- Red Hat OpenShift Data Foundation architecture:
  https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.20/html-single/red_hat_openshift_data_foundation_architecture/index
- Deploying OpenShift Data Foundation using Amazon Web Services:
  https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.20/html-single/deploying_openshift_data_foundation_using_amazon_web_services/index
- Updating OpenShift Data Foundation:
  https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.20/html-single/updating_openshift_data_foundation/index
- Monitoring OpenShift Data Foundation:
  https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.20/html-single/monitoring_openshift_data_foundation/index
- Troubleshooting OpenShift Data Foundation:
  https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.20/html-single/troubleshooting_openshift_data_foundation/index

The user provided the ODF 4.21 troubleshooting URL. This skill uses the ODF
4.20 troubleshooting URL because `docs/PLATFORM_BASELINE.md` pins ODF 4.20.

## Supporting Red Hat Article

- Red Hat OpenShift Data Foundation for developers and data scientists:
  https://developers.redhat.com/articles/2024/07/31/red-hat-openshift-data-foundation-developers-and-data-scientists

Use the article for narrative and lightweight MCG/OBC examples only. Official
ODF documentation remains the product configuration authority.

## Sections Used

- ODF planning and architecture overview.
- AWS deployment support and standalone MCG deployment path.
- Verification of ODF, NooBaa, and related pods.
- Dashboard health validation for StorageCluster and Object service.
- Storage class creation and verification outputs.
- ODF update version alignment with OCP.
- ODF monitoring dashboards and alert signals.
- ODF troubleshooting and must-gather collection.

## Source Boundaries

- This skill does not define RHOAI storage UX. Use `rhoai-storage-classes`,
  `rhoai-cluster-pvc-size`, or `rhoai-s3-object-storage-data`.
- This skill does not define generic OCP PV/PVC semantics. Use `ocp-storage`.
- This skill does not authorize unsupported Ceph commands.
- Recheck all source URLs when the ODF or OCP baseline changes.
