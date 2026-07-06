---
name: rhoai-guardrails-safety
metadata:
  author: rhoai3-demo
  version: 1.1.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when documenting, reviewing, deploying, or operating Red Hat OpenShift AI
  guardrails and AI safety workflows from the official guardrails guide:
  NeMo Guardrails, NemoGuardrails custom resources, TrustyAI-managed guardrails
  services, built-in Presidio and regex detectors, validation-only guardrail
  checks, guarded chat completions, service account token authentication to
  model-serving endpoints, NeMo ConfigMaps with config.yaml, prompts.yml,
  rails.co, custom Python actions, LLM self-check rails, separate self-check
  models, OpenTelemetry, input/output/retrieval rails, PII masking, prompt
  injection and jailbreak detection, hate/profanity filtering, industry
  self-check examples, legacy FMS Guardrails, GuardrailsOrchestrator, detector
  serving runtimes, Guardrails Gateway, Llama Stack PII integration, and
  guardrails metrics. Do NOT use for chatbot UI prompts alone (use
  rhoai-chatbot-customization), model-serving platform setup (use
  rhoai-model-serving-platform), Llama Stack platform configuration (use
  rhoai-llama-stack), formal evaluation and automated risk assessment (use
  rhoai-evaluation), observability stack setup (use rhoai-observability), or
  live cluster changes without the OpenShift safety guard.
---

# RHOAI Guardrails Safety

Use this skill for official Red Hat OpenShift AI guardrails and AI safety
workflows on the active product baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior details.
Official Red Hat documentation is product authority. This skill adapts the
official Guardrails guide to this repo's GitOps and README review model.

## Scope

This skill covers:

- NeMo Guardrails for new RHOAI guardrailing work
- `NemoGuardrails` custom resources managed by the TrustyAI Operator
- NeMo standalone built-in detector quickstart with no LLM calls
- `/v1/guardrail/checks` validation-only workflows
- `/v1/chat/completions` guarded generation workflows
- Presidio sensitive-data detection and regex detection
- service account and Secret-based authentication to internal model endpoints
- ConfigMap-based NeMo configuration with `config.yaml`, `prompts.yml`, and
  `rails.co`
- custom Python actions, self-check input/output rails, and separate
  self-check models
- OpenTelemetry configuration and performance considerations for NeMo
- NeMo library flows for input, output, retrieval, and statistics
- common safety patterns: PII detection, PII masking, prompt injection,
  jailbreak, hate speech, profanity, and combined guardrails
- industry self-check examples for financial services, telecommunications,
  and custom policies
- legacy FMS Guardrails workflows when required by existing examples or
  migration analysis
- `GuardrailsOrchestrator`, built-in detectors, Hugging Face detector serving
  runtimes, Guardrails Gateway, OpenTelemetry, and metrics for FMS
- Llama Stack PII detection integration through FMS Guardrails

Use other skills for adjacent work:

- `rhoai-model-serving-platform` for KServe, vLLM, `ServingRuntime`, and
  `InferenceService` platform configuration
- `rhoai-model-management-monitoring` for deployed model operations and model
  metrics outside guardrails-specific metrics
- `rhoai-llama-stack` for Llama Stack distributions, providers, RAG, OAuth,
  ABAC, and OpenAI-compatible API behavior
- `rhoai-gen-ai-playground` for product playground testing and prompt export
  workflows
- `rhoai-evaluation` for EvalHub, LM-Eval, automated risk assessment, Garak,
  judge models, and formal safety evaluation
- `rhoai-observability` for platform observability, OpenTelemetry Collector,
  Prometheus, Alertmanager, and Tempo setup
- `ocp-opentelemetry` for Red Hat build of OpenTelemetry Operator, Collector,
  instrumentation, and telemetry-pipeline behavior below guardrails-specific
  telemetry semantics
- `ocp-distributed-tracing` for Tempo Operator, `TempoStack`, tenants, trace
  RBAC, and distributed tracing backend behavior below guardrails-specific
  telemetry semantics
- `rhoai-api-tiers` for `trustyai.opendatahub.io/v1alpha1`,
  `serving.kserve.io`, and Llama Stack API support posture
- `rhoai-chatbot-customization` for repo-specific chatbot UI behavior and
  prompt text after product guardrails are selected

## Demo Policy

For this repo:

- Prefer NeMo Guardrails for new guardrailing and safety controls.
- Treat FMS Guardrails as legacy; use it only when an official example or
  migration need requires FMS-specific behavior.
- Keep the TrustyAI component `Managed` before deploying either NeMo or FMS
  guardrails resources.
- Enable route authentication for shared demo guardrails services with
  `security.opendatahub.io/enable-auth: 'true'`.
- Store model API keys and service account tokens in Kubernetes Secrets. Do
  not put real tokens or external API keys in ConfigMaps or committed files.
- Use `/v1/guardrail/checks` for validation-only gates, including pre-LLM,
  RAG retrieval, and tool payload validation.
- Use `/v1/chat/completions` only when the guardrails service should proxy and
  guard generation through a model endpoint.
- Keep policy prompts, custom rails, and Python actions reviewed as code.
- For European enterprise READMEs, frame guardrails as safety controls and
  policy enforcement, not as proof that the system is compliant or risk-free.
- Pair guardrails with `rhoai-evaluation` when the claim requires measured
  evidence, adversarial testing, or benchmark results.
- Verify detector images and model artifacts before committing them. Treat
  testing registries or upstream examples as examples only unless product
  provenance is documented.

## Live-Verified Platform Behaviors (RHOAI 3.4, Stage 240, 2026-07-05)

These behaviors were verified on a live cluster and are not documented in
the official guide; account for them before authoring NeMo configurations:

- The RHOAI NeMo server does not substitute `${VAR}` placeholders in
  `config.yaml`; it loads the raw YAML and merges `MAIN_MODEL_ENGINE` /
  `MAIN_MODEL_BASE_URL` environment values over it per request. Never set
  `api_key` in `config.yaml` — a literal placeholder is sent to the model
  endpoint as the key (401). The OpenAI client falls back to the
  `OPENAI_API_KEY` environment variable from the CR Secret, which works.
- The request `model` field overrides the config main model at runtime, and
  MaaS-governed endpoints authorize per model. Clients (including the Llama
  Stack `remote::nvidia` shield provider, which sends `shield_id` as the
  model) must use the governed model name.
- The server wraps internal failures as HTTP 200: `status: "error"` on
  `/v1/guardrail/checks` and an "Internal server error" assistant message
  on `/v1/chat/completions`. The Llama Stack `remote::nvidia` provider
  treats any non-"blocked" status as no violation, so LLM-rail failures
  masquerade as passes. Always validate that a benign message returns
  `status: "success"` — that is the canary that self-check rails actually
  run.
- Reasoning models (for example Nemotron) spend their first completion
  tokens on the reasoning channel, and the nemoguardrails self-check
  default of `max_tokens: 3` then yields an empty verdict that fails
  closed, blocking everything that reaches the LLM rail. Set per-task
  `max_tokens` (for example 512) in `prompts.yml`; prompt toggles such as
  `/no_think` do not disable reasoning on the vLLM build tested.
- With `security.opendatahub.io/enable-auth: 'true'`, the TrustyAI operator
  fronts the NeMo container (plain HTTP :8000) with a kube-rbac-proxy
  sidecar (Service 443→8443, bearer token required). Header-less in-cluster
  consumers need an explicit internal Service targeting the container port;
  record that as a demo exception and keep the external route
  authenticated.
- `/v1/guardrail/checks` with a `[user, assistant]` message pair runs input
  rails over the user message and output rails over the assistant message —
  this is how Llama Stack output shields work through the
  `remote::nvidia` provider.
- The TrustyAI component flip in the shared `DataScienceCluster` must be
  protected from the DSC owner's Argo CD selfHeal via an
  `ignoreDifferences` entry for `/spec/components/trustyai`, like every
  other later-stage component flip.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/source-capture.md` and
   `references/official-doc-extraction.md`.
3. Decide whether the task is:
   - NeMo standalone validation
   - NeMo guarded model endpoint
   - NeMo custom rails or policy prompts
   - NeMo OpenTelemetry
   - FMS legacy orchestrator, detector, or gateway work
   - Llama Stack PII integration through FMS
   - guardrails README or architecture narrative
4. Use `examples/guardrails-safety-patterns.md` for compact review patterns.
5. For live cluster work, follow the OpenShift safety guard in `AGENTS.md`.
6. Validate with `references/validation-checklist.md`.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/guardrails-safety-patterns.md`
