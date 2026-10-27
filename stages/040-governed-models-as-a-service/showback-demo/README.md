# Showback demo: three teams, three service offerings

This demo answers "What did AI cost us?" on a governed MaaS platform. Three teams consume AI through three service offerings, each priced differently, and three live dashboards show usage and cost as load runs.

| Team | Offering | Model | How it is priced |
|---|---|---|---|
| Engineering | Shared private | Qwen 3.8 27B on a platform-owned RTX PRO 6000 worker | Committed tariff for 150M tokens a month, on demand above it; the platform carries idle capacity |
| Support | Shared private and External | Qwen 3.8 27B; GPT-6 Luna, Claude Sonnet 5.5, Nemotron | Tariff for Qwen; provider list price per token for external models |
| Marketing | Dedicated private | Mistral Small 4 119B on its own RTX PRO 6000 worker | Full running cost of the worker, busy or idle |

The cluster resources are the optional [040-showback-demo component](../../../gitops/stages/040-governed-models-as-a-service/040-showback-demo/README.md): Engineering, Support and Marketing subscriptions and policies, Marketing's dedicated Mistral model (stopped in Git), the three dashboards and the external metering service. Mistral is served on its own Gateway listener (`mistral-small4-maas.<cluster-domain>`), not the shared MaaS endpoint, because on RHOAI 3.5.2 a second local model on the shared listener breaks Qwen calls ([Troubleshooting](../../../docs/TROUBLESHOOTING.md#qwen-calls-through-maas-hang-then-return-503)); `team-keys.sh` records both endpoints and `generate-load.sh --offer dedicated` uses Mistral's.

## Dashboards

Open **Observe & monitor → Dashboard** in the OpenShift AI console. Each Offer tab has a collapsed **How this offering is priced** section, then Overview, Trends and Breakdown. Panels query the RHOAI monitoring datasource live; the time range picker sets the billing period, and the Model and Subscription filters narrow the view.

| Tab | Shows |
|---|---|
| **Offer · Shared private** | Monthly running cost, committed revenue floor, cost coverage, and the monthly platform balance with commitments and if every team paid on demand; token rate by consumer; per subscription: tokens, commitment, projected use, commitment used and monthly charge |
| **Offer · Dedicated private** | Sponsor charges, paid idle, effective cost per million tokens and projected monthly charge; GPU utilisation; charges per dedicated model and sponsor |
| **Offer · External model** | Month-to-date provider spend, requests and projected monthly spend; spend by subscription over the month; statement by subscription and model; the provider price list (collapsed) |

Each Offer dashboard also projects the selected time range to a month: **Usage hours / month** (default 168, 8 hours x 21 working days) and **Users per team** (default 1, each demo team is one synthetic user) scale the observed usage, and **GPU hours / month** (default 730, always on; 168 for working hours only) sets the private worker schedule. Projected values show the monthly charge per consumer and sponsor, the platform's monthly balance and the monthly external spend.

**Tokenomics · break-even** answers when an external workload should move to a private model. Pick the external model a team uses and its subscriptions, and a private candidate; the dashboard shows the projected monthly tokens and external cost, the private cost (GPU workers sized from the candidate's demonstrated capacity), the break-even volume of one worker and the monthly savings if moved. In the demo run, Support's Claude workload is about 3% of break-even with one user; raising **Users per team**, or scheduling the GPU for working hours only, shows where moving to private pays off.

The dashboards name no model. The **offer catalog** (`offer-catalog.yaml` in the component, a PrometheusRule evaluated by the RHOAI Prometheus) records which private models are shared or dedicated, the sponsoring subscription of each dedicated model, the demonstrated capacity of one worker, the GPU worker price ($3.36312 per hour, AWS `g7e.2xlarge` on-demand in us-east-2, saved 2026-10-15) the shared tariffs ($4.00 per million tokens on demand, $3.00 committed) and each team’s shared commitment (Engineering 150M, Support 30M tokens a month). A committed team pays its commitment whether used or not and on-demand above it; its MaaS token-rate limit is sized to use it in working hours (Engineering 1M tokens/hour), which `validate.sh` checks. To onboard another model or change a price, edit the catalog and redeploy the component. Running cost counts the minutes a model is serving; node start-up and model loading are not included. Every period is priced with the catalog values in force at the end of the selected time range.

## Run the demo

Run the commands from the repository root after the usual cluster login. Each step is safe to repeat.

1. **Deploy the component** (once per revision):

   ```bash
   ./stages/040-governed-models-as-a-service/deploy.sh --component 040-showback-demo --revision <full-sha>
   ```

2. **Start the models you need.** Shared needs Qwen, External needs neither. Dedicated needs Mistral on a second GPU worker (the last command).

   ```bash
   stages/020-gpu-infrastructure-private-ai/deploy.sh --gpus 2
   oc patch llminferenceservice qwen3-8-27b -n internal-models --type=merge -p '{"spec":{"replicas":1}}'
   oc patch llminferenceservice mistral-small4-119b -n internal-models --type=merge -p '{"spec":{"replicas":1}}'
   ```

3. **Mint team keys.** `team-keys.sh` creates the `showback-engineering`, `showback-marketing` and `showback-support` users in the `sso` realm if they are missing, signs each in through OpenShift and mints that user's own MaaS key on its team subscription. Passwords and keys are kept in `~/.config/rhoai3-showback` (override with `SHOWBACK_STATE_DIR`).

   ```bash
   stages/040-governed-models-as-a-service/showback-demo/team-keys.sh --hours 8 --insecure
   ```

4. **Generate load.** One command runs the whole demo, every team at its own pace; or run one offering at a time:

   ```bash
   stages/040-governed-models-as-a-service/showback-demo/generate-load.sh --offer all --minutes 15 --insecure
   stages/040-governed-models-as-a-service/showback-demo/generate-load.sh --offer shared --minutes 10 --insecure
   stages/040-governed-models-as-a-service/showback-demo/generate-load.sh --offer dedicated --minutes 10 --insecure
   stages/040-governed-models-as-a-service/showback-demo/generate-load.sh --offer external --model claude-sonnet-5-5 --minutes 30 --concurrency 1 --insecure
   ```

   The teams work on the Coolstore application with the tasks in [`prompts.json`](prompts.json). Each team has a system
   prompt with the facts a finished answer needs (Support: Coolstore's return, refund and password policy; Marketing:
   every brief names product, date, link and length), so the quality judges grade the model, not a missing brief.

   | Team | Work | Shape |
   |---|---|---|
   | Engineering | Code reviews with real code, and agent tasks: the model gets `read_file` and `run_tests` tools, which the script plays from `prompts.json` | One trace per task; an agent task is `AGENT > CHAT_MODEL > TOOL > TOOL > CHAT_MODEL` (the Tool calls tab) |
   | Support | Customer cases grounded in the stated policy; most continue as a conversation with one or two customer replies | One trace per turn, the turns of a conversation in one MLflow session (the Sessions tab) |
   | Marketing | Campaign briefs; some with a revision round | Same as Support |

   `--pause` sets the think time between requests for every team (fixed seconds or a range such as `5-30`); without
   it each team keeps its own pace (Engineering 2-6 s, Support 5-15 s, Marketing 10-30 s, also between the turns of a
   conversation). `--concurrency` (default 2 loops per team), `--max-tokens` (one answer cap for every team; by default
   Engineering 2048, since code answers are longer, and Support and Marketing 1024, so answers normally finish; an answer
   the cap cuts off is marked by the `finished` check) and `--team` (one team of the
   offering) shape the load; Support's Qwen allowance is 300K tokens per hour. `--model` picks the external model for
   Support (default `gpt-6-luna`; `nemotron-3-ultra-550b-a55b` is free). Each run prints turns, tokens and tool calls
   per team. External calls are billed by the provider.

5. **Stop the models** when the demo ends: set both replicas back to 0 and run `stages/020-gpu-infrastructure-private-ai/deploy.sh --gpus 0`.

## MLflow traces per request

`generate-load.sh` also writes every request to MLflow as one trace, and a nightly judge grades a sample of them, so
each model's use can be inspected request by request next to the aggregate dashboards. Open MLflow from the OpenShift
AI dashboard, pick the workspace **Models-as-a-Service** (`models-as-a-service`, the MaaS project; only `rhods-admins`
have access) and a model's experiment. There is one experiment per MaaS model, named after the namespace of its model
reference: `internal-qwen3-8-27b`, `internal-mistral-small4-119b`, `external-claude-sonnet-5-5`, `external-gpt-6-luna`,
`external-nemotron-3-ultra-550b-a55b`. Its tags record the offering (shared, dedicated or external) and the provider;
the offering is a tag, not part of the name, because it can change. Each experiment is a scorecard for that model:

| Overview tab | Shows | Team view |
|---|---|---|
| **Usage** | Token usage, tokens per trace, cost over time | Filter **User** = `showback-<team>` |
| **Quality** | Pass rates of the judges `relevance`, `completeness` and `team_guidelines` | Same filter |

The cross-model money comparison stays in Perses (**Offer** tabs, **Tokenomics · break-even**); MLflow adds the
request-level view and answer quality per model.

| Span | Content |
|---|---|
| `team-<team> request` (root, `CHAIN`, or `AGENT` when tools were used) | Trace tags `team`, `subscription`, `offering`, `source`, `finish_reason` (`stop`, or `length` when the max-tokens cap cut the answer off); trace user `showback-<team>`; the prompt and the answer |
| `chat <model>` (`CHAT_MODEL`, one per model call) and `tool <name>` (`TOOL`, one per tool call) | OpenTelemetry GenAI fields: model, provider (`openshift-ai` for private models), input and output tokens, messages, `gen_ai.response.finish_reasons`, HTTP status; cost |

- **Sessions:** the turns of a conversation carry one `session.id` (OpenTelemetry semantic convention), which
  MLflow stores as the trace session, so the experiment's **Sessions** tab shows each conversation turn by turn.
- **Cost:** shared private models at the on-demand tariff, a dedicated model at its worker price per token at
  demonstrated capacity (both from `offer-catalog.yaml`), external models at the list price of
  `metering/provider-pricing.json`. A per-request figure is an indication: the sponsor of a dedicated model pays the
  worker busy or idle, and committed tariffs are monthly; the Offer dashboards show those charges. MLflow does not look
  up a price by model name.
- **Path:** the script posts OTLP/HTTP JSON to the internal MLflow Service (`/v1/traces`, through a local port-forward)
  with the operator's token, the `X-MLFLOW-WORKSPACE` header and the experiment id, the same endpoint a platform trace
  collector would use. The scorer creates an experiment for every MaaS model reference and refreshes its
  offering and provider tags, so each model has its scorecard before its first request; the script creates a missing
  one on first use.
- **Fails open:** a failed export never stops the load; the summary prints `traced` and `trace_failed` per team.
  `--no-trace` skips tracing. Failed requests are traced as errors.
- **Quality:** the CronJob `maas-quality-scorer` (component folder `quality/`) is a nightly batch job, at 01:00 UTC,
  outside working hours. It grades every successful, unscored trace of the previous 25 hours (paged; at most 2000
  per experiment and run), asks a judge three true/false questions and logs the verdicts as MLflow feedback: `relevance`,
  `completeness` (every part of the request answered) and `team_guidelines` (the guideline of the trace's team). A
  fourth verdict, `finished`, is code, not a judge: it is false when the trace's `finish_reason` is `length`, the
  max-tokens cap cut the answer off. Each trace gets only the verdicts it does not have yet. The scorer also registers its LLM judges
  in each experiment (Judges page: name, instructions, judge model; never the endpoint or key), so the page shows what
  grades that experiment; `finished` is not listed there, since MLflow registers custom code scorers only on Databricks. They are display only: MLflow cannot run them itself on OpenShift AI 3.5, the batch job does. The Quality tab shows each
  scorer's average, the pass rate. The judges are the private models, reached through MaaS on their own subscription
  `maas-quality-judge`: Qwen grades every model except itself and Mistral grades Qwen, so no model grades its own
  answers and judging costs nothing at a provider. Both must be serving when the job runs; if either is stopped (GPUs
  scaled down), the run is skipped with a message. A run stops after 2.5 hours, and unscored traces wait for the next
  one. To score right after a demo load, start it by hand:
  `oc create job --from=cronjob/maas-quality-scorer maas-quality-scorer-now -n models-as-a-service`.
- **Scope:** only this load generator's requests are traced. Platform-side tracing of every MaaS client is planned work.

## External metering

The MaaS gateway's `external-metering-streaming` plugin (Developer Preview in RHOAI 3.5) posts one event per external-model response to a metering service in `redhat-ods-monitoring`: a patched build of the community Noyitz backend with a PostgreSQL ledger on a retained PVC. Each event keeps the user, subscription, model, token counts and a price estimate frozen from the versioned catalog `metering/provider-pricing.json`. The service exposes month-to-date gauges for the External dashboard.

- **Activation:** the targeted deployment writes the plugin into the MaaS-owned ConfigMap `openshift-ingress/payload-processing-plugins` when `metering/profile.yaml` has `enabled: 'true'`, and restarts `payload-processing` only when the profile changes. The plugin fails open, so a metering outage never blocks inference.
- **Prices:** add a new catalog version and new `price_version` values for any change; earlier events keep their estimates.
- **Disable:** set `enabled: 'false'`, publish and redeploy the component; keep the PVC. Reverting the Application alone does not remove the plugin.
- **After a cluster start** the backend restarts a few times until PostgreSQL is ready.
- **Limits:** one delivery attempt per event, and a response without usage may produce no event. Estimates are list prices, not invoices.
- **The metering image** is built in the cluster by the component's BuildConfig; see [metering build](../../../gitops/stages/040-governed-models-as-a-service/040-showback-demo/metering/build/README.md).

## Files

| File | Purpose |
|---|---|
| `team-keys.sh` | Team users and their MaaS keys |
| `generate-load.sh` | Demo load per offering or `all`, one MLflow trace per request turn |
| `prompts.json` | The teams' Coolstore tasks: system prompts, code reviews, agent tasks with tool fixtures, conversations |
| `validate.sh` | Offline checks: script syntax, access matrix, dashboards, metering bundle |
| `tests/test-metering-profile.sh` | Mocked test of the metering activation in the Stage 040 deploy script |

The earlier report pipeline (offline allocation, report publisher, MLflow archive, monthly statements and their dashboards) was retired on 2026-10-20 and is in Git history at `87aaf9c1`.
