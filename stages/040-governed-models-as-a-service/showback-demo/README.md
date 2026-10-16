# MaaS service offers and three-team showback demo

This package implements the question “What did AI cost us this quarter?” using two shared private models, governed team identities and an explicit allocation policy. **Implemented and tested offline; not deployed or qualified on the live models.** All candidate manifests are detached from the active GitOps applications. The existing `../showback/` platform utilities remain unchanged.

The package also implements **offline monthly accounting for three service offers**: external provider pass-through, dedicated private managed capacity and shared private inference priced per token. Native Loki showback and external-metering integration inputs are retained as inert review artifacts, with a captured-event importer; they are not enabled or deployed. The [plan](PLAN.md) distinguishes implemented source from native/downstream qualification and remaining live work. The bounded allocation policy and stopped state below are unchanged.

## Service offers

| Offer | Consumer charge | Idle and recovery policy |
|---|---|---|
| External provider | Applicable input/output/cache/tool rates, plus separately disclosed fees and credits | Provider invoice differences remain visible; platform-owned retries are not hidden in user charges. Missing rates or usage stay unknown. |
| Dedicated private | Full evidenced capacity/operations cost, or an explicit fixed quote | Sponsor pays for availability even with zero use; quote versus cost variance remains visible. |
| Shared private | Prospective input/output tariffs; optional reservation fees and capped included-use credits | Forecast idle is included in price. Unexpected shortfall stays visible to the platform; subsidy and reservation revenue are counted once. |

`offers/service-report.sh` produces versioned JSON/CSV statements for UTC calendar months, keeping costs, charges and recovery separate. Its editable `month.example.json` is intentionally unpriced and incomplete; fixture prices are synthetic and cannot become observed rates. Corrections replace a prior statement through a hash-linked revision. The existing bounded allocator is a separate report mode.

`native/` reuses source contracts for newer MaaS Loki showback and IPP external metering. Its renderer emits only ConfigMaps containing candidate configuration documents, never live Config/LokiStack resources or gateway hooks. The source review found incompatible upstream/downstream assumptions, including a logging flag that is not reliably an off switch and an unqualified metering backend. Matching installed schemas, artifact pins and supported integration still need review. See [native integration](native/README.md) before promotion; no product support is claimed for a linked development backend.

## Scenario

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

Three predeclared four-minute windows demonstrate busy shared use, sparse use and fully idle models. The client uses distinct synthetic code-review, campaign and customer-question prompts. Leading scrape buffers and trailing drain time keep boundaries observable. Access and quota probes are separate runs. Missing baselines, ambiguous resources, resets or in-flight boundary work do not become fabricated zero usage. The collector requires all planned windows, including idle. The implementation conservatively leaves uncertain windows unresolved; it does not reconstruct unobserved reset epochs.

## Dashboard views

- **Bill allocation:** selected report identity and UTC period, price sources and exclusions, team/model allocations, platform idle, unresolved costs and exact reconciliation.
- **Usage and governance:** allowed model matrix, configured allowances, actual consumption, receipt input/output counts, requests, errors and quota events when evidence supplies them.
- **Model cost and efficiency:** paid instance-hours, worker rates, effective cost per million tokens, serving latency/throughput, queue depth and GPU utilization/memory. Live performance has its own time range; financial gauges retain the selected closed report's period. End-to-end request latency remains pending runtime metric qualification.

Financial panels use the allocator's report, not a second cost formula. Unknown values remain absent/unknown rather than zero. The publisher starts at **zero replicas** and has an intentionally empty report selection until an operator supplies reviewed evidence. Neither metrics nor synthetic fixtures are installed automatically. Dashboard rendering, scrape integration and live metering remain unverified.

The additional [service views](service-views/README.md) provide five platform dashboard candidates covering six requirements: consumption/team statements, dedicated efficiency, shared recovery, accounting completeness and workload quality/sourcing. They reuse the existing publisher and native LLM operational views. Private user/team JSON, CSV and readable statements use explicit operator-verified scopes; this offline export is not a self-service authorization service. Native self-only usage access and any team-manager delivery need live qualification before exposing financial data.

`analysis/analyze.sh` evaluates explicitly accepted tasks, corrective retries, planned turns and fallbacks, including full service costs and human rework. Its sourcing scenarios include external commitments, private capacity steps and migration payback. Evidence must identify model profiles and prompt versions; sampled traces or successful HTTP responses cannot supply missing task outcomes. Application instrumentation and native MLflow drill-down remain qualification work, not automatic MaaS capture.

## Package contents

| Source | Purpose |
|---|---|
| `scenario.json`, `render-access.sh` | Workloads, user/subscription mapping and generated access policies |
| `run-workload.sh` | Preview by default; bounded HTTP only with explicit execution |
| `collect-usage.sh`, `metering.json` | Raw range capture and offline counter/receipt reconciliation |
| `costs.json`, `instance-intervals.example.json` | Dated prices and required lifecycle evidence |
| `allocate.sh` | Deterministic cost allocation, JSON and CSV reports |
| `publish-report.sh`, `generate-dashboards.sh` | Report gauges and three generated Perses dashboards |
| `archive.sh` | Private hashed evidence bundles; optional explicit MLflow upload |
| `archive-index.sh` | Offline monthly continuity and selection of one correction chain per period |
| `offers/` | Three-offer monthly accounting, exact pricing, safe unpriced input template and synthetic regression cases |
| `native/` | Pinned source contracts, inert Loki/metering integration inputs and local captured-event normalization |
| `service-views/` | Five detached financial dashboards, snapshot metrics and private scoped statements |
| `analysis/` | Accepted-task economics and capacity/quality-bounded sourcing advice |
| `manifests/` | Detached access, dashboard, stopped publisher and evidence-workspace bundle |
| `model-drafts/` | Separate stopped Mistral candidate and Qwen FP8/stop component |
| `fixtures/`, `tests/`, `validate.sh` | Clearly labelled synthetic evidence and offline verification |

See [OPERATIONS.md](OPERATIONS.md) for local commands, prerequisites, evidence formats and failure handling, and [PLAN.md](PLAN.md) for research and acceptance gates. Operator tools and tests are Bash scripts using the repository's `jq`, `curl`, Ruby YAML conversion and checksum tools. Kustomize renders the candidate manifests. Operator commands require no Python interpreter or SDK; the native vLLM container runtime is unchanged.

## Containment and review

No active Argo CD application, stage deploy script, existing dashboard or live resource is changed by this package. There is no deployment entrypoint. Later promotion must preserve existing consumers and replica/registry delegation, qualify models, verify identity and limiter labels, and obtain deployment authorization. The `showback-reporting` workspace grant is a candidate namespaced binding for platform administrators; users and API keys remain prerequisites, not committed credentials.

Private evidence is written with restricted permissions and must stay outside Git. Fixture usage is synthetic and visibly labelled; it cannot prove live attribution or a quarter's history. Local archives request 400-day retention but do not enforce storage lifecycle policy. Monthly correction/continuity indexing and supplied full-cost inputs are implemented offline; automatic collection/close, actual invoices and enforced retention remain qualification work. No new billing server or dashboard engine is deployed.
