# Showback demo: three teams, three service offerings

This demo answers "What did AI cost us?" on a governed MaaS platform. Three teams consume AI through three service offerings, each priced differently, and six live dashboards show what each team costs as load runs.

| Team | Offering | Model | How it is priced |
|---|---|---|---|
| Engineering | Shared private and External | Qwen 3.8 27B on a platform-owned RTX PRO 6000 worker; Claude Sonnet 5.5, GPT-6 Luna, Nemotron | Committed tariff for 1.625B tokens a month (625M developers, 1B CI overnight), on demand above it, the platform carries idle capacity; provider list price per token for external models |
| Support | Shared private | Qwen 3.8 27B | Committed tariff for 250M tokens a month, on demand above it |
| Marketing | Dedicated private | Mistral Small 4 119B on its own RTX PRO 6000 worker | Full running cost of the worker, busy or idle |

The cluster resources are the optional [040-showback-demo component](../../../gitops/stages/040-governed-models-as-a-service/040-showback-demo/README.md): Engineering, Support and Marketing subscriptions and policies, the showback dashboards and the external metering service. Marketing's dedicated model, Mistral Small 4 (`mistral-small4-119b`), is served and published to MaaS by [040-local-models](../../../gitops/stages/040-governed-models-as-a-service/040-local-models/README.md), next to Qwen. Mistral is served on its own Gateway listener (`mistral-small4-maas.<cluster-domain>`), not the shared MaaS endpoint, because on RHOAI 3.5.2 a second local model on the shared listener breaks Qwen calls ([Troubleshooting](../../../docs/TROUBLESHOOTING.md#qwen-calls-through-maas-hang-then-return-503)); `team-keys.sh` records both endpoints and `generate-load.sh --offer dedicated` uses Mistral's.

## Dashboards

Open **Observe & monitor → Dashboard** in the OpenShift AI console. The six **Showback** tabs are numbered in demo order. Each starts with a collapsed section that explains its pricing; panels query the RHOAI monitoring datasource live.

**Teams.** Every MaaS subscription belongs to the team of its owner, so a team's cost includes its tools, not only its demo subscription. **Platform** carries the platform's own services. The mapping is part of the offer catalog; a subscription without a team shows as *unassigned*, and `validate.sh` fails for any subscription in Git that has none.

| Team | Subscriptions |
|---|---|
| Engineering | `team-engineering`, `team-engineering-ci`, `devspaces-coding-models`, `personal-ai-developer`, `opencode-developer-qwen38`, `mta-migration-ai` |
| Support | `team-support`, `personal-ai-admin`, `hermes-private-qwen38`, `opencode-private-qwen38` |
| Marketing | `marketing-content`, `marketing-rag`, `marketing-campaigns` (one per use case) |
| Platform | `maas-quality-judge`, `openshift-lightspeed`, `model-qualification`, `quota-probe`, `playground-sandbox`, `personal-kube-admin` |

**Time.** Figures marked **in range** follow the time picker. Figures marked **/ month** are projections from the hours that had usage: tokens in the time range ÷ **Active hours** × **Usage hours / month** (default 168, 8 hours × 21 working days) × **Users per team** (default 1, usage as measured), or the pace of the whole range when that is higher, so a team that also runs overnight is not cut to 168 hours; a range of a week or more uses the pace of the range alone, because it holds real history, and private workers × **GPU hours / month** (default 730, always on; 168 for working hours only). Each table shows the active hours behind its projection, so a figure resting on one hour reads as thin. All tabs open on the last 24 hours. Subscriptions the catalog marks as test traffic (`model-qualification`) count as Platform usage only: they are left out of peak shares, fair-share bills and fleet savings. External spend stays, because a provider charges it. *Month to date* (External only) is the metering ledger's running total and ignores the time picker.

| Tab | Question | Shows |
|---|---|---|
| **Showback 1 · By team** | What does each team cost? | No filters: every team, at the default hours and users. An Overview that opens with a pie of the monthly cost by team next to the cost per team as stacked bars over time; then the platform's monthly balance across shared and dedicated workers (red when it carries a shortfall) beside each team's projected total bill across all offerings. The Breakdown has a monthly bill per team (people on team subscriptions with usage, shared, dedicated, external, total) and every subscription with its team |
| **Showback 2 · Shared private** | Who uses the shared model, do teams use what they commit to, and what do those tokens deliver? | Two filters: Team, and Model, which opens on the first shared model of the catalog (Qwen). Every section reads the selected period. Overview: a pie of total tokens per team, gauges of how much of each team's commitment was used (red below 67%, green to 115%, orange above: the bands of the capacity plan), tokens per subscription as stacked bars (subscriptions without a commitment together), and demand against capacity, where each step of the capacity line is one worker, so a temporary second worker shows and adds its share of the month to the running cost. Capacity plan: each commitment against its monthly pace with an action (on plan from 67% to 115%) and a suggested size, and how the monthly capacity splits among commitments, the reservation, on demand and what is not allocated (mostly nights and weekends). Quality: the MLflow judges' pass rate per subscription of the selected model (relevance, completeness, team guidelines, finished; blue from 95%, yellow from 90%, red below). Breakdown: the charges by consumer. A commitment promises peak capacity, so commitments are sized to fit: interactive ones, fully used, stay within 80% of one worker in the busy hour. The actions are advice, and MaaS enforces none of this: its limits count per user |
| **Showback 3 · Dedicated private** | What does Marketing get for its GPU, and which use case uses it? | Two filters: Team (the sponsoring team) and Model. A load gauge (the sponsor's tokens against what the worker can serve), a pie of the paid capacity split into used and unused, and tokens by use case; GPU utilisation and tokens by use case over time; charges per model; and the charge per use case: each subscription's tokens, its share of the team's tokens on the model and that share of the monthly charge |
| **Showback 4 · External model** | What do the providers charge? | Spend, requests and tokens in range, projected monthly spend; a pie of spend by team and bars of spend by model; month-to-date spend stacked by team and requests by team; statement by team, subscription and model; the provider price list (collapsed) |
| **Showback 5 · Break-even** | When should an external workload move to a private model? | A gauge of the workload against the break-even volume of the workers it needs, projected monthly tokens, and the monthly savings if moved (red when it should stay external); external against private cost per month as bars (GPU workers sized from the candidate's demonstrated capacity over its **GPU hours / month** at the **Planning load %**, 70 by default); relevance and completeness pass rates of both models with the verdict counts behind them; the private fleet's spend against the same tokens at the external price |
| **Showback 6 · Fair share** | What if the teams paid the whole running cost? | An alternative to the tariffs on tabs 1 and 2: every private worker is paid in full by the teams using it. Running cost, team bills, fleet load and the shared worker's cost per token; cost recovered; a pie of the bill by team and one of usage against capacity; how each bill is built (usage = tokens x tier x model weight x base rate, capacity = the running cost usage does not cover, split by share of the worker's busiest hour; a dedicated sponsor pays all of its own worker); cost per token by utilization; the same tokens on private workers and external models; prompt mix, share of peak, GPU hours allocated by token share (an estimate), model weight and first-token latency; and a tier table saying what backs each tier: multipliers are prices, with no latency target or preemption behind them |

The dedicated Mistral is reachable only from Marketing's use-case subscriptions, all owned by `showback-marketing`. The catalog names the sponsoring team; tabs 1, 3 and 6 split its charge over those subscriptions by their share of its tokens in the range (evenly when it used none). **Cost per token** (a Stage 040 platform tab with one editable flat price in USD) is not part of the walkthrough.

### Talk track

1. **By team:** "This is what AI cost each team this month, across every way they use it." The pie gives the split, the cost bars show when it was spent. Then the second row: the platform balance (red when the teams do not pay for the shared capacity yet) and each team's total bill.
2. **Shared private:** Engineering's commitment is its revenue floor; Dev Spaces, OpenCode and MTA count against Engineering too. The commitment gauges show whether a team uses what it pays for; whether the charges cover the platform is the balance on tab 1.
3. **Dedicated private:** Marketing pays the whole worker. Load and paid unused capacity say how much of it is used; the *Who used the capacity* bars show who else uses capacity Marketing pays for.
4. **External:** every response is metered at list price, per team. Run Engineering's external load on Claude or GPT before the demo; Nemotron is free and shows €0.
5. **Break-even:** pick Engineering's external model and Qwen as the candidate, raise **Users per team** or set **GPU hours / month** to 168, and show where moving to private pays off.
6. **Fair share:** the same workers, another way to split them. The tariffs carry the platform coefficient, so what the platform keeps moves with the load; here the teams pay exactly the running cost. Show how little of each bill is usage and how much is capacity, then how the cost per token falls as the load rises.
7. **MLflow:** for any team, open the model's experiment with User = `showback-<team>` to show what was asked, how good the answers were and what a request costs (see below).

The dashboards name no model. The **offer catalog** (`offer-catalog.yaml` in the component, a PrometheusRule evaluated by the RHOAI Prometheus) records the team of each MaaS subscription, which private models are shared or dedicated, the sponsoring subscription of each dedicated model, the demonstrated capacity of one worker, the GPU worker price ($3.36312 per hour, AWS `g7e.2xlarge` on-demand in us-east-2, saved 2026-10-15) the shared tariffs ($1.50 per million tokens on demand, $1.00 committed), the platform coefficient `showback_platform_coefficient` (1.2) and each team’s shared commitment (Engineering 1.2B on `team-engineering` and 800M on `team-engineering-ci`, Support 250M tokens a month). Prices stay in USD, as AWS and the providers charge them; the six Showback tabs show euros through one catalog rate, `showback_usd_per_eur` (1 EUR = 1.1179 USD, ECB reference rate of 2026-11-03), so the monthly worker costs €2,196. The coefficient multiplies what teams pay on private models to pay for running the platform: Qwen is billed at $1.80 on demand and $1.20 committed, and Marketing pays €2,635 for its worker. External models stay at provider list price, and running costs and tab 6 do not use it. A committed team pays its commitment whether used or not and on-demand above it; MaaS limits count per user, so the limit times the team's planned users must carry the commitment in working hours (Engineering 25 × 1M tokens/hour, CI 8 × 1M), which `validate.sh` checks. To onboard another model or change a price, edit the catalog and redeploy the component. Running cost counts the minutes a model is serving, on shared models times the workers serving; node start-up and model loading are not included. Every period is priced with today's catalog, so a catalog change also reprices the past periods you look at.

## Run the demo

Run the commands from the repository root after the usual cluster login. Each step is safe to repeat.

1. **Deploy the component** (once per revision):

   ```bash
   ./stages/040-governed-models-as-a-service/deploy.sh --component 040-showback-demo --revision <full-sha>
   ```

2. **Start the models you need.** Shared needs Qwen, External needs neither. Dedicated needs Mistral on a second GPU worker (the last command; Git declares one replica, so this only resumes a parked model).

   ```bash
   stages/020-gpu-infrastructure-private-ai/deploy.sh --gpus 2
   oc patch llminferenceservice qwen3-8-27b -n internal-models --type=merge -p '{"spec":{"replicas":1}}'
   oc patch llminferenceservice mistral-small4-119b -n internal-models --type=merge -p '{"spec":{"replicas":1}}'
   ```

3. **Mint team keys.** `team-keys.sh` creates the `showback-engineering`, `showback-marketing` and `showback-support` users in the `sso` realm if they are missing, signs each in through OpenShift and mints that user's own MaaS key on its team subscription; Marketing gets one key per use case. Passwords and keys are kept in `~/.config/rhoai3-showback` (override with `SHOWBACK_STATE_DIR`).

   ```bash
   stages/040-governed-models-as-a-service/showback-demo/team-keys.sh --hours 8 --insecure
   ```

4. **Generate load.** One command runs the whole demo, every team at its own pace; or run one offering at a time:

   ```bash
   stages/040-governed-models-as-a-service/showback-demo/generate-load.sh --offer all --minutes 15 --insecure
   stages/040-governed-models-as-a-service/showback-demo/generate-load.sh --offer shared --minutes 10 --insecure
   stages/040-governed-models-as-a-service/showback-demo/generate-load.sh --offer shared --team engineering-ci --minutes 10 --insecure
   stages/040-governed-models-as-a-service/showback-demo/generate-load.sh --offer dedicated --minutes 10 --insecure
   stages/040-governed-models-as-a-service/showback-demo/generate-load.sh --offer external --model claude-sonnet-5-5 --minutes 30 --concurrency 1 --insecure
   ```

   The teams work on the Coolstore application with the tasks in [`prompts.json`](prompts.json). Each team has a system
   prompt with the facts a finished answer needs (Support: Coolstore's return, refund and password policy; Marketing:
   every brief names product, date, link and length), so the quality judges grade the model, not a missing brief.

   | Team | Work | Shape |
   |---|---|---|
   | Engineering | Code reviews with real code, and agent tasks: the model gets `read_file` and `run_tests` tools, which the script plays from `prompts.json` | One trace per task; an agent task is `AGENT > CHAT_MODEL > TOOL > TOOL > CHAT_MODEL` (the Tool calls tab) |
| Engineering CI | CI job failures (build, test, container image) with their logs; only with `--team engineering-ci`, after `team-keys.sh --teams engineering-ci` mints its key | One trace per job; the `team_guidelines` judge asks for the root cause from the log and a specific fix |
   | Support | Customer cases grounded in the stated policy; most continue as a conversation with one or two customer replies | One trace per turn, the turns of a conversation in one MLflow session (the Sessions tab) |
   | Marketing | Three use cases, each on its own subscription: `marketing-content` (product copy, social posts, blog drafts), `marketing-campaigns` (campaign briefs, email and ad variants) and `marketing-rag` (product questions answered from passages, some out of date or incomplete); some with a revision round. `--team` takes one use case | Same as Support |

   `--pause` sets the think time between requests for every team (fixed seconds or a range such as `5-30`); without
   it each team keeps its own pace (Engineering 2-6 s, Support 5-15 s, Marketing 10-30 s, also between the turns of a
   conversation). `--concurrency` (default 2 loops per team), `--max-tokens` (one answer cap for every team; by default
   Engineering 2048, since code answers are longer, and Support and Marketing 1024, so answers normally finish; an answer
   the cap cuts off is marked by the `finished` check) and `--team` (one team of the
   offering) shape the load; Support's Qwen allowance is 500K tokens per hour per user. `--model` picks the external model for
   Engineering (default `gpt-6-luna`; `nemotron-3-ultra-550b-a55b` is free). Each run prints turns, tokens and tool calls
   per team. External calls are billed by the provider.

5. **Stop the models** when the demo ends: set both replicas back to 0 and run `stages/020-gpu-infrastructure-private-ai/deploy.sh --gpus 0`.

## MLflow traces per request

`generate-load.sh` also writes every request to MLflow as one trace, and a daily judge run grades them, so
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

**Money and evidence have one owner each.**

| Question | Where | Why there |
|---|---|---|
| Who consumed how much, what is charged per subscription, commitments, break-even | Perses: product **Usage** dashboard, the **Showback** tabs | MaaS usage telemetry, measured by the platform for every client per user, subscription and model, priced with the offer catalog: the documented OpenShift AI 3.5 showback path |
| What was asked and answered, how good it was, what one request or agent task costs | MLflow: the model experiment (Traces, Sessions, Tool calls, Quality; User filter for a team) | Request-level evidence and quality; cost as an indicative **unit cost** |

MLflow's cost charts group only by model and provider: its cost feature estimates what an LLM call costs, it is not a
ledger, so per-subscription charges are deliberately not rebuilt there. Each trace's `cost_basis` tag says what its
figure means: `tariff` (shared: the on-demand tariff), `capacity-equivalent` (dedicated: the worker price per token
at demonstrated capacity; the sponsor's real charge is the worker, busy or idle, on the Showback 3 · Dedicated tab) or
`list-price` (external: the provider's list price, the same catalog the metering ledger uses). MLflow totals therefore
differ from the Showback charges by design. Talk track: the Showback 1 · By team tab shows a team's charge; MLflow, User =
`showback-support`, shows what Support asked, how good the answers were and what a typical request costs.

| Span | Content |
|---|---|
| `team-<team> request` (root, `CHAIN`, or `AGENT` when tools were used) | Trace tags `team`, `subscription`, `offering`, `source`, `finish_reason` (`stop`, or `length` when the max-tokens cap cut the answer off); trace user `showback-<team>`; the prompt and the answer |
| `chat <model>` (`CHAT_MODEL`, one per model call) and `tool <name>` (`TOOL`, one per tool call) | OpenTelemetry GenAI fields: model, provider (`openshift-ai` for private models), input and output tokens, messages, `gen_ai.response.finish_reasons`, HTTP status; cost |

- **Sessions:** the turns of a conversation carry one `session.id` (OpenTelemetry semantic convention), which
  MLflow stores as the trace session, so the experiment's **Sessions** tab shows each conversation turn by turn.
- **Cost:** shared private models at the on-demand tariff with the platform coefficient, a dedicated model at its worker price per token at
  demonstrated capacity (both from `offer-catalog.yaml`), external models at the list price of
  `metering/provider-pricing.json`. A per-request figure is an indication: the sponsor of a dedicated model pays the
  worker busy or idle, and committed tariffs are monthly; the Showback tabs show those charges. MLflow does not look
  up a price by model name, and its figures stay in USD.
- **Path:** the script posts OTLP/HTTP JSON to the internal MLflow Service (`/v1/traces`, through a local port-forward)
  with the operator's token, the `X-MLFLOW-WORKSPACE` header and the experiment id, the same endpoint a platform trace
  collector would use. The scorer creates an experiment for every MaaS model reference and refreshes its
  offering and provider tags, so each model has its scorecard before its first request; the script creates a missing
  one on first use.
- **Fails open:** a failed export never stops the load; the summary prints `traced` and `trace_failed` per team.
  `--no-trace` skips tracing. Failed requests are traced as errors.
- **Quality:** the CronJob `maas-quality-scorer` (component folder `quality/`) is a daily batch job at 17:00 UTC, the end
  of the working day, while the judge models usually still run, so the GPU workers can be scaled down for the night. It grades every successful, unscored trace of the previous 25 hours (paged; at most 2000
  per experiment and run), asks a judge three true/false questions and logs the verdicts as MLflow feedback: `relevance`,
  `completeness` (every part of the request answered) and `team_guidelines` (the guideline of the trace's team). A
  fourth verdict, `finished`, is code, not a judge: it is false when the trace's `finish_reason` is `length`, the
  max-tokens cap cut the answer off. Each trace gets only the verdicts it does not have yet. The scorer also registers its LLM judges
  in each experiment (Judges page: name, instructions, judge model; never the endpoint or key), so the page shows what
  grades that experiment; `finished` is not listed there, since MLflow registers custom code scorers only on Databricks. They are display only: MLflow cannot run them itself on OpenShift AI 3.5, the batch job does. The Quality tab shows each
  scorer's average, the pass rate. The judges are reached through MaaS on their own subscription
  `maas-quality-judge`: Qwen grades every model except itself and GPT-6 Luna grades Qwen, so no model grades its own
  answers and Marketing's Mistral serves only its sponsor. Grading Qwen sends its prompts and answers, playground
  conversations included, to Luna's provider, and Platform pays for it at list price. Both must be serving when the job runs; if either is stopped (GPUs
  scaled down), the run is skipped with a message. A run stops after 2.5 hours, and unscored traces wait for the next
  one. To score right after a demo load, start it by hand:
  `oc create job --from=cronjob/maas-quality-scorer maas-quality-scorer-now -n models-as-a-service`.
  The exporter `showback-quality-exporter` (`redhat-ods-monitoring`) reads the verdicts from MLflow every 6 hours and
  publishes them to Prometheus twice: the last 7 days, so tab 5 shows the pass rate per model and the verdict counts
  behind it, and a running total of every verdict, so tab 2 shows the pass rate per subscription for any selected period
  (verdicts count on the day they are scored, usually the day after the request).
- **Scope:** only this load generator's requests are traced. Platform-side tracing of every MaaS client is planned work.
- **Other projects:**

  | Project | Experiments | Quality |
  |---|---|---|
  | AI Coding Sandbox (`demo-sandbox`) | `Default`, written by the Gen AI playground; the name comes from the product, and one chat can use any model | The same scorer and judges grade every conversation (traces with the root span `gen-ai-bff`): `relevance`, `completeness`, and `finished` from the answer's status. Conversations that used document search also get `groundedness`, which checks the answer against the retrieved passages. No `team_guidelines`, because the playground has no teams. A judge never grades its own model. The other traces in this experiment are platform calls and are not graded |
  | Evaluated Models (`evaluated-models`) | `models-onboarding`, runs from the qualification pipeline and EvalHub; no traces | The benchmarks and the qualification verdict; judges grade traces, so they do not apply |
  | AI Agents (`ai-agents`) | None yet | Nothing to grade until agent traces are written |

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
