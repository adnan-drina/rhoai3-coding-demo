# Showback demo: three teams, three service offerings

This demo answers "What did AI cost us?" on a governed MaaS platform. Three teams consume AI through three service offerings, each priced differently, and three live dashboards show usage and cost as load runs.

| Team | Offering | Model | How it is priced |
|---|---|---|---|
| Engineering | Shared private | Qwen 3.8 27B on a platform-owned RTX PRO 6000 worker | Published tariff per million tokens; the platform carries idle capacity |
| Support | Shared private and External | Qwen 3.8 27B; GPT-6 Luna, Claude Sonnet 5.5, Nemotron | Tariff for Qwen; provider list price per token for external models |
| Marketing | Dedicated private | Mistral Small 4 119B on its own RTX PRO 6000 worker | Full running cost of the worker, busy or idle |

The cluster resources are the optional [040-showback-demo component](../../../gitops/stages/040-governed-models-as-a-service/040-showback-demo/README.md): team subscriptions and policies, the Mistral model (stopped in Git), the three dashboards and the external metering service.

## Dashboards

Open **Observe & monitor → Dashboard** in the OpenShift AI console. All three tabs query the RHOAI monitoring datasource live; the time range picker sets the billing period.

| Tab | Shows |
|---|---|
| **Offer · Shared private** | Qwen running cost, tokens served, tariff revenue, the platform's balance (revenue minus cost) and a per-subscription table of tokens, tariff charge, token share and cost share |
| **Offer · Dedicated private** | Marketing's charge (Mistral serving hours × worker rate), tokens, effective cost per million tokens, busy share and paid idle |
| **Offer · External model** | Month-to-date provider spend by subscription and model from the metering ledger, unpriced requests, the price list and live token rates |

Both private dashboards have a **GPU worker $/hour** field (default $3.36312, the AWS `g7e.2xlarge` on-demand price in us-east-2 saved on 2026-10-15). The shared dashboard also has the **tariff $/1M tokens** field (default $4.00). Running cost counts the minutes a model is serving; node start-up and model loading are not included.

## Run the demo

Run the commands from the repository root after the usual cluster login. Each step is safe to repeat.

1. **Deploy the component** (once per revision):

   ```bash
   ./stages/040-governed-models-as-a-service/deploy.sh --component 040-showback-demo --revision <full-sha>
   ```

2. **Start the models you need.** Shared needs Qwen, Dedicated needs Mistral on a second GPU worker, External needs neither.

   ```bash
   stages/020-gpu-infrastructure-private-ai/deploy.sh --gpus 2
   oc patch llminferenceservice qwen3-8-27b -n internal-models --type=merge -p '{"spec":{"replicas":1}}'
   oc patch llminferenceservice mistral-small4-119b -n internal-models --type=merge -p '{"spec":{"replicas":1}}'
   ```

3. **Mint team keys.** `team-keys.sh` creates the `showback-engineering`, `showback-marketing` and `showback-support` users in the `sso` realm if they are missing, signs each in through OpenShift and mints that user's own MaaS key on its team subscription. Passwords and keys are kept in `~/.config/rhoai3-showback` (override with `SHOWBACK_STATE_DIR`).

   ```bash
   stages/040-governed-models-as-a-service/showback-demo/team-keys.sh --hours 8 --insecure
   ```

4. **Generate load** for one offering at a time, or run several in parallel terminals:

   ```bash
   stages/040-governed-models-as-a-service/showback-demo/generate-load.sh --offer shared --minutes 10 --insecure
   stages/040-governed-models-as-a-service/showback-demo/generate-load.sh --offer dedicated --minutes 10 --insecure
   stages/040-governed-models-as-a-service/showback-demo/generate-load.sh --offer external --minutes 5 --insecure
   ```

   `--concurrency` (default 2 loops per team) and `--max-tokens` (default 256) shape the load; `--model` picks the external model (default `gpt-6-luna`; `nemotron-3-ultra-550b-a55b` is free). Each run prints requests and tokens per team. External calls are billed by the provider.

5. **Stop the models** when the demo ends: set both replicas back to 0 and run `stages/020-gpu-infrastructure-private-ai/deploy.sh --gpus 0`.

## External metering

The MaaS gateway's `external-metering-streaming` plugin (Developer Preview in RHOAI 3.5) posts one event per external-model response to a metering service in `redhat-ods-monitoring`: a patched build of the community Noyitz backend with a PostgreSQL ledger on a retained PVC. Each event keeps the user, subscription, model, token counts and a price estimate frozen from the versioned catalog `metering/provider-pricing.json`. The service exposes month-to-date gauges for the External dashboard.

- **Activation:** the targeted deployment writes the plugin into the MaaS-owned ConfigMap `openshift-ingress/payload-processing-plugins` when `metering/profile.yaml` has `enabled: 'true'`, and restarts `payload-processing` only when the profile changes. The plugin fails open, so a metering outage never blocks inference.
- **Prices:** add a new catalog version and new `price_version` values for any change; earlier events keep their estimates.
- **Disable:** set `enabled: 'false'`, publish and redeploy the component; keep the PVC. Reverting the Application alone does not remove the plugin.
- **After a cluster start** the backend restarts a few times until PostgreSQL is ready.
- **Limits:** one delivery attempt per event, and a response without usage may produce no event. Estimates are list prices, not invoices.
- **Rebuild the image** (it exists only in the cluster registry) with [metering-backend/](metering-backend/README.md).

## Files

| File | Purpose |
|---|---|
| `team-keys.sh` | Team users and their MaaS keys |
| `generate-load.sh` | Demo load per offering |
| `validate.sh` | Offline checks: script syntax, access matrix, dashboards, metering bundle |
| `metering-backend/` | Patches, Containerfile and build/publish scripts for the metering image |
| `tests/test-metering-profile.sh` | Mocked test of the metering activation in the Stage 040 deploy script |

The earlier report pipeline (offline allocation, report publisher, MLflow archive, monthly statements and their dashboards) was retired on 2026-10-20 and is in Git history at `87aaf9c1`.
