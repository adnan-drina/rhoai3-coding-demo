---
name: rhoai-maas-governance
metadata:
  author: rhoai3-demo
  version: 1.2.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when documenting, reviewing, or rebuilding Red Hat OpenShift AI
  Models-as-a-Service governance from the official guide: MaaS enablement,
  Red Hat Connectivity Link and Kuadrant prerequisites, Gateway API and
  Authorino TLS prerequisites, PostgreSQL API key database secret,
  DataScienceCluster and OdhDashboardConfig MaaS feature flags, Tenant,
  MaaSModelRef, ExternalModel, MaaSSubscription, MaaSAuthPolicy, subscription
  priority and token limits, API key lifecycle, OpenAI-compatible MaaS
  endpoints, observability and usage export, external OIDC authentication, and
  governed external model providers such as OpenAI. Do NOT use for standard
  model deployment without MaaS (use rhoai-model-deployment), model-serving
  platform/runtime setup (use rhoai-model-serving-platform), Llama Stack RAG or
  providers (use rhoai-llama-stack), playground-only testing (use
  rhoai-gen-ai-playground), or live cluster changes without the OpenShift
  safety guard.
---

# RHOAI Models-as-a-Service Governance

Use this skill for governed LLM access through Red Hat OpenShift AI
Models-as-a-Service on the active product baseline in
`docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md`,
`references/official-doc-extraction.md`, and
`references/working-configuration.md` before using product behavior details.
Official Red Hat documentation is product authority. The working configuration
captures repo-validated design decisions and implementation traps; it does not
override official docs or installed CRD schema.

## Scope

This skill covers:

- MaaS versus standard model serving decision criteria
- subscription-based quota management, priority, and token limits
- self-service and administrator API key lifecycle
- MaaS CRDs: `Tenant`, `MaaSModelRef`, `ExternalModel`, `MaaSSubscription`,
  and `MaaSAuthPolicy`
- Red Hat Connectivity Link Operator, `Kuadrant`, Gateway API, and Authorino
  TLS prerequisites
- PostgreSQL database secret for API key lifecycle management
- `DataScienceCluster` and `OdhDashboardConfig` MaaS feature flags
- publishing local llm-d or vLLM models and external provider models through
  MaaS
- group/user access through subscriptions plus authorization policies
- MaaS management through the dashboard, CLI, API, and GitOps-managed CRs
- OpenAI-compatible inference endpoints under `/llm/{model-name}/v1`
- MaaS observability, Kuadrant observability, telemetry, and usage export
- external OIDC authentication for MaaS users
- external model routing through `ExternalModel` and provider-key Secrets
- administrator and user troubleshooting for 401, 403, 404, token limit, and
  subscription phase failures

Use other skills for adjacent work:

- `rhoai-model-serving-platform` for KServe/vLLM/NIM serving platform
  enablement, runtime templates, and runtime arguments
- `rhoai-model-deployment` for direct model deployment, routes, endpoint token
  lookup, and runtime-specific smoke tests outside MaaS
- `rhoai-distributed-inference-llmd` for `LLMInferenceService`, Gateway
  discovery, Connectivity Link auth, scheduler, autoscaling, and flow-control
  details before MaaS governance is layered on top
- `rhoai-model-management-monitoring` for deployed-model operations before or
  below the MaaS governance layer
- `rhoai-gen-ai-playground` for exploratory product playground testing of AI
  asset endpoints and MaaS endpoints
- `rhoai-llama-stack` for Llama Stack distributions, providers, vector stores,
  RAG, and Responses API workflows
- `rhoai-central-authentication-service` for broader external OIDC
  authentication service behavior outside MaaS
- `rhoai-dashboard-customization` for general `OdhDashboardConfig` feature
  flags and dashboard navigation behavior
- `rhoai-observability` and `rhoai-monitoring-trustyai` for platform
  observability and TrustyAI monitoring beyond MaaS usage telemetry
- `rhoai-api-tiers` for support posture review of MaaS-related APIs

## Demo Policy

For this repo:

- Use MaaS when the demo needs centralized LLM governance, group-based access,
  token limits, API keys, usage tracking, showback, or GitOps-managed model
  access policy.
- Keep direct standard model serving for single-team, single-user, or
  prototype paths where MaaS governance overhead is unnecessary.
- Treat vLLM runtime support with MaaS, external models, external OIDC
  authentication, and the MaaS observability dashboard as Technology Preview
  unless the active baseline changes.
- Expose the primary local model `nemotron-3-nano-30b-a3b` through MaaS only
  after the underlying serving endpoint and Gateway/API compatibility are
  verified.
- Register external OpenAI `gpt-4o-mini` through the MaaS `ExternalModel` path
  when external provider access is required. Use `gpt-4o-mini` as the
  Kubernetes/MaaS resource name and keep `spec.targetModel: gpt-4o-mini` as
  the provider model ID. Prefer provider model IDs that are also valid
  Kubernetes Service names for Playground-facing demos; otherwise document the
  resource-name alias and validate the UI path explicitly. The ExternalModel
  controller creates Kubernetes Services from the resource name, so dotted
  names fail Service validation.
  Do not bypass MaaS for shared demo access to external OpenAI models unless
  the project explicitly documents a different governance decision.
- Store MaaS PostgreSQL credentials, provider API keys, API keys, and endpoint
  tokens in Kubernetes Secrets or an approved secret store. Never commit secret
  values.
- Require both a matching `MaaSSubscription` and `MaaSAuthPolicy` before
  claiming a user or group can access a MaaS model.
- Revoke and recreate API keys after group membership changes when immediate
  access revocation or new group access must be reflected.
- Use MaaS usage metrics for internal showback and capacity planning, not
  billing-grade external invoicing.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/source-capture.md` and
   `references/official-doc-extraction.md`.
3. Read `references/working-configuration.md` before changing Stage 220,
   authoring new MaaS manifests, or debugging MaaS rollout behavior.
4. Decide whether the task is:
   - phase-one MaaS prerequisite enablement before MaaS CRDs exist
   - MaaS prerequisite and enablement review
   - Gateway, Kuadrant, Authorino TLS, or PostgreSQL setup
   - dashboard feature flag review
   - publishing local or external models through MaaS
   - subscription, priority, token-limit, or cost metadata design
   - authorization policy design
   - API key lifecycle management
   - MaaS API or OpenAI-compatible inference client work
   - observability, telemetry, or usage export
   - external OIDC or external provider integration
   - troubleshooting user or admin access errors
5. Use `examples/maas-governance-patterns.md` for compact manifest and review
   patterns.
6. For GitOps implementation, gate work in phases:
   - install/enable prerequisites and DSC/dashboard feature flags
   - rerun live CRD and `oc explain` checks
   - only then commit MaaS model, subscription, auth-policy, and external-model
     resources
7. For live cluster work, follow the OpenShift safety guard in `AGENTS.md`.
8. Validate with `references/validation-checklist.md`, including real
   dashboard and Gateway API checks with demo users.
9. After a new live failure or design correction, update
   `references/working-configuration.md` before considering the stage done.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/working-configuration.md`
- `references/validation-checklist.md`
- `examples/maas-governance-patterns.md`
