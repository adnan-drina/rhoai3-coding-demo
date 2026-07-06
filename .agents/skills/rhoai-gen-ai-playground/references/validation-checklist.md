# Validation Checklist

Use this checklist before accepting Gen AI studio playground documentation,
runbooks, GitOps changes, or demo scripts.

## Source Alignment

- Product links use the active baseline in `docs/PLATFORM_BASELINE.md`.
- The official gen AI playground source is recorded when the workflow is
  introduced.
- Playground, AI asset endpoints, custom endpoints, multi-model comparison, and
  prompt management are labeled Technology Preview in user-facing material.
- Llama Stack server and provider details are checked with
  `rhoai-llama-stack`.
- Model-serving runtime details are checked with
  `rhoai-model-serving-platform`.
- Dashboard-wide feature flag behavior is checked with
  `rhoai-dashboard-customization`.

## Prerequisite Review

- OpenShift AI is installed on an OpenShift cluster that meets the documented
  version prerequisite.
- Dashboard configuration includes `spec.dashboardConfig.genAiStudio: true`.
- OpenShift AI user and administrator group prerequisites are satisfied when
  groups are used.
- The Llama Stack Operator is enabled through `DataScienceCluster`.
- Required MCP servers are configured before MCP workflows are demonstrated.
- The project exists and the user has access.
- Required project connections exist.
- At least one model is deployed and added as an AI asset endpoint.

## Model And Runtime Review

- The selected model supports tool calling before using RAG or MCP.
- The selected model has enough context length for the intended RAG documents
  and conversation history.
- vLLM runtime arguments are reviewed for tool calling:
  `--enable-auto-tool-choice`, `--tool-call-parser`, and any required
  `--chat-template`.
- Chat template paths use `/opt/app-root/template/` and are not relative.
- Demo model choices are not copied from official examples unless the project
  intentionally chooses them.

## AI Asset Endpoint Review

- AI asset endpoints are scoped to the selected project.
- Project-local model deployments are marked as AI asset endpoints before
  playground testing.
- Custom endpoints are enabled only when required.
- External provider endpoints are enabled only after data egress and security
  posture are documented.
- Endpoint tokens and provider API keys are stored in Secrets and are not
  committed.
- Verify model is used when creating custom endpoints.

## MaaS-Backed Playground Review

- MaaS-backed playground use is paired with `rhoai-maas-governance` and
  validates subscription, authorization policy, API key, and Gateway behavior.
- A dashboard-created project `LlamaStackDistribution` does not rely on
  placeholder endpoint tokens. Token environment variables are backed by a
  project Secret, and the Secret value is not committed.
- The generated Llama Stack deployment reflects the Secret-backed token env.
  If the operator fails to merge `valueFrom` over literal placeholder values,
  recreate the generated deployment and let the operator render it again.
- The Llama Stack config maps the local MaaS-published Nemotron model through
  the MaaS vLLM provider.
- External OpenAI `gpt-4o-mini` published through MaaS uses the same stable
  model identity for the MaaS resource name and provider target model ID.
- External GPT tool-calling claims are validated separately from MCP. A simple
  OpenAI-compatible MaaS Chat Completions request with a function schema should
  return `tool_calls` before claiming direct GPT function calling works.
- Registered model entries use `provider_model_id` only when the product
  generated config needs an explicit provider target. Do not use unverified
  field names copied from memory.
- Playground validation uses the model IDs returned by Llama Stack
  `/v1/models`, which can be provider-qualified.
- Validation sends real `/v1/responses` requests from inside the Llama Stack
  pod for each MaaS-backed model before claiming the playground works.
- Validation checks the dashboard BFF
  `/gen-ai/api/v1/lsd/models?namespace=<project>` model list and confirms the
  external GPT entry exposes `gpt-4o-mini`.
- Validation also sends `/gen-ai/api/v1/lsd/responses` requests through the
  dashboard BFF with a real user token before claiming the browser Playground
  works. Non-browser BFF tests need both `Authorization: Bearer <user-token>`
  and `x-forwarded-access-token: <user-token>`.

## Playground Workflow Review

- Dashboard path is Gen AI studio -> Playground or Gen AI studio -> AI asset
  endpoints.
- Playground creation selects the project containing the model deployment.
- Each selected model is classified as inference or embedding.
- The loaded playground shows the selected model in the Model tab and header.
- Temperature, streaming, and system instructions are recorded when they matter
  to results.
- Multi-model comparison is labeled Technology Preview and requires at least
  two available models.

## RAG Review

- Playground RAG upload is documented as using an inline vector database.
- External or remote vector database support is not claimed for the playground
  upload path.
- Uploaded files match supported types: PDF, DOC, or CSV.
- Upload limits are respected: up to 10 files and 10 MB per file.
- Chunk length, chunk overlap, and delimiter settings are recorded when they
  affect results.
- System instructions explicitly direct use of knowledge search when the model
  otherwise ignores uploaded documents.

## Prompt Management Review

- Prompt management is labeled Technology Preview.
- MLflow availability in the project is confirmed before promising persistent
  prompts.
- Saved prompts are described as project-scoped and versioned.
- Prompt names, versions, and commit messages are captured when used for demo
  evidence.

## MCP Review

- MCP server entries come from the platform-level `gen-ai-aa-mcp-servers`
  `ConfigMap` in `redhat-ods-applications`.
- MCP server data keys are unique and case-sensitive.
- MCP server values are valid JSON.
- OpenShift cluster-context MCP demos use the newer
  `openshift/openshift-mcp-server` source and Red Hat preview guidance, not the
  older generic server pattern.
- The OpenShift MCP server is labeled Developer Preview or Technology Preview
  in user-facing material.
- The OpenShift MCP server runs with `read_only = true`.
- The OpenShift MCP server uses `list_output = "table"` for compact list
  results.
- The OpenShift MCP server enables only required toolsets.
- The OpenShift MCP server uses an `enabled_tools` allowlist for the specific
  demo inspection tools, so Llama Stack does not expose an unnecessarily large
  tool schema to the selected model.
- The OpenShift MCP server has enough memory for tool-list handling and does
  not show recent `OOMKilled` restarts.
- Sensitive resource types are denied in the MCP server config: `Secret`,
  `ConfigMap`, `Role`, `RoleBinding`, `ClusterRole`, and
  `ClusterRoleBinding`.
- ServiceAccount/RBAC grants are reviewed as a separate context-access
  boundary from MaaS model access.
- The MCP Service URL in `gen-ai-aa-mcp-servers` points to a ready Service with
  endpoints.
- The selected model supports tool calling.
- The selected model has enough served context and a small enough output-token
  budget for MCP context. For the Stage 220 MaaS-published Nemotron model,
  validate `--max-model-len=131072` on the `LLMInferenceService` and a
  512-token provider default before demonstrating MCP.
- For Stage 220, use Nemotron as the primary OpenShift MCP demo model. External
  `gpt-4o-mini` can complete bounded MCP calls through Llama Stack, but broad
  MCP prompts can send large tool schemas or results to the external provider
  and fail with `Request too large`, `rate_limit_exceeded`, or
  `tokens per min` even though GPT function calling is enabled.
- The OpenShift MCP allowlist avoids broad cluster-wide list tools such as
  `namespaces_list`, `pods_list`, broad event listing, and log tools; use
  bounded tools such as `pods_list_in_namespace`, `pods_get` for known pods,
  and node status.
- Token authorization behavior is documented as browser-session scoped.
- The demo verifies MCP through the Llama Stack Responses API. At minimum,
  validation must prove that the project Llama Stack server receives an
  `mcp_list_tools` response from the configured server; when model/tool
  behavior is the claim, validation must also prove a real `mcp_call`.

## Export, Update, And Delete Review

- Exported Python is described as a template, not a runnable script.
- Exported code is checked for the expected model, parameters, RAG files, and
  MCP tools.
- Updating a playground is documented as permanently deleting the inline vector
  database for all project users.
- Deleting a playground is documented as removing the playground for all users
  in the project.

## Optional Read-Only Checks

Run only after following the OpenShift safety guard in `AGENTS.md`:

```bash
oc get odhdashboardconfig -A -o yaml
oc get datasciencecluster -A -o yaml
oc get configmap gen-ai-aa-mcp-servers -n redhat-ods-applications -o yaml
oc get deployment,service,endpoints -n rhoai-mcp
oc get configmap openshift-mcp-config -n rhoai-mcp -o yaml
oc get pods -A | rg 'lsd-genai-playground|predictor'
```

Schema checks:

```bash
oc explain odhdashboardconfig.spec.dashboardConfig
oc explain odhdashboardconfig.spec.genAiStudioConfig
oc explain datasciencecluster.spec.components.llamastackoperator
```

## Fail Conditions

Stop and correct the work if any of these are true:

- The playground is presented as production-supported without Technology
  Preview context.
- External provider endpoints are enabled without documenting that user input,
  RAG context, and MCP tool results can leave the cluster.
- Provider tokens or API keys are committed.
- A MaaS-backed playground still uses literal placeholder tokens such as
  `fake`.
- A MaaS-backed external OpenAI playground route uses a vLLM provider and fails
  on `max_tokens` instead of using an OpenAI-compatible provider through MaaS.
- The playground RAG upload path is described as using an external or remote
  vector database.
- RAG or MCP behavior is promised without checking model tool-calling support
  and runtime arguments.
- GPT MCP failures are interpreted as lack of tool-calling support without
  checking direct MaaS Chat Completions function calling and Llama Stack logs
  for external-provider token-limit errors.
- OpenShift MCP is exposed with write-capable tools, missing denied-resource
  configuration, or no explicit preview-status caveat.
- Updating a playground omits the inline vector database deletion warning.
- Exported Python is presented as a complete runnable application.
