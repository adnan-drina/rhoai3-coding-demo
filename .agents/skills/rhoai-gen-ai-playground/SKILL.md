---
name: rhoai-gen-ai-playground
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when documenting, reviewing, or operating Red Hat OpenShift AI Gen AI
  studio playground workflows: enabling the playground dashboard feature,
  preparing AI asset endpoints, configuring project playgrounds, testing
  models, comparing models side by side, using playground RAG uploads and RAG
  chunk settings, saving reusable prompts in MLflow, configuring and testing
  MCP servers, creating custom internal or external endpoints, exporting
  playground Python templates, updating or deleting playgrounds, and
  troubleshooting playground response, RAG, or MCP behavior. Do NOT use for
  Llama Stack server/provider/vector-store configuration (use
  rhoai-llama-stack), model-serving runtime configuration (use
  rhoai-model-serving-platform), dashboard-wide feature flag authoring beyond
  playground-related fields (use rhoai-dashboard-customization), custom app
  chatbot code (use rhoai-chatbot-customization), NeMo/FMS Guardrails product
  safety controls (use rhoai-guardrails-safety), or live cluster changes
  without the OpenShift safety guard.
---

# RHOAI Gen AI Playground

Use this skill for OpenShift AI Gen AI studio playground work on the active
product baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product workflow details.
Official Red Hat documentation is product authority. This skill adapts the
official gen AI playground guide to this repo's demo workflow and GitOps review
model.

## Scope

This skill covers:

- Gen AI studio playground Technology Preview support posture
- dashboard and project prerequisites for playground use
- `OdhDashboardConfig` fields specific to Gen AI studio and custom endpoints
- AI asset endpoints for project models, custom endpoints, MaaS models, and MCP
  servers
- model and vLLM runtime requirements for RAG and MCP tool-calling behavior
- configuring a playground from Gen AI studio -> Playground or AI asset
  endpoints
- creating internal and external custom endpoints
- model experimentation, temperature, streaming, system instructions, and
  side-by-side comparison
- playground RAG uploads, inline vector database limitations, and chunking
  settings
- reusable prompt save/load workflows backed by MLflow
- MCP server configuration, browser-session authorization, and tool testing
- exporting playground configuration as a Python template
- updating or deleting project playgrounds
- troubleshooting playground response, RAG, and MCP issues

Use other skills for adjacent work:

- `rhoai-llama-stack` for Llama Stack Operator activation,
  `LlamaStackDistribution`, providers, vector stores, Responses API behavior,
  OAuth/ABAC, CA trust, and HA/autoscaling
- `rhoai-autorag` for Gen AI studio AutoRAG optimization runs, remote Milvus
  prerequisites, RAG pattern leaderboard review, and generated notebooks
- `rhoai-model-serving-platform` for KServe, vLLM, model-serving runtimes,
  runtime arguments, and model deployment settings
- `rhoai-model-deployment` for deploying project models as AI asset endpoints,
  routes, token authentication, and runtime-specific endpoint smoke tests
- `rhoai-dashboard-customization` for broader `OdhDashboardConfig` behavior and
  dashboard feature flags
- `rhoai-model-catalog-workflows` for catalog discovery and deployment into an
  AI asset endpoint before playground testing
- `rhoai-model-management-monitoring` for operating deployed models behind AI
  asset endpoints
- `rhoai-mlflow` for MLflow availability, workspace access, and prompt
  persistence storage checks
- `rhoai-users-groups-access` and `rhoai-access-group-selection` for user and
  group access prerequisites
- `rhoai-chatbot-customization` for custom demo chatbot application code,
  prompts, and UI behavior outside the product playground
- `rhoai-guardrails-safety` for product guardrails, detector services,
  validation-only checks, and guarded generation around playground endpoints
- `rhoai-evaluation` for official EvalHub, LM-Eval, and automated risk
  assessment workflows beyond exploratory playground testing
- `rhoai-model-evaluation` for legacy repo-specific RAGAS, custom judge, and
  Step 08 evaluation rebuild details
- `rhoai-maas-governance` for governed MaaS endpoint access and external model
  provider access

## Demo Policy

For this repo:

- Treat Gen AI studio playground, AI asset endpoints, custom endpoints,
  multi-model comparison, and prompt management as Technology Preview unless
  the active baseline changes.
- Use the playground to demonstrate exploratory model selection and prompt/RAG
  iteration, not as formal evaluation evidence by itself.
- Prefer project-local AI asset endpoints for private model demos.
- For external OpenAI or other third-party endpoints, document that Responses
  API data, RAG context, MCP tool results, and user input can leave the
  cluster.
- Keep endpoint tokens and provider API keys in Kubernetes Secrets; never
  commit secret values.
- Do not claim the playground RAG upload path supports external or remote
  vector databases. The official guide says this path uses an inline vector
  database.
- Before relying on RAG or MCP behavior, verify the selected model supports
  tool calling and that the vLLM runtime has the required tool-calling
  arguments.
- Treat exported Python as a starting template, not a runnable application.
- Warn users that updating a playground deletes the inline vector database for
  all users in the project.
- Warn users that deleting a playground removes it for all users in the
  project.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/source-capture.md` and
   `references/official-doc-extraction.md`.
3. Decide whether the task is:
   - cluster or dashboard prerequisite review
   - AI asset endpoint review
   - custom endpoint enablement
   - playground creation or model selection
   - RAG upload and chunking
   - reusable prompt management
   - MCP server setup or testing
   - export, update, delete, or troubleshooting
4. Use `examples/gen-ai-playground-patterns.md` for focused review patterns.
5. Validate with `references/validation-checklist.md`.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/gen-ai-playground-patterns.md`
