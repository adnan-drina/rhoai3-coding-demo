# Showback

Stage 040 adds one custom Observability tab (**Showback 5 · Break-even**) and can export measured MaaS usage for a
time window. Neither is an invoice: the tab prices usage from the showback catalogs, and the raw export stays unpriced
(`../showback-ratecard.json` is the reviewed unpriced rate card it requires).

| Script | When to run |
|---|---|
| `generate-dashboards.sh [--write\|--check]` | After changing a dashboard. Edit the generator, run `--write`, review and commit the file in `gitops/stages/040-governed-models-as-a-service/040-maas-platform/observability/`; Argo CD applies it. `--check` (read-only) fails when the committed dashboard differs from the generator; without an option it prints it. Offline, no cluster access. |
| `export-usage.sh --from UTC --to UTC --output FILE` | When you need raw governed usage for an explicit UTC window (1 minute to 89 days): tokens, authorized and limited calls per user, subscription and model from the native RHOAI Thanos, through a local port-forward. Read-only on the cluster. Writes a private CSV and `FILE.json` coverage receipt (mode 0600) and refuses to overwrite either; they contain identities, so keep them out of Git. For everyday usage, the dashboard **Usage** page's **Export as CSV** is the native path. |

The generator writes the file in PyYAML's `safe_dump` layout (the format they were first generated in) through
Ruby's libyaml emitter, so a regeneration without a content change leaves `git diff` empty.

## How the dashboards are deployed

The dashboard is a plain `PersesDashboard` object (`perses.dev/v1alpha2`) in `redhat-ods-monitoring`, committed in
`gitops/stages/040-governed-models-as-a-service/040-maas-platform/observability/` and applied by the Argo CD
Application `040-maas-platform` when Stage 040 `deploy.sh` syncs it. No operator, Job or script runs at deploy time.
OpenShift AI 3.5 shows every `PersesDashboard` in `redhat-ods-monitoring` whose name starts with `dashboard-` as a tab
of its Observability page, ordered by the number; the product ships tabs 0–4, this one is 5. The showback tabs 1–4 come from the optional `040-showback-demo` component.

| Dashboard | Metrics | Default variables |
|---|---|---|
| `dashboard-offer-5-break-even-admin` | One use case (a team subscription) on its external model and on a private model: tokens over time on each, monthly savings if moved, workload against the break-even volume of a dedicated worker, MLflow pass rates per judge and the monthly cost of each option | External model (priced models only, default `claude-sonnet-5-5`), use case (subscriptions on that model, default `team-engineering-ci`), private model (offer catalog, default `qwen3-8-27b`); default range 30 days |

It relies on three things other stages and components provide:

1. **RHOAI monitoring** (Stage 010): its `Monitoring` resource creates the Perses data sources the panels query,
   `data-science-prometheus-datasource` and `cluster-prometheus-datasource`.
2. **The optional showback component** `040-showback-demo`: the offer catalog (`showback_offer_*`), the external
   metering ledger (`showback_external_metering_*`) and the MLflow quality verdicts. Without it the tab shows no data.
3. **Attributed MaaS usage telemetry**, for the per-subscription tokens: the `040-maas-platform` Job
   `job-enable-maas-telemetry` sets `spec.telemetry` of `MaaSTenantConfig default-tenant` (`enabled`, `captureUser`,
   `captureModelUsage`, `captureOrganization`). Without it the token panels stay empty.

## Reusing it on another OpenShift AI 3.5 cluster

1. Check the prerequisites:

   ```bash
   oc get persesdatasource -n redhat-ods-monitoring   # data-science-prometheus-datasource, cluster-prometheus-datasource
   oc get persesdashboard -n redhat-ods-monitoring    # the product's dashboard-0..4 tabs; 5 must be free
   oc get maastenantconfig default-tenant -n models-as-a-service -o jsonpath='{.spec.telemetry}'   # token panels need it
   ```

   Missing data sources mean RHOAI monitoring is not enabled. If telemetry is off, apply the `spec.telemetry` merge
   patch from `gitops/stages/040-governed-models-as-a-service/040-maas-platform/jobs/enable-maas-job.yaml`.
2. Set the defaults for that environment: change the GPU price and count or the API prices in the generator and run
   `generate-dashboards.sh --write`, or edit the `TextVariable` values in the YAML. Viewers can also change the
   variables for their own session in the dashboard.
3. Apply the file. It holds nothing cluster-specific:

   ```bash
   oc apply -n redhat-ods-monitoring \
     -f gitops/stages/040-governed-models-as-a-service/040-maas-platform/observability/dashboard-6-tokenomics-break-even.yaml
   ```

   To keep them under GitOps, point an Argo CD Application at a copy of the `observability/` folder (its
   `kustomization.yaml` lists the file); the `app.kubernetes.io/part-of: rhoai3-coding-demo` label can go.
4. Open the OpenShift AI Observability page: the **Showback 5 · Break-even** tab appears
   next to the product tabs. The model list fills from the metrics.

Keep the `dashboard-` prefix and an unused number, and check `oc get persesdashboard` after an upgrade in case a later
release adds tabs with the same number.
