# MaaS showback: preparation report and implementation handoff

**Prepared:** 2026-10-19. **Repository:** `rhoai3-coding-demo`. **Audience:** the architecture lead, implementation/validation agents and human reviewer.

**Current state:** the demo and three service-offer accountants are implemented and tested offline. Native integration candidates are prepared. A corrected Noyitz metering image has been built and tested locally. **Nothing in this package has been deployed, connected to the gateway, or qualified against the live models.** The user has subsequently started the environment and indicated that live deployment and tests can follow readiness. The read-only refresh below supersedes the earlier assumption that the whole environment is stopped; the demo source remains inactive. This document itself authorizes no deployment, image publication, GPU start, credential provisioning, provider call or inference.

The lead agent retains the scenario, source-authority and accounting-policy decisions and approves bounded implementation scopes. GPT-6.1 Sol implementation agents own disjoint changes; a separate GPT-6.1 Sol validation agent tests and reviews them. The lead integrates the resulting diff and evidence and reports remaining limits. This document supports that collaboration; it does not transfer architecture ownership away from the lead.

The current source adds one optional manual-sync `040-showback-demo` Application. Its canonical component owns the demo resources; the default Stage 040 deploy still selects eight ordered components. The optional ninth component requires explicit selection, keeps the publisher stopped and excludes Mistral. Native Loki/backend activation remains separately gated and unpublished. This source integration does not establish any live readiness.

This is a handoff of the current working tree, not a release. At the final source review on 2026-10-19, `main` was at `3613c8d67c3a8e509bc7feb9d67e596f2a53553f`, with additional modified and untracked files, including the backend patch and both local evidence directories. This is a base snapshot, not a delivery commit: a checkout of it alone is insufficient. Hand over this complete package, including untracked source/evidence, or a subsequently reviewed commit containing it. The local OCI archive is outside Git; its identity and rebuild inputs are retained below. No commit or push was performed by this handoff task.

## Live readiness refresh — 2026-10-19

A GPT-6.1 Sol agent inspected the guarded target read-only from 07:59:19 to 08:03:42 UTC. The lead reviewed the sanitized results and local source. No resource, replica, credential or image was changed; no inference was attempted. These are observations at that time, not ongoing health guarantees.

- **Available foundations:** OCP 4.22.14, RHOAI 3.5.1 and Connectivity Link 1.4.3 were observed. All 27 Stage 010–050 Applications were Synced; 26 were Healthy and the model-qualification Application was Suspended. Required namespaces and MaaS/Perses/ServiceMonitor APIs were available. Monitoring and MLflow workloads reported ready replicas. UI, data freshness and archive readback were not exercised.
- **Capacity and models:** one Ready `g7e.2xlarge` RTX PRO 6000 worker existed, with its only GPU assigned to Qwen. There was no free slot or second worker. Qwen still used NVFP4 through its existing `040-local-models` owner; its storage initialization had completed, but its main workload was initializing and not ready. Mistral and its model reference were absent. Neither finding qualifies the agreed FP8/Mistral scenario.
- **Deployment prerequisite mismatch:** the candidate RoleBinding and preflight require `mlflow-edit`, which is absent. Installed `mlflow-operator-mlflow-edit` grants writes but omits `get/list`; the separate view role supplies reads. Native namespace `edit` contains the aggregated MLflow read/write rules and is a candidate correction. Do not blindly rename the binding to the write-only operand, create a duplicate ClusterRole, or bypass the preflight. Review the native namespace-role choice, update the binding/preflight/docs consistently, and later prove authorization plus archive upload/readback. No correction or permission grant was made during this refresh.
- **Demo/native activation:** `040-showback-demo` and its candidate resources were absent. LokiStack's CRD was absent, MaaS `usageLogging` was false, and the IPP profile did not enable external metering. User-level metric capture was enabled. The corrected backend still needs a published deployment artifact and live integration qualification.
- **Source publication:** the new Application/component and backend evidence remain local modified/untracked source. The stage deployment selector requires a matching published commit and will refuse this checkout as a deployment revision. The current base is `5002a5ee9b232792526e719aa6f861edc2484826`; its only committed change since the earlier snapshot is an unrelated Stage 070 fix. Preserve all prepared showback files when preparing the delivery commit.

**Next execution order:** correct and validate the archive-access source contract, review/publish the complete package at an immutable revision, qualify the agreed model configurations and second worker through their existing owners, then reconcile the dedicated demo component and prove the four allowed/two denied team/model paths. Follow with the bounded measured workload, report/dashboard reconciliation and archive readback. Native Loki and external-metering activation retain their separate storage, artifact and delivery qualification steps. Preserve the current shared Qwen workload until its reviewed FP8 transition; startup observations alone do not justify a restart or checkpoint change.

The earlier offline validation result remains 19 passing validation groups, with repository structure checks passing. This refresh adds live prerequisite evidence only; it does not turn those offline assertions into live acceptance.

## Authorized Qwen-only source correction — 2026-10-19

On 2026-10-19, the user authorized publishing and deploying the dedicated component, then bounded testing with the one existing Qwen model. The source now enables `components/qwen-only`: 21 resources, Engineering/Support Qwen access only, publisher stopped, native inputs inert. `qualification-qwen-only.json` retains the observed NVFP4 identity and bounds workload execution to six minutes/24 requests; it does not qualify the planned FP8/Mistral scenario. The archive RoleBinding keeps its object name but targets native `edit`; preflight verifies aggregated MLflow experiment get/list/create/update/delete. Live deployment, inference and archive readback remain unproven by this source change.

This supersedes the refresh’s proposed two-worker execution order for the current first qualification only. Preserve the full scenario, generated policies and excluded Mistral draft. Native `edit` grants ordinary namespace editing in the separate administrator workspace as well as MLflow operations; no role is created.

## 1. Read this first

The implementation has two related financial workflows:

1. **The talk's three-team allocation demo:** explain an evidenced bill for two shared private models, including fully idle capacity and incomplete evidence. Allocate each model/window's full included cost by actual governed token shares.
2. **Three monthly service offers:** price external provider consumption, dedicated private availability and shared private usage under explicit agreements. Consumer charges can differ from allocated costs and actual platform expenditure.

Keep these workflows distinct. The three-team demo's idle rule must not make a dedicated team's idle availability free. Conversely, a shared service's fixed tariff must not be changed retrospectively merely to make revenue equal the bill.

The implementation should reuse RHOAI's identity, subscriptions, gateway, usage collection and operational dashboards. The package supplies the local policy and evidence processing that those capabilities do not establish: cost scope, effective prices, idle responsibility, invoice differences, deterministic allocation, monthly statements and recovery analysis.

Read in this order:

| Document or input | Responsibility |
|---|---|
| [Repository instructions](../../../AGENTS.md) and `.agents/rules/` | Shell-only operator tooling, GitOps ownership, cluster safety and documentation rules |
| [Package overview](README.md) | Delivered behavior and current containment |
| [Implementation plan](PLAN.md) | Canonical scenario, accounting agreements, research and acceptance gates |
| [Operations](OPERATIONS.md) | Exact supported commands, input formats, failure handling and execution boundaries |
| [Native integration](native/README.md), [provenance](native/provenance.json), [backend decision](native/backend-decision.json) | Version-specific contracts, source/image bindings and unresolved integration work |
| [Corrected backend evidence](native/evidence/noyitz-local-20261019/README.md) | What the local build and runtime tests actually establish |
| This handoff | Consolidated findings and ordered remaining work; it does not replace executable configuration or the canonical policies above |

## 2. Agreed scenario and environment baseline

### Teams, models and access

| Team | Workload | Demo user / subscription | Qwen | Mistral |
|---|---|---|---|---|
| Engineering | Code reviews | `showback-engineering` / `team-engineering` | Allowed | Denied |
| Marketing | Campaign creation | `showback-marketing` / `team-marketing` | Denied | Allowed |
| Support | Customer questions | `showback-support` / `team-support` | Allowed | Allowed |

The scenario assumes **Qwen3.8 27B FP8**, ID `qwen3-8-27b`, and **Mistral Small 4 119B NVFP4**, ID `mistral-small4-119b`. Both are private models in `internal-models`, each using one separate NVIDIA RTX PRO 6000 worker. The Mistral checkpoint is `RedHatAI/Mistral-Small-4-119B-2603-NVFP4`, revision `a7b11eb3bdf01f38077f6704e96cc1d9b83a4cfc`.

The user explicitly deferred model qualification and asked us to assume this Mistral fits for planning. That remains an assumption. The inspected active Qwen definition uses **NVFP4**, so its existing evidence does not qualify the FP8 scenario. Do not silently change the agreed models or claim either candidate configuration is proven.

Use separate identities and explicitly subscription-bound API keys. A `MaaSSubscription` declares ownership and model token allowances; a matching `MaaSAuthPolicy` grants access. Both are required. Inspect all inherited and overlapping policies before claiming the two forbidden combinations are denied. A namespace containing shared models cannot identify which consuming team generated a request. The financial join is versioned **subscription/user → team/cost center**, not serving namespace. [Sources S1, S5; local contract: `scenario.json` and `render-access.sh`.]

The Qwen 70/30 proposal is currently **700,000 tokens/hour for Engineering and 300,000 for Support**, subject to calibration. It is not a GPU reservation, throughput guarantee, fixed cost split, dollar ceiling or automatic borrowing mechanism. Mistral currently has 700,000/300,000 allowances for Marketing/Support as provisional configuration; no Mistral ratio has been agreed. With multiple people in a subscription, verify the documented per-user limiter behavior before advertising a pooled team quota.

### Evidence dates matter

| Evidence | Observed or prepared state | Limit |
|---|---|---|
| Guarded environment inspection, 2026-10-15 | OCP 4.22.14, RHOAI 3.5.1, Connectivity Link 1.4.3; existing monitoring/MaaS components; GPU MachineSets and Qwen inference replicas at zero | Historical snapshot, not a current cluster inventory. Qwen's router/scheduler remained running; Ready did not establish inference. |
| Installed schema and image inspection, 2026-10-16 | MaaS/IPP contracts bound to downstream source; Loki 6.6.1 catalog/schema candidate | Loki was not installed by this work; metadata validation is not admission or runtime validation. |
| Bounded refresh, 2026-10-18 | Cluster guard timed out before a resource read | No newer live-state conclusion can be drawn. |
| Backend build/probe, 2026-10-18 | Original pinned Noyitz tested locally; correctness failures retained | Historical unpatched artifact, not the implementation candidate to activate. |
| Corrected backend build/probe, 2026-10-19 | New patched image passed local tests; owned disposable resources removed; Podman VM stopped | No gateway, provider, model or OpenShift integration tested. |
| This handoff, 2026-10-19 | Source/evidence review, official reference recheck, both evidence checksum manifests verified, local links checked and five stopped-bundle checks passed | No environment refresh, container start or deployment performed. The complete software suite was not rerun for this documentation-only change. |

### Existing platform to reuse

| Component | Role and existing owner | Addition needed for this demo |
|---|---|---|
| Stage 020 GPU infrastructure | RTX PRO 6000 `g7e.2xlarge` workers, hardware profiles and queues; exclusive GPUs, no time slicing | Qualify two concurrent model workers; reconcile CPU/RAM budgets and any reviewed larger-host contingency |
| Stage 040 local model serving | RHOAI-managed serving, llm-d/vLLM and MaaS model references | Qwen FP8 alignment and separately qualified Mistral deployment |
| MaaS + Connectivity Link | Gateway API routing, Authorino authorization, Limitador token controls, keys and subscriptions | Three narrow team subscription/auth-policy pairs and real user-owned keys |
| Existing identity authority | Environment-provided Keycloak and OpenShift identity | Add/confirm demo identities through the existing workflow; do not adopt the base realm into this package |
| Prometheus/Thanos + Perses | MaaS usage and native LLM operational views | Canonical metric identity validation, selected-report publisher and additional financial views |
| NVIDIA DCGM | GPU activity and memory signals | Verified model/pod/node/instance mapping; no invented per-team GPU-seconds |
| Stage 050 MLflow + ODF artifacts | Existing experiment and artifact infrastructure | Proposed isolated `showback-reporting` workspace and `showback-accounting` experiment, access/readback/retention qualification |
| Native MaaS usage-log pipeline | Controller source supports OTLP logs, proxy and dashboards | Loki Operator/store prerequisites and reviewed `Config/default.spec.usageLogging` activation |
| Gateway IPP | Installed source includes external-metering plugins | Qualified persistent backend, event export/completeness path and reviewed profile activation |

The MaaS API-key PostgreSQL database is **not** the external metering database. Keep their lifecycle, schema, persistence and credentials separate.

## 3. What has been prepared

Tooling and evidence paths below are relative to this package. Canonical manifests are in [040-showback-demo](../../../gitops/stages/040-governed-models-as-a-service/040-showback-demo/README.md), relative to the repository root. Operator tooling is Bash with existing repository tools such as `jq`, `curl`, Ruby YAML conversion, checksums and Kustomize. The backend correction patches the existing upstream **Go** service; it does not introduce Python operator scripts.

| Area | Delivered artifacts | Current proof / remaining boundary |
|---|---|---|
| Scenario and access | [scenario.json](scenario.json), [render-access.sh](render-access.sh), six canonical `team-*.yaml` resources | Generated subscription/auth-policy pairs match the scenario; offline allowed/denied matrix tested. Users, keys and enforcement are not provisioned/proven. |
| Model candidates | [canonical Mistral draft](../../../gitops/stages/040-governed-models-as-a-service/040-showback-demo/model-drafts/mistral/), [local Qwen FP8 component](model-drafts/qwen-fp8/) | Stopped candidates. Mistral is excluded from the Application render; Qwen requires its existing shared-model owner. Mistral flags/resources remain hypotheses. |
| Bounded workload | [run-workload.sh](run-workload.sh) | Preview by default; explicit execution required. Distinct synthetic prompts, bounded requests/time, JSON or SSE receipts, separate access/quota probes. |
| Usage reconciliation | [collect-usage.sh](collect-usage.sh), [metering.json](metering.json) | Range capture and offline sample/receipt reconciliation. Canonical live limiter fields deliberately remain unset. |
| Infrastructure allocation | [costs.json](costs.json), [allocate.sh](allocate.sh), [instance interval template](instance-intervals.example.json) | Deterministic exact-cent compute-only allocation with explicit idle/unresolved/other buckets. Optional shared-overhead allocation is not implemented. Lifecycle template is empty; no real run bill exists. |
| Bounded financial views | [publish-report.sh](publish-report.sh), [dashboard definitions](dashboard-definitions.json), canonical component root | Three generated Perses dashboard candidates and static HTTP publisher, `replicas: 0`, no selected report. Rendering and scraping unqualified. |
| Three monthly offers | [offers/service-report.sh](offers/service-report.sh), [offers/month.example.json](offers/month.example.json) | Effective prices, fees, actual costs, credits, corrections and recovery calculations tested on synthetic monthly input. Real rates and agreement evidence remain unset. |
| Monthly views/statements | [service-views](service-views/README.md) | Five platform dashboard candidates and scoped JSON/CSV/Markdown exports. No authenticated consumer portal or team-manager authorization service. |
| Quality and sourcing advice | [analysis/analyze.sh](analysis/analyze.sh) | Accepted-task cost, retries/fallbacks, human rework and capacity-bounded sourcing scenarios. Real application outcome instrumentation is not supplied. |
| Archive and continuity | [archive.sh](archive.sh), [archive-index.sh](archive-index.sh) | Hashed bundles, optional guarded MLflow upload/readback, monthly correction/continuity index. Storage enforcement, recovery and unattended close remain unqualified. |
| Native integration | [native/integration.json](native/integration.json), [native/render-integration.sh](native/render-integration.sh), [canonical native inputs](../../../gitops/stages/040-governed-models-as-a-service/040-showback-demo/native-inputs/) | Emits only two ConfigMaps containing review documents. No active Config, LokiStack, backend workload or gateway hook. |
| Native event import | [native/import-events.sh](native/import-events.sh), [capture example](native/examples/capture.json) | Local normalization of saved CloudEvents with source/hash bindings and identity/category checks. It does not collect live events or export the backend database. |
| Backend correction | [native/backend](native/backend/README.md), [native/test-backend-local.sh](native/test-backend-local.sh) | Pinned build, correctness patch and local API/database validation. No registry publication or cluster selection. |
| Regression coverage | [validate.sh](validate.sh), `tests/`, offer/native/view/analysis test suites | Offline checks block real HTTP, AWS and cluster transport; fixtures remain explicitly synthetic. |

No load Job/CronJob or autoscaler is included. The optional Application uses the existing Stage 040 deploy/validate entrypoints with `--component 040-showback-demo`; it has no automated sync. The workload generator runs in the foreground only when explicitly requested. Do not interpret source integration or a rendering command as deployment.

### Workload prepared for the talk

The financial scenario is twelve minutes: **busy**, **quiet**, then **fully idle**, each four minutes. Engineering uses Qwen, Marketing Mistral and Support both during busy load. Support pauses during quiet load. During idle, no team submits requests while model workers remain available.

Current load targets are Engineering 4,096 input / 512 maximum output tokens every 12 seconds; Marketing 1,024 / 1,024 every 20 seconds; Support 256 / 128 every 5 seconds, with a 20/80 Qwen/Mistral request mix. Each team has concurrency one. Quiet spacing is six times longer. These describe offered load, not achieved token shares or a performance promise.

The runner caps total requests at 200, uses a 45-second request deadline, and reserves leading scrape and trailing drain time. Receipts retain identity, subscription, model, timestamps, HTTP status, usage, completion and latency without prompt/response content or secrets. A timeout can leave server-side work running; it cannot establish zero usage. A completed stream without final usage leaves accounting incomplete. Access and quota tests use separate runs and cost scopes; the runner never automatically retries 429.

## 4. Pricing and allocation agreements

### Evidence-backed cost basis

The [saved AWS extract](showback-aws-pricing-2026-10-15.json) was retrieved on 2026-10-15 from the official Ohio (`us-east-2`) EC2 price list: Linux, Shared tenancy, On-Demand, no preinstalled software. Its price-list version is `20261012193925`, effective 2026-10-01. This handoff preserves that dated evidence; it is not a fresh account-price lookup. [S9–S11.]

| Instance | GPU / host memory | Saved USD per instance-hour |
|---|---|---:|
| `g7e.2xlarge` | One 96 GB RTX PRO 6000 / 64 GiB RAM | 3.36312 |
| `g7e.4xlarge` | One 96 GB RTX PRO 6000 / 128 GiB RAM | 3.99816 |

Two `g7e.2xlarge` workers therefore have a saved compute estimate of **$6.72624/hour**, displayed as $6.73. Running both continuously for Q4 2026's 2,208 hours would project **$14,851.54 in worker compute**. Neither number is an invoice or a complete managed-service cost. The slide's **$14,200 remains an unsupported placeholder** and must not enter accounting inputs.

Use actual paid instance lifecycle intervals, including boot, loading, warm-up and idle. Do not substitute pod Ready duration. Refresh prices and obtain effective account rates/CUR or invoice evidence when available. Account for discounts, commitments, credits, taxes and exclusions explicitly. Include storage, network, software/support, operations effort and allocated shared services only with evidence and a declared allocation basis. The full instance rate already includes its CPU/RAM; do not charge them twice. Cloud rental is OpEx; owned hardware requires a different depreciation/power/facilities model.

### Bounded three-team bill allocation

For each model in each predeclared closed window:

```text
team_share = team_governed_total_tokens / all_governed_total_tokens_for_model
team_allocated_cost = full_included_model_window_cost * team_share
```

The denominator includes known non-demo consumers, allocated to `other_consumers`. Qwen's allowance percentages are not inputs. Version 1 weights governed input and output tokens equally within each model; it does not claim equal computational cost across tokens or models.

| Window condition | Cost owner / reporting result |
|---|---|
| Complete coverage, positive tokens | Allocate the full window cost by actual shares, including quiet time inside that window |
| Complete coverage, only one consuming team | That team pays the full model/window cost under this allocation policy |
| Complete coverage, zero tokens, no inference in flight | Entire cost is **Platform — idle capacity** |
| Missing counters, identity ambiguity, reset/gap or incomplete boundary evidence | Entire affected model/window cost remains **Unresolved allocation** |
| Known background consumers | Retain their denominator contribution and **Other consumers** allocation |
| Missing price | Full monetary total remains unknown; show only an explicitly identified known subtotal |

GPU utilization is an efficiency signal. It neither reduces a paid instance bill nor determines an individual team's GPU ownership. A quota denial also does not stop compute charges.

Reports must reconcile exactly in cents:

```text
teams + other_consumers + platform_idle
  + platform_shared_overhead + unresolved_allocation
  = all included priced cost pools
```

The allocator carries rounding across ordered windows and pools, with deterministic remainder distribution. Rollups sum finalized atomic-window allocations. Do not recalculate a quarter from aggregate token shares; that reallocates quiet/idle costs differently. The bounded demo uses four-minute windows; sustained allocation proposes UTC hourly windows. Do not combine overlapping scopes. Hourly scheduling and revision indexing for this bounded allocator are not implemented.

The equation includes the proposed overhead extension for completeness, but **the delivered bounded allocator is compute-only**: `platform_shared_overhead` is not an implemented cost input/output pool. Keep it absent in the initial demo. Broader cost inputs are supported by the separate monthly service-offer accountant; adding overhead to the bounded allocator requires an explicit schema/calculation/view/test change first.

### Three monthly offers

| Offer | Price agreement | Idle / shortfall owner | Required evidence |
|---|---|---|---|
| External pass-through | Applicable provider usage charges plus disclosed platform fees and signed adjustments | No local GPU idle. Named purchaser owns unused commitments unless contract assigns them differently | Individual identity, model, disjoint usage categories, effective rates, retries/credits and provider reconciliation |
| Dedicated private managed model | Full attributable availability/operations cost, or agreed fixed quote with variance shown | Sponsoring team owns contracted capacity, including zero-use periods, warm-up and agreed standby | Paid intervals, full cost components, sponsor, workload/SLO, availability and quality evidence |
| Shared private inference | Prospective input/output tariffs; optional reservation plus usage minus capped credits | Expected idle/headroom included in forecast; unexpected shortfall remains with platform unless explicitly contracted otherwise | Actual service costs, forecast, calibrated weight, published rates, reservations/subsidy/credits and measured consumption |

External pricing is calculated across model, billing category and effective-rate interval:

```text
provider charge = sum(billable quantity * applicable unit rate)
                + attributable non-token fees - credits
consumer charge = provider charge + disclosed platform fee + policy adjustments
```

Provider categories must not overlap. For example, reasoning already counted in output is not charged again. Cache read/write semantics vary by provider; missing categories remain unresolved. **The external input schema uses USD per token, or per tool call**, while displayed internal tariffs use USD per million tokens. Convert provider price units explicitly. Platform-fault retries belong to the platform under the proposed default; consumer-requested attempts follow the provider's actual billing.

For a dedicated service:

```text
monthly actual service cost = paid compute + storage/network + software/support
                            + operations + attributable shared platform costs
consumer charge = actual service cost              # reimbursement contract
recovery balance = fixed quote - actual cost        # alternative quote contract
```

For pure usage pricing of a shared service, with recoverable target `C`, forecast input/output quantities `I` and `O`, and calibrated output/input price weight `w`:

```text
input price per million  = 1,000,000 * C / (I + w * O)
output price per million = w * input price per million
recovery balance = consumer charges + explicit subsidy - actual service cost
```

An empty forecast cannot define a tariff. Zero consumption generates no usage revenue. The reservation/credit variant is already supported by the accountant; follow the exact contract in [PLAN.md](PLAN.md), including credit caps and avoidance of double-counted revenue. Neither a reservation fee nor a token allowance proves a serving-capacity guarantee.

Monthly reports use **USD and UTC calendar months**. Keep actual expenditure, allocated responsibility and consumer charges separate. Corrections create a new hash-linked statement revision. Closed statements need invoice/completeness evidence; synthetic complete months are not observed months. Real numeric tariffs remain unset.

### Efficiency and sourcing advice

Measure **full workflow cost per unique accepted task**, including failed attempts, retries, fallbacks and attributable human rework. Define acceptance with the consumer. A successful HTTP response is not an accepted code review, campaign or resolved ticket. Separate intentional multi-turn work from corrective reprompting. Zero accepted tasks means undefined unit cost.

For a comparable workload, an initial crossover calculation is:

```text
external cost(N) = F_external + e * N
private cost(N)  = F_private  + v * N
crossover N     = (F_private - F_external) / (e - v)
```

`N` is accepted tasks, not equal raw tokens across different models. The positive-threshold interpretation requires suitable signs; commitments, tiering and additional replicas make the curves piecewise. Qualify quality, peak concurrency, latency and capacity before recommending a switch. Include migration cost, fallback and payback once. `analysis/analyze.sh` implements the supplied-evidence analysis, not automatic instrumentation or migration.

## 5. Observability and reporting architecture

```text
Individual/team identities and subscription-bound keys
                         |
                 MaaS gateway / IPP
                   /             \
          private vLLM models    approved external providers
                   |             |
             serving/DCGM     provider usage/invoice

Independent observation paths:
  Limitador -> Prometheus/Thanos -> native usage + LLM operational dashboards
  MaaS usage logs -> OTLP collector -> Loki -> native self/admin usage views
  IPP CloudEvents -> corrected metering candidate -> separate PostgreSQL

Evidence processing (not all collection paths connected yet):
  counters + receipts + lifecycle/rates -> bounded allocation report
  saved events + agreements + full costs/invoices -> monthly service statement
  instrumented task outcomes -> quality/sourcing analysis
                            |
             one reviewed selected report snapshot
                   /                        \
        Perses financial gauges       scoped statement exports
                            |
             hashed archive + correction/continuity index
```

The native paths and Bash accountants have different roles. Do not add the same request's metric count and CloudEvent count together. Reconcile independent measurements; choose one qualified usage authority per report contract. Traces and request IDs provide drill-down, not additional billable consumption.

### Native capability boundaries

RHOAI 3.5 documents Loki-based MaaS showback and self-only usage views as **Technology Preview**, with a separate administrator fleet view. External metering is **Developer Preview**. This support posture and feature description were rechecked on 2026-10-19; neither establishes an installed backend image or a billing-grade service. [S2, S3.]

Use native LLM Traffic, Performance and Utilization for operational metrics, with paid-capacity and pricing context added by the package. MLflow Traces/Sessions require instrumented applications. Enabling tracing or a healthy Tempo instance does not capture every arbitrary MaaS/agent request or establish accepted business outcomes. Sampled traces cannot establish complete financial usage. [S4; retained source contracts in S5–S7.]

### Loki preparation

The inspected installed controller treats `maas.opendatahub.io/v1alpha1 Config/default.spec.usageLogging` as an **enable/remove switch for its owned pipeline**. It creates/removes collector, proxy, RBAC, dashboard and logging resources. The separately owned LokiStack remains independent. Do not copy newer upstream collector-selection behavior into this build.

The candidate uses Loki Operator **6.6.1**, channel `stable-6.6`, a `LokiStack` named `usage` in `redhat-ods-monitoring`, `gp3-csi`, schema v13, `openshift-logging` tenancy and explicit **30-day** retention. The shipped OTLP target is the `usage-gateway-http` service's application-tenant endpoint. Operator image/source and CRD bindings are retained in [artifacts.json](native/evidence/artifacts.json); object storage and credentials are not provisioned. [S5, S7.]

For the existing NooBaa approach, later map the approved OBC bucket/endpoint and private credentials into the Loki object-store Secret, with the documented path-style and CA settings. Do not deploy the full Vector collection stack merely to satisfy MaaS's own collector. Validate the actual logging requirements before choosing additional components.

The shipped log body is status/path; usage and identity are structured metadata. Absent/unparseable usage can become zeros. The reviewed logging filter covers POST chat-completion/completion routes, not every possible AI protocol. No guessed JSON-body financial parser has been supplied. Native self-only filtering must be proved with cross-user denial tests; it does not automatically grant a team-manager view. Thirty-day operational retention cannot cover every calendar month plus invoice close/correction, or a quarter.

### External-metering preparation

The installed IPP source is bound to RHOAI 3.5.1, not inferred from upstream `main`. Its example names OpenMeter or a compatible service and links **Noyitz for development testing**. The official-documentation investigation found no backend image/install recipe in the reviewed materials. This is a scoped finding, not proof that no supported artifact can exist. Noyitz is a community derivative candidate; PriceTag's successor history was also investigated, but it is not the installed RHOAI default or a selected replacement. [S3, S6, S8; details in `native/backend-decision.json`.]

The profile customization target is the existing ConfigMap `openshift-ingress/payload-processing-plugins`, key `custom-ipp-config.yaml`. Preserve all other metadata/data, especially `custom-pre-processing-ipp-config.yaml`. The shipped controller marks the post-bootstrap ConfigMap `opendatahub.io/managed=false` to preserve customization. Do not seed that opt-out in bootstrap input. Reload requires a controlled `payload-processing` restart after a later approved edit.

`PayloadProcessorConfig`, `llm-d.ai/v1alpha1`, is a **file-loaded configuration schema**, not a Kubernetes CRD. Use `parameters`, not a stale example's `json` field. The candidate preserves this request order:

```text
maas-headers-guard -> stream-usage-enforcer -> model-provider-resolver
  -> external-metering-streaming -> api-translation -> apikey-injection
```

The response chain uses `external-metering-streaming`. Its source handles SSE and reassembled non-streaming JSON; both still need end-to-end tests. The framework cannot combine buffered response translation and chunk response processors in one profile. Keep the existing OpenAI-compatible paths initially; qualify other provider translations separately. There is no invented automatic multi-profile selector or disabled-plugin flag. The inactive state omits the plugin from the active profile.

The wire contract is a balance GET at `/api/v1/customers/{user}/entitlements/{feature}/value?model={model}`, followed by POST of a CloudEvents 1.0 object to `/api/v1/events`. Balance responses use HTTP 200 with `hasAccess`, `balance`, `usage` and `overage`; accepted event POSTs return 200 or 204. The installed client has no configurable authorization header. Candidate `failOpen=true` controls backend failures; an explicit `hasAccess=false` still denies. The invalid URL `https://metering.invalid` is intentional review data, not a destination.

The producer generates event UUIDs, not gateway request IDs. Source-plus-ID replay protection does not deduplicate a repeated inference assigned a new ID. Delivery failures are logged; there is no verified durable retry queue. The plugin can turn missing upstream usage into numeric zeros before the backend sees it. Therefore backend validation alone cannot prove capture completeness. A capture/export and independently evidenced completion contract remains required before closed financial statements.

There is also a concrete importer gap: [native/normalize-events.jq](native/normalize-events.jq) currently accepts `inference.tokens.used` for accounting and quarantines `inference.request.error` as an unsupported event type when its model mapping is known. The corrected backend retains those errors, but that does not make them usable accounting events automatically. Preserve them in raw exports and define their agreement/coverage treatment explicitly; never filter them away to manufacture a complete month.

## 6. Corrected local metering backend

### Artifact and provenance

| Item | Recorded identity |
|---|---|
| Noyitz source | `f9a56b1769b0933e3fe7454a174b1f42a229f07a` |
| Patch | [0001-metering-correctness.patch](native/backend/0001-metering-correctness.patch) |
| Patch SHA-256 | `c997048addb0afbfe25d38eb8de5ec06dca2d08e7f3414d3593737480c385a1e` |
| Corrected local tag | `localhost/showback-metering:f9a56b1-c997048addb0` |
| Image config ID | `sha256:34bf73af2c838edb000d18915b42bb5d9fbb98c97f7c9e5962b8ef7b8b8616d9` |
| Exported OCI manifest | `sha256:ff3eb4b2759460150c35b3622ee8ef2668c75ff95b62f78bf1d53cfc99820931` |
| Build/runtime | Linux amd64, Go 1.26.0, pinned Go/UBI bases, runtime UID 1001 |
| Database qualification | PostgreSQL 16.15 in an isolated local test; patch requires PostgreSQL 15+ |
| OCI archive | Repository-relative, Git-ignored `tmp/showback-noyitz-local-20261019/metering.oci.tar` |

These are local artifact identifiers, **not a published registry reference**. Preserve the distinctions between image config ID, local storage manifest and exported OCI manifest. Publication requires an approved destination and verified remote digest, platform and content after transfer. The helper uses a clean pinned source, applies the exact patch in a separate build context and records the inputs. Its base digests and complete build command are in [Containerfile](native/backend/Containerfile), [build-local.sh](native/backend/build-local.sh) and [build evidence](native/evidence/noyitz-local-20261019/build/build.json).

### What was fixed and proved

| Problem | Implemented correction | Local evidence |
|---|---|---|
| Replay double-counting | Unique `(source, event_id)` key; compare full semantic JSON; raw event and rollup commit together | Identical replay returns 204 without another charge/token/quota increment, including concurrent delivery and restart; conflicting payload returns 409 |
| Missing usage treated as zero | Strict successful-event envelope and all six explicit nonnegative integer counters; reject invalid/ambiguous JSON and inconsistent totals | Missing/null/partial/invalid usage rejected; explicit all-zero usage stays complete |
| Native error without token data | Retain original semantic event, `usage_complete=false`, raw `cost_usd=NULL` | Error preserved without pretending audit sentinel zeros are measured usage; backfill/rebuild checks preserve distinction |
| Health returned success without DB | Bounded primary database query in `/health` and `/ready`; bounded ingestion database work | 503 during database outage, 200 after recovery; failed ingestion then successful retry/replay counted once |
| Unsafe upgrade of historical data | Migration refuses duplicate source/ID history; preserves legacy unknown completeness/raw payload | Existing history not deleted; unverifiable legacy replay conflicts rather than being accepted as equal |

The corrected evidence contains **115 passing top-level Go tests, 201 including subtests, no failed or skipped test cases**, plus **93 passing runtime checks and two observed limitations**. Three packages contain no tests; their package-level skip records are not skipped test cases. Tests used the final patched source and newly built image. All 65 files in its retained checksum manifest were verified while preparing this handoff. See [summary.json](native/evidence/noyitz-local-20261019/summary.json), [runtime results](native/evidence/noyitz-local-20261019/runtime/result.json) and [SHA256SUMS](native/evidence/noyitz-local-20261019/SHA256SUMS).

The [original 2026-10-18 evidence](native/evidence/noyitz-local-20261018/README.md) and failed first corrective build remain history; do not overwrite them. A future rerun needs a new evidence directory and disposable database. Local resources were cleaned up and the VM restored to stopped.

### Remaining limits

- Native request totals include quota-denial audit records; they are not automatically successful inference counts.
- Numeric rollups omit completeness and can show known subtotals as zeros for incomplete events. Consult raw completeness, and keep the Bash accountant as financial authority.
- Fallback prices, mutable catalog behavior and provider-independent cache calculations remain unsuitable for the agreed unknown-price/provider-category policies.
- A primary read health check does not prove writes, storage capacity, complete capture or invoice agreement. Do not blindly use it as a restart-triggering liveness probe.
- PostgreSQL 15 is a minimum imposed by the index; the tested version is 16.15. Arbitrary OpenShift UID/SCC, persistent volume permissions and deployment probes still need qualification.
- No live backend export, producer retry/recovery, gateway integration, consumer isolation or provider invoice reconciliation has passed.

Accordingly, `native/backend-decision.json` still has no selected deployment name/image and keeps `activation_allowed=false` and `live_qualified=false`. A successful local corrective build does not remove those gates.

## 7. Dashboard and report deliverables

### Talk sequence: three bounded views

| View | What the presenter shows | Acceptance requirement |
|---|---|---|
| Bill allocation | Included bill by team/model/window, Other consumers, Platform — idle capacity, Unresolved allocation, period and price scope | Every included cent reconciles to the selected report; missing evidence is visible |
| Usage and governance | Four allowed cells, two denials, actual token shares, input/output receipts, requests/errors and quota events; 70/30 allowance alongside actual Qwen consumption | Actual usage can differ from allowances; rejected access is proved, not assumed from configuration |
| Model cost and efficiency | Paid hours/rates, full model cost, cost per million consumed tokens, GPU utilization/memory, throughput, TTFT, inter-token latency and queues | Quiet load raises effective unit cost while hourly rate stays constant; idle unit cost is undefined, not zero |

### Monthly service views

Five prepared dashboard candidates cover six requirements by combining consumption and team statements. Keep them platform-only until query access is verified.

| Requirement | Available now | Work still needed |
|---|---|---|
| My consumption | User/model/category/rate charges and scoped statement exports | Authenticated self-service delivery, qualified request/allowance data and month-to-date forecast |
| Team statement | Team charges, availability/reservation fees, credits and revisions | Verified team-manager authorization and delivery |
| Dedicated efficiency | Full cost components, sponsor charge, quote variance and certified tokens | Real availability/SLO data and native operational drill-down |
| Shared economics | Cost, charges, reservation/subsidy, recovery balance and ratios | Actual forecasts, qualified capacity and prospective tariff review |
| Quality and sourcing | Optional task/outcome/retry/fallback cost and switching/payback analysis | Instrumented representative tasks and MLflow session/trace linkage |
| Accounting completeness | Known/full amounts, invoice difference, coverage, corrections and continuity | Reliable live capture, actual invoices, operational retention and recovery |

**Financial panels read one selected immutable report.** Gauges are not usage counters: never apply `rate`, `increase` or `sum_over_time` to derive money. A dashboard time picker must not relabel a fixed report as a new accounting period. Show report ID/hash, revision, UTC bounds, evidence kind, currency, policy/rate version and completeness.

The bounded and monthly views currently use alternative metric snapshots in the same `showback-selected-report` ConfigMap and stopped publisher. Selecting the monthly snapshot replaces the bounded metric family; both report modes are not simultaneously supplied. Plan the demonstration switch explicitly, or implement and validate a reviewed combined selection contract later. Do not introduce a duplicate ConfigMap with the same identity.

Offline scoped exports rely on an operator-verified authorization file bound to the report hash. This is not an authentication mechanism. Dashboard filters are not access control, and native self-only usage isolation does not prove isolation of custom monetary metrics. Verify server-side datasource/export permissions before sharing consumer financial data.

## 8. Sources and how they were used

Authority order: **official versioned product documentation → installed schema/image-bound source → provider/publisher data → local observed tests → illustrative articles/fixtures**. A source can establish one layer without establishing the next. Local accounting and idle policies are our agreements, not product defaults.

| ID | Source | Used for / claim boundary |
|---|---|---|
| S1 | [RHOAI 3.5 MaaS guide](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/govern_llm_access_with_models-as-a-service/deploy-and-manage-models-as-a-service) | Subscriptions, auth policies, keys, telemetry, formats and native usage export. Does not establish our prices, GPU reservations or invoice policy. |
| S2 | [RHOAI 3.5 Technology Preview notes](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/technology-preview-features_relnotes) | Loki-based showback, self-scoped dashboards, retention description and support boundary. Rechecked 2026-10-19. |
| S3 | [RHOAI 3.5 Developer Preview notes](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/developer-preview-features_relnotes) | IPP external metering and separate BBR credit/webhook feature descriptions. Do not merge their contracts or infer an image/install recipe. Rechecked 2026-10-19. |
| S4 | [RHOAI observability](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/managing_openshift_ai/managing-observability_managing-rhoai), [MLflow experiments/traces](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_with_mlflow/track-and-compare-mlflow-experiments_mlflow) | Native operational views and instrumented application evidence. No automatic outcomes or complete billing from sampled traces. |
| S5 | [MaaS downstream source at `563117f`](https://github.com/red-hat-data-services/models-as-a-service/tree/563117f178f04c8eac7058df481815a97694a88d), [retained artifact evidence](native/evidence/artifacts.json) | Installed 3.5.1 Config/tenant schema, usage-log pipeline, identity proxy and ConfigMap preservation. File-level source routes are in `native/provenance.json`. |
| S6 | [IPP downstream source at `a98a265`](https://github.com/red-hat-data-services/ai-gateway-payload-processing/tree/a98a2650e74f8b832ff75206f795cbb62b9cd688), [installed-source metering example](https://github.com/red-hat-data-services/ai-gateway-payload-processing/blob/a98a2650e74f8b832ff75206f795cbb62b9cd688/deploy/examples/external-metering/README.md), [framework pin](https://github.com/llm-d/llm-d-inference-payload-processor/tree/a8bbe6a6a75a9435cbf8d0703613cf5ac9875f90) | Shipped plugin, exact wire/configuration contracts, ordering and backend reference. Source coverage does not prove live delivery. |
| S7 | [Loki Operator 6.6 installation](https://docs.redhat.com/en/documentation/red_hat_openshift_logging/6.6/html/install/install-the-loki-operator), [OTLP](https://docs.redhat.com/en/documentation/red_hat_openshift_logging/6.6/html/configure/configure-lokistack-otlp), [storage](https://docs.redhat.com/en/documentation/red_hat_openshift_logging/6.6/html/install/prepare-object-storage-for-lokistack), [image-bound source](https://github.com/openshift/loki/tree/678e5e8f46311c6dd591e105117f4616a0cc82b1) | Candidate operator/schema, storage and tenancy. Candidate not installed; no availability/capacity proof. |
| S8 | [Noyitz pinned source](https://github.com/noyitz/ai-gateway-metering-service/tree/f9a56b1769b0933e3fe7454a174b1f42a229f07a), [PriceTag source/history](https://github.com/redhat-et/pricetag-metering/blob/586356a1844d2e18dee602068bf43512fd3b49c6/SOURCE-MAP.md), [backend decision](native/backend-decision.json) | Intended development backend and image-build route; alternative investigation. Neither is a verified Red Hat operand. Registry authorization failures mean unverified access, not proof of absence. |
| S9 | [AWS Ohio EC2 public price list](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/us-east-2/index.csv), [saved selected rows](showback-aws-pricing-2026-10-15.json) | Dated On-Demand compute estimate. Saved SKU/rate provenance is reproducible; the current URL can change and is not account billing evidence. |
| S10 | [AWS G7e specifications](https://aws.amazon.com/ec2/instance-types/g7e/) | GPU and host-size comparison; identical GPU count can accompany larger host RAM. |
| S11 | [AWS On-Demand billing](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-on-demand-instances.html), [additional charges](https://aws.amazon.com/ec2/pricing/on-demand/) | Paid lifecycle/cost-scope framing. Actual agreements and invoice adjustments still require account evidence. |
| S12 | [Pinned Mistral model card](https://huggingface.co/RedHatAI/Mistral-Small-4-119B-2603-NVFP4/blob/a7b11eb3bdf01f38077f6704e96cc1d9b83a4cfc/README.md), [model support matrix](https://docs.redhat.com/en/documentation/red_hat_ai/3/html/validated_models/model-support-matrix_validated-models) | Checkpoint/quantization and qualification research. General model validation is not proof of this checkpoint/runtime/RTX combination. Detailed loader/MLA research and fallback references remain in PLAN.md R2–R6. |
| S13 | [Token provider article, 2026-09-10](https://developers.redhat.com/articles/2026/09/10/from-token-consumer-to-token-provider-building-your-orgs-ai-api) | Governed organizational API and shared-service narrative. No prescribed 70/30 GPU or financial reservation. Rechecked 2026-10-19. |
| S14 | [AI cost article, 2026-09-18](https://developers.redhat.com/articles/2026/09/18/what-did-ai-cost-you-this-quarter), [demo-chargeback reviewed revision](https://github.com/suhasvkashyap/demo-chargeback/tree/959b6829c3d71fa2c8dc8ad041ba4dac812e0ac6) | Workload/showback inspiration and configured input/output tariff example. Sample bill, prices, models and simplified attribution are not our evidence. Article rechecked 2026-10-19. |
| S15 | [Connectivity Link 1.4 guide](https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/deploying_red_hat_connectivity_link/index) | Token admission/completion timing; overshoot from already admitted work is an inference to test, not a strict spend ceiling. |
| S16 | [FinOps unit economics](https://www.finops.org/framework/capabilities/unit-economics/), [local analysis](analysis/analyze.sh) | Business-outcome cost framing. Accepted-task definitions, formulas and idle rules are local agreements. |
| S17 | [Original backend evidence](native/evidence/noyitz-local-20261018/README.md), [corrected evidence](native/evidence/noyitz-local-20261019/README.md), [offline validator](validate.sh) | Synthetic/offline/local behavior, with explicit artifact bindings. No live billing, provider or quarter-history claim. |

The two articles inspired the story. They did not supply our complete hosting-bill allocation, idle ownership, exact-cent conservation or service agreements. We retained the organization's existing Perses/Prometheus stack and wrote shell tooling to comply with project rules rather than adopting the companion project's Python generator.

## 9. Remaining implementation plan

### Phase A — review and freeze bounded scopes; remain offline

**Actions:** read repository rules and relevant MaaS/observability/storage skills; inventory the full working tree; preserve unrelated changes; verify both evidence checksum manifests and patch/image bindings. Run the package's offline validator. Freeze scenario, policy and model profile identities for future runs. Record outstanding decisions in the plan rather than substituting fixture data.

**Decisions required before dependent work:** final reporting period and cost scope; effective rate/invoice source; qualified model runtime/checkpoint; calibrated quotas; external fee/retry/commitment owners; dedicated reimbursement versus quote and SLO; shared forecast/weight/subsidy/reservation policy; approved backend registry/deployment choice; persistence/retention owners and consumer access audience.

**Exit evidence:** offline tests pass, generated artifacts match, optional GitOps source remains unactivated, runtime candidates remain stopped, and a reviewed list of live changes is ready. No live dependency should cause an offline check to start infrastructure.

### Phase B — review the dedicated optional GitOps component; remain stopped

Development source, generators, tests and evidence stay in `showback-demo`. Canonical demo resources are concentrated in `gitops/stages/040-governed-models-as-a-service/040-showback-demo/`, with one optional manual-sync Application. Its root includes core resources, nested financial `service-views/` and inert `native-inputs/`; nested `model-drafts/mistral/` remains excluded. Existing platform owners retain shared fields and resources:

| Change | Owner / integration boundary |
|---|---|
| Demo subscriptions, authorization, financial dashboards, stopped publisher and workspace grant | `040-showback-demo` component root and nested `service-views/`; reuse existing datasource/MLflow infrastructure |
| Mistral serving/model reference | Nested excluded `040-showback-demo/model-drafts/mistral/`; inclusion requires separate runtime/ownership review |
| Qwen FP8 alignment | Existing `040-local-models` owner; local `model-drafts/qwen-fp8/` is a review input, not a second owner |
| GPU host-size, placement or queue change if needed | Existing Stage 020 infrastructure/profile owners; no duplicate MachineSet/queue ownership |
| Native MaaS pipeline enablement and existing IPP profile customization | Existing `040-maas-platform` owner, preserving controller customization semantics |
| Native Loki/store and metering database/service | Not deployed or included as workloads. Later demo-owned resources belong in this component after artifact/storage qualification and an ownership check |

`deploy.sh --component 040-showback-demo` uses the normal guard, published-source selection, adoption preflight, apply/sync/wait flow. Its read-only prerequisites check namespaces, APIs and the native `edit` role’s aggregated MLflow experiment read/write permissions. It starts no GPU or report publisher and provisions no identity or key. Default stage deployment remains eight ordered Applications. Broad status skips an absent optional app as `SKIP 040-showback-demo (not activated)`; a present app must pass strict source, immutable revision, sync and health checks and retain manual sync. Explicit component validation requires presence and checks its own immutable revision; `RHOAI_STAGE040_SHOWBACK_EXPECTED_REVISION` additionally requires the supplied SHA. Deployment supplies its selected SHA automatically. The enabled Qwen-only Component removes active Mistral access dependencies; no degraded-health exception is granted.

Do not patch generated Kuadrant output policies or duplicate Stage 010 dashboard configuration ownership. Shared-field changes need explicit delegation or their existing owner's reviewed update; they are not copied into this component. Keep one complete Stage 040 deploy/validate entrypoint and task helpers in this package. Source publication and live activation remain separate steps requiring review.

Keep the initial bounded bill compute-only. If the agreed scope expands, implement and test the optional overhead extension before collecting that report; do not pass the monthly service-offer schema into `allocate.sh` or silently append a second cost formula in dashboards.

**Exit evidence:** rendered desired state, explicit resource ownership/order, disabled runtime activation, rollback diff and a concrete bounded qualification proposal with maximum GPU hours/provider spend. At this point obtain the required deployment/execution authorization. All following phases describe future work after that authorization; it has not been granted by this handoff.

### Phase C — refresh actual environment and qualify model capacity

1. Use `load_env` and `check_oc_logged_in` from `scripts/lib.sh`, with the expected API server. Record current versions/images, relevant resource UIDs, replica delegation, active policies, operator ownership, storage and other consumers. Stop if the target cannot be verified.
2. Confirm the retained schemas/source bindings still match the installed release. Re-review drift rather than applying a 3.5.1 profile to an unknown build.
3. Qualify Mistral on one RTX GPU with the reviewed bounded profile: start with 16K context, four sequences, text-only, no speculative decoding. Prove first decode, JSON/SSE, near-context-bound requests, cold load twice and operational memory headroom. Measure host RAM, GPU/workspace/cache memory, storage and latency/throughput.
4. Qualify the selected Qwen FP8 build independently, then prove both models can serve concurrently on separate workers. Validate combined queue CPU/RAM/GPU requirements and serving-helper overhead.
5. If host RAM is the specific blocker, review `g7e.4xlarge` for Mistral with explicit placement and profile/queue updates. A larger host does not fix unsupported NVFP4 MoE/MLA kernels. Do not silently switch model, runtime, instance size or GPU count.

**Exit evidence:** exact checkpoint/runtime/image/GPU profile, positive functional receipts, no OOM/eviction, workload/SLO envelope and actual paid preparation intervals. Failed qualification remains a named blocker; preserve evidence and return capacity to its approved stopped state.

### Phase D — activate identity/access and qualify canonical usage

1. Create/confirm demo users through the existing identity workflow; render and integrate the three subscription/auth-policy pairs without altering existing consumers.
2. Mint separate private user-owned keys explicitly selecting `team-engineering`, `team-marketing` and `team-support`. Verify server-side owner/subscription metadata.
3. Prove four positive model paths, two explicit authorization denials and unauthenticated denial. A 401, 404 or 429 is not proof of the expected forbidden-model 403; universal denial does not pass.
4. Prime only allowed combinations outside the measured run. Inspect actual raw counter labels/resources; fill a private `metering.json` with one canonical `limitador_namespace` per subscription/model. Include all observed background consumers.
5. For isolated requests, prove an exact positive token delta against completed response usage after leading/trailing scrapes. Do not mask missed requests with tolerance or overlapping counters. Only then use the existing proposed 1% aggregate tolerance for a longer run, with boundary explanations.
6. Calibrate normal load below quota and a separate bounded quota probe that demonstrably receives 429. Verify JSON/SSE, failed/aborted completion and the behavior of admitted in-flight requests.

**Exit evidence:** genuine identity/access matrix, verified canonical mapping and complete isolated usage receipts. No invented team attribution from client labels alone.

### Phase E — qualify native Loki showback

1. Review/install the compatible Loki Operator only if absent; provision the owned object store, Secret/CA and LokiStack using the inspected schema. Verify endpoint, tenancy, persistence, capacity and retention.
2. Snapshot the existing MaaS Config and relevant ownership. Enable usage logging through the existing controller interface; do not hand-create a second copy of its pipeline.
3. Send bounded approved requests and inspect structured metadata, model/subscription/user identity, failed/missing usage, latency and route coverage. Verify the collector delivers to the expected tenant.
4. Test self-only views with at least two genuine users, tampered filters/direct datasource requests, and the separate admin fleet view. Verify the native interface before claiming isolation.
5. Document observed export/query shape and retention behavior. Keep this operational path separate from the durable financial capture path; do not build a money parser on default-zero log values.

**Exit evidence:** functioning native log pipeline and rendered self/admin views with negative access tests. If export/completeness is not qualified, retain that limit even when dashboards look correct.

### Phase F — publish and qualify the corrected metering backend

1. Select an approved registry and deployment artifact explicitly. Transfer the verified corrected OCI content or rebuild from the pinned source/patch/recipe; record remote digest, architecture, source and patch labels. Do not deploy `latest`, the original unpatched image or a local config ID as a registry digest.
2. Prepare a separate persistent PostgreSQL 16 service using an approved compatible image; inspect migrations against an empty test database first. Back up existing ledgers before any upgrade. Refuse duplicate legacy event keys rather than deleting history.
3. Configure the backend Service, persistent storage, credentials and minimal access appropriate to the demo. The installed IPP cannot send a configurable bearer header; choose a compatible private endpoint/access arrangement and validate it rather than inventing an auth field.
4. Review probes: primary-database checks are appropriate dependency readiness signals; choose liveness independently to avoid restart storms during a database outage. Qualify OpenShift UID/SCC and volume permissions.
5. Set an intentional entitlement/quota/pricing policy. The local `MONTHLY_TOKEN_QUOTA=1000` was a test value, not a deployment default. Fallback prices and cache math must not become financial authority.
6. Repeat replay/conflict, restart/persistence, missing/zero usage and database outage/recovery cases in an isolated cluster test scope before connecting real gateway traffic. Retain the exact image/database evidence.

**Exit evidence:** approved digest, owned persistent database, tested service endpoint and reviewed quota/failure policy. No claim of full financial correctness from backend dashboard totals.

### Phase G — connect IPP and close the capture/export gap

1. Save the existing entire plugin ConfigMap and deployment revision. Construct the source-correct candidate from current content, preserving the header guard, provider resolution, translation/key injection and pre-processing profile. Confirm its reconciliation annotation before editing.
2. Replace the invalid URL only with the qualified service endpoint; review `failOpen` and quota behavior explicitly. Activate by the supported persistent profile edit and controlled reload. Scope probes so existing consumers and provider routes are not inadvertently reconfigured.
3. Prove JSON and SSE each emit one correct logical usage event; verify final usage, stream completion, cache/reasoning categories, trusted identity, access denials and no caller-spoofed ownership. Exercise explicit balance denial, backend timeout/down, producer delivery failure and concurrent admission.
4. Implement a **bounded, durable raw-event export** into the importer's saved-JSONL/capture contract. Preserve source/ID, semantic original payload, completeness, timestamps, schema/source binding and export cursor/bounds; test pagination, restart, repeated export and corrections. Keep native error events and resolve their current importer quarantine through a reviewed coverage rule. A raw table's numeric rollup alone is insufficient.
5. Supply independent completeness evidence: expected requests/final responses, streaming completion and provider usage/invoice reconciliation as applicable. Detect missing events and upstream zero-substitution. Mark incomplete intervals unresolved. The backend has no validated producer retry queue; do not claim lost events were recovered without proof.
6. Run `native/import-events.sh` over saved snapshots, then `offers/service-report.sh`. Compare native known subtotals with the shell result; explain category/pricing/audit-count differences. Keep unresolved or missing prices out of full totals.

**Exit evidence:** export/import reproducibility, correctly attributed events, observed failure/recovery behavior and a documented completeness decision. If durable producer loss recovery needs an additional component, propose that scope with evidence; do not silently build a new billing platform.

### Phase H — implement the three offers and dashboards end to end

1. Finalize actual agreements and non-synthetic monthly inputs. Keep external rates effective-dated and provider categories disjoint. Obtain dedicated capacity ownership/full-cost evidence and shared forecasts/weights/approved tariffs.
2. For a dedicated live demonstration, use a separately evidenced exclusive capacity interval or a later explicitly reconfigured reservation. Do not simultaneously charge the same two shared workers again as dedicated capacity. No third model/GPU or dedicated live workload is provisioned by the current fixtures.
3. Generate monthly JSON/CSV statements and scoped user/team exports. Test missing categories/rates, zero-use dedicated months, shared shortfall, reservation credits, platform retries, invoice differences and correction chains.
4. Supply one reviewed report to the stopped publisher, then activate it within the approved scope. Qualify HTTP readiness, ServiceMonitor scraping, datasource access and all Perses renderers. Compare panel values against the report, including unknowns and period labels.
5. Demonstrate the three bounded views and five monthly platform candidates. Switch the selected report deliberately; verify stale or unavailable publisher data is not presented as a current complete report. Prove authenticated consumer/team delivery before exposing those statements beyond the operator.
6. Instrument task/attempt/outcome evidence for quality/sourcing analysis if that claim is included. Require matched quality/SLO evidence before advising external-to-private migration; otherwise label this view as a synthetic analytical example.

**Exit evidence:** each offer has a traceable statement and correct idle/recovery treatment; dashboards match their authoritative reports; user/team disclosure is authorized. A fixture demonstration remains visibly synthetic until real evidence supports it.

### Phase I — close, retain and rehearse

1. Freeze the scenario and run the twelve-minute busy/quiet/idle test with actual instance intervals and trailing scrapes. Drain requests before idle. Background/in-flight activity invalidates the idle assertion; do not move phase boundaries to hide it.
2. Close allocations, verify exact conservation and retain excluded/preparation costs separately. Run the quota probe separately. Explain why allowances, token shares, utilization and bill allocation are different quantities.
3. Archive all source snapshots, rates, mappings, receipts, report/CSV, hashes, policy/model/runtime versions and corrections. Qualify MLflow workspace authorization and proxied upload, then fresh-process download/replay.
4. Establish enforceable **at least 400-day** financial evidence retention, storage ownership/capacity and recovery checks. The monthly index already detects gaps/overlap and selects corrections; unattended close/export and bounded hourly revision indexing still need implementation before continuous-quarter claims.
5. Verify the presenter account can open intended views. Capture dated fallback screenshots and reports. Show a measured bounded run and label any quarterly projection separately. Do not fabricate three months of history from a short load run.
6. Stop owned load, close streams/evidence, revoke only relevant demo keys and restore reviewed model/worker states. Record residual persistent-storage cost. Leave unrelated resources and consumers intact.

**Exit evidence:** a rehearsable live demonstration, an independently replayable evidence bundle, an explicit list of remaining limits, and verified cleanup. Production financial completeness is a separate claim from demo acceptance.

## 10. Validation matrix and implementation-agent completion criteria

| Area | Required positive and negative checks | Retained result |
|---|---|---|
| Source integrity | Complete handoff, evidence checksums, generated-file parity, no secret inputs committed | Reviewed revision/patch and validation output |
| Stopped state | Detached candidates, zero serving/publisher replicas, no implicit load/scheduler or active hook | Rendered manifests and ownership review; later actual UID/replica observations |
| Model capacity | Cold loads, first decode, JSON/SSE, concurrent/near-cap requests; no OOM or unsupported kernel workaround | Runtime/checkpoint/profile and measured capacity/SLO evidence |
| Access | Four allowed paths; two 403 forbidden-model paths; unauthenticated/revoked-key denial | Genuine persona receipts and effective policy evidence |
| Usage | Exact isolated delta; ambiguous/missing/reset/boundary cases remain incomplete | Canonical series mapping, snapshots and reconciled receipts |
| Idle/allocation | Positive-use full allocation; sole consumer; proven zero-use platform bucket; unknown bucket; background consumers | Exact-cent report and replay parity |
| Loki | Correct structured identity/usage, route coverage, self/admin rendering and cross-user denial | Source/version-bound native observations |
| Metering | Same source/ID replay, conflict, different source, restart, missing/zero/error usage, DB outage, producer loss | Raw event/SQL/API evidence and completeness findings |
| Offers | Provider effective prices/categories/invoice; dedicated idle ownership; shared revenue/cost variance; credits/corrections | Non-synthetic agreement-bound statements, or explicit synthetic status |
| Financial views | Panel/report parity, fixed report period, missing values, stale/unavailable publisher and unauthorized access | Presenter and consumer-role evidence |
| Retention | Full snapshot archive, fresh download/hash/replay, correction chain and missing-month detection | Durable bundle/index plus retention/recovery evidence |
| Cleanup | Owned traffic stopped, selected profiles restored as needed, approved replicas/instances stopped, data retained | Before/after owned-resource inventory and residual-cost note |

Safe local starting command from the repository root:

```bash
./stages/040-governed-models-as-a-service/showback-demo/validate.sh
```

It blocks real transports and uses synthetic inputs. It does not run the disposable backend runtime probe, start a VM, contact OpenShift or qualify live behavior. For exact offline render/import/report/archive commands and later authorized execution flags, use [OPERATIONS.md](OPERATIONS.md); do not invent a new all-in-one deployment command.

The implementation agent should deliver the smallest reviewable change set for each phase, with **what changed, source/contract used, tests, observed evidence, unresolved risks and rollback**. Human review remains required under repository policy. Do not mark a gate complete because a resource is Ready, a schema rendered, a URL returned 200 or a synthetic fixture balanced.

## 11. Rollback and preservation

Before activation, capture owned resource identities, original profile/configuration and relevant delegated replica state. Git `replicas: 0` does not necessarily overwrite a live field ignored by Argo CD; validate actual ownership and stopped state.

If metering must be disconnected, stop new test admissions, preserve/export evidence, restore the exact reviewed prior IPP profile and reload it **before** stopping its backend. Keep existing guard/routing/credential plugins and pre-processing data. Restoring the opt-out annotation incorrectly can cause controller default replacement; follow the source-backed reset procedure only when that is intended.

Disabling `usageLogging` removes its controller-owned pipeline, not the independent LokiStack/store. Preserve logs and storage deliberately; do not delete the bucket or database as an incidental rollback. Keep the corrected ledger schema and uniqueness constraint. Rolling an existing ledger back to the unpatched writer is unsafe; use a reviewed database-compatible recovery plan or stop ingestion while preserving data.

For model/publisher rollback, reverse only the approved demo integration and restore the recorded states. Do not broadly sync the entire stage or park every GPU pool as a shortcut. Quiesce only owned traffic and preserve other consumers. Confirm AWS lifecycle state rather than assuming a stopped client stops the bill.

**Completion boundary:** source, offline financial workflows and the corrected local backend are prepared. Live model qualification, native pipeline activation, reliable capture/export, service agreements, authenticated financial views, durable history and rehearsal remain implementation work. This handoff keeps those steps reviewable without starting the environment.
