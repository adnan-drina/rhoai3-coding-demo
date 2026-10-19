# MaaS service offers and three-team showback demo

This package addresses “What did AI cost us?” through governed team identities and an explicit allocation policy. **The Qwen-only component is deployed and its bounded inference, attribution, accounting and archive checks passed on 2026-10-19.** The six-minute run produced 14 successful SSE requests and 1,753 tokens: Engineering 653 and Support 1,100. Its allocated-capacity estimate is **$0.34: Engineering $0.15, Support $0.07 and platform idle $0.12**, with no other-consumer or unresolved allocation. This uses a dated public rate and observed allocated capacity; AWS billed lifecycle and invoice amounts remain unverified. See the [qualified run and correction evidence](evidence/qwen-live-20261019/README.md).

Canonical manifests belong to the optional, manual-sync [040-showback-demo component](../../../gitops/stages/040-governed-models-as-a-service/040-showback-demo/README.md). Its first deployment reconciled Synced/Healthy with strict 21-resource readback at `4349dd62429d15e68bb0e6935d3f1f0e617cdbc8`. The corrected publisher release `adecf57cab87982f5b5a48c966860376474f8f62` reconciled Synced/Healthy with exact readback of all 21 objects, one Ready publisher and a current healthy scrape (`up=1`). Its live financial queries reproduce the selected R2 estimate and allocations. The default Stage 040 deployment still selects eight ordered components; this ninth component requires explicit selection. The existing `../showback/` platform utilities remain unchanged.

The package also implements **offline monthly accounting for three service offers**: external provider pass-through, dedicated private managed capacity and shared private inference priced per token. Real monthly tariffs and complete observed monthly inputs remain unset. Native Loki showback and external-metering integration inputs remain inert review artifacts; the captured-event importer does not enable those integrations. The [plan](PLAN.md) distinguishes the qualified Qwen slice from these remaining scopes.

For implementation-agent transfer, use the [preparation report and implementation handoff](IMPLEMENTATION-HANDOFF.md). It consolidates the prepared artifacts, source authority, dated validation evidence, remaining gaps and phased environment implementation/rollback gates.

## Service offers

| Offer | Consumer charge | Idle and recovery policy |
|---|---|---|
| External provider | Applicable input/output/cache/tool rates, plus separately disclosed fees and credits | Provider invoice differences remain visible; platform-owned retries are not hidden in user charges. Missing rates or usage stay unknown. |
| Dedicated private | Full evidenced capacity/operations cost, or an explicit fixed quote | Sponsor pays for availability even with zero use; quote versus cost variance remains visible. |
| Shared private | Prospective input/output tariffs; optional reservation fees and capped included-use credits | Forecast idle is included in price. Unexpected shortfall stays visible to the platform; subsidy and reservation revenue are counted once. |

`offers/service-report.sh` produces versioned JSON/CSV statements for UTC calendar months, keeping costs, charges and recovery separate. Its editable `month.example.json` is intentionally unpriced and incomplete; fixture prices are synthetic and cannot become observed rates. Corrections replace a prior statement through a hash-linked revision. The existing bounded allocator is a separate report mode.

`native/` binds MaaS Loki showback and IPP external metering to the installed RHOAI 3.5.1 schemas and image revisions. The Loki 6.6.1 candidate has a matching image-bound schema, explicit storage class and 30-day retention. Its renderer emits only ConfigMaps containing candidate documents, never live Config/LokiStack resources or gateway hooks. In this installed release, `usageLogging` enables/removes the owned logging pipeline; the separately owned store remains independent. The pinned Noyitz development backend has an original local build plus a [reviewable correction patch](native/backend/README.md) for replay deduplication, missing usage and database health. The [original evidence](native/evidence/noyitz-local-20261018/README.md) remains unchanged; the [2026-10-19 correction evidence](native/evidence/noyitz-local-20261019/README.md) records the rebuilt artifact, 115 top-level Go tests and 93 runtime checks. It is not published, deployed or connected to MaaS. Native pricing and completeness limits still prevent treating its dashboard totals as our financial ledger. See [native integration](native/README.md); no product support is claimed for the development backend.

The current Application root enables a **Qwen-only qualification slice** through `components/qwen-only`: Engineering and Support access the existing Qwen NVFP4 model. Marketing and all active Mistral references are removed from the render. [qualification-qwen-only.json](qualification-qwen-only.json) bounds this run to six minutes, 24 requests and tiny synthetic prompts; it does not qualify the full FP8/Mistral scenario below. The full `scenario.json` and generated access files are preserved for later qualification.

## Full scenario — qualification pending

| Team | Workload | Access | Illustrative token allowance |
|---|---|---|---|
| Engineering | Code reviews | Qwen3.8 27B FP8 | 700,000 Qwen tokens/hour |
| Marketing | Campaign creation | Mistral Small 4 119B NVFP4 | 700,000 Mistral tokens/hour |
| Support | Customer questions | Both | 300,000 tokens/hour for each model |

Qwen's allowances implement the requested 70/30 ratio. Mistral's independently configured numbers are provisional calibration inputs. These limits reserve neither GPU throughput nor a fixed share of the bill. One user and one explicitly selected subscription represent each team; the demo does not claim pooled quotas across multiple people. The matching authorization policies restrict access to the four allowed combinations and deny the other two. These are [MaaS subscription and authorization capabilities](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/govern_llm_access_with_models-as-a-service/deploy-and-manage-models-as-a-service).

Each model is assumed to use one AWS Ohio `g7e.2xlarge` with an NVIDIA RTX PRO 6000. Qwen FP8 and Mistral fit/runtime qualification remain deployment gates. The included cost basis is the saved public price of **$3.36312 per worker-hour, retrieved 2026-10-15**. It is a compute estimate, excluding shared platform, extra storage, networking, licenses and account discounts. It is not an AWS invoice.

## Accounting and observability

```text
Team keys -> MaaS gateway -> Qwen / Mistral
                 |                 |
           Canonical counters   Model / GPU metrics
                 |
Request receipts + running intervals + dated rates
                 |
       Closed-window reconciliation
                 |
       Immutable allocation report
          /                 \
 Retained evidence      Perses report gauges
```

For each model/window, allocate the full measured running cost by actual governed token shares. With complete evidence but no usage, retain **Platform — idle capacity**. With incomplete evidence, retain **Unresolved allocation**. Other consumers remain visible. The whole included bill reconciles in cents, with carry across windows and models; the quota ratio does not enter the calculation. Input/output usage is retained separately but equally weighted in the first policy. GPU utilization explains efficiency, not team ownership of GPU-seconds.

The full scenario plans three four-minute busy/quiet/idle windows. The qualified Qwen slice instead used three two-minute windows and synthetic Engineering/Support prompts. Genuine owner keys passed isolated JSON/SSE checks with exact response/counter token deltas and unchanged other-team counters; absent and invalid keys returned 401. There were 24 inference POSTs across all attempts: 10 preflight requests, including two denials, and 14 workload requests. No quota-exhaustion test was performed. Native samples and collector configuration established a 30-second cadence. The original 20-second boundary tolerance left all $0.34 unresolved; an explicit 30-second calibration replayed the unchanged scenario, run, receipts and samples into a hash-linked R2 report. Stable boundary flanks, gap/reset checks and exact cent reconciliation remain required.

## Dashboard views

- **Bill allocation:** selected report identity and UTC period, price sources and exclusions, team/model allocations, platform idle, unresolved costs and exact reconciliation.
- **Usage and governance:** allowed model matrix, configured allowances, actual consumption, receipt input/output counts, requests, errors and quota events when evidence supplies them.
- **Model cost and efficiency:** paid instance-hours, worker rates, effective cost per million tokens, serving latency/throughput, queue depth and GPU utilization/memory. Live performance has its own time range; financial gauges retain the selected closed report's period. End-to-end request latency remains pending runtime metric qualification.

Financial panels use the allocator's report, not a second cost formula. Unknown values remain absent/unknown rather than zero. The reviewed R2 report is live through **one Ready publisher replica**. Actual financial panel queries return $0.34 total, $0.15 Engineering, $0.07 Support and $0.12 idle, with pricing/allocation completeness both 1 and unique selected-report/consumer rows. All eight Perses dashboard definitions were ingested through the API and all seven operational selector queries passed against their configured datasource. Browser rendering and presenter interaction remain untested.

The additional [service views](service-views/README.md) provide five platform dashboard candidates covering six requirements: consumption/team statements, dedicated efficiency, shared recovery, accounting completeness and workload quality/sourcing. They reuse the existing publisher and native LLM operational views. Private user/team JSON, CSV and readable statements use explicit operator-verified scopes; this offline export is not a self-service authorization service. Native self-only usage access and any team-manager delivery need live qualification before exposing financial data.

`analysis/analyze.sh` evaluates explicitly accepted tasks, corrective retries, planned turns and fallbacks, including full service costs and human rework. Its sourcing scenarios include external commitments, private capacity steps and migration payback. Evidence must identify model profiles and prompt versions; sampled traces or successful HTTP responses cannot supply missing task outcomes. Application instrumentation and native MLflow drill-down remain qualification work, not automatic MaaS capture.

## Package contents

| Source | Purpose |
|---|---|
| `scenario.json`, `render-access.sh` | Workloads, user/subscription mapping and generated access policies |
| `qualification-qwen-only.json` | Six-minute Engineering/Support qualification profile for the existing Qwen NVFP4 owner |
| `qualify-qwen-identities.sh` | Explicit creation of two new demo identities through the existing SSO authority, genuine OpenShift login and owner-created ephemeral MaaS keys; private recovery evidence only |
| `qualify-qwen-metering.sh` | Bounded JSON/SSE and authentication probes against native RHOAI counters; exact isolated deltas and verified 30-second cadence |
| `run-workload.sh` | Preview by default; bounded HTTP only with explicit execution |
| `collect-usage.sh`, `metering.json` | Raw range capture and offline counter/receipt reconciliation |
| `costs.json`, `instance-intervals.example.json` | Dated prices and required lifecycle evidence |
| `allocate.sh` | Deterministic cost allocation, JSON and CSV reports |
| `publish-report.sh`, `generate-dashboards.sh` | Report gauges and three generated Perses dashboards |
| `archive.sh` | Private hashed evidence bundles; optional explicit MLflow upload |
| `archive-index.sh` | Offline monthly continuity and selection of one correction chain per period |
| `offers/` | Three-offer monthly accounting, exact pricing, safe unpriced input template and synthetic regression cases |
| `native/` | Pinned source contracts, inert Loki/metering integration inputs and local captured-event normalization |
| `service-views/` | Generators for five financial dashboards, snapshot metrics and private scoped statements |
| `analysis/` | Accepted-task economics and capacity/quality-bounded sourcing advice |
| `gitops/stages/040-governed-models-as-a-service/040-showback-demo/` (repository root) | Canonical access, dashboards, selected R2 report, one-replica publisher source and evidence workspace; inert `native-inputs/` remain included |
| Canonical `model-drafts/mistral/`; local `model-drafts/qwen-fp8/` | Mistral candidate excluded from the component render; Qwen FP8/stop component remains a shared-model owner dependency |
| `fixtures/`, `tests/`, `validate.sh` | Clearly labelled synthetic evidence and offline verification |

See [OPERATIONS.md](OPERATIONS.md) for local commands, prerequisites, evidence formats and failure handling, and [PLAN.md](PLAN.md) for research and acceptance gates. Operator tools and tests are Bash scripts using the repository's `jq`, `curl`, Ruby YAML conversion and checksum tools. Kustomize renders the candidate manifests. Operator commands require no Python interpreter or SDK; the native vLLM container runtime is unchanged.

## Containment and review

`deploy.sh --component 040-showback-demo` uses the normal reviewed published-revision selection, adoption preflight, apply, sync and wait flow. It reconciles the publisher/report state authored in source. Native inputs are inert and Mistral is excluded. The Application has no automated sync. Broad validation prints `SKIP 040-showback-demo (not activated)` while absent; once present it must pass revision, source, sync and health checks. Explicit component validation requires presence. The Qwen-only Component removes active Mistral access dependencies; no degraded health is accepted. Publisher runtime, exact selected-data readback and actual financial panel queries passed at the corrected release; browser acceptance remains separate.

Extensions to the full scenario must preserve existing consumers and replica/registry delegation and qualify the additional models and identities. The completed run kept the existing single Qwen NVFP4 model and GPU configuration unchanged. Demo-owned resources stay in this component; shared Qwen, GPU, MaaS and IPP fields retain their existing owners. Genuine `ai-admin` access uploaded both the original and R2 bundles to `showback-reporting`, then verified every archived file by hash; the Engineering user was denied experiment access with 403. Runtime credentials stay private and outside Git.

Private evidence is written with restricted permissions and must stay outside Git. Fixture usage is synthetic and visibly labelled; it cannot prove live attribution or a quarter's history. Local archives request 400-day retention but do not enforce storage lifecycle policy. Monthly correction/continuity indexing and supplied full-cost inputs are implemented offline; automatic collection/close, actual invoices and enforced retention remain qualification work. No new billing server or dashboard engine is deployed.
