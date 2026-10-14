# External Models (`040-external-models`)

This Application registers the approved third-party models with Models-as-a-Service (MaaS): GPT-6 Luna (OpenAI),
Claude Sonnet 5.5 (Anthropic) and Nemotron 3 Ultra 550B (NVIDIA's hosted API). Each model is an `ExternalProvider` (the
provider endpoint and credential reference), an `ExternalModel` (the client-facing model name) and a `MaaSModelRef` (the
MaaS publication). Users and tools reach these models through the same MaaS gateway, API keys and subscriptions as the
private model; requests leave the cluster for the provider.

| | |
|---|---|
| Argo CD Application | `040-external-models` ([manifest](../../../argocd/app-of-apps/040-governed-models-as-a-service/external-models.yaml)) |
| Deployed by | `stages/040-governed-models-as-a-service/deploy.sh` (deploy-order 5, together with `040-local-models`); provider Secrets by `setup-provider-secret.sh`, called from `deploy.sh` |
| Validated by | `stages/040-governed-models-as-a-service/validate.sh --readiness` (`validate-native.py`: providers and models Ready and equal to Git, provider Secret has a non-placeholder `api-key` and the `inference.llm-d.ai/ipp-managed` label, model route owned by the `ExternalModel` and attached to listener `api`, `MaaSModelRef` Ready with endpoint on the API hostname); `validate-functional.py` with `RHOAI_STAGE040_MODEL=<model>` for one bounded completion; `scripts/shared/stage_apps.py status` |
| Sync | Automated, `prune` and `selfHeal`. Sync options `CreateNamespace`, `SkipDryRunOnMissingResource`, `RespectIgnoreDifferences` (and a `ServerSideDiff=true` sync option that has no effect). Compare option `ServerSideDiff=true` (annotation). No `ignoreDifferences` |
| Depends on | `040-maas-platform` (MaaS and the external-model controller enabled; `externalModels` dashboard flag), `040-gateway-governance` (Gateway `maas-default-gateway`, listener `api` admits `external-models`), Stage 010 (`rhods-admins` group); provider API keys in the private `.env` |
| Used by | `040-model-access` (personal, qualification and playground subscriptions), `040-genai-studio` (GPT-6 Luna playground endpoint), Stage 050 evaluations (models under test and judges), Gen AI playground and OpenAI-compatible IDE clients |

## Why

Some work is better served by a frontier model than by the private model. OpenShift AI 3.5 lets an administrator
register an external provider and publish its models through MaaS, so that the same identity, API keys, subscriptions,
token limits and usage telemetry apply as for local models [1]. External models are a Technology Preview feature [1][2].
A model is visible to subscriptions only when a `MaaSModelRef` exists in the same namespace as the `ExternalModel` [1].

The providers, models and references live in a dedicated `external-models` project, separate from the private models,
so the data boundary is visible: anything routed here leaves the cluster. This is its own Application because the model
catalog changes more often than the platform; adding or removing a model syncs only this component.

## What

### Project and access

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| Namespace | `external-models` | cluster | Project for external models. Labels: `opendatahub.io/dashboard`, `maas-gateway-access=true` (admitted by the Gateway `api` listener). Wave 1, `Prune=false,Delete=false` |
| RoleBinding | `rhods-admins-external-models-admin` | `external-models` | ClusterRole `admin` for group `rhods-admins`. Wave 3 |

### Providers (wave 15)

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| ExternalProvider | `openai` | `external-models` | `provider: openai`, `endpoint: api.openai.com`, Secret `openai-provider-api-key` |
| ExternalProvider | `anthropic` | `external-models` | `provider: anthropic`, `endpoint: api.anthropic.com`, Secret `anthropic-provider-api-key` |
| ExternalProvider | `nvidia` | `external-models` | `provider: openai` (NVIDIA's API is OpenAI-compatible), `endpoint: integrate.api.nvidia.com`, Secret `nvidia-provider-api-key` |

### Models (wave 16) and MaaS references (wave 17)

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| ExternalModel | `gpt-6-luna` | `external-models` | Provider `openai`, target `gpt-6-luna`, `apiFormat: openai-chat`, path `/v1/chat/completions` |
| ExternalModel | `claude-sonnet-5-5` | `external-models` | Provider `anthropic`, target `claude-sonnet-5-5`, `apiFormat: openai-chat`, path `/v1/chat/completions` (Anthropic's OpenAI-compatible endpoint) |
| ExternalModel | `nemotron-3-ultra-550b-a55b` | `external-models` | Provider `nvidia`, target `nvidia/nemotron-3-ultra-550b-a55b`, `apiFormat: openai-chat`, path `/v1/chat/completions` |
| MaaSModelRef | `gpt-6-luna`, `claude-sonnet-5-5`, `nemotron-3-ultra-550b-a55b` | `external-models` | Publish each `ExternalModel` to MaaS with its display name |

### Objects not in Git

| Object | Owner |
|---|---|
| Secrets `openai-provider-api-key`, `anthropic-provider-api-key`, `nvidia-provider-api-key` (key `api-key`, label `inference.llm-d.ai/ipp-managed=true`) | `stages/040-governed-models-as-a-service/setup-provider-secret.sh`, from `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` and `NVIDIA_API_KEY` in the private `.env`. Not tracked by Argo CD |
| HTTPRoutes `gpt-6-luna`, `claude-sonnet-5-5`, `nemotron-3-ultra-550b-a55b` (owner reference to the `ExternalModel`) | External-model controller |
| Auth and token-rate-limit policies for the models | MaaS and Connectivity Link controllers |

## How

**Ordering.** Application wave 4, deploy-order 5. Inside it: namespace (1), RoleBinding (3), providers (15), models
(16), references (17). `deploy.sh` applies the Applications first and then runs `setup-provider-secret.sh` three times
(OpenAI, then `RHOAI_STAGE040_PROVIDER_SECRET=anthropic-provider-api-key`, then `nvidia-provider-api-key`). Until a
Secret exists, its provider is not Ready.

**Provider credentials.** The procedure in the MaaS guide creates a Secret with key `api-key` and labels it
`inference.llm-d.ai/ipp-managed=true` [1]. `setup-provider-secret.sh` does the same without putting the value in Git or on
a command line: it waits until the namespace carries this Application's tracking id, reuses an existing Secret
(it checks the label and that no other Application tracks it), copies a Secret left in the former
`models-as-a-service` location if one exists, and otherwise creates it from the `.env` value through standard input.
Rotation (`RHOAI_STAGE040_ROTATE_PROVIDER_SECRET=true`) is implemented only for the OpenAI key. The Secrets are outside
Git on purpose; Argo CD does not prune them.

**API format.** All three models use `apiFormat: openai-chat`. MaaS subscription token limits apply only to OpenAI Chat
Completions requests, and `openai-chat` always uses translation [1]. Using one format keeps every external model
subscription-token-metered.

**Workaround: Claude through Anthropic's OpenAI-compatible endpoint.** The MaaS guide offers `apiFormat: messages` for
Anthropic's native Messages API [1]. This demo registers Claude against Anthropic's OpenAI SDK compatibility endpoint
(`/v1/chat/completions`) instead, for two reasons:
- Connectivity Link 1.4.3 ships wasm-shim 0.14.2, which holds a response open when it has no OpenAI
  `usage.total_tokens`; native Messages responses hang until the client times out (`docs/TROUBLESHOOTING.md`, "MaaS
  Gateway Holds A Response Open Until The Client Times Out").
- Messages requests are not subscription-token-metered [1].
The cost: Anthropic describes this layer as intended for testing and comparing models, not as a long-term production
path. It ignores `response_format`, `logprobs`, penalties and `seed`, does not support prompt caching, and hoists system
messages into one system prompt [3]. On current Claude models any `temperature` below 1 and any `top_p` other than the default
return HTTP 400 [3]; playground users set Temperature to 1. Revisit this once a Connectivity Link release with wasm-shim 0.14.3 or later is installed
(`BACKLOG.md`).

**Workaround: GPT-6 Luna in the playground.** GPT-6 Luna rejects `max_tokens` and non-default temperature. The 3.5.1
playground's MaaS provider path sends `max_tokens` (RHOAIENG-90257, not in 3.5.1), so `040-genai-studio` provisions a
separate custom endpoint for it. API clients send `max_completion_tokens` and, for function calls,
`reasoning_effort: none`.

**NVIDIA as an `openai` provider.** The gateway has built-in support for `openai`, `anthropic`, `azure`, `vertex` and
`bedrock`; `endpoint` is the provider FQDN without scheme or path [1]. NVIDIA's hosted API is OpenAI-compatible at
`https://integrate.api.nvidia.com/v1` [4], so it is registered as `provider: openai` with that endpoint, and `targetModel`
maps the client name `nemotron-3-ultra-550b-a55b` to NVIDIA's `nvidia/nemotron-3-ultra-550b-a55b`.

**Tenant.** External models work only in the default MaaS tenant [1]; this demo uses only the default tenant.

**Cluster-specific values.** None. The `MaaSModelRef` endpoint resolves to the Gateway `api` hostname that `deploy.sh`
patches into `040-gateway-governance`.

## Validation

`validate.sh --readiness` checks each provider and model is Ready with a current `Ready` condition and contains the Git
spec, each provider Secret has a non-empty, non-placeholder `api-key` and the discovery label, each model's route is owned
by the model and attached to the `api` listener, and each `MaaSModelRef` is Ready with `GovernanceAttached` and
`RuntimeReady` and reports the API hostname as endpoint. It does not prove provider entitlement or inference;
`validate-functional.py` with a persona kubeconfig sends one bounded completion per selected model with a temporary key.

By hand (read-only; never print the Secrets):

```bash
oc get externalprovider,externalmodel -n external-models
oc get maasmodelref -n external-models
```

## Alignment with official guidance

| Topic | Official guidance (link) | This repository | Status |
|---|---|---|---|
| Resource model | `ExternalProvider` + `ExternalModel` + `MaaSModelRef` in the same namespace [1] | Three of each in `external-models` | Aligned |
| Credential Secret | Key `api-key`, label `inference.llm-d.ai/ipp-managed=true`, referenced by `auth.secretRef.name` [1] | Same, created by script outside Git | Aligned |
| Provider endpoint | FQDN without scheme or path; built-in provider values [1] | `api.openai.com`, `api.anthropic.com`, `integrate.api.nvidia.com` | Aligned |
| Anthropic format | `messages` for Anthropic's native API; subscription token limits apply only to Chat Completions [1] | Claude as `openai-chat` on Anthropic's OpenAI-compatible endpoint | Deviation (justified: wasm-shim 0.14.2 hang and Messages not token-metered; provider calls the endpoint a testing path [3]) |
| Token metering | Use OpenAI Chat Completions for subscription token limits [1] | All three models `openai-chat` | Aligned |
| Tenancy | External models only in the default tenant [1] | Default tenant only | Aligned |
| Support status | External models are Technology Preview [1][2] | Demo use; not production | Aligned |
| Credential rotation | Not prescribed | Scripted rotation only for OpenAI | Gap (no scripted rotation for Anthropic and NVIDIA keys) |

## References

1. Govern LLM access with Models-as-a-Service, "Deploy and manage Models-as-a-Service" (section "Configure external models for Models-as-a-Service"), Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/govern_llm_access_with_models-as-a-service/deploy-and-manage-models-as-a-service
2. Release notes, "Technology Preview features", Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/technology-preview-features_relnotes
3. Anthropic, "OpenAI SDK compatibility" (upstream). https://platform.claude.com/docs/en/api/openai-sdk
4. NVIDIA, Nemotron 3 Ultra 550B A55B on build.nvidia.com (upstream). https://build.nvidia.com/nvidia/nemotron-3-ultra-550b-a55b
