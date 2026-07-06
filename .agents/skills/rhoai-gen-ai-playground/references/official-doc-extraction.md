# Official Documentation Extraction

This extraction is derived from the official RHOAI 3.4 guide captured in
`source-capture.md`.

## Support Posture

The gen AI playground is Technology Preview in Red Hat OpenShift AI 3.4.
Technology Preview features are not supported with Red Hat production SLAs,
might not be functionally complete, and are not recommended by Red Hat for
production use.

The captured guide also labels these related areas as Technology Preview:

- AI asset endpoints
- custom endpoints
- multi-model comparison
- prompt management

## Concept Model

The gen AI playground is an interactive environment in the OpenShift AI
dashboard. Users can prototype and evaluate foundation models, custom models,
external model endpoints, RAG behavior, and MCP tool use before building an
application.

The playground settings panel includes these tabs:

- Model: select models and adjust parameters such as temperature and streaming
- Prompt: write, save, and load system instructions
- Knowledge: upload files for RAG or select knowledge sources exposed by the
  product workflow
- MCP: connect to Model Context Protocol servers and authorize tool access

Chat history and parameter settings are not preserved across browser refresh or
session end. Saved prompts are stored in MLflow and persist across sessions.

## Cluster Administrator Prerequisites

Before users configure a playground, the administrator completes platform
setup:

- OpenShift AI is installed on an OpenShift cluster running 4.19 or later.
- Dashboard configuration sets `spec.dashboardConfig.genAiStudio` to `true`.
- If OpenShift AI groups are used, users are added to the relevant
  `rhods-users` and `rhods-admins` groups.
- The Llama Stack Operator is enabled through the `DataScienceCluster` custom
  resource by setting its management state to `Managed`.
- MCP servers are configured when the demo needs playground tool use.

## User Prerequisites

Before using the playground, the user:

- is logged in to OpenShift AI
- belongs to the appropriate OpenShift AI user or administrator group when
  group access is configured
- has created or selected a project
- has added a connection to the project when required by the workflow
- has deployed a model in the project and made it available as an AI asset
  endpoint

## MCP Server Configuration

The official guide configures MCP servers at the platform level with a
`ConfigMap` in `redhat-ods-applications`.

Resource shape:

- `kind: ConfigMap`
- `apiVersion: v1`
- `metadata.name: gen-ai-aa-mcp-servers`
- `metadata.namespace: redhat-ods-applications`
- each `data` key is a unique, case-sensitive MCP server display name
- each `data` value is valid JSON containing server information such as `url`
  and `description`

Verification checks that the `ConfigMap` exists and includes the expected
server key.

## OpenShift MCP Server Pattern For This Demo

When the demo needs an OpenShift cluster-context MCP server, prefer the newer
Red Hat/OpenShift MCP server project and Red Hat preview guidance over older
generic Kubernetes MCP examples.

Source-grounded implementation points:

- Treat the MCP server for Red Hat OpenShift as Developer Preview unless the
  active product baseline changes.
- Use the `openshift/openshift-mcp-server` source for image, chart defaults,
  endpoint shape, configuration, and safety guidance.
- The OpenShift MCP server exposes an HTTP MCP endpoint at `/mcp` when run with
  an HTTP port.
- Run with `read_only = true` for Stage 220-style demos.
- Use `list_output = "table"` for Stage 220-style list tools so MCP tool
  results stay compact when Llama Stack forwards them into the model context.
- Enable only needed toolsets to reduce tool surface and model confusion. For
  the MaaS demo, use `toolsets = ["core", "config"]`.
- Use the OpenShift MCP server `enabled_tools` allowlist for the demo
  inspection tools instead of exposing the whole toolset. A smaller tool
  catalog reduces Llama Stack Responses API context size and improves model
  tool selection.
- Prefer namespace-scoped or known-resource tools such as
  `pods_list_in_namespace`, `pods_get`, and `nodes_top`. Avoid cluster-wide
  `namespaces_list`, `pods_list`, broad event listing, and log tools in the
  Stage 220 Playground demo because the tool result can dominate the external
  provider request.
- Deny sensitive resource access in `config.toml`, especially `Secret`,
  `ConfigMap`, `Role`, `RoleBinding`, `ClusterRole`, and
  `ClusterRoleBinding`.
- Use ServiceAccount/RBAC for in-cluster authentication. A cluster `view`
  binding is acceptable for a broad read-only demo only when paired with MCP
  read-only mode and denied resources.
- Register the server in the RHOAI product discovery ConfigMap:
  `redhat-ods-applications/gen-ai-aa-mcp-servers`.
- Prefer an internal cluster Service URL such as
  `http://openshift-mcp.<namespace>.svc:8080/mcp` for the dashboard-discovered
  server entry.
- Do not enable write-capable MCP tools without a separate agentic-AI stage,
  explicit security review, user approval workflow, and stronger gateway or
  OAuth controls.

## Model And Runtime Requirements

RAG and MCP features rely on model tool-calling behavior. The official guide
calls out these model selection factors:

- tool-calling support, verified from the model card or model documentation
- sufficient context length for RAG documents and conversation history
- vLLM version and configuration

Common runtime arguments called out by the guide:

- `--enable-auto-tool-choice`
- `--tool-call-parser`
- `--chat-template=/opt/app-root/template/<template_file>.jinja`

The chat template path must be absolute and must use `/opt/app-root/template/`
for standard Jinja templates in the Red Hat OpenShift AI image. Relative paths
can cause deployment failure.

If the model or runtime is not configured correctly, RAG document search or MCP
tool execution can fail without a clear user-facing error.

In this demo, MCP tool-list responses are part of the model context and output
budget. For the MaaS-published Nemotron model, Stage 220 uses
`--max-model-len=131072` to match the working code-assistant MaaS
implementation and provide Playground MCP headroom. Keep the Playground vLLM
provider output default conservative, for example 512 tokens, so tool context
and short answers do not compete unnecessarily. A broad tool catalog or a
4096-token output default can still produce context pressure, rate-limit
failures, or empty Playground responses.

The official guide includes a Qwen model example for field placement. Treat it
as an example, not as this demo's default model choice.

## AI Asset Endpoints

The AI asset endpoints page is scoped to the selected project and organizes
available generative AI assets.

Model sources:

- models deployed in the project namespace and marked as AI asset endpoints
- custom endpoints from models in another namespace on the same cluster
- external third-party provider endpoints when enabled
- MaaS models provided through Models as a Service

MCP server assets come from the platform-level MCP server `ConfigMap`.

Users can start playground testing from the AI asset endpoints page by adding a
model to a playground or trying a model in the playground.

## MaaS-Backed Playground Notes For This Demo

When the RHOAI dashboard creates a project playground, it creates a project
`LlamaStackDistribution` and a generated deployment. For MaaS-backed AI asset
endpoints, verify that the generated Llama Stack server has a real MaaS API key
available through a project Secret. Placeholder token values such as `fake`
can let the playground UI load while inference calls fail with `401`
responses from the MaaS Gateway.

For this demo, store the MaaS API key in a project Secret and wire the
`LlamaStackDistribution` environment variables to `valueFrom.secretKeyRef`.
Do not commit the API key. If the generated deployment keeps the old literal
placeholder values, recreate the generated deployment and let the operator
render it from the corrected `LlamaStackDistribution`.

Changing selected Playground models from the dashboard can regenerate the
project `LlamaStackDistribution`, ConfigMap, and deployment. For this demo,
complete the desired model selection first and wait for the
dashboard-generated Playground to become ready before validating. A model
checkbox state in the UI does not prove that the generated Llama Stack backend
can complete requests.

For the local Nemotron model, keep the Llama Stack provider on the MaaS vLLM
route. For the external OpenAI `gpt-4o-mini` model published through MaaS, the
MaaS resource name and provider target model ID intentionally match. This lets
the dashboard-created Playground use one stable model identity instead of a
Kubernetes alias plus a separate upstream model ID.

The AI asset endpoints MaaS tab should display the MaaS resource id
`gpt-4o-mini`. For this model, the governed MaaS asset identity and upstream
OpenAI provider model id are the same.

Use the model IDs returned by Llama Stack `/v1/models`. In the validated demo
configuration they are provider-qualified IDs. The dashboard-generated provider
number can change based on model selection order, for example:

```text
maas-vllm-inference-<n>/nemotron-3-nano-30b-a3b
maas-vllm-inference-<m>/gpt-4o-mini
```

Existing Playground browser sessions can keep stale model selections after the
dashboard recreates the Playground backend. After changing selected models,
refresh the page or start a new chat so the UI uses the current `/v1/models`
output.

Do not collapse all tool-use behavior into one check. For the external
`gpt-4o-mini` MaaS model, direct OpenAI-compatible Chat Completions function
calling through the MaaS Gateway is supported and was validated with a simple
forced tool schema. Playground MCP goes through the Llama Stack Responses API
and adds MCP tool schemas plus tool output to the provider request. A GPT MCP
call can therefore fail from external-provider token pressure even when direct
function calling works.

For the Stage 220 demo, use Nemotron as the primary OpenShift MCP model. Use
external GPT with MCP only for tightly bounded checks and only after
validating that `/v1/responses` returns `mcp_list_tools`, `mcp_call`, and a
final `message`. If Llama Stack logs show `Request too large`,
`rate_limit_exceeded`, or `tokens per min`, reduce the MCP tool surface,
result format, prompt, and requested output instead of assuming GPT tool
calling is disabled.

For non-browser validation of the dashboard BFF path, send both
`Authorization: Bearer <user-token>` and `x-forwarded-access-token:
<user-token>`. First verify that
`/gen-ai/api/v1/lsd/models?namespace=<project>` exposes the provider-qualified
target model ID such as `maas-vllm-inference-<m>/gpt-4o-mini`. Then validate
`/gen-ai/api/v1/lsd/responses` with that listed model ID. A direct Llama Stack
`/v1/responses` success proves the provider mapping, but it does not prove the
product Playground backend can authorize, list, and forward the request.

## Configure A Playground

Dashboard paths:

```text
Gen AI studio -> Playground
Gen AI studio -> AI asset endpoints
```

The user selects the project that contains the model deployment, creates a
playground, and selects models for the playground. For each selected model, the
user chooses whether the model is used for inference or embedding.

Verification:

- playground interface loads with chat area and settings panel
- Model tab shows the selected model
- chatbot header model list shows the selected model name

## Custom Endpoints

Custom endpoints are Technology Preview.

Administrator enablement fields in `OdhDashboardConfig`:

```yaml
spec:
  dashboardConfig:
    aiAssetCustomEndpoints: true
  genAiStudioConfig:
    aiAssetCustomEndpoints:
      externalProviders: true
      clusterDomains: []
```

Field intent:

- `aiAssetCustomEndpoints` shows the custom endpoints feature; default is
  `false`
- `externalProviders` allows external third-party provider endpoints; default
  is `false` and requires custom endpoints to be enabled
- `clusterDomains` adds internal domains beyond `.svc.cluster.local`, which is
  always treated as internal

External provider warning:

- Responses API data can be sent outside the cluster.
- This data can include RAG context, MCP tool results, and user input.
- External endpoint use must match the organization's data security policy.

User workflow fields for custom endpoints:

- model type: inference or embedding
- model ID, matching the provider ID exactly
- display name
- embedding dimension for embedding models
- URL for an internal cluster service or external provider
- token or API key, stored as a Kubernetes Secret shared at project level
- optional use case

Verification:

- optional Verify model sends a test request and checks that the endpoint is
  reachable and returns an OpenAI-compatible response
- endpoint appears on AI asset endpoints
- model can be selected in the playground and returns inference responses

## Model Experimentation

The playground supports testing one model or comparing two models side by side.

Parameters:

- temperature from 0 to 2
- streaming on or off
- system instructions

Temperature behavior:

- near 0: more deterministic and factual output
- around 0.7: balanced output
- near 1: more creative output
- over 1: can produce incoherent output

Multi-model comparison helps compare quality, tone, accuracy, latency, model
versions, and open source versus commercial model trade-offs. Starting
comparison clears the current chat history and copies the configuration to both
chat panels.

## Playground RAG

The playground RAG upload feature uses an inline vector database. The official
guide states there is no mechanism for this playground RAG feature to connect
to an external or remote vector database.

Upload limits:

- supported file formats: PDF, DOC, CSV
- up to 10 files
- maximum 10 MB per file

Configurable chunk settings:

- maximum chunk length
- chunk overlap
- delimiter

Prompt guidance:

- if the model does not use uploaded RAG documents, edit the system
  instructions to explicitly tell the model to use the knowledge search tool
  for the relevant questions.

## Reusable Prompts

Prompt management is Technology Preview.

Saved system instructions are stored in MLflow, scoped to the project, and can
be loaded by project members. Saving a refinement creates a new prompt version.
The prompt workflow supports optional commit messages.

Prompt workflows are available from:

- Prompt tab in the playground
- Gen AI studio Prompts page

Prerequisite:

- the MLflow service is available in the project

## MCP Testing

To test MCP tools in the playground:

- the selected model must have tool-calling capabilities enabled
- a playground instance must exist
- an administrator must have configured an MCP server
- the MCP server must appear in the settings panel MCP tab

The user selects the server, authorizes it when required, views available
tools, and sends a prompt that uses a tool.

Authorization tokens for MCP servers are stored only for the current browser
session. Closing the browser requires re-authorization.

## Export, Update, And Delete

Export:

- the playground can export the current configuration as a Python code template
- the template is not a runnable script
- the template captures selected model, model parameters, optional RAG files,
  and optional MCP tools

Update:

- updating a playground lets users add new models, re-register stopped models,
  or change selected models
- updating permanently deletes the inline vector database for all users in the
  project

Delete:

- deleting a playground removes the instance for every user with access to the
  project
- after deletion, models on AI asset endpoints no longer show Try in
  playground and instead show Add to playground

## Troubleshooting

The chatbot thinks indefinitely:

- likely cause: query or accumulated context exceeds the model's maximum
  context length
- check the playground pod `lsd-genai-playground-<id>`
- check the model-serving predictor pod `<model-name>-predictor-<id>`
- look for context length or OOM errors

The model does not use RAG data:

- update Prompt tab system instructions to explicitly force use of the search
  tool for questions that require the uploaded documents

MCP servers are missing from the UI:

- MCP servers must be configured at the cluster level by an administrator

The model fails to call MCP tools:

- verify the model supports tool calling
- verify vLLM runtime arguments such as `--enable-auto-tool-choice` and
  `--tool-call-parser`
- when a model outputs raw thinking tags, the guide suggests adding
  `/no_think` to the prompt

## Out Of Scope For This Guide

This guide does not define:

- full Llama Stack server configuration
- production support for Technology Preview capabilities
- full model-serving runtime configuration
- production MaaS governance for external model providers
- formal evaluation metrics or evidence workflows
- custom demo chatbot implementation
