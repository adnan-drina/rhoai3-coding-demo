# Source Capture

## Baseline

- Product family: Red Hat OpenShift Data Foundation
- Product version: repository baseline in `docs/PLATFORM_BASELINE.md`
- Active ODF baseline while authored: 4.20
- Active OCP baseline while authored: 4.20
- Retrieved: 2026-06-10

## Official Sources

- Managing and allocating storage resources:
  https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.20/html-single/managing_and_allocating_storage_resources/index
- Red Hat OpenShift Data Foundation architecture:
  https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.20/html-single/red_hat_openshift_data_foundation_architecture/index
- Deploying OpenShift Data Foundation using Amazon Web Services:
  https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.20/html-single/deploying_openshift_data_foundation_using_amazon_web_services/index

## Sections Used

- ODF storage services and storage-class model.
- Storage class creation and storage-pool selection.
- Default ODF storage class ownership and support boundaries.
- AWS deployment verification output for ODF-created storage classes.

## Related Sources

- `ocp-storage` covers generic OpenShift storage API behavior.
- `rhoai-storage-classes` covers RHOAI dashboard storage-class visibility.

## Source Boundaries

- This skill does not define all OpenShift StorageClass semantics.
- This skill does not define RHOAI dashboard UX.
- Recheck source URLs whenever the ODF baseline changes.
