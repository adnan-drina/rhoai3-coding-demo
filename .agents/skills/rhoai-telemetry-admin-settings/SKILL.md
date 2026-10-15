---
name: rhoai-telemetry-admin-settings
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when reviewing or changing Red Hat usage data collection for OpenShift
  AI (Settings > General settings, the odh-segment-key-config ConfigMap,
  dashboard disableTracking) or MaaS usage telemetry (spec.telemetry on the
  MaaS tenant default-tenant set by the Stage 040 enable Job, the Usage tab,
  CSV export, export-maas-usage.sh). Do NOT use for the observability stack
  itself (use rhoai-observability), MaaS subscriptions, keys and policies
  (use rhoai-maas-governance), TrustyAI (use rhoai-monitoring-trustyai), or
  cluster telemetry (use ocp-observability).
---

# RHOAI telemetry admin settings

Thin skill: two different things share the word telemetry. Red Hat usage data
collection (product analytics) and MaaS usage telemetry (token metrics for
showback). Repo decisions here, product behavior in the linked OpenShift AI
3.5 sections. Detailed record:
`gitops/stages/040-governed-models-as-a-service/maas-platform/README.md`.

## When to use

- A question whether this demo sends usage data to Red Hat.
- A change to MaaS telemetry attribution, the Usage tab, or the usage export.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Red Hat usage data collection is left at the product default; `odh-segment-key-config` is not managed in Git | none under `gitops/` | [Usage data collection notice][notice], [Disable by using the CLI][disable-cli] |
| `disableTracking: false` (the default) is written down, so the Usage data collection section stays visible in the dashboard settings | `gitops/stages/010-openshift-ai-platform-foundation/rhoai-platform/odhdashboardconfig.yaml` | [Hide the usage data collection section][hide], [Dashboard configuration options][options] |
| MaaS telemetry on: the Sync-hook Job patches `spec.telemetry` of `maastenantconfigs.maas.opendatahub.io/default-tenant` in `models-as-a-service` (owner check plus UID and resourceVersion guard) | `gitops/stages/040-governed-models-as-a-service/maas-platform/jobs/enable-maas-job.yaml`, `jobs/enable-maas-telemetry-role.yaml`, `jobs/enable-maas-telemetry-binding.yaml` | [Enable telemetry for MaaS][maas-telemetry] |
| `captureUser: true` (product default `false`), `captureGroup: false`, `captureOrganization` and `captureModelUsage: true`; recorded deviation for per-user showback | same Job; `maas-platform/README.md` (Alignment table) | [Enable telemetry for MaaS][maas-telemetry] |
| Showback beyond the Usage tab: two custom PersesDashboards (cost per token, tokenomics) and a measured-usage CSV script that reads Thanos; unpriced rate card | `gitops/stages/040-governed-models-as-a-service/maas-platform/observability/`, `stages/040-governed-models-as-a-service/export-maas-usage.sh` | [Export usage data for cost attribution][maas-export] |

## Procedure

1. Red Hat usage data collection: decide in Git. To turn it off, add the
   `odh-segment-key-config` change from [Disable by using the CLI][disable-cli]
   as a Stage 010 manifest; to hide the settings section, set
   `disableTracking: true` in `odhdashboardconfig.yaml`. Record the choice in
   the rhoai-platform README.
2. MaaS telemetry: change the patch in `enable-maas-job.yaml` and the
   README's telemetry choices together, then
   `./stages/040-governed-models-as-a-service/deploy.sh` and
   `./stages/040-governed-models-as-a-service/validate.sh` (telemetry has no
   automated check; verify by hand).
3. Read-only checks, after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get maastenantconfigs default-tenant -n models-as-a-service -o jsonpath='{.spec.telemetry}{"\n"}'
   oc get configmap odh-segment-key-config -n redhat-ods-applications -o yaml
   ```

4. Usage export: `./stages/040-governed-models-as-a-service/export-maas-usage.sh
   --from <UTC> --to <UTC> --output <private path>`; never commit the CSV
   (it holds user identities).

## Pitfalls

- `disableTracking` only hides the dashboard section; it does not stop
  collection ([Hide the section][hide] vs [Disable][disable]).
- The 3.5 MaaS guide calls the telemetry resource a `Tenant`; the API this repo
  patches is `maastenantconfigs.maas.opendatahub.io`. Confirm with
  `oc api-resources --api-group=maas.opendatahub.io` before changing names.
- The 3.5 MaaS guide marks the observability dashboard Technology Preview
  and calls its data showback, not billing-grade metering
  ([Observability dashboard][maas-dashboard], [Export usage data][maas-export]).
- `captureUser: true` puts user identities into metrics and exports.

## Official documentation (OpenShift AI 3.5)

| Topic | Section |
|---|---|
| Usage data collection | [Chapter][usage], [Notice][notice], [Enable][enable], [Disable][disable], [Disable by CLI][disable-cli], [Hide the section][hide] |
| Dashboard option | [Dashboard configuration options][options] |
| MaaS usage telemetry | [Monitor MaaS usage][maas-obs], [Overview][maas-overview], [Kuadrant observability][maas-kuadrant], [Enable telemetry][maas-telemetry], [Observability dashboard][maas-dashboard], [Export usage data][maas-export] |

## Related skills

`rhoai-observability`, `rhoai-maas-governance`,
`rhoai-dashboard-customization`, `ocp-observability`.

[usage]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#managing-collection-of-usage-data
[notice]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#usage-data-collection-notice-for-openshift-ai
[enable]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#enabling-usage-data-collection_data-collection
[disable]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#disabling-usage-data-collection_data-collection
[disable-cli]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#disabling-usage-data-collection-cli_data-collection
[hide]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#hiding-usage-data-collection-ui_data-collection
[options]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#ref-dashboard-configuration-options_dashboard
[maas-obs]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/govern_llm_access_with_models-as-a-service/index#maas-observability_maas-deploy
[maas-overview]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/govern_llm_access_with_models-as-a-service/index#maas-observability-overview_maas-deploy
[maas-kuadrant]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/govern_llm_access_with_models-as-a-service/index#enable-kuadrant-observability-maas_maas-deploy
[maas-telemetry]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/govern_llm_access_with_models-as-a-service/index#enable-maas-telemetry_maas-deploy
[maas-dashboard]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/govern_llm_access_with_models-as-a-service/index#view-maas-observability-dashboard_maas-deploy
[maas-export]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/govern_llm_access_with_models-as-a-service/index#export-maas-usage-data_maas-deploy
