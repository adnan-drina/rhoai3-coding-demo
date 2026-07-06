# Source Capture

## Baseline

- Product family: Red Hat OpenShift AI Self-Managed
- Product version: repository baseline in `docs/PLATFORM_BASELINE.md`
- Active RHOAI baseline while authored: 3.4
- Active OCP baseline while authored: 4.20
- Retrieved: 2026-06-10

## Official Sources

- Installing and deploying OpenShift AI:
  https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/installing_and_uninstalling_openshift_ai_self-managed/installing-and-deploying-openshift-ai_install
- Managing observability:
  https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_openshift_ai/managing-observability_managing-rhoai
- Viewing logs and audit records:
  https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/installing_and_uninstalling_openshift_ai_self-managed/viewing-logs-and-audit-records_install

## Sections Used

- Platform and component requirements.
- Configuring custom namespaces.
- Installing Red Hat OpenShift AI components by creating a
  `DataScienceCluster`.
- `managementState` values for `Managed` and `Removed`.
- Verification of `DataScienceCluster` phase and installed component status.
- DSCI monitoring configuration handoff.
- Audit-record boundary for changes to DSC and DSCI custom resources.

## Source Boundaries

- This skill captures CR ownership and field-placement patterns. Use
  component-specific skills for individual component behavior.
- Use live `oc explain` and CRD inspection before introducing fields not
  present in official examples.
- Recheck all links when `docs/PLATFORM_BASELINE.md` changes.
