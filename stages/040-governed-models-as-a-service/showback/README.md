# Showback

Stage 040 shows what the private models cost in two custom Observability tabs (**Cost per token**, **Tokenomics ·
break-even (live)**) and can export measured MaaS usage for a time window. Neither is an invoice: prices are dashboard
variables, and the raw export stays unpriced (`../showback-ratecard.json` is the reviewed unpriced rate card it
requires).

| Script | When to run |
|---|---|
| `generate-dashboards.sh [--write\|--check]` | After changing a dashboard. Edit the generator, run `--write`, review and commit both files in `gitops/stages/040-governed-models-as-a-service/040-maas-platform/observability/`; Argo CD applies them. `--check` (read-only) fails when a committed dashboard differs from the generator; without an option it prints both. Offline, no cluster access. |
| `export-usage.sh --from UTC --to UTC --output FILE` | When you need raw governed usage for an explicit UTC window (1 minute to 89 days): tokens, authorized and limited calls per user, subscription and model from the native RHOAI Thanos, through a local port-forward. Read-only on the cluster. Writes a private CSV and `FILE.json` coverage receipt (mode 0600) and refuses to overwrite either; they contain identities, so keep them out of Git. For everyday usage, the dashboard **Usage** page's **Export as CSV** is the native path. |

The generator writes the files in PyYAML's `safe_dump` layout (the format they were first generated in) through
Ruby's libyaml emitter, so a regeneration without a content change leaves `git diff` empty.

## How the dashboards are deployed

The two dashboards are plain `PersesDashboard` objects (`perses.dev/v1alpha2`) in `redhat-ods-monitoring`, committed in
`gitops/stages/040-governed-models-as-a-service/040-maas-platform/observability/` and applied by the Argo CD
Application `040-maas-platform` when Stage 040 `deploy.sh` syncs it. No operator, Job or script runs at deploy time.
OpenShift AI 3.5 shows every `PersesDashboard` in `redhat-ods-monitoring` whose name starts with `dashboard-` as a tab
of its Observability page, ordered by the number; the product ships tabs 0–4, these are 5 and 6.

| Dashboard | Metrics | Default variables |
|---|---|---|
| `dashboard-5-cost-per-token-admin` | vLLM `kserve_vllm:prompt_tokens_total` and `generation_tokens_total` per model; MaaS `authorized_hits_total` and `authorized_calls_total` per user and subscription | Prompt 0.10, completion 0.40, blended 0.25 per million tokens |
| `dashboard-6-tokenomics-break-even-admin` | vLLM token throughput against the worker spend of serving private models | Private model (from the showback offer catalog) and reference external model (default `gpt-6-luna`, prices from the external-metering catalog); no price variables |

They rely on three things other stages provide:

1. **RHOAI monitoring** (Stage 010): its `Monitoring` resource creates the Perses data sources the panels query,
   `data-science-prometheus-datasource` and `cluster-prometheus-datasource`.
2. **vLLM model serving through KServe** (Stages 030 and 040), which produces the `kserve_vllm:*` token counters.
3. **Attributed MaaS usage telemetry**, for the per-user and per-subscription panels: the `040-maas-platform` Job
   `job-enable-maas-telemetry` sets `spec.telemetry` of `MaaSTenantConfig default-tenant` (`enabled`, `captureUser`,
   `captureModelUsage`, `captureOrganization`). Without it those panels stay empty.

## Reusing them on another OpenShift AI 3.5 cluster

1. Check the prerequisites:

   ```bash
   oc get persesdatasource -n redhat-ods-monitoring   # data-science-prometheus-datasource, cluster-prometheus-datasource
   oc get persesdashboard -n redhat-ods-monitoring    # the product's dashboard-0..4 tabs; 5 and 6 must be free
   oc get maastenantconfig default-tenant -n models-as-a-service -o jsonpath='{.spec.telemetry}'   # per-user panels only
   ```

   Missing data sources mean RHOAI monitoring is not enabled. If telemetry is off, apply the `spec.telemetry` merge
   patch from `gitops/stages/040-governed-models-as-a-service/040-maas-platform/jobs/enable-maas-job.yaml`.
2. Set the defaults for that environment: change the GPU price and count or the API prices in the generator and run
   `generate-dashboards.sh --write`, or edit the `TextVariable` values in the YAML. Viewers can also change the
   variables for their own session in the dashboard.
3. Apply both files. They hold nothing cluster-specific:

   ```bash
   oc apply -n redhat-ods-monitoring \
     -f gitops/stages/040-governed-models-as-a-service/040-maas-platform/observability/dashboard-5-cost-per-token.yaml \
     -f gitops/stages/040-governed-models-as-a-service/040-maas-platform/observability/dashboard-6-tokenomics-break-even.yaml
   ```

   To keep them under GitOps, point an Argo CD Application at a copy of the `observability/` folder (its
   `kustomization.yaml` lists both files); the `app.kubernetes.io/part-of: rhoai3-coding-demo` label can go.
4. Open the OpenShift AI Observability page: the **Cost per token** and **Tokenomics · break-even (live)** tabs appear
   next to the product tabs. The model list fills from the metrics.

Keep the `dashboard-` prefix and an unused number, and check `oc get persesdashboard` after an upgrade in case a later
release adds tabs with the same number.
