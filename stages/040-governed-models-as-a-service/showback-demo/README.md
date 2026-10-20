# Three-team showback and MaaS service offers

This package answers "What did AI cost us?" for a shared private AI platform. Governed team identities in MaaS supply the usage, dated infrastructure rates supply the cost, and an explicit allocation policy turns them into a bill that reconciles to the cent. A second workflow prices three monthly service offers: external models, dedicated private models and shared private models.

The canonical cluster resources are the optional, manual-sync [040-showback-demo component](../../../gitops/stages/040-governed-models-as-a-service/040-showback-demo/README.md). This folder holds the generators, accounting tools, tests and operator scripts. Commands are in [OPERATIONS.md](OPERATIONS.md).

## Scenario

"Three departments. Two shared models. One bill."

| Team | Workload | Model access | Status |
|---|---|---|---|
| Engineering | Code reviews | Qwen 3.8 27B | Live |
| Support | Customer questions | Qwen 3.8 27B and Mistral Small 4 119B | Qwen live; Mistral planned |
| Marketing | Campaign creation | Mistral Small 4 119B | Planned |

Each model runs on its own AWS `g7e.2xlarge` worker with one NVIDIA RTX PRO 6000. The cost basis is the saved public on-demand price of **$3.36312 per worker-hour** in us-east-2 ([source](showback-aws-pricing-2026-10-15.json)). It is a compute estimate: shared platform, storage, networking, licences and discounts are out of scope, and it is not an AWS invoice.

One user and one MaaS subscription represent each team. Subscriptions carry token allowances (Qwen 700,000 tokens/hour for Engineering, 300,000 for Support); allowances limit consumption, they do not reserve GPU capacity or set the cost split.

## Allocation policy

For each model and time window, the full measured running cost is split by the teams' actual governed token shares. Two buckets keep the bill honest:

- **Platform — idle capacity:** a window with complete evidence and no usage.
- **Unresolved allocation:** a window whose usage evidence is incomplete.

Other consumers of the same model stay visible as their own line. Input and output tokens count equally in this first policy, and GPU utilization explains efficiency rather than ownership. The allocator works in exact integer arithmetic and the report reconciles to the cent.

## Service offers

The monthly workflow keeps actual cost, allocated cost and consumer charge separate.

| Offer | Consumer charge | Who carries idle capacity |
|---|---|---|
| External provider | Provider input/output/cache rates, plus any disclosed platform fee | No local idle; unused provider commitments stay with their purchaser |
| Dedicated private | Full capacity and operations cost, or a fixed quote with visible variance | The sponsoring team, including zero-use months |
| Shared private | Prospective per-token tariffs from a demand forecast, with optional reservation fees and included credits | Forecast idle is priced in; an unexpected shortfall stays with the platform |

`offers/service-report.sh` produces versioned monthly JSON/CSV statements. Corrections replace an earlier statement through a hash-linked revision. Real tariffs and monthly inputs are not set yet; `offers/month.example.json` is an unpriced template and the fixtures are synthetic.

## What runs today

**Qwen showback (2 teams, 1 model).** A bounded 6-minute busy/quiet/idle run on 2026-10-19 used genuine Engineering and Support keys against the existing Qwen 3.8 NVFP4 model:

| | Tokens | Allocated cost |
|---|---|---|
| Engineering | 653 | $0.15 |
| Support | 1,100 | $0.07 |
| Platform — idle | 0 | $0.12 |
| **Total** | **1,753** | **$0.34** |

Engineering pays more than Support despite fewer tokens because it alone used the quiet window. The report is served by a small Apache publisher and archived in MLflow (`showback-reporting` workspace).

**Dashboards** in the RHOAI Observability page, all generated from this folder:

| Group | Dashboards | Data |
|---|---|---|
| Bounded showback | Costs, Usage, Efficiency | The selected allocation report plus live serving metrics |
| Offer comparison | External model, Dedicated private, Shared private | Continuous external capture, the Qwen allocation and explicit Unknown values for missing monthly inputs |
| Service views | Statements, Dedicated, Shared, Completeness, Quality | Monthly service-offer report; platform-only candidates |

**Continuous external metering.** The MaaS gateway's `external-metering-streaming` plugin sends each external-model response to a metering backend (a patched community Noyitz service) with a PostgreSQL ledger. Each event keeps its user, subscription, model and a frozen estimate from the versioned [provider price catalog](native/provider-pricing.json). The External dashboard shows current-month tokens and conditional list-price estimates. It is deployed but has not yet been checked against real requests; see [OPERATIONS.md](OPERATIONS.md#continuous-external-metering).

## Package contents

| Source | Purpose |
|---|---|
| `scenario.json`, `render-access.sh` | Full three-team scenario and generated subscription/auth-policy pairs |
| `qualification-qwen-only.json` | Bounded Engineering/Support Qwen profile used for the live run |
| `qualify-qwen-identities.sh`, `qualify-qwen-metering.sh` | Create the demo users and their keys; prove exact per-team token attribution |
| `run-workload.sh` | Bounded busy/quiet/idle workload, access probe and quota probe (preview by default) |
| `collect-usage.sh`, `metering.json` | Capture native usage counters and reconcile them with request receipts |
| `costs.json`, `instance-intervals.example.json` | Dated rates and the required instance running intervals |
| `allocate.sh` | Deterministic cost allocation with JSON and CSV output |
| `publish-report.sh`, `generate-dashboards.sh` | Report metrics for the publisher; Perses dashboards from `dashboard-definitions.json` and `offer-dashboard-definitions.json` |
| `external-probe.sh`, `render-external-probe.sh` | Bounded external-model probe and its report metrics |
| `archive.sh`, `archive-index.sh` | Hashed evidence bundles, MLflow upload and monthly continuity checks |
| `offers/` | Monthly accounting for the three offers |
| `service-views/` | Five service-view dashboards and scoped user/team statements |
| `analysis/` | Cost per accepted task and external-versus-private sourcing advice |
| `native/` | Provider price catalog, metering backend patches and build scripts, captured-event importer |
| `model-drafts/qwen-fp8/` | Stopped Qwen FP8 component for the existing model owner |
| `fixtures/`, `tests/`, `validate.sh` | Synthetic inputs and offline tests |

Operator tools are Bash with `jq`, `curl`, Ruby (YAML conversion), `shasum` and Kustomize. `./validate.sh` runs every offline test; it starts nothing and contacts no cluster.

## Limits

- Marketing, Mistral and Qwen FP8 are not live; the Mistral model draft is excluded from the component render.
- No quota-exhaustion test has run.
- External metering is best effort: the gateway plugin has no retry queue, and events without usage may be lost. Estimates are list prices, not invoices.
- Monthly offers use synthetic fixtures until real tariffs and inputs are supplied.
- MLflow archives request 400-day retention but do not enforce it.

The dated qualification records, the former implementation plan and the agent handoff were removed from the working tree on 2026-10-20; they remain in Git history at `ea5ad451`.
