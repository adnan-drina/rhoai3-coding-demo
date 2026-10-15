---
name: rhoai-maas-governance
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when changing, reviewing, or debugging Stage 040 Models-as-a-Service
  governance: MaaS enablement on default-dsc (aigateway, modelsAsAService),
  MaaSTenantConfig telemetry, the maas-db-config database Secret, Gateway
  maas-default-gateway and Authorino TLS, MaaSModelRef publication of
  qwen3-8-27b and external models (ExternalProvider, ExternalModel),
  MaaSSubscription and MaaSAuthPolicy in models-as-a-service, API keys, token
  limits, 401/403/429 from the MaaS gateway, and usage export. Do NOT use for
  the llm-d serving spec (use rhoai-distributed-inference-llmd), generated
  Kuadrant policies (use rhcl-configure), Connectivity Link upgrades (use
  rhcl-update), or playground setup (use rhoai-gen-ai-playground).
---

# RHOAI Models-as-a-Service Governance

Thin skill: repo decisions and pitfalls here, product behavior in the linked
OpenShift AI 3.5 sections. Detailed record: component READMEs under
`gitops/stages/040-governed-models-as-a-service/` (start with `040-maas-platform/README.md`);
repo lessons not in Git live in `references/working-configuration.md`.

## When to use

- A Stage 040 MaaS component (`040-maas-*`, `040-gateway-governance`,
  `040-*-models`, `040-model-access`) changes or fails validation.
- A user, Dev Spaces workspace, evaluation or agent gets 401, 403, 404 or 429
  from `maas.<cluster-domain>`.
- Someone adds a model, a consumer, or a token budget.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| MaaS is enabled by a Sync-hook Job patching delegated `default-dsc` fields (`aigateway`, `aigateway.modelsAsAService`, `ogx` Managed; `batchGateway` Removed), not the deprecated `kserve.modelsAsService` | `gitops/stages/040-governed-models-as-a-service/040-maas-platform/jobs/enable-maas-job.yaml` | [MaaS configuration][config] |
| Dashboard flags `modelAsService`, `vLLMDeploymentOnMaaS`, `externalModels`, `genAiStudio` and others are set by the same Job; Stage 010 owns `odh-dashboard-config` | same Job; `gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-platform/odhdashboardconfig.yaml` | [Dashboard configuration][dash] |
| Telemetry on the controller-owned `MaaSTenantConfig` `default-tenant` with `captureUser: true` (product default `false`) for per-user showback | same Job | [Enable telemetry][telemetry] |
| In-cluster PostgreSQL 16 in `models-as-a-service-db`; `maas-db-config` (`DB_CONNECTION_URL`) in `redhat-ai-gateway-infra` is created by script, `sslmode=disable` behind a NetworkPolicy | `gitops/stages/040-governed-models-as-a-service/040-maas-database/`, `stages/040-governed-models-as-a-service/deploy.sh` | [Database secret][db] |
| Gateway `maas-default-gateway` in `openshift-ingress`, class `data-science-gateway-class`, both required annotations, listeners `api` and `qwen3-8` on the cert-manager ingress certificate; hostnames patched at deploy time | `gitops/stages/040-governed-models-as-a-service/040-gateway-governance/gateway/` | [Gateway requirements][gw], [Configure TLS][tls] |
| Authorino TLS: serving-cert annotation by hook Job, TLS listener and CA mount declared on the Authorino CR instead of `oc set env` | `gitops/stages/040-governed-models-as-a-service/040-gateway-governance/governance/`, `.../gateway-governance/jobs/` | [Configure TLS][tls] |
| Private model `qwen3-8-27b` published by `MaaSModelRef` in `internal-models` | `gitops/stages/040-governed-models-as-a-service/040-local-models/qwen38-27b-maas-modelref.yaml` | [Deploy models with MaaS][deploy] |
| External models `gpt-6-luna`, `claude-sonnet-5-5`, `nemotron-3-ultra-550b-a55b` in `external-models`, all `apiFormat: openai-chat` so every model is subscription-token-metered; Claude uses Anthropic's OpenAI-compatible path | `gitops/stages/040-governed-models-as-a-service/040-external-models/` | [External models][ext], [apiFormat values][apiformat] |
| Provider keys in Secrets `*-provider-api-key` (key `api-key`, label `inference.llm-d.ai/ipp-managed=true`) created from `.env`, never in Git | `stages/040-governed-models-as-a-service/deploy.sh` | [External models][ext] |
| One `MaaSSubscription` + `MaaSAuthPolicy` pair per consumer, owned by a user or one ServiceAccount (not groups); personal priority 150-170 above service subscriptions; 1 h windows | `gitops/stages/040-governed-models-as-a-service/040-model-access/` | [Subscriptions][subs], [Priority levels][prio], [Authorization policies][authz] |
| Default MaaS tenant only (external models require it) | `040-model-access/README.md`, `040-external-models/README.md` | [Multi-tenancy][tenancy] |
| API keys use the product default lifetime; keys are minted at runtime by owners (dashboard, Stage 070 provisioner, playground and Stage 050 Jobs) | not in Git | [Manage API keys][keys], [Expiration limit][keyexp] |
| Usage export uses the dashboard Usage page's native **Export as CSV** (the former Thanos script `export-maas-usage.sh` is in git history at `82092e01`) | not in Git | [Export usage data][export] |

## Procedure

1. Change the component under `gitops/stages/040-governed-models-as-a-service/`
   that owns the object (component README "What" tables). Access changes go
   only in `040-model-access/`; a model change only in `040-local-models/` or
   `040-external-models/`.
2. Deploy and validate after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   ./stages/040-governed-models-as-a-service/deploy.sh
   ./stages/040-governed-models-as-a-service/validate.sh --readiness
   ./stages/040-governed-models-as-a-service/validate.sh --functional   # needs RHOAI_STAGE040_PERSONA_KUBECONFIG
   ```

   Readiness does not prove inference or quota; the functional run (temporary
   key, bounded requests, revoke) does. One external model:
   `RHOAI_STAGE040_MODEL=<name>` + `RHOAI_STAGE040_SINGLE_COMPLETION=true`.
3. Read-only inspection:

   ```bash
   oc get maasmodelref -A
   oc get maassubscription,maasauthpolicy -n models-as-a-service
   oc get externalprovider,externalmodel -n external-models
   oc get maastenantconfigs default-tenant -n models-as-a-service -o jsonpath='{.spec.telemetry}{"\n"}'
   ```

4. A new upstream namespace needs a Gateway `allowedRoutes` entry and an allow
   rule in AdminNetworkPolicy `maas-gateway-boundary` (`040-gateway-governance/README.md`).

## Pitfalls

- A subscription without a matching `MaaSAuthPolicy` returns 403 even with
  quota ([Authorization policies][authz]).
- Subscription token limits apply only to OpenAI Chat Completions; `messages`
  and `openai-responses` models are not metered ([apiFormat values][apiformat]).
- `ExternalProvider`/`ExternalModel` are `inference.opendatahub.io/v1alpha1`;
  the MaaS kinds are `maas.opendatahub.io/v1alpha1`. Check with `oc explain`.
- `Tenant` is deprecated in 3.5 in favour of `AITenant` and `MaasTenantConfig`;
  do not author a `Tenant` ([Multi-tenancy][tenancy]).
- Native Messages responses hang on Connectivity Link 1.4.3:
  `docs/TROUBLESHOOTING.md#maas-gateway-holds-a-response-open-until-the-client-times-out`.
- 429 is an exhausted hourly budget:
  `docs/TROUBLESHOOTING.md#maas-gateway-returns-429`.
- Empty MaaS tab: `docs/TROUBLESHOOTING.md#maas-tab-shows-no-models` (still
  names 3.4 namespaces; `maas-api` and `maas-db-config` are now in `redhat-ai-gateway-infra`).
- Generated `AuthPolicy`/`TokenRateLimitPolicy` are controller output; never
  patch them (`rhcl-configure`).

## Official documentation (OpenShift AI 3.5)

| Topic | Section |
|---|---|
| Prerequisites (Connectivity Link, user workload monitoring) | [Prerequisites][prereq] |
| Gateway and TLS | [Gateway requirements][gw], [Configure TLS][tls] |
| Database Secret | [Database secret][db] |
| Enablement and dashboard | [MaaS configuration][config], [Dashboard configuration][dash] |
| Subscriptions and authorization | [Subscriptions][subs], [Authorization policies][authz] |
| API keys and the MaaS API | [Manage API keys][keys], [MaaS API][api] |
| Observability | [Kuadrant observability][kobs], [Telemetry][telemetry], [Export][export] |
| Multi-tenancy (TP) and external models (TP) | [Multi-tenancy][tenancy], [External models][ext] |
| Troubleshooting | [Administration][admints], [User access][userts] |

## Related skills

`rhoai-distributed-inference-llmd`, `rhcl-configure`, `rhcl-update`,
`rhoai-gen-ai-playground`, `rhoai-telemetry-admin-settings`,
`ocp-ingress-gateway-routes`, `manage-devspaces`, `rhoai-troubleshoot`.

[prereq]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/govern_llm_access_with_models-as-a-service/index#maas-prerequisites_maas-deploy
[gw]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/govern_llm_access_with_models-as-a-service/index#maas-gateway-requirements_maas-deploy
[tls]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/govern_llm_access_with_models-as-a-service/index#configure-tls-for-maas_maas-deploy
[db]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/govern_llm_access_with_models-as-a-service/index#configure-postgresql-secret-for-maas_maas-deploy
[config]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/govern_llm_access_with_models-as-a-service/index#maas-configuration_maas-deploy
[dash]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/govern_llm_access_with_models-as-a-service/index#maas-dashboard-configuration_maas-deploy
[deploy]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/govern_llm_access_with_models-as-a-service/index#deploy-models-using-dashboard-wizard_maas-deploy
[subs]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/govern_llm_access_with_models-as-a-service/index#maas-subscriptions_maas-deploy
[prio]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/govern_llm_access_with_models-as-a-service/index#priority_levels
[authz]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/govern_llm_access_with_models-as-a-service/index#maas-authorization-policies_maas-deploy
[keys]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/govern_llm_access_with_models-as-a-service/index#managing-admin-api-keys_maas-deploy
[keyexp]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/govern_llm_access_with_models-as-a-service/index#configure-api-key-expiration-limit_maas-deploy
[api]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/govern_llm_access_with_models-as-a-service/index#access-maas-api_maas-deploy
[kobs]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/govern_llm_access_with_models-as-a-service/index#enable-kuadrant-observability-maas_maas-deploy
[telemetry]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/govern_llm_access_with_models-as-a-service/index#enable-maas-telemetry_maas-deploy
[export]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/govern_llm_access_with_models-as-a-service/index#export-maas-usage-data_maas-deploy
[tenancy]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/govern_llm_access_with_models-as-a-service/index#managing-maas-multi-tenancy
[ext]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/govern_llm_access_with_models-as-a-service/index#configuring-maas-external-models_maas-deploy
[apiformat]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/govern_llm_access_with_models-as-a-service/index#apiformat_field_values
[admints]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/govern_llm_access_with_models-as-a-service/index#maas-administration-troubleshooting_maas-deploy
[userts]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/govern_llm_access_with_models-as-a-service/index#maas-user-access-troubleshooting_maas-user
