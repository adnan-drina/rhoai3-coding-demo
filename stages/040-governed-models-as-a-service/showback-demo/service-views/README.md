# Service report views

This offline package turns one versioned service-offer report into candidate platform financial dashboards and private, scoped statements. Canonical dashboard manifests live in `gitops/stages/040-governed-models-as-a-service/040-showback-demo/service-views/` (from the repository root), included by the optional manual-sync Application. It reuses the existing Perses datasource and stopped static report publisher. These local tools render files; deployment uses the explicit Stage 040 component entrypoint. No preview feature or consumer authorization service is enabled.

| Required view | Source delivered here | Qualification still needed |
|---|---|---|
| My consumption | Scoped user JSON, CSV and readable Markdown; platform panel with user/category/rate charges | Authenticated consumer delivery, native self-view isolation, per-user request counts, allowance and MTD forecast |
| Team statement | Scoped team exports, including explicitly team-owned fees; same platform panel | Verified team-manager directory/authorization integration and authenticated delivery |
| Dedicated efficiency | Actual cost, sponsor charge, recovery balance, cost components and certified tokens | Paid-capacity/SLO evidence; use native operational dashboards alongside the financial context |
| Shared economics | Published charges, actual cost, explicit subsidy, recovery balance and ratios before/after subsidy | Live billing-category evidence and qualified capacity forecasts |
| Workload quality and sourcing | Optional accepted-task/retry/turn, cost-per-accepted-task, sourcing savings/payback panels | Instrumented workflow/outcome evidence and native MLflow drilldown |
| Accounting completeness | Price/cost/usage coverage, invoice/difference, known versus full costs | Actual provider reconciliation, complete retained history and live access enforcement |

The generated dashboards are **platform-only candidates**, not access controls. A label, title or filter does not restrict the underlying datasource. Before integrating them, prove that only the intended platform audience can query financial metrics; do not put sensitive consumer charges on a broadly readable endpoint. Native [RHOAI observability](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/managing_openshift_ai/managing-observability_managing-rhoai) supplies LLM Traffic, Performance and Utilization. Native [MLflow GenAI Traces/Sessions](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_with_mlflow/track-and-compare-mlflow-experiments_mlflow) supplies drilldown for instrumented workflows. Neither substitutes for complete financial records or accepted-task evidence.

## Render a reviewed snapshot

Generate the input with `../offers/service-report.sh`; this is a distinct schema from the bounded worker allocator. Then:

```bash
bash render-report.sh --report /private/tmp/service-report.json \
  --output /private/tmp/services.prom \
  --configmap-output /private/tmp/selected-services.yaml
```

Add `--analysis /private/tmp/service-advice.json` only for an analysis from `../analysis/analyze.sh` with the same period, currency and evidence kind. Advice retains a separate report ID/hash and remains an analytical projection. No advice input means no invented zero outcomes.

All metrics are gauges of **one selected immutable report**, including report hash, revision, period, currency, policy, evidence kind and estimate/closed status. The dashboards read the latest snapshot at the selected time, guarded by publisher health. Never use `increase`, `rate`, `sum_over_time` or scrape-time integration to calculate money. A time picker does not recalculate historical allocation. Missing full totals are omitted; explicitly named known portions remain diagnostic. Recovery ratios are absent at zero actual cost.

The optional generated ConfigMap uses the existing `showback-selected-report` identity and `metrics.prom` key. It is an alternative selection for the existing zero-replica standard HTTP publisher, not a second publisher or a resource to add alongside the existing ConfigMap. Its content is not applied by this script. Rendering the new snapshot replaces the old metric family in that candidate; the bounded demo panels will then have no selected bounded report. Output files are replaced atomically only after validation and rendering succeed. Each file is atomic; separate output files are not a multi-file transaction.

## Export a scoped statement

The trusted operator first verifies the recipient's identity and authority through the organization's existing access process, then records that decision in a private authorization JSON object:

```json
{
  "schema_version": 1,
  "principal": "demo-engineer",
  "role": "consumer",
  "allowed_users": ["demo-engineer"],
  "allowed_teams": [],
  "report_sha256": "CANONICAL_REPORT_SHA256",
  "verified_by": "operator-identity",
  "verified_at": "2026-11-01T10:00:00Z",
  "authorization_evidence": "reference-to-reviewed-access-decision"
}
```

Compute the report binding with `jq -cS . service-report.json | shasum -a 256`. This is an operator attestation, **not cryptographic authentication**: an untrusted caller must never be allowed to supply their own authorization file to a service. The command runs locally with access to the full report, and only filters an explicitly approved export. Production server-side authorization remains a separate qualification gate.

```bash
bash export-statement.sh --report /private/tmp/service-report.json \
  --authorization /private/tmp/verified-access.json \
  --scope user --id demo-engineer --output-dir /private/tmp/statement-demo-engineer
```

A `consumer` can select only their own explicitly allowed user ID. A `team_manager` can select only an explicitly allowed team. A `platform_admin` must also have the requested user/team in the allowlist. Wrong subject, role or report hash fails before producing an export. The output directory must be new and is private by default. It contains only `statement.json`, `statement.csv` and `statement.md`; the full fleet report and broader authorization allowlist are removed before delivery. CSV string cells are escaped against spreadsheet-formula interpretation.

User statements contain only explicitly user-attributed charges. They exclude team-owned availability/reservation fees, with a scope notice; those fees remain in team statements and platform reconciliation. No matching charge evidence is an error rather than a fabricated zero bill. Missing pricing or usage evidence leaves the full charge unknown while preserving the known portion. Corrections use a new report revision and a new export directory, not an additive re-export of the old statement.

## Offline validation

Run `bash test-views.sh`. It creates synthetic service and analysis evidence, checks line/report/panel parity, rejects cross-user/team and report-hash mismatches, exercises missing coverage and zero denominators, verifies atomic failure behavior, and renders the canonical Kustomize bundle. Run `bash generate-dashboards.sh --write` after editing the JSON definitions; `--check` detects stale generated YAML.

No cluster, provider API or inference request is used. Not validated against a live OpenShift cluster. Static and synthetic tests only.
