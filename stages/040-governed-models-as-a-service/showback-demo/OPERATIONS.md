# Showback demo operations

## Current boundary

This package is implemented for **offline review and testing**, with source for the optional manual-sync `040-showback-demo` Application. A pinned backend image build and disposable local validation were separately authorized on 2026-10-18. On 2026-10-19, the user authorized publication, deployment and bounded testing with the one available Qwen model. This authorization does not qualify the full two-model scenario or activate native/backend workloads. Default Stage 040 deployment excludes this component. The existing `../showback/` utilities still serve the current platform.

Requirements for offline work: Bash, `jq`, `curl`, Ruby for YAML conversion, `shasum` and Kustomize, as used by the repository. Tools source `scripts/lib.sh`; only explicitly requested live actions invoke its environment and cluster guard. No Python, dependency installation, image pull or cluster login is needed for offline checks.

## Offline validation

From the repository root:

```bash
./stages/040-governed-models-as-a-service/showback-demo/validate.sh
```

This runs shell regression tests, verifies generated files, previews workloads, renders canonical manifests and exercises synthetic samples → reconciled evidence → allocation → metric exposition → hashed archive. It also checks the three service offers, native event import, scoped statements, task analysis and monthly archive continuity. Real cluster, HTTP and AWS commands are blocked; HTTP tests supply explicit mocks. Synthetic output is temporary and explicitly labelled. The bounded integration fixture totals 135 cents, including 45 cents of fully idle model capacity; those are test assertions, not a measured bill.

Preview workload and access decisions without credentials:

```bash
stages/040-governed-models-as-a-service/showback-demo/run-workload.sh
stages/040-governed-models-as-a-service/showback-demo/run-workload.sh --mode access-probe
```

Edit `scenario.json` to calibrate budgets/profiles, then regenerate and validate:

```bash
stages/040-governed-models-as-a-service/showback-demo/render-access.sh --write gitops/stages/040-governed-models-as-a-service/040-showback-demo
stages/040-governed-models-as-a-service/showback-demo/generate-dashboards.sh --write
```

The access renderer writes six named YAML files, one subscription and one authorization policy per team. Its default remains a stdout preview. If the scenario changes intentionally, update the synthetic fixture's `scenario_sha256` to the SHA256 of the new exact file bytes and review its request expectations. Do not change a scenario to fit an already observed run: retain that run's original configuration instead. Dashboard definitions must match their shell generator. The cluster publisher serves a reviewed metrics snapshot; it does not run the accounting code.

## Package and promotion

- `gitops/stages/040-governed-models-as-a-service/040-showback-demo/` (from the repository root) is the sole canonical owner of the source for three subscription/auth-policy pairs; its enabled `components/qwen-only` selects only Engineering/Support with Qwen. The same component owns three bounded Perses dashboards, a zero-replica publisher, Service/ServiceMonitor, empty selected-report ConfigMap and the evidence workspace/access grant.
- Its nested `model-drafts/mistral/` is excluded from the root render and separately renders a **zero-replica** Mistral service and model reference. Its 48 GiB request/56 GiB limit and serving flags are hypotheses, not a cold-load qualification. One GPU is requested and no runtime image is overridden. Cache dtype is `auto`; actual dtype and reasoning behavior require qualification.
- `model-drafts/qwen-fp8/` is a detached Kustomize component copied from the existing FP8 component with an added `replicas: 0` patch. It preserves the model ID. It is not a standalone deployment or an active serving configuration change.
- Canonical nested `native-inputs/` contains only two inert ConfigMaps holding candidate documents. No LokiStack, metering workload or controller configuration is activated. The source-backed importer processes saved events locally; it does not collect them from the platform.
- Canonical nested `service-views/` contains five platform financial dashboards. They reuse the same stopped publisher and datasource; they do not establish user/team access controls.
- The manual-sync Application is marked `demo.rhoai.io/optional: 'true'` and uses `deploy-script`, with no `deploy-order`. No load Job/CronJob or autoscaler is added. The runtime workload generator remains a foreground client with explicit execution.

After separate live authorization and source publication, operate only this component through the stage entrypoints:

```bash
./stages/040-governed-models-as-a-service/deploy.sh --component 040-showback-demo --revision REVIEWED_REF
RHOAI_STAGE040_SHOWBACK_EXPECTED_REVISION=REVIEWED_SHA ./stages/040-governed-models-as-a-service/validate.sh --component 040-showback-demo
```

The deploy path uses the existing environment/cluster guard, published-source selection, adoption preflight and component apply/sync/wait. Read-only prerequisites check namespaces, required APIs and the existing native `edit` role’s aggregated MLflow experiment get/list/create/update/delete permissions. It does not create identities/keys, start GPUs, scale the publisher or activate native telemetry. Default deployment still selects eight ordered components. Broad validation reports `SKIP 040-showback-demo (not activated)` when the optional Application is absent; present Applications receive strict source/revision/sync/health validation and must retain manual sync. Explicit component validation requires presence; `RHOAI_STAGE040_SHOWBACK_EXPECTED_REVISION` additionally checks the supplied SHA. Without that input it checks the Application's own immutable revision. Deployment supplies its selected SHA automatically. The enabled Qwen-only Component removes the Marketing pair and Support Mistral references, so the active root has 21 resources and no Mistral dependency. No exception accepts degraded health.

Preserve existing consumer policies and resource IDs; shared Qwen, GPU, MaaS and IPP fields retain their current owners. Verify named replica/registry-label delegation before any later model integration. Adding a Git replica value of zero does not override an existing ignored live replica field. Confirm resource absence or the expected stopped UID before a future sync. Never apply this folder over the whole active stage as a shortcut.

The candidate namespace binding grants `rhods-admins` the existing native namespace `edit` role, including aggregated MLflow experiment permissions, in `showback-reporting`; verify the installed role and target membership before promotion. Native `edit` also permits ordinary namespace editing in this isolated administrator evidence workspace; no new ClusterRole is introduced. It does not change the shared MLflow server, bucket or other experiments. No Keycloak realm ownership or real users are changed here.

## Authorized Qwen-only qualification

Use the checked-in [qualification-qwen-only.json](qualification-qwen-only.json) for execution, collection and publication. Freeze its exact bytes in the private evidence bundle. It records the observed NVFP4 configuration under the existing `040-local-models` owner, with no quantization or GPU change. Its two positive access cases cannot prove the full scenario's cross-model denials. Confirm Engineering/Support identities and their selected subscriptions; obtain separate runtime keys outside Git. Preserve all existing consumer policies.

```bash
stages/040-governed-models-as-a-service/showback-demo/run-workload.sh \
  --scenario stages/040-governed-models-as-a-service/showback-demo/qualification-qwen-only.json
stages/040-governed-models-as-a-service/showback-demo/run-workload.sh \
  --scenario stages/040-governed-models-as-a-service/showback-demo/qualification-qwen-only.json \
  --mode access-probe --execute --insecure --output /private/tmp/showback-qwen-access
stages/040-governed-models-as-a-service/showback-demo/run-workload.sh \
  --scenario stages/040-governed-models-as-a-service/showback-demo/qualification-qwen-only.json \
  --execute --insecure --output /private/tmp/showback-qwen-run
```

The qualification workload has three 120-second busy/quiet/idle phases, a 30-second leading buffer, 45-second drain and request timeout, at most one request per team, 24 requests overall, and approximate input/output bounds of 128/32 tokens. It retains the current illustrative 700,000/300,000 Qwen allowances and does not prove quota exhaustion. Use the same `--scenario` with `collect-usage.sh prepare` and `publish-report.sh`; use a private Qwen-only metering map with verified canonical labels and captured running intervals. The committed full-scenario metering file is a template, not live evidence. A zero or incomplete price/allocation must retain its existing uncertainty state. Native integration remains inactive; the initial publisher stays at zero with no report.

## Before any later full two-model rehearsal

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

Follow [native/README.md](native/README.md) for installed RHOAI 3.5.1 schema/image evidence and the offline renderer/importer. Preview/check emits only ConfigMaps containing candidate data. In this installed build, `Config/default.spec.usageLogging` enables/removes the owned logging pipeline. The separately owned LokiStack is outside that removal, so this is not a general stop command. Neither setting is applied by this package. Do not add the unsupported `telemetry.logs.captureUser` or a DSCI logging field.

For captured events, `native/import-events.sh` takes saved CloudEvents JSONL, a capture manifest and a monthly offer input with an empty event list. It snapshots all inputs, verifies their binding, normalizes provider categories, deduplicates exact source/ID replays, and quarantines unknown identities. Final token/category coverage and stream completion need independent retained evidence; a received event alone cannot prove complete capture. The output goes directly to the service accountant. Do not count a native monetary charge and a recalculated charge as separate expenditure: this report remains the local policy result, with native/provider amounts used for reconciliation.

Guarded read-only inspection on 2026-10-16 verified the installed controller/IPP images, source revisions, CRDs and current profile. The saved Loki 6.6.1 schema is bound to the catalog candidate's image source; its operator is not installed. The candidate specifies `gp3-csi`, v13, 30-day retention and the separate store expected by MaaS. Before activation, supply reviewed object-store credentials/CA and confirm ownership. The supported source mechanism preserves an existing plugins ConfigMap under `opendatahub.io/managed=false`; a later controlled processor restart reloads edits. The candidate preserves routing/authentication and uses a single streaming metering plugin for JSON and SSE.

The official RHOAI 3.5 documentation does not supply a backend installation recipe. The upstream IPP example identifies OpenMeter or a compatible service, with Noyitz's development backend as the testing reference; see [the retained decision](native/backend-decision.json). The pinned Noyitz image now has local build/API/database evidence; publication and RHOAI integration remain unqualified. No Loki export parser or live event capture process is supplied as if qualified. The 2026-10-18 bounded metadata refresh timed out at the cluster guard before any resource read; the retained installed evidence remains dated 2026-10-16.

After those source prerequisites, later authorized qualification must prove user isolation, category/streaming semantics, loss/replay recovery, balance overshoot and failure behavior, storage retention, invoice reconciliation and rendering. Native operational views and MLflow diagnostics are reused where qualified. Prometheus sampling and sampled traces cannot replace complete financial records. These are future gates; nothing in this runbook authorizes deployment.

### Obtain or build the reference backend image

**The pinned local build was executed on 2026-10-18.** The development reference is
[noyitz/ai-gateway-metering-service at f9a56b1](https://github.com/noyitz/ai-gateway-metering-service/tree/f9a56b1769b0933e3fe7454a174b1f42a229f07a),
as linked by the installed IPP source. [Build/runtime evidence](native/evidence/noyitz-local-20261018/README.md)
records the original artifact, checks and retained failures. The current [local derivative](native/backend/README.md) adds replay, missing-usage and database-health corrections without changing the source pin. The optional Application contains no backend workload, and the image remains unpublished.

1. **Existing image route:** its pinned `deploy/metering-service.yaml` names
   `ghcr.io/noyitz/ai-gateway-metering-service:latest`. Obtain registry access and verify its Linux amd64
   manifest digest and source revision before use. The tag is an example input, not evidence of availability
   or provenance. The checked repository has no image-publishing workflow, release or tag to establish those facts.
2. **Source route:** use the pinned checkout and its Dockerfile with a local OCI builder, for example Podman.
   No PostgreSQL instance or provider credentials are needed to build the image. The upstream Dockerfile uses
   `golang:1.25-alpine`, `GOTOOLCHAIN=auto`, and a module requiring Go 1.26.0; it needs toolchain/module network
   access. It compiles `CGO_ENABLED=0 GOOS=linux GOARCH=amd64` and packages into UBI 9 minimal as UID 1001.
   Registry metadata inspection on 2026-10-18 resolved both Linux amd64 base digests. The recipe below derives a
   separate Containerfile that pins those bases and requests exactly Go 1.26.0, and applies the reviewed correctness patch. Its toolchain/dependencies still
   need downloading on a fresh build. The recorded build and local tests establish only their stated scope.

```bash
# Explicit local-only rebuild; requires an already running local Podman engine.
set -euo pipefail
METERING_REV=f9a56b1769b0933e3fe7454a174b1f42a229f07a
METERING_WORK=$(mktemp -d)
METERING_CONNECTION=podman-machine-default # Verify this is the intended local connection.
git init "$METERING_WORK/source"
git -C "$METERING_WORK/source" remote add origin https://github.com/noyitz/ai-gateway-metering-service.git
git -C "$METERING_WORK/source" fetch --depth=1 origin "$METERING_REV"
git -C "$METERING_WORK/source" checkout --detach FETCH_HEAD
podman --connection "$METERING_CONNECTION" pull --platform linux/amd64 \
  docker.io/library/golang@sha256:78c9e40f10516d7070156948a1747347cc5093022f06deeff3c9decd5faa3af7
podman --connection "$METERING_CONNECTION" pull --platform linux/amd64 \
  registry.access.redhat.com/ubi9/ubi-minimal@sha256:865c6a875328a1174ff7f17599574412edd327aa47812951b9bead902806dc53
mkdir "$METERING_WORK/build"
bash native/backend/build-local.sh --source "$METERING_WORK/source" \
  --connection "$METERING_CONNECTION" --output "$METERING_WORK/build"
```

Keep the build log, source commit, Dockerfile/base/toolchain evidence and local image inspection together.
A local image ID is not a registry manifest digest. A later, separately authorized publication must retain the
registry digest and verify that exact artifact before preparing any workload. Do not set `artifact_verified`
or `live_qualified` from a successful build alone.

PriceTag's deployment repository also documents local Podman builds and intends to use
`quay.io/redhat-et/pricetag-metering`, but its reviewed
[image-provenance instructions](https://github.com/redhat-et/pricetag/blob/cb06d37dedf8160c2bd5c2434e43527524e4103c/docs/operations/image-provenance.md)
leave publication pending. A source release does not establish a corresponding published container.
Its `build-metering-et.sh` creates OpenShift build resources and is not a local image-only procedure.
Do not run it, `docker compose up`, or the example `kubectl apply` commands during this stopped phase.
The earlier speculative PriceTag GHCR lookup is not a publisher-advertised image reference.

Later runtime qualification needs a separate PostgreSQL database/PVC and Secret-backed `DATABASE_URL`,
reviewed quota behavior and a verified export path. The backend's fallback prices and cache arithmetic differ
from our service-offer policy; preserve raw events and use the existing accountant for the financial result.
Backend self-reported health, a 204 ingestion response or a visible dashboard does not establish complete metering.

### Local backend validation

The [2026-10-19 corrected local run](native/evidence/noyitz-local-20261019/README.md)
passed 115 top-level Go tests and 93 runtime checks. It preserves two known dashboard/audit
limitations, the earlier build failure and final cleanup evidence. The local VM is stopped.

This explicit local action is separate from the default offline checks. Use an isolated Podman internal
network, a disposable PostgreSQL database and private environment files; do not load `.env`, provider keys
or a kubeconfig. Publish only backend port 8080 on loopback, leave the database unpublished, and set
`MONTHLY_TOKEN_QUOTA=1000`. The retained run used pinned PostgreSQL 16.15 ARM64 and the AMD64 backend
under QEMU. Blocked startup downloads selected bundled prices, which are not our service-offer rates.

`native/test-backend-local.sh` takes an already-running backend/database and an existing empty output
directory. Supply `--url http://127.0.0.1:PORT --connection LOCAL_CONNECTION
--backend-container BACKEND --db-container DATABASE --output EMPTY_DIRECTORY`.
It checks source and patch image labels and port ownership, inserts synthetic events, reads PostgreSQL,
restarts the named backend and temporarily stops/starts the named disposable database. It retains passed assertions, observed limitations and failures. It does not
create or remove containers. After preserving evidence, remove only owned test containers/network/volume
and restore the local VM's initial state.

Upstream Go tests need `DATABASE_URL` and `PREFLIGHT_DSN` for the disposable, migrated database, with
permission to create/drop temporary databases. Use PostgreSQL 15 or later for the replay index
(16.15 in local evidence). The patched migration refuses duplicate history; it does not repair or delete it.
The evidence records the exact command using the cached
Go 1.26.0 binary. The ordinary Go launcher refuses toolchain verification with `GOSUMDB=off`; invoking
the cached binary with `GOTOOLCHAIN=local` preserves the pinned version and blocked network. Backend
denial audit rows do not establish actual gateway 429 responses or IPP delivery.

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
