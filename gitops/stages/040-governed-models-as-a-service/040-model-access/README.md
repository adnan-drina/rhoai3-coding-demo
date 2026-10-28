# Model Access (`040-model-access`)

This Application decides who may use which governed model and with what token budget. It holds one `MaaSSubscription`
(quota and owners) and one `MaaSAuthPolicy` (authorization) per consumer: three personal users, the Dev Spaces key
provisioner, the Gen AI playground's custom endpoint and the Stage 050 evaluation tenant. API keys minted against a
subscription inherit its models and limits.

| | |
|---|---|
| Argo CD Application | `040-model-access` ([manifest](../../../applications/040-model-access.yaml)) |
| Deployed by | `stages/040-governed-models-as-a-service/deploy.sh` (deploy-order 6) |
| Validated by | `scripts/stage-apps.sh status` through `validate.sh --readiness` (Synced and Healthy at the deployed revision); `stages/040-governed-models-as-a-service/validate.sh --functional` (persona discovers its `personal-<user>` subscription, mints and revokes a temporary key, bounded requests) |
| Sync | Automated, `prune` and `selfHeal`. Sync options `CreateNamespace`, `SkipDryRunOnMissingResource`, `RespectIgnoreDifferences` (and a `ServerSideDiff=true` sync option that has no effect). Compare option `ServerSideDiff=true` (annotation). No `ignoreDifferences` |
| Depends on | `040-maas-database` (namespace `models-as-a-service`), `040-maas-platform` (MaaS controllers and CRDs), `040-local-models` and `040-external-models` (the referenced `MaaSModelRef`s); the owner ServiceAccounts: `wksp-ai-developer/devspace-maas-key-provisioner` (Stage 070), `demo-sandbox/playground-maas-key-provisioner` (`040-genai-studio`), `evaluated-models/evalhub-maas-key-provisioner` (Stage 050) |
| Used by | Personal API keys (dashboard and Gen AI playground), Stage 070 Dev Spaces key provisioning, `040-genai-studio` endpoint Job, Stage 050 EvalHub jobs |

## Why

MaaS is the control point for model access: a `MaaSSubscription` defines which owners have quota for which models, and a
`MaaSAuthPolicy` authorizes subjects to reach those model endpoints through the gateway [1]. Keeping every policy in Git
makes access reviewable and reproducible. Access policies change more often than models, so they are their own
Application; a change here does not resync the serving deployment.

Each consumer gets its own subscription so usage is attributed separately (personal, Dev Spaces, playground, evaluation)
in the Usage dashboard and in the `tokenMetadata`/`meteringMetadata` labels.

## What

All objects are in namespace `models-as-a-service`.

| Kind | Name | Owner / subjects | Models and hourly token limits | Priority | Wave |
|---|---|---|---|---|---|
| MaaSSubscription + MaaSAuthPolicy | `personal-kube-admin` | users `kube:admin` and `admin` | `qwen3-8-27b` and `mistral-small4-119b` 1,000,000 each; `gpt-6-luna`, `claude-sonnet-5-5`, `nemotron-3-ultra-550b-a55b` 100,000 each | 160 | 18 |
| MaaSSubscription + MaaSAuthPolicy | `personal-ai-developer` | user `ai-developer` | same as above | 150 | 18 |
| MaaSSubscription + MaaSAuthPolicy | `personal-ai-admin` | user `ai-admin` | same as above | 170 | 18 |
| MaaSSubscription + MaaSAuthPolicy | `devspaces-coding-models` | ServiceAccount `wksp-ai-developer/devspace-maas-key-provisioner` | `qwen3-8-27b` 60,000,000 (local model only) | 100 | 18 |
| MaaSSubscription + MaaSAuthPolicy | `playground-sandbox` | ServiceAccount `demo-sandbox/playground-maas-key-provisioner` | `gpt-6-luna` 1,000,000 | 50 | 18 |
| ServiceAccount, MaaSSubscription + MaaSAuthPolicy | `maas-quota-probe`, `quota-probe` | ServiceAccount `models-as-a-service/maas-quota-probe` | `qwen3-8-27b` 100 per minute | 40 | 18 |
| MaaSSubscription + MaaSAuthPolicy | `model-qualification` | ServiceAccount `evaluated-models/evalhub-maas-key-provisioner` | `qwen3-8-27b` 5,000,000; each external model 1,000,000 | 70 | 30 |

Every subscription sets `tokenMetadata` (`organizationId: rhoai3-coding-demo`, `costCenter: ai-platform`, labels
`environment`, `provider`, `modelSet`), and every auth policy sets the same `meteringMetadata`.

### Objects not in Git

| Object | Owner |
|---|---|
| API keys (stored in the MaaS PostgreSQL database) | Users (dashboard), Stage 070 Dev Spaces provisioner, `040-genai-studio` Job `provision-playground-endpoint`, Stage 050 provisioner (evaluation key), `stages/040-governed-models-as-a-service/validate.sh --functional` (temporary) |
| Generated Kuadrant `AuthPolicy` and `TokenRateLimitPolicy` objects | MaaS controller |
| Other subscriptions in the same namespace: `hermes-private-qwen38`, `opencode-private-qwen38` | `060-openshell-runtime` |
| Subscription and auth policy `mta-migration-ai` | `070-mta` |

## How

**Ordering.** Application wave 4, deploy-order 6, so the `MaaSModelRef`s from deploy-order 5 exist first. Objects use
wave 18, except `model-qualification` at wave 30.

**Owners are users and ServiceAccounts, not groups.** The product examples use groups [1]. This demo binds each
personal subscription to one user so the demo can show per-person budgets, and binds service subscriptions to the one
ServiceAccount that mints their keys. A new user needs a new pair of objects.

**Priority.** When an owner matches several subscriptions, the one with the highest priority is used [1]. The personal
subscriptions (150-170) win over service subscriptions, so a key that a person creates in the dashboard or playground is
metered as personal use. Service subscriptions have unique owners, so their priorities only order them.

**Token budgets.**
- `devspaces-coding-models` is 60,000,000 tokens per hour. Agentic assistants resend large contexts; a 20,000,000 budget
  throttled an autonomous migration that measured 25,000,000 tokens in its busiest hour (comment in the manifest). On a
  local GPU model the budget shows governance, not cost control. Dev Spaces gets only the private model.
- Personal budgets are 1,000,000 tokens per hour for the local model and 100,000 for each external model, because
  external tokens are paid per use.
- `model-qualification` meters evaluation without becoming its bottleneck: the local limit is above what one GPU
  produces. External models are included because they are evaluated and serve as judge models.
- `quota-probe` exists only for `stages/040-governed-models-as-a-service/validate.sh --quota`: its budget is reached within a few small requests and resets every minute, so the probe proves the gateway answers 429. No person or workload uses the identity.
- `playground-sandbox` exists only for the GPT-6 Luna playground custom endpoint (see `040-genai-studio`), a workaround
  for RHOAIENG-90257 in the 3.5.1 playground.

**Metering limits.** Subscription token limits apply to OpenAI Chat Completions requests [1]. All governed models are
registered with that format, so all are metered. Provider-side limits still apply to the shared provider key across all
users.

**Secrets.** None in this component. Keys are minted at runtime by their owners and never stored in Git.

## Validation

`validate.sh --readiness` requires this Application to be Synced and Healthy at the deployed revision; `stages/040-governed-models-as-a-service/validate.sh`
does not read the subscriptions or auth policies individually. `validate.sh --functional` (as the
developer persona from `RHOAI_DEVELOPER_KUBECONFIG`, or `RHOAI_STAGE040_PERSONA_KUBECONFIG`) checks that the persona can discover `personal-<user>`, mints a temporary key for
it, sends bounded requests and revokes the key.

By hand (read-only):

```bash
oc get maassubscription,maasauthpolicy -n models-as-a-service
oc get maassubscription personal-ai-developer -n models-as-a-service -o jsonpath='{.spec.modelRefs}{"\n"}'
```

## Alignment with official guidance

| Topic | Official guidance (link) | This repository | Status |
|---|---|---|---|
| Quota | `MaaSSubscription` with `owner`, `modelRefs[].tokenRateLimits` (limit, window) [1] | Six subscriptions, 1 h windows | Aligned |
| Authorization | `MaaSAuthPolicy` with `subjects` and `modelRefs` [1] | One policy per subscription, same subjects and models | Aligned |
| Subject type | Examples use `owner.groups` / `subjects.groups` [1] | Individual users and ServiceAccounts | Deviation (justified: per-person budgets and single-identity key provisioners in a demo) |
| Priority | Highest priority wins for a multi-match owner [1] | Personal 150-170 above service subscriptions | Aligned |
| Token metering | Subscription token limits apply only to OpenAI Chat Completions [1] | All referenced models use Chat Completions | Aligned |
| API key lifetime | Default and maximum 90 days, configurable per tenant [1] | Product default | Aligned |
| Support status | Core MaaS governance (subscriptions, authorization policies, API keys, rate limits) is generally available; external model egress and provider passthrough, the MaaS observability dashboard and Loki showback are Technology Preview (3.4 and 3.5 release notes) [2] | Subscriptions, policies and keys are core MaaS; the external-model subscriptions use Technology Preview egress | Aligned |
| Readiness validation | Not prescribed | Only Argo CD health; no per-object `Active` phase check | Gap (subscription or auth policy phase not checked by `stages/040-governed-models-as-a-service/validate.sh`) |

## References

1. Govern LLM access with Models-as-a-Service, "Deploy and manage Models-as-a-Service" (sections on subscriptions, authorization policies and API keys), Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/govern_llm_access_with_models-as-a-service/deploy-and-manage-models-as-a-service
2. Release notes, "Technology Preview features", Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/technology-preview-features_relnotes
