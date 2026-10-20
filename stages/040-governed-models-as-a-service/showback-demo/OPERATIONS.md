# Showback demo operations

Run cluster commands only after the repository guard (`load_env` and `check_oc_logged_in` from `scripts/lib.sh`). Keys, tokens and raw request evidence stay in private directories outside Git; never pass them as command arguments.

## Deploy and validate the component

`040-showback-demo` is an optional, manual-sync Application. The default Stage 040 deployment does not select it.

```bash
./stages/040-governed-models-as-a-service/deploy.sh --component 040-showback-demo --revision <full-sha>
RHOAI_STAGE040_SHOWBACK_EXPECTED_REVISION=<full-sha> \
  ./stages/040-governed-models-as-a-service/validate.sh --component 040-showback-demo
```

Deployment checks namespaces, APIs and the native `edit` role's MLflow experiment permissions, then applies, syncs and waits for this Application only. It creates no users or keys and starts no GPU. Broad Stage 040 validation prints `SKIP 040-showback-demo (not activated)` when the Application is absent and validates it strictly when present.

## Continuous external metering

The `metering/` folder of the component owns the backend, its PostgreSQL database (retained PVC), the provider price catalog, a ServiceMonitor and the NetworkPolicy that lets the gateway reach the backend. The gateway plugin lives in the MaaS-owned ConfigMap `openshift-ingress/payload-processing-plugins`; the component's `metering/profile.yaml` declares the intended profile.

**Activation.** The targeted deployment waits for the backend, then writes the metering plugin into `custom-ipp-config.yaml` and restarts `payload-processing` only when the profile changed. It accepts only the reviewed baseline or candidate profile and preserves the rest of the ConfigMap. The plugin runs with `failOpen: true`, so a backend outage never blocks inference.

**Acceptance (still open).** Send a few bounded requests to an external model as a genuine user, in JSON and SSE. Then compare the response usage with the ledger rows and the External dashboard, check that a replayed event is not counted twice, and revoke the temporary key. A healthy scrape does not prove delivery.

**Price change.** Add a new catalog version and new `price_version` values in `native/provider-pricing.json`, copy it to `metering/provider-pricing.json` (the tests require identical files) and deploy. Earlier events keep their frozen estimates. The NVIDIA endpoint is a free prototype; a commercial endpoint needs its own price entry.

**Disable.** Set `metering/profile.yaml` data `enabled: 'false'`, publish and run the same targeted deployment. Confirm the baseline profile and a healthy `payload-processing` rollout before stopping the backend. Keep the PVC and database credential. Reverting the Application alone does not remove the plugin from the MaaS ConfigMap.

**After a cluster start** the backend exits until its database accepts connections and restarts a few times; this is expected. If the ConfigMap was updated but the processor did not restart, run `oc rollout restart deployment/payload-processing -n openshift-ingress`, wait for the rollout and repeat the acceptance check.

**Rebuild the backend image** with `native/backend/build-local.sh --continuous` (pinned source and patches) and publish it to the cluster registry with `native/backend/publish-local.sh`; see [native/backend/README.md](native/backend/README.md). Put the returned digest in `metering/deployment.yaml`, commit, publish and deploy as above. The image exists only in the cluster registry, so a rebuilt cluster needs this step.

## Offline validation

```bash
./stages/040-governed-models-as-a-service/showback-demo/validate.sh
```

This runs the shell regression tests, checks generated files against their sources, renders the component and exercises synthetic samples through reconciliation, allocation, metrics and archive. It also covers the three offers, the event importer, scoped statements and task analysis. Cluster, HTTP and AWS commands are blocked; HTTP tests use mocks. The synthetic close totals 135 cents including 45 cents of idle capacity; that is a test assertion, not a bill.

## Regenerate access and dashboards

Edit `scenario.json`, then regenerate:

```bash
stages/040-governed-models-as-a-service/showback-demo/render-access.sh --write gitops/stages/040-governed-models-as-a-service/040-showback-demo
stages/040-governed-models-as-a-service/showback-demo/generate-dashboards.sh --write
stages/040-governed-models-as-a-service/showback-demo/service-views/generate-dashboards.sh --write
```

Each command has a `--check` mode that detects drift. The access renderer writes one subscription and one authorization policy per team. If the scenario changes intentionally, update the synthetic fixture's `scenario_sha256`. Never edit a scenario to fit a run that already happened. The bounded dashboards come from `dashboard-definitions.json`, the offer dashboards from `offer-dashboard-definitions.json`.

After deploying a dashboard change, open each view in the RHOAI console at a narrow (about 788 px) and a desktop (about 1440 px) width. Check that labels are readable, token counts are exact, team and idle costs are distinct, missing values show as Unknown rather than zero, and no authored panel scrolls horizontally.

## Run a bounded Qwen workload

`qualification-qwen-only.json` is the Engineering/Support profile: three 120-second busy/quiet/idle phases, at most 24 requests, about 128 input and 32 output tokens each, one concurrent request per team.

1. Create the two demo users and their one-hour MaaS keys. Both scripts preview by default.

   ```bash
   stages/040-governed-models-as-a-service/showback-demo/qualify-qwen-identities.sh \
     --execute --insecure --output /private/tmp/showback-qwen-identities
   stages/040-governed-models-as-a-service/showback-demo/qualify-qwen-metering.sh \
     --execute --insecure --identities /private/tmp/showback-qwen-identities \
     --output /private/tmp/showback-qwen-metering
   ```

   The identity script creates the users in the existing `sso` Keycloak authority, logs in through OpenShift and mints each user's own key. It refuses unrelated existing identities and never resets a password; `--resume` continues from its private journal. For a later rehearsal, mint fresh keys for the same users instead of recreating them. The metering script proves exact per-team token deltas for JSON and SSE and checks 401 for missing or invalid keys, within eight requests.

2. Export the gateway URL and keys from [env.example](env.example) in a private shell, then run the workload:

   ```bash
   demo=stages/040-governed-models-as-a-service/showback-demo
   bash "$demo/run-workload.sh" --scenario "$demo/qualification-qwen-only.json" \
     --mode access-probe --execute --insecure --output /private/tmp/showback-qwen-access
   bash "$demo/run-workload.sh" --scenario "$demo/qualification-qwen-only.json" \
     --execute --insecure --output /private/tmp/showback-qwen-run
   ```

   Without `--execute` the script prints a preview. The output directory must be new. Streaming requests need final SSE usage followed by `[DONE]`. Ending the client does not stop model workers.

3. Collect usage, reconcile and allocate. Pass the same `--scenario` to `collect-usage.sh prepare` and `publish-report.sh`. Use a private copy of `metering.json` with the verified limiter labels, a private copy of `costs.json` scoped to Qwen, and observed instance intervals.

   ```bash
   bash "$demo/collect-usage.sh" capture --url "$SHOWBACK_PROMETHEUS_URL" \
     --run /private/tmp/showback-qwen-run/run.json --output /private/tmp/showback-qwen-run/samples.json
   bash "$demo/collect-usage.sh" prepare --scenario "$demo/qualification-qwen-only.json" \
     --run /private/tmp/showback-qwen-run/run.json \
     --receipts /private/tmp/showback-qwen-run/receipts.jsonl \
     --samples /private/tmp/showback-qwen-run/samples.json \
     --metering /private/tmp/showback-metering-verified.json \
     --intervals /private/tmp/showback-instance-intervals.json \
     --costs /private/tmp/showback-costs-qwen.json \
     --output /private/tmp/showback-qwen-run/accounting.json
   bash "$demo/allocate.sh" --input /private/tmp/showback-qwen-run/accounting.json \
     --output /private/tmp/showback-qwen-run/report.json --csv /private/tmp/showback-qwen-run/report.csv
   ```

   `capture` reads `SHOWBACK_PROMETHEUS_TOKEN` from the environment and refuses redirects. The collector requires stable scrapes around each boundary, no unexplained counter reset or gap, and receipts matching the counters within 1%. The native scrape cadence is 30 seconds, so the metering map's boundary tolerance must be 30 seconds.

## Publish and archive a report

```bash
bash "$demo/publish-report.sh" --scenario "$demo/qualification-qwen-only.json" \
  --report /private/tmp/showback-qwen-run/report.json \
  --output /private/tmp/showback-qwen-run/report.prom \
  --configmap-output /private/tmp/showback-qwen-run/selected-report.yaml
bash "$demo/archive.sh" pack --report /private/tmp/showback-qwen-run/report.json \
  --file /private/tmp/showback-qwen-run/accounting.json --file /private/tmp/showback-qwen-run/samples.json \
  --file /private/tmp/showback-qwen-run/run.json --file /private/tmp/showback-qwen-run/receipts.jsonl \
  --output /private/tmp/showback-evidence-bundle
bash "$demo/archive.sh" verify /private/tmp/showback-evidence-bundle
bash "$demo/archive.sh" upload /private/tmp/showback-evidence-bundle
```

Also pack the frozen scenario, metering map, intervals and price file. `upload` uses the MLflow REST API with the token file named by `MLFLOW_TOKEN_PATH` (see `env.example`), creates a run in experiment `showback-accounting` in workspace `showback-reporting`, verifies every file by hash and only then marks the run finished.

To show the report in the dashboards, review the generated ConfigMap's labels and values, replace `040-showback-demo/publisher-report.yaml` with it, keep `publisher-deployment.yaml` at one replica and deploy the component at the new revision. Report IDs, team names, prices and dates become public source; raw receipts stay private. To stop the publisher, set zero replicas and an empty report together. Never patch the live ConfigMap or scale the Deployment by hand.

## External-model probe

`external-probe.sh` makes exactly two non-streaming Nemotron calls through an existing personal subscription (128-token cap, no retries) and revokes its temporary key. It previews by default.

```bash
bash "$demo/external-probe.sh" --execute --persona /private/tmp/existing-persona/kubeconfig \
  --output /private/tmp/new-external-probe --insecure
bash "$demo/render-external-probe.sh" --probe /private/tmp/new-external-probe/probe.json \
  --publisher gitops/stages/040-governed-models-as-a-service/040-showback-demo/publisher-report.yaml \
  --output /private/tmp/publisher-report-with-probe.yaml
```

Rendering replaces only the `showback_external_*` metrics and keeps the Qwen report. Review the output before replacing `publisher-report.yaml`.

## Monthly service offers (offline)

Start from `offers/month.example.json`. A real close needs a report ID, UTC calendar month, consumer mapping, agreements and retained usage and cost evidence. External prices are USD per token (convert per-million quotes); tool calls are USD per call.

```bash
review_dir=$(mktemp -d /private/tmp/showback-service-review.XXXXXX)
bash "$demo/offers/service-report.sh" --input "$demo/offers/fixtures/month.json" \
  --output "$review_dir/statement.json" --csv "$review_dir/statement.csv"
bash "$demo/analysis/analyze.sh" --input "$demo/analysis/fixtures/tasks.json" --output "$review_dir/advice.json"
bash "$demo/service-views/render-report.sh" --report "$review_dir/statement.json" \
  --analysis "$review_dir/advice.json" --output "$review_dir/services.prom" \
  --configmap-output "$review_dir/selected-services.yaml"
mkdir "$review_dir/bundles"
bash "$demo/archive.sh" pack --report "$review_dir/statement.json" \
  --file "$demo/offers/fixtures/month.json" --output "$review_dir/bundles/october"
bash "$demo/archive-index.sh" --bundles "$review_dir/bundles" \
  --start 2026-10-01T00:00:00Z --end 2027-01-01T00:00:00Z --output "$review_dir/quarter-index.json"
```

The index reports November and December as missing on purpose. Corrections need a new report ID, an incremented revision, `supersedes_report_id`, a reason and `--previous PREVIOUS_REPORT`. Scoped user and team statements come from [service-views/export-statement.sh](service-views/README.md#export-a-scoped-statement). Captured external events can be imported into an offer input with `native/import-events.sh`; see [native/README.md](native/README.md).

## Full two-model rehearsal

Steps to make the whole scenario live:

1. Qualify Qwen FP8 and Mistral Small 4 on separate RTX PRO 6000 workers: first token, JSON and SSE, host and GPU memory, concurrency and cold load. The Mistral draft is in the component's `model-drafts/mistral/` (zero replicas, excluded from the render); `model-drafts/qwen-fp8/` here is input for the existing Qwen owner.
2. Create the Marketing user, render all three subscription/auth-policy pairs by removing `components/qwen-only` from the component, and mint three user-owned keys bound to their subscriptions.
3. Prove four allowed paths and two 403 denials (Engineering → Mistral, Marketing → Qwen). A 401, 404 or 429 does not count as the expected denial.
4. Fill a private `metering.json` with the verified limiter label for every subscription and model, including other consumers.
5. Run the 12-minute busy/quiet/idle workload from `scenario.json` (three 4-minute windows), capture instance running intervals for both workers, then collect, allocate, publish and archive as above.
6. Run the quota probe separately (`run-workload.sh --mode quota-probe --quota-model MODEL --quota-requests N`); it fails if no 429 is observed.
7. Scale both GPU workers back down when the rehearsal ends.

## Failure handling

| Symptom | Action |
|---|---|
| Missing limiter series or label | Verify the canonical resource and prime the counters; never allocate from guessed labels |
| Counter reset, gap or activity at a boundary | Keep the raw evidence; the window stays unresolved |
| Receipt count or hash mismatch | Keep the original run and recover missing receipts; do not close an incomplete bill |
| Activity during the idle phase | The idle assertion failed; do not move phase boundaries after the fact |
| Full-cost metric absent | Price or usage coverage is incomplete; never display zero dollars |
| Publisher returns 404 | The selected report is empty; promote a reviewed report |
| Access or quota probe fails | Keep the receipts and fix identities or model references; never route around MaaS |
| Metering ledger empty while external traffic flows | Check the `payload-processing` logs and the profile in `payload-processing-plugins`, then repeat acceptance |

Rollback stops owned load, reverts report selection and replicas together, revokes only demo keys and reverts the component through its Application. Shared Qwen, GPU, MaaS and MLflow resources stay with their owners. Stopping a client does not stop AWS charges; scale the GPU workers down.
