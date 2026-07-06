# Validation Checklist

Use this checklist when authoring docs, GitOps, runbooks, or troubleshooting
notes for Models-as-a-Service.

## Source And Scope

- The work references `docs/PLATFORM_BASELINE.md` and the RHOAI 3.4 MaaS
  guide, not an unversioned latest documentation path.
- MaaS is used only for governed shared model access, not as a replacement for
  direct single-user model serving.
- Technology Preview features are labeled: vLLM with MaaS, external models,
  external OIDC authentication, and the MaaS observability dashboard.
- API support posture is checked with `rhoai-api-tiers` before making upgrade
  durability claims.

## Prerequisites

- OpenShift and RHOAI versions satisfy the active baseline.
- If MaaS CRDs are absent, the implementation is split into a prerequisite
  phase before model-publication and policy resources are committed.
- `DataScienceCluster` has KServe managed and MaaS enabled through the
  documented `modelsAsService` path.
- User Workload Monitoring is enabled.
- cert-manager Operator for Red Hat OpenShift is installed and the
  `CertManager` cluster resource exists when RHCL requires cert-manager.
- Red Hat Connectivity Link Operator is installed at the pinned MaaS-compatible
  CSV for the active demo baseline.
- `Kuadrant` in `kuadrant-system` is ready.
- The MaaS Gateway API resources and annotations are present.
- The MaaS Gateway TLS Secret exists in the same namespace as the Gateway
  before the Gateway resource is applied; for this demo the stable Secret name
  is `maas-gateway-tls` in `openshift-ingress`, generated from the active
  OpenShift ingress certificate by a GitOps sync hook.
- Authorino TLS and service CA trust are configured.
- `maas-db-config` exists in `redhat-ods-applications` with
  `DB_CONNECTION_URL` stored as a Secret value. In this demo, the URL must
  resolve to `maas-postgres.models-as-a-service-db.svc.cluster.local` because
  the database intentionally lives outside the Kueue-managed MaaS model
  namespace.
- If `maas-db-config` is changed after MaaS is already `Managed`, restart
  `deployment/maas-api` in `redhat-ods-applications` as documented by the
  RHOAI 3.4 MaaS guide before validating API-key workflows.
- Demo-local PostgreSQL is clearly labeled as demo posture. Production guidance
  should use an operationally managed PostgreSQL 14+ database.
- Dashboard flags are enabled only for features the demo actually uses.

## Resource Review

- `Tenant`, `MaaSModelRef`, `ExternalModel`, `MaaSSubscription`, and
  `MaaSAuthPolicy` manifests use fields confirmed by official docs or
  installed CRD schema.
- Resource namespaces match the active controller behavior and are not guessed
  from mixed examples.
- Each published local model has a healthy underlying serving resource before
  it is exposed through MaaS.
- Each external model has a provider Secret, provider endpoint, target model
  ID, subscription, authorization policy, and explicit Technology Preview
  label.
- External model resource names are valid DNS-1035 labels because the MaaS
  controller creates Kubernetes Services from the `ExternalModel` name. Keep
  provider model IDs containing dots in `spec.targetModel`, not in
  `metadata.name`.
- External provider Secrets use the official MaaS label
  `inference.networking.k8s.io/bbr-managed=true` and contain the provider token
  under data key `api-key`; otherwise the external route can be Ready while
  provider requests fail with `provider '<name>' credentials not found`.
- Each subscription includes at least one token rate limit per model ref and a
  supported time window such as seconds, minutes, or hours.
- Subscription priority is intentional when groups overlap.
- Metering metadata is included on authorization policies when showback or
  cost-center reporting is claimed.
- Authorization policy subjects match the intended groups/users and model refs.

## API Key And Access Review

- Users have both subscription quota and gateway authorization before access is
  claimed.
- Dashboard and Gateway discovery are validated with real demo user tokens, not
  inferred from MaaS CR readiness. The RHOAI dashboard
  `/gen-ai/api/v1/maas/models` path and the Gateway
  `/maas-api/v1/subscriptions` path must return usable model/subscription data
  for an allowed user before claiming the AI asset endpoints experience.
- The Gateway/AuthPolicy path injects `X-MaaS-Username` and `X-MaaS-Group` into
  `maas-api` requests. If `maas-api` logs `Missing or empty username header`,
  investigate Kuadrant/AuthPolicy/EnvoyFilter behavior before changing MaaS
  model or subscription CRs. Do not codify patches against generated Kuadrant
  `AuthPolicy` or EnvoyFilter resources unless official Red Hat documentation
  or support guidance requires that exact change.
- API keys are never committed or embedded in notebooks/manifests.
- Persistent keys are stored in an approved secret store.
- API key expiration limits are documented and align with the `Tenant` max.
- Validation must create a temporary MaaS API key for an allowed demo user,
  use it against the OpenAI-compatible inference endpoint, verify response
  token usage, and revoke the key before declaring the MaaS endpoint functional.
- External OpenAI `gpt-4o-mini` validation uses the standard Chat Completions
  `max_tokens` field. Provider-specific OpenAI API compatibility errors must
  be fixed in the client payload, not hidden by MaaS readiness checks.
- If direct external GPT tool calling is claimed, validate it with a
  MaaS API-key-authenticated Chat Completions request that includes a simple
  function schema and returns `tool_calls`. Do not infer GPT tool calling from
  MaaS CR readiness or model listing.
- Do not validate `/v1/chat/completions` with raw OpenShift OAuth tokens. The
  generated AuthPolicy permits Kubernetes tokens for discovery paths such as
  `/v1/models`; inference requests use `Authorization: Bearer <maas-api-key>`.
- Group membership changes include API key revocation/recreation guidance when
  immediate access change is required.
- External OIDC users use MaaS API key management flows rather than dashboard
  flows.

## Gen AI Playground Access Review

- If the stage claims the Gen AI Playground experience, validate the existing
  project `LlamaStackDistribution` and generated deployment in addition to MaaS
  CR readiness.
- Dashboard-created placeholder MaaS endpoint tokens are replaced by
  Secret-backed MaaS API key references before model prompts are tested.
- Old persistent Playground API keys are revoked or rotated when the Secret is
  recreated.
- The Playground Llama Stack config maps the local Nemotron model and external
  OpenAI `gpt-4o-mini` model to MaaS Gateway URLs generated by the product
  workflow. Do not require a diagnostic provider rewrite unless response
  validation proves the generated provider type is incompatible.
- Registered Llama Stack model entries use the validated field
  `provider_model_id` when the external provider ID must be preserved. Prefer
  a provider model ID that is also a valid MaaS resource name for
  Playground-facing demos; if an alias is required, keep the alias only in
  MaaS resource names and URL paths.
- Validation checks Llama Stack `/v1/models` and sends `/v1/responses`
  requests for both MaaS-backed models. Dashboard model listing alone is not
  enough.
- GPT MCP behavior is validated separately from direct GPT function calling.
  When testing external `gpt-4o-mini` with MCP, require an actual
  `mcp_call` through Llama Stack `/v1/responses` and inspect Llama Stack logs
  for external-provider token-limit errors before changing MaaS resources.
- Validation checks the dashboard BFF `/gen-ai/api/v1/lsd/responses` path with
  real user credentials. Use both `Authorization: Bearer <user-token>` and
  `x-forwarded-access-token: <user-token>` for non-browser tests.

## Observability Review

- Kuadrant observability is enabled before claiming rate-limit metrics.
- `Tenant` telemetry is enabled before claiming MaaS model-usage metrics.
- Dashboard observability is labeled Technology Preview.
- Showback language is used instead of billing-grade metering or external
  invoicing claims.
- Privacy-sensitive telemetry fields such as user and group capture are
  reviewed before enablement.

## Working Configuration Regression Gates

Use `working-configuration.md` as a mandatory preflight for Stage 220 rebuilds,
RHOAI upgrades, RHCL upgrades, or MaaS troubleshooting.

- `DataScienceCluster` has KServe and `kserve.modelsAsService` managed.
- Llama Stack Operator and `genAiStudio` are enabled when Gen AI Studio,
  Playground, or AI asset endpoints are in scope.
- MaaS CRDs resolve to the installed API group/version before GitOps changes
  are made.
- RHCL installed CSV matches the pinned MaaS-compatible CSV unless a newer CSV
  has already passed full Gateway, dashboard, API, and model access validation.
- `models-as-a-service-db` is not Kueue-managed, and the demo-local PostgreSQL
  StatefulSet runs there instead of the MaaS model namespace.
- Demo-local PostgreSQL with `sslmode=disable` is documented as a demo
  exception. Production-like guidance uses a managed PostgreSQL 14+ service and
  TLS-protected connection such as `sslmode=require`.
- External model Kubernetes resource names are DNS-safe aliases, with provider
  IDs kept in `ExternalModel.spec.targetModel`.
- Generated Kuadrant `AuthPolicy`, `TokenRateLimitPolicy`, and `EnvoyFilter`
  resources are observed for health but not hand-authored or patched in GitOps.
- Validation includes real dashboard AI asset endpoint calls and Gateway
  `/maas-api/v1/subscriptions` calls as allowed demo users.
- Validation includes real MaaS API key creation, authenticated Nemotron
  inference through the MaaS Gateway, structured tool-call output, token usage,
  external OpenAI function calling through the same MaaS Gateway, token usage,
  and key revocation.
- Validation includes the Gen AI Playground/Llama Stack response path when a
  playground exists in the demo project.
- Validation includes the dashboard BFF response path when the stage claims the
  product Playground experience, because direct Llama Stack success is not
  sufficient evidence for the browser workflow.
- Validation confirms unauthenticated inference is rejected, so model readiness
  is not mistaken for public access.
- Validation checks that generated model auth and rate-limit policies are
  enforced and that recent Gateway logs do not show generated filter rejection.
- Stage plans and operations docs are updated from the working configuration
  when a live issue changes the design.

## Readonly Verification Commands

Run only after the OpenShift safety guard in `AGENTS.md` is satisfied:

```bash
oc get dsc default-dsc -n redhat-ods-operator -o yaml
oc get odhdashboardconfig -n redhat-ods-applications
oc get certmanager cluster
oc get deployment cert-manager cert-manager-cainjector cert-manager-webhook -n cert-manager
oc get subscription rhcl-operator -n openshift-operators
oc get subscription rhcl-operator -n openshift-operators \
  -o jsonpath='{.spec.installPlanApproval}{" "}{.spec.startingCSV}{" "}{.status.installedCSV}{"\n"}'
oc get kuadrant kuadrant -n kuadrant-system
oc get authorino authorino -n kuadrant-system
oc get gatewayclass
oc get secret maas-gateway-tls -n openshift-ingress
oc get gateway maas-default-gateway -n openshift-ingress -o yaml
oc get secret maas-db-config -n redhat-ods-applications
oc get secret maas-db-config -n redhat-ods-applications \
  -o jsonpath='{.data.DB_CONNECTION_URL}' | base64 -d
oc api-resources | grep -i maas
oc get crd maasauthpolicies.maas.opendatahub.io \
  maasmodelrefs.maas.opendatahub.io \
  maassubscriptions.maas.opendatahub.io \
  externalmodels.maas.opendatahub.io \
  tenants.maas.opendatahub.io
oc get tenants.maas.opendatahub.io -n models-as-a-service
oc get tenants.maas.opendatahub.io default-tenant -n models-as-a-service -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}'
oc get maasmodelrefs -A
oc get maassubscriptions -A
oc get maasauthpolicies -A
oc get externalmodels.maas.opendatahub.io -A
oc get authpolicy,tokenratelimitpolicy -n models-as-a-service
oc get envoyfilter -n openshift-ingress
oc logs -n openshift-ingress \
  -l gateway.networking.k8s.io/gateway-name=maas-default-gateway --since=10m
oc logs -n redhat-ods-applications deploy/maas-api --since=10m
```

Use schema checks before durable GitOps authoring:

```bash
oc explain maasmodelrefs.maas.opendatahub.io.spec
oc explain maassubscriptions.maas.opendatahub.io.spec
oc explain maasauthpolicies.maas.opendatahub.io.spec
oc explain externalmodels.maas.opendatahub.io.spec
oc explain tenants.maas.opendatahub.io.spec
```

If `oc api-resources` reports `MaaSModelRef`, `MaaSSubscription`, or
`MaaSAuthPolicy` under a group other than `maas.opendatahub.io`, use the
installed group/version for schema validation and record the discrepancy in the
stage `PLAN.md`.

## Failure Conditions

Do not approve a MaaS change when:

- a README claims governed model access but GitOps lacks matching
  subscription and authorization policy
- the implementation bypasses MaaS for shared OpenAI `gpt-4o-mini` demo access
  without an explicit documented exception
- provider API keys or MaaS API keys appear in repository files
- a claimed MaaS-backed Gen AI Playground still uses placeholder endpoint
  tokens, stale API keys, or unvalidated Llama Stack provider mappings
- token limits are absent from a model subscription
- preview features are described as generally available
- external provider limits are ignored in capacity planning
- a GPT MCP failure is treated as missing tool-calling support without first
  validating direct Chat Completions function calling and checking for
  external-provider `Request too large`, `rate_limit_exceeded`, or
  `tokens per min` errors
- stale API keys remain after a group removal where immediate revocation is
  required
- exact CR fields are copied from memory instead of official docs or installed
  schema
- dashboard AI asset endpoints cannot load MaaS models for an allowed user
- API-key creation, inference with `sk-oai-*`, token-usage capture, or API-key
  revocation fails for an allowed user
- `maas-api` reports missing `X-MaaS-Username` or `X-MaaS-Group` headers on
  Gateway-routed requests
- `maas-api` reports `lookup maas-postgres.models-as-a-service.svc.cluster.local`
  after the database has been moved to `models-as-a-service-db`; update
  `maas-db-config` and restart `deployment/maas-api`
