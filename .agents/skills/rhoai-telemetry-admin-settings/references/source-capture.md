# Source Capture

## Baseline

- Product family: Red Hat OpenShift AI Self-Managed
- Product version: repository baseline in `docs/PLATFORM_BASELINE.md`
- Active RHOAI baseline while authored: 3.4
- Active OCP baseline while authored: 4.20
- Retrieved: 2026-06-10

## Official Sources

- Managing resources:
  https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/managing_resources/index
- Managing observability:
  https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_openshift_ai/managing-observability_managing-rhoai
- Govern LLM access with Models-as-a-Service:
  https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/govern_llm_access_with_models-as-a-service/index
- Technology Preview features in release notes:
  https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/release_notes/technology-preview-features_relnotes

## Sections Used

- Managing collection of usage data.
- Usage data collection notice.
- Enabling and disabling usage data collection.
- Dashboard configuration option `disableTracking`.
- MaaS telemetry enablement in the `Tenant` custom resource.
- MaaS observability dashboard and CSV usage export.
- Technology Preview posture for MaaS observability dashboard.

## Source Boundaries

- This skill does not replace `rhoai-observability`.
- This skill does not define all MaaS governance resources.
- Recheck release notes before describing MaaS telemetry as supported or
  preview.
