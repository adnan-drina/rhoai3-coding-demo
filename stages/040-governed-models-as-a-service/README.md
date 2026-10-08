# Stage 040: Governed Models-as-a-Service

## Why This Matters

A model endpoint alone does not provide a shared enterprise service. Models-as-a-Service (MaaS) gives developers governed access to private and approved external models through API keys, subscriptions, quotas and usage telemetry.

## Architecture

Qwen models are hosted in the Internal Models project; Qwen3.6 is parked and Qwen3.8 uses one exclusive L40S GPU. Native OpenShift AI controllers connect them to one governed Gateway. MaaS governance stays in models-as-a-service, and external providers stay in the External Models project. The shared API hostname and `/v1` are the default for body-based model routing. Dedicated Qwen HTTPS listeners remain as compatibility endpoints; each listener retains its explicit namespace restriction. Each admitted namespace also requires `maas-gateway-access=true`; the label alone does not grant access to another listener. Native MaaS policies control access across the same Gateway.

## What This Stage Adds

- Registered Qwen 3.6 27B FP8, parked at zero replicas, and active Qwen 3.8 27B INT4 on one exclusive GPU.
- Native MaaS API key storage, subscriptions, authentication and token quotas.
- Reusable single-node topology and queue-routing configurations, with native NVIDIA accelerator templates.
- Approved GPT-6 Luna access through the native OpenAI external-provider integration.
- GenAI Studio enablement for experimenting with available model endpoints.
- A bounded, read-only OpenShift MCP endpoint for later coding workflows.

## What To Notice And Why It Matters

Clients use the common `/v1` base and the canonical `publishers/internal-models/models/<model-name>` local model IDs. MaaS preserves a common governance boundary. The two full GPUs are this project's model-memory choice; the configuration does not enable time slicing or automatic scaling.

GPT-6 Luna uses the OpenAI Chat Completions protocol. Function calls require `reasoning_effort: none`. OpenAI Responses built-in tools are outside this connection's protocol. External requests leave the cluster for the approved provider.

Native external-model access is Technology Preview. GPT-6 Luna and MiniMax M2 use `openai-chat`, which always uses translation rather than passthrough. Response buffering applies when translating between different API formats; it is not a blanket statement that all external responses are buffered. MaaS subscription token metering applies to OpenAI Chat Completions responses, not models configured as `messages` or `openai-responses`. Provider-key limits apply to aggregate usage by all users sharing that key, and provider entitlement is separate from gateway readiness.

External models are supported only through the default tenant. If a `messages` model is added, its `x-api-key` authentication support is gateway-wide; deleting the last such model disables that header's authentication gateway-wide. GPT and MiniMax use `Authorization: Bearer` with each user's MaaS key. Claude adds the native Messages `x-api-key` path, but its stopped HTTP401 qualification remains unresolved. See the [external-model formats and limitations](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/govern_llm_access_with_models-as-a-service/deploy-and-manage-models-as-a-service).

GenAI Studio uses existing model endpoints. A user creates a playground in their project through the dashboard; the native service creates its supporting pgvector storage. Basic playground use does not add another GPU or an object-storage bucket. The fresh creation helper mounts the retained Studio PVC at its actual SQLite directory; existing playgrounds require private backup and native restore before changing persistence. RAG, AutoRAG and AutoML are outside this stage.

## How Red Hat And Open Source Make It Work

OpenShift AI manages AIGateway, KServe and OGX. Red Hat Connectivity Link supplies native authentication and rate limiting. Service Mesh and Gateway API provide routing. PostgreSQL stores MaaS API-key state. GitOps owns customer configuration while native operators own generated workloads.

## Trust Boundaries

Provider keys and database credentials stay outside Git. Each model request must use its authorized MaaS key. OpenShift MCP exposes only the selected read-only tools and retains Kubernetes RBAC restrictions. Browser checks use your own session.

## Red Hat Products Used

Red Hat OpenShift AI 3.5, OpenShift Container Platform 4.22, Red Hat Connectivity Link 1.4 and OpenShift Service Mesh 3.4. Native external-model integration and GenAI Studio retain their documented product support status; upstream MCP is a separately pinned project component.

## Deploy And Validate

Use the reviewed published branch configured in your private environment. Keep the Argo CD CLI compatible with the installed GitOps version: the deploy helper uses its native nonselective hook sync once if selective reconciliation leaves the tracing capability unset.

```bash
./stages/040-governed-models-as-a-service/deploy.sh
./stages/040-governed-models-as-a-service/validate.sh --readiness
./stages/040-governed-models-as-a-service/register-model-cards.sh
```

Readiness checks do not establish inference, streaming or quota behavior. Bounded functional checks and user playground interaction complete acceptance. In the dashboard, create a playground in your project and select an available governed model endpoint. Do not use the playground to create a replacement serving deployment.

To qualify just one approved external model with one completion, set `RHOAI_STAGE040_MODEL=minimax-m2` (or `gpt-6-luna`) and `RHOAI_STAGE040_SINGLE_COMPLETION=true` when running `validate-functional.py`, together with `RHOAI_STAGE040_PERSONA_KUBECONFIG` and the reviewed deployed revision. This scope does not run local models, streaming or tool-call tests. Its temporary key is revoked afterward.

## Optional Studio Tracing

GenAI Studio exposes the Technology Preview tracing capability. Enable tracing explicitly in an individual playground session only when its prompts, code and tool outputs may be retained under your project policy. This is not automatic tracing of every MaaS request or agent. The embedded MLflow trace viewer does not by itself prove where this installed session persists traces; end-to-end storage and session rendering remain to be verified by the user. The separate Observe trace dashboard currently has a product-generated panel-reference error.

## Usage And Showback

As a platform administrator, open **Observe & monitor → Dashboard → Usage** to inspect governed usage by user, subscription and model. Choose a Time period, then use the User, Subscription and Model filters. The native table offers Export as CSV; its format is distinct from the project helper below. These counters measure authorized total tokens and calls; they do not expose a trustworthy input/output token split or an agent's internal tool trajectory.

A platform administrator can export existing usage for an explicit UTC window:

```bash
./stages/040-governed-models-as-a-service/export-maas-usage.sh \
  --from 2026-10-06T00:00:00Z --to 2026-10-06T12:00:00Z \
  --output /private/tmp/maas-usage.csv
```

This original helper queries native RHOAI Thanos; it is not the dashboard's CSV format. The private CSV and coverage receipt contain identities and must stay outside Git. Missing categories remain unknown. If no counter baseline exists at the window start, period usage stays unknown: the observed increase and latest cumulative counter are shown separately, without adding the first sample to the period. Financial columns remain **unpriced**, with no currency, zero-cost assumption or invoice. Actual approved rates are required before any financial allocation. Prometheus sampling, counter resets and the configured 90-day retention limit reporting accuracy. Rows stay scoped to native limiter resources; do not sum overlapping policies. Duplicate underlying semantic-resource series cause a refusal instead of inflated usage. MCP/agent traces and GPU fixed costs are outside these token counters.

This workflow is inspired by [demo-chargeback](https://github.com/suhasvkashyap/demo-chargeback); its code and sample prices are not copied.

## References

- [OpenShift AI 3.5 Models-as-a-Service](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/govern_llm_access_with_models-as-a-service/index)
- [GenAI Playground prerequisites](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/experimenting_with_models_in_the_gen_ai_playground/playground-prerequisites_rhoai-user)
- [Connectivity Link 1.4 installation](https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html/install_connectivity_link/rhcl-install-on-ocp)
- [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna)
- [Kubernetes MCP Server](https://github.com/containers/kubernetes-mcp-server/tree/v0.0.67)

## Next Stage

[Stage 050: Model Evaluation](../050-model-evaluation/README.md)

## Direct Catalog MCP Connection

In **Gen AI studio → Playground → MCP**, select **OpenShift-Catalog** while using project **AI Coding Sandbox**. Enter your own OpenShift session access token, choose **Authorize**, then **View tools**. The token is session-only; do not enter a model MaaS API key. The catalog server offers 13 read-only core/config tools and denies Secrets and writes. The separate **MCP servers** hosting project and Registry are accessible to `ai-admin`; `ai-developer` consumes tools using its own project permissions without hosting access. **OpenShift-MCP** remains the legacy entry until the visual handoff.

This follows the [documented MCP connection procedure](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/experimenting_with_models_in_the_gen_ai_playground/index). It is a direct HTTPS connection, not MCP Gateway aggregation or MaaS API-key/quota governance. Gateway qualification is tracked separately.

The single discovery field is published with `publish-catalog-mcp.py`; exact Argo field delegation preserves it, regular deploy republishes/validates it, and validation detects drift. This is customer-managed field publication, not operator synchronization from the Registry. Retain its private UID-scoped ownership journal for repeated deployment. Stage040 does not require Stage060 on a fresh foundation: publication defers while the catalog runtime is absent, and Stage060 explicitly publishes once ready.

Model-free qualification is reproducible without saved acceptance artifacts:

```bash
python3 ./stages/040-governed-models-as-a-service/qualify-catalog-mcp.py \
  --bootstrap-kubeconfig "$KUBECONFIG" \
  --admin-kubeconfig "$AI_ADMIN_KUBECONFIG" \
  --developer-kubeconfig "$AI_DEVELOPER_KUBECONFIG" \
  --receipt /private/qualification/studio-mcp.json
```

Create the receipt's parent directory with private permissions. The helper keeps tokens in memory and records only safe status/count checks. It verifies native session status/tools and bounded caller reads/hosting denial; browser rendering and model-generated tool invocation remain separate.

For catalog publication or qualification, supply the reviewed immutable deployed revisions as `RHOAI_STAGE040_EXPECTED_REVISION` and `RHOAI_STAGE060_EXPECTED_REVISION` (or the helpers' explicit revision arguments). Helper-only source publication does not require moving either live Application. Metadata connection and tool listing prove bearer-header transport; the server's opaque-token mode validates caller authority when an actual Kubernetes resource is requested. A nonempty invalid bearer must be denied on that resource call, not inferred invalid from metadata discovery.

Operator installation uses native Automatic approval on the selected channels. Historical CSVs shown here are qualified baselines, not immutable future installation pins. See the [fresh deployment policy](../../docs/migration/035-operator-automatic-policy.md) for compatible-version checks, rolling-channel limits and the standard cluster-credential prerequisite.

### Claude Sonnet 5.5

Claude Sonnet 5.5 uses the documented Anthropic provider and native Messages format. Supply `ANTHROPIC_API_KEY` privately; deployment creates `anthropic-provider-api-key` through standard input. The exact provider model ID must be available to that key; catalog readiness alone does not prove provider entitlement or inference. The three personal subscriptions include Claude; DevSpaces remains local-only.

Use the discovered model endpoint with its `/v1/messages` path, your MaaS key in `x-api-key`, and `anthropic-version: 2023-06-01`. Native Messages passthrough supports streaming but is **not subscription-token-metered**. Cross-format translation buffers streaming responses; provider-key limits aggregate all users. Creating the first Messages ExternalModel enables `x-api-key` authentication gateway-wide; removing the last one disables it. Existing Bearer authentication remains supported. See [RHOAI 3.5 external-model formats](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/govern_llm_access_with_models-as-a-service/deploy-and-manage-models-as-a-service).

For a bounded native check, select `RHOAI_STAGE040_MODEL=claude-sonnet-5-5` and `RHOAI_STAGE040_SINGLE_COMPLETION=true` when running `validate-functional.py` with your genuine persona. It performs one positive streaming request with at most 32 output tokens and missing/invalid/revoked-key negatives; it does not retest other models.

## Current Routing Qualification

Three small common-host requests passed: Qwen 3.8 native SSE, GPT-6 Luna JSON and MiniMax M2 JSON. Qwen 3.6 remains parked and has no inference qualification. The local namespace-qualified legacy path returned HTTP 503 on the API hostname but passed native SSE on the retained Qwen 3.8 hostname. Use common `/v1` for current clients; keep the compatibility hostname until that native path limitation is resolved or its retirement is explicitly accepted. The old `models-as-a-service` local paths and publisher IDs are not aliases. No Claude request was repeated.

Studio retained both saved profile UUIDs/settings and its saved response through a consistent private backup and supported OGX PVC mount. Two unreferenced historical model registrations remain cached: the installed native model API exposes no unregister operation. Fresh persistence attachment is source-reviewed and has not been tested end-to-end in a new environment.
