# Showback demo operations

## Current boundary

This package is implemented for **offline review and testing**. No deployment, GPU resume, credential creation or inference has been authorized. The active stage deploy scripts and GitOps paths do not reference it. Keep that separation until the live gate is approved. The existing `../showback/` utilities still serve the current platform.

Requirements for offline work: Bash, `jq`, `curl`, Ruby for YAML conversion, `shasum` and Kustomize, as used by the repository. Tools source `scripts/lib.sh`; only explicitly requested live actions invoke its environment and cluster guard. No Python, dependency installation, image pull or cluster login is needed for offline checks.

## Offline validation

From the repository root:

```bash
./stages/040-governed-models-as-a-service/showback-demo/validate.sh
```

This runs shell regression tests, verifies generated files, previews workloads, renders detached manifests and exercises synthetic samples → reconciled evidence → allocation → metric exposition → hashed archive. It also checks the three service offers, native event import, scoped statements, task analysis and monthly archive continuity. Real cluster, HTTP and AWS commands are blocked; HTTP tests supply explicit mocks. Synthetic output is temporary and explicitly labelled. The bounded integration fixture totals 135 cents, including 45 cents of fully idle model capacity; those are test assertions, not a measured bill.

Preview workload and access decisions without credentials:

```bash
stages/040-governed-models-as-a-service/showback-demo/run-workload.sh
stages/040-governed-models-as-a-service/showback-demo/run-workload.sh --mode access-probe
```

Edit `scenario.json` to calibrate budgets/profiles, then regenerate and validate:

```bash
stages/040-governed-models-as-a-service/showback-demo/render-access.sh --write stages/040-governed-models-as-a-service/showback-demo/manifests
stages/040-governed-models-as-a-service/showback-demo/generate-dashboards.sh --write
```

The access renderer writes six named YAML files, one subscription and one authorization policy per team. Its default remains a stdout preview. If the scenario changes intentionally, update the synthetic fixture's `scenario_sha256` to the SHA256 of the new exact file bytes and review its request expectations. Do not change a scenario to fit an already observed run: retain that run's original configuration instead. Dashboard definitions must match their shell generator. The cluster publisher serves a reviewed metrics snapshot; it does not run the accounting code.

## Package and promotion

- `manifests/` is a **candidate bundle**, containing three subscription/auth-policy pairs, three Perses dashboards, a zero-replica publisher, Service/ServiceMonitor, empty selected-report ConfigMap and the evidence workspace/access grant.
- `model-drafts/mistral/` is a separately rendered, **zero-replica** Mistral service and model reference. Its 48 GiB request/56 GiB limit and serving flags are hypotheses, not a cold-load qualification. One GPU is requested and no runtime image is overridden. Cache dtype is `auto`; actual dtype and reasoning behavior require qualification.
- `model-drafts/qwen-fp8/` is a detached Kustomize component copied from the existing FP8 component with an added `replicas: 0` patch. It preserves the model ID. It is not a standalone deployment or an active serving configuration change.
- `native/manifests/` contains only two inert ConfigMaps holding candidate documents. No LokiStack, metering workload or controller configuration is activated. The source-backed importer processes saved events locally; it does not collect them from the platform.
- `service-views/manifests/` contains five detached platform financial dashboards. They reuse the same stopped publisher and datasource; they do not establish user/team access controls.
- No load Job/CronJob, autoscaler, Argo Application or deployment script is added. The runtime workload generator is a foreground client with explicit execution.

Later promotion requires a reviewed stage-owned GitOps integration. Preserve existing consumer policies and resource IDs; verify named replica/registry-label delegation for the new model. Adding a Git replica value of zero does not override an existing ignored live replica field. Confirm resource absence or the expected stopped UID before a future sync. Never apply this folder over the whole active stage as a shortcut.

The candidate namespace binding grants `rhods-admins` the documented `mlflow-edit` role in `showback-reporting`; verify the installed role and target membership before promotion. It does not change the shared MLflow server, bucket or other experiments. No Keycloak realm ownership or real users are changed here.

## Before any later live rehearsal

After authorization, use the repository's normal `scripts/lib.sh` environment and API-server guard before cluster commands. This package does not discover a cluster or bypass that guard.

1. Qualify Qwen FP8 and the selected Mistral artifact on separate RTX workers, including first token, host/GPU memory, streaming and concurrency. Keep the host-size contingency explicit.
2. Create/confirm the three user identities in the existing environment Keycloak authority and their OpenShift access. Subscription owner usernames must match the identity actually presented to MaaS. Check for inherited or overlapping model grants; the intended restricted access must be proved against the complete effective policy set.
3. Promote the reviewed subscriptions/auth policies, then obtain **three distinct user-owned API keys explicitly bound to the named subscriptions**. Keep keys outside Git. Verify the selected subscription through MaaS and actual metering; receipt labels alone do not establish server-side identity.
4. Calibrate per-model budgets and offered load. The committed values are provisional. The normal financial scenario must stay below quota. The separate quota probe needs a nearly exhausted/calibrated budget; it does not change limits or manufacture enough requests to exhaust a large quota.
5. Run the separate access probe: four successful calls, Engineering→Mistral denied, Marketing→Qwen denied. Successful responses must identify the requested model by its short or canonical MaaS ID. A 401, 404 or 429 does not satisfy the expected 403 authorization denial. Universal denial cannot pass the four positive paths.
6. Prime the four allowed token counters. Inspect raw metric labels and fill every `limitador_namespace` in a private copy of `metering.json` with the verified canonical resource. Known-team mappings must retain the user identity from the frozen scenario. Inspect any other consumers and add them with their real identity/resource mapping; they receive `other_consumers` allocation. Null canonical values intentionally prevent complete allocation.
7. Capture AWS instance running intervals, including warm-up and idle, and save the exact scenario, model/runtime identity and rate evidence. `instance-intervals.example.json` is intentionally empty; it cannot produce a priced report.

This is future execution guidance, not authorization to perform it now.

## Future foreground workload

Export the values from this package's [env.example](env.example) in a private shell; do not put keys in command arguments. `SHOWBACK_GATEWAY_URL` is the common MaaS gateway base URL. The client sends canonical local-model API IDs on `/v1/chat/completions`. `--insecure` is available for this demo's self-signed certificate.

The examples below use the checkout's `scenario.json`. Its exact bytes must remain unchanged between execution, collection and publication. When using a frozen private copy, pass the same `--scenario /path/to/frozen-scenario.json` to `run-workload.sh`, `collect-usage.sh prepare` and `publish-report.sh`, then include it in the archive.

Only after the live gate:

```bash
stages/040-governed-models-as-a-service/showback-demo/run-workload.sh \
  --execute --output /private/tmp/showback-live-run
```

The output directory must be new and its parent must exist. For known accounting usage, `--stream` needs final SSE usage followed by `[DONE]`. A completed stream without usage can pass the request/access check but leaves accounting incomplete; a missing `[DONE]` is an invalid response. Access and quota probes use different runs:

```bash
stages/040-governed-models-as-a-service/showback-demo/run-workload.sh \
  --mode access-probe --execute --output /private/tmp/showback-access-probe
stages/040-governed-models-as-a-service/showback-demo/run-workload.sh \
  --mode quota-probe --quota-model qwen3-8-27b --quota-requests 3 \
  --execute --output /private/tmp/showback-quota-probe
```

A quota probe that observes no 429 fails its proof, even if all requests complete successfully. It never retries 429. A 429 stops that team's further admissions. Model workers continue accruing cost until actually stopped; ending the client does not stop them.

The financial run is 12 minutes with three fixed four-minute windows. Each has a 45-second leading scrape buffer and 50-second drain. Requests have a hard 45-second deadline, at most one per team, and a global 200-request cap. A hard timeout can leave inference completing server-side: reconcile raw counters and mark uncertainty, rather than trusting a cancelled client's zero usage. `run.json` and `receipts.jsonl` use private permissions. Neither includes prompt/response content, keys or raw error bodies.

## Collection and close

Use an authorized native RHOAI Thanos endpoint or a manually established local tunnel. `collect-usage.sh capture` checks the repository's current-cluster guard before its explicit read-only HTTP request; it does not create a tunnel. Provide `SHOWBACK_PROMETHEUS_TOKEN` through the environment when required; the token reaches `curl` through its configuration input, never command arguments. Redirects and HTTP except localhost are refused. Wait for the trailing capture margin before invoking it. `prepare` remains entirely offline.

```bash
stages/040-governed-models-as-a-service/showback-demo/collect-usage.sh capture \
  --url "$SHOWBACK_PROMETHEUS_URL" --run /private/tmp/showback-live-run/run.json \
  --output /private/tmp/showback-live-run/samples.json
stages/040-governed-models-as-a-service/showback-demo/collect-usage.sh prepare \
  --run /private/tmp/showback-live-run/run.json \
  --receipts /private/tmp/showback-live-run/receipts.jsonl \
  --samples /private/tmp/showback-live-run/samples.json \
  --metering /private/tmp/showback-metering-verified.json \
  --intervals /private/tmp/showback-instance-intervals.json \
  --output /private/tmp/showback-live-run/accounting.json
stages/040-governed-models-as-a-service/showback-demo/allocate.sh \
  --input /private/tmp/showback-live-run/accounting.json \
  --output /private/tmp/showback-live-run/report.json \
  --csv /private/tmp/showback-live-run/report.csv
```

All source snapshots remain retained. Each measured instance interval has `instance_id`, `model`, `start`, `end`, `rate_id`, and `source`; timestamps are UTC. The allocator requires continuous lifecycle evidence for each included model/window. Same-instance overlaps are rejected. Missing rates leave the full total unknown and expose only a known subtotal. Costs outside the report period are listed separately; this does not erase them from a full preparation bill.

The shell allocator uses guarded integer/rational arithmetic for hosting costs and exact cent reconciliation. UTC timestamps support milliseconds; rates are nonnegative decimal strings with at most 12 fractional places, subject to its exact-integer bound. Oversized arithmetic fails explicitly. Consumer-share carry uses fixed increments of one billionth of a cent, with a maximum half-increment error per active consumer/model/window; each accumulated bound is retained in the report. This bounds carry precision without changing the exact total bill or sum of allocated cents. Corrections replay the full ordered evidence.

The collector uses raw `authorized_hits_total` range samples, including series that disappeared before the range ended. It requires stable scrape brackets around boundaries, no unexplained reset/gap, an explicit canonical limiter and matching response receipts. Noncanonical policy resources are not summed. The bounded workload's receipt tolerance is 1%; isolated single-call qualification must first prove exact deltas. Receipt count, identities, models, token arithmetic and the frozen scenario hash are checked. The recorded windows must match the frozen phase IDs, durations and full planned reporting period, including the idle phase. Conflicting duplicate JSON fields or multiple configuration documents are rejected before normalization. Evidence explicitly marked synthetic cannot be mixed with observed run inputs.

`accounting.json` holds models, subscription mapping, rates, instance intervals and ordered windows; each model/window includes `coverage`, token counts and issues. The allocator can be replayed over contiguous hourly windows for a longer period. Recompute the full ordered evidence set after a correction so rounding carry remains valid. Do not concatenate overlapping demo and hourly scopes or recalculate a quarter using aggregate token shares. Automated hourly close is not implemented. The separate service-offer archive index described below accepts monthly statements, not these bounded allocation reports.

## Report, dashboards and evidence archive

Render the exact financial report locally without starting a server:

```bash
stages/040-governed-models-as-a-service/showback-demo/publish-report.sh \
  --report /private/tmp/showback-live-run/report.json \
  --output /private/tmp/showback-live-run/report.prom
stages/040-governed-models-as-a-service/showback-demo/archive.sh pack \
  --report /private/tmp/showback-live-run/report.json \
  --file /private/tmp/showback-live-run/accounting.json \
  --file /private/tmp/showback-live-run/samples.json \
  --file /private/tmp/showback-live-run/run.json \
  --file /private/tmp/showback-live-run/receipts.jsonl \
  --output /private/tmp/showback-evidence-bundle
stages/040-governed-models-as-a-service/showback-demo/archive.sh verify \
  /private/tmp/showback-evidence-bundle
```

Also include the frozen scenario, verified metering, interval evidence and dated price file with `--file` when closing a real run. Hashes alone cannot reconstruct absent inputs. Bundles name their report file, bind the manifest identity to that report, retain per-file hashes, refuse overwrite and preserve correction predecessor/reason fields. They do not enforce retention or authenticity; the operator owns access, storage, review and the no-cleanup policy.

`publish-report.sh` validates the whole report before atomically writing metrics. Its optional `--configmap-output FILE` emits the exact `showback-selected-report` snapshot for later reviewed promotion; it never applies it or starts a listener. The stopped publisher uses a digest-pinned standard Red Hat Apache HTTP server and serves `/metrics.prom` as plain text. The empty committed ConfigMap has no metrics file, so readiness and scraping fail with 404 until a valid selection is supplied. An invalid local replacement is refused, preserving the previous snapshot and its original report identity. There is no per-scrape application interpreter.

Keep quarter-sized archives in artifact/file storage; the renderer limits the ConfigMap below its 1 MiB API limit. It contains metrics, never keys or raw request receipts. Financial panels show the selected report's UTC boundaries and the allowances configured when its snapshot was generated. These gauges must never be integrated across scrape time. Live serving panels retain their separate time range. The official registry metadata pin is retained in `publisher-image-evidence.json`; no image layers were pulled, and runtime HTTP/rendering compatibility remains a live gate.

Optional future `archive.sh upload BUNDLE_DIRECTORY` uses the documented MLflow REST tracking and proxied-artifact APIs with `curl`, the workspace header and an existing bearer token from `MLFLOW_TOKEN_PATH`. The token is sent through curl's configuration input, never command arguments. Set the namespaced values in this package's `env.example`; the repository cluster guard runs before HTTP. The script creates a run named after the report ID in experiment `showback-accounting`, workspace `showback-reporting`, uploads the bundle, verifies readback hashes and only then marks the run finished. It neither requires a Python SDK nor receives S3 keys or changes the shared server. REST contracts are referenced in `archive.sh` and tested with mocked responses; the installed RHOAI authorization and artifact path remain live qualification gates. Fresh-process recovery and 400-day retention still require operational proof.

## Three service offers: offline monthly workflow

Use `offers/month.example.json` as the **unpriced, incomplete observed-input template**. It creates no users, grants or dedicated capacity. Supply a unique report ID, UTC calendar month, versioned consumer/membership mapping, agreements and retained usage/cost evidence before a real close. The separate `offers/fixtures/month.json` is synthetic and is used only for reproducible review. Its example users/models are not provisioned identities or a change to the Engineering/Marketing/Support access matrix.

The three contracts calculate different things:

| Offer | Required inputs | Charge and idle treatment |
|---|---|---|
| External | Disjoint billable categories, effective provider rates, consumer identity, retries/adjustments, fees and provider invoice | Provider pass-through plus explicit fees/adjustments. Platform fault retries and unused commitments have named owners. Invoice differences remain visible. |
| Dedicated | Sponsor, paid capacity intervals, effective instance rates and attributable storage/network/software/operations/overhead | Full availability cost, including zero-use capacity, goes to the sponsor; a fixed quote exposes recovery variance. |
| Shared | Full service cost, approved prospective tariff, demand forecast, input/output weight, subsidy and any reservation/credits | Metered usage plus agreed reservation minus capped included credits. Platform owns demand shortfall under the default contract. |

External `prices` are decimal **USD per token**, except `tool_calls` in USD per call. Convert a provider's per-million quote explicitly; do not copy it directly into a per-token field. Internal tariff outputs show USD per million input/output tokens. Costs and charges remain separate; cloud instance prices already include their bundled CPU/RAM. Keep one physical interval and each overhead item in one cost pool. The accountant rejects overlapping supplied instance intervals, but the operator must still reconcile the declared scope against the actual invoice.

Reproduce a complete local sample without a server or network:

```bash
demo=stages/040-governed-models-as-a-service/showback-demo
review_dir=$(mktemp -d /private/tmp/showback-service-review.XXXXXX)
bash "$demo/offers/service-report.sh" \
  --input "$demo/offers/fixtures/month.json" \
  --output "$review_dir/statement.json" --csv "$review_dir/statement.csv"
bash "$demo/analysis/analyze.sh" \
  --input "$demo/analysis/fixtures/tasks.json" --output "$review_dir/advice.json"
bash "$demo/service-views/render-report.sh" \
  --report "$review_dir/statement.json" --analysis "$review_dir/advice.json" \
  --output "$review_dir/services.prom" --configmap-output "$review_dir/selected-services.yaml"
mkdir "$review_dir/bundles"
bash "$demo/archive.sh" pack --report "$review_dir/statement.json" \
  --file "$demo/offers/fixtures/month.json" --output "$review_dir/bundles/october"
bash "$demo/archive-index.sh" --bundles "$review_dir/bundles" \
  --start 2026-10-01T00:00:00Z --end 2027-01-01T00:00:00Z \
  --output "$review_dir/quarter-index.json"
```

The index deliberately reports November and December missing. The sample advice is a separate synthetic workload, bound by its own report ID/hash; it is not a breakdown of the service statement. A matching period/currency/evidence kind only makes it eligible to display alongside that statement. Do not represent the two as reconciled cohorts without real matching evidence.

`service-report.sh --check-report FILE` validates the report contract and financial identities. Input files are snapshotted before validation, hashing and calculation. Amounts use bounded exact rational arithmetic with deterministic cumulative cent rounding by agreement and stable line ID. Values beyond the exact-integer bound fail; missing price/cost/usage keeps the full total unknown while exposing known portions. A closed statement requires complete evidence; a closed statement with an invoice difference is still unreconciled.

Corrections require a new report ID, incremented revision, `supersedes_report_id`, a reason and `--previous PREVIOUS_REPORT`. Archive the new report and exact new input in a new bundle; pass the prior manifest hash and matching reason to `archive.sh pack`. The index verifies both report and archive chains and selects one latest revision per month. Forks, missing predecessors, altered files and ambiguous initial statements fail. `financially_complete` also requires every selected month closed/complete and external invoices reconciled. This proves retained-file continuity, not unseen traffic completeness, signature authenticity or enforced retention. No scheduler or automatic cleanup is supplied.

Private monthly delivery uses [service-views/export-statement.sh](service-views/export-statement.sh) with a separately verified authorization file; see [the export contract](service-views/README.md#export-a-scoped-statement). The operator must verify the recipient and bind the approval to the canonical report hash. Never accept that file from an untrusted caller as authentication. User statements exclude team-owned availability/reservation fees; team statements include them. No fleet financial datasource is exposed to consumers by this package.

The optional analysis input needs explicit accepted-task outcomes, trusted user/subscription identity, task/attempt IDs, model profile and prompt versions, and initial/planned/corrective/fallback classifications. Its full service-cost numerator includes idle and failed work; attempt costs are explanatory subsets, not added twice. Zero accepted tasks gives unknown unit cost. Sourcing advice uses supplied quality/SLO/privacy evidence, external commitment floors, private capacity steps, demand scenarios and migration payback. Native event UUIDs alone cannot join these task records; application instrumentation and representative model evaluation remain prerequisites.

## Native Loki and external-metering preparation

Follow [native/README.md](native/README.md) for pinned source contracts and the offline renderer/importer. Preview/check emits only ConfigMaps containing candidate data. The current upstream `usageLogging:false` value selects a collector and **does not stop logging**; source/version matching is required before any future activation.

For captured events, `native/import-events.sh` takes saved CloudEvents JSONL, a capture manifest and a monthly offer input with an empty event list. It snapshots all inputs, verifies their binding, normalizes provider categories, deduplicates exact source/ID replays, and quarantines unknown identities. Final token/category coverage and stream completion need independent retained evidence; a received event alone cannot prove complete capture. The output goes directly to the service accountant. Do not count a native monetary charge and a recalculated charge as separate expenditure: this report remains the local policy result, with native/provider amounts used for reconciliation.

Before activation, resolve the exact downstream controller and IPP images/source, saved CRD schemas, chart/profile syntax, Loki store ownership, and approved metering backend artifact. The upstream-linked development backend is not a verified Red Hat product operand. The 2026-10-16 guarded read-only attempt stopped before schema inspection because the API/login could not be confirmed, so compatibility is unverified. No backend, Loki export parser or live event capture process is supplied as if qualified.

After those source prerequisites, later authorized qualification must prove user isolation, category/streaming semantics, loss/replay recovery, balance overshoot and failure behavior, storage retention, invoice reconciliation and rendering. Native operational views and MLflow diagnostics are reused where qualified. Prometheus sampling and sampled traces cannot replace complete financial records. These are future gates; nothing in this runbook authorizes deployment.

## Failure handling and rollback

| Symptom | Meaning / action |
|---|---|
| Null canonical limiter or missing series | Verify the resource identity and prime/baseline counters; no allocation from guessed labels. |
| Reset, disappearing epoch, boundary activity or scrape gap | Retain raw evidence and classify the affected model/window unresolved. Rehearse with complete coverage; never add an unseen initial counter value. |
| Receipt count/hash mismatch | Keep the original run/configuration and recover missing receipts; do not normalize incomplete evidence into a full bill. |
| Intended idle phase has activity | Check in-flight requests and other consumers. The phase failed its idle assertion; do not relabel it after observing results. |
| Full cost metric absent | Price coverage is incomplete or report selection invalid. Inspect known subtotal/coverage; do not display zero dollars. |
| Publisher returns 404 / is not ready | Generate and review a valid metrics ConfigMap before later promotion; an empty selection is deliberately not a zero-cost report. |
| Access or quota probe fails | Preserve its receipts and correct identity/model references or calibrate a future quota probe. Never route around MaaS. |
| Mistral fails first token or cold load | Stop the qualification and review the deferred kernel/memory gates in PLAN.md; do not expand GPUs or switch images silently. |

Rollback of this undeployed work removes only this package and its navigation links. After a later deployment, stop owned load, restore reviewed replicas, revoke only demo keys and revert the scoped GitOps additions. Preserve shared consumers, existing models and evidence. Stopping an application does not by itself prove that AWS compute or persistent-storage charging has stopped.
