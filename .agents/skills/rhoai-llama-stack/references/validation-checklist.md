# Validation Checklist

Use this checklist before accepting Llama Stack documentation, runbooks, or
GitOps changes.

## Source Review

- Product links use the active baseline in `docs/PLATFORM_BASELINE.md`.
- The official guide URL uses the active `/3.4/` baseline path.
- Llama Stack is labeled Technology Preview in user-facing material.
- Model serving configuration is delegated to `rhoai-model-serving-platform`.
- GPU enablement is delegated to `rhoai-nvidia-gpu-accelerators`.
- Chatbot UI, prompt, and suggested-question changes are delegated to
  `rhoai-chatbot-customization`.
- Evaluation implementation details are delegated to `rhoai-model-evaluation`.

## Operator Activation Review

- OpenShift AI is installed.
- Operator has `cluster-admin`.
- `DataScienceCluster` sets:

  ```yaml
  spec:
    components:
      llamastackoperator:
        managementState: Managed
  ```

- The Llama Stack Operator controller manager pod is running in
  `redhat-ods-applications`.

## LlamaStackDistribution Review

- `apiVersion` is `llamastack.io/v1alpha1` unless active schema and docs prove
  otherwise.
- `kind` is `LlamaStackDistribution`.
- Namespace is the intended application namespace.
- `spec.server.distribution.name` is sourced from official docs or installed
  distribution resources.
- Server port matches the selected distribution and route/service setup.
- On OpenShift, prefer a GitOps-managed `Route` to the operator-managed
  Llama Stack `Service` when the installed operator creates a hostless Ingress;
  do not patch generated Ingress resources.
- Provider environment variables match enabled providers.
- Secrets are used for passwords and API keys.
- PostgreSQL metadata storage is configured.
- `VLLM_URL`, `INFERENCE_MODEL`, and TLS verification behavior match the active
  model-serving endpoint.
- When Llama Stack consumes a MaaS model, `VLLM_API_TOKEN` is Secret-backed and
  was issued by the MaaS API for the intended consumer persona. Validate both
  the selected `MaaSSubscription` phase and that its `.spec.modelRefs[*].name`
  includes the generation model being called, such as
  `nemotron-3-nano-30b-a3b`.
- Keep MaaS resource names separate from Llama Stack runtime model IDs.
  `MaaSModelRef` and `MaaSSubscription` use the short resource name, while
  Llama Stack chat/completion requests must use the model ID returned by
  `client.models.list()` or `/v1/models` for the active distribution, for
  example `vllm-inference/nemotron-3-nano-30b-a3b`.
- For RHOAI 3.4 inline embeddings, `ENABLE_SENTENCE_TRANSFORMERS=true`,
  `EMBEDDING_PROVIDER=sentence-transformers`, and `EMBEDDING_MODEL` are present.
- For pgvector, use the documented `PGVECTOR_HOST`, `PGVECTOR_PORT`,
  `PGVECTOR_DB`, `PGVECTOR_USER`, and `PGVECTOR_PASSWORD` Secret keys.
- Storage settings match the selected vector store and metadata design.

## Provider Review

- Provider support status is checked against the active baseline.
- Disconnected status is recorded for every remote provider.
- `remote::openai`, remote search providers, and other internet-dependent
  providers are not used in disconnected environments.
- Inline embedding providers are explicitly enabled only for development or
  test use.
- Remote vLLM provider points at an OpenShift AI model-serving endpoint.
- External OpenAI use is approved by project governance or routed through MaaS.

## RAG Review

- Inference model and embedding model IDs are listed from the active Llama Stack
  server before use.
- Vector database provider is selected intentionally.
- Document ingestion records source documents, chunking settings, embedding
  model, and vector store ID.
- If the RAG source documents are staged in S3-compatible object storage,
  validate both object upload and vector database ingestion; an uploaded object
  does not prove the vector store was populated.
- Query workflows use Responses API with `file_search` when citations are
  required.
- File citation expectations are document-level, not chunk-level or token-level.
- Search mode is documented as keyword, vector, or hybrid.
- Docling is treated as document preparation, not as a Llama Stack server
  component.

## OAuth And ABAC Review

- OIDC issuer, audience, and JWKS URI are configured from the chosen identity
  provider.
- `AUTH_VERIFY_TLS` is intentionally set for the target certificate posture.
- Bearer-token client requests are tested after authentication is enabled.
- ABAC policies match intended users, groups, and service accounts.
- Anonymous access is not assumed after authentication is enabled.

## Certificate Review

- Custom CA ConfigMap exists in the target namespace.
- `spec.server.tlsConfig.caBundle.caCertConfigMapName` points to the reviewed
  ConfigMap.
- Llama Stack pod is restarted after CA bundle changes.
- Certificate handling is consistent with `rhoai-certificate-management`.

## HA And Autoscaling Review

- Database and vector store are ready for multiple Llama Stack replicas.
- `spec.replicas` is intentional.
- Pod disruption budget and topology spread constraints match cluster topology.
- Autoscaling min/max replicas are compatible with downstream model-serving
  endpoint capacity.
- CPU and memory utilization targets are documented.
- Endpoint behavior is tested during scale-up or restart.

## Optional Read-Only Checks

Run only after following the OpenShift safety guard in `AGENTS.md`:

```bash
oc get datasciencecluster -A -o yaml
oc get pods -n redhat-ods-applications | rg llama
oc get llamastackdistribution -A
oc describe llamastackdistribution <name> -n <namespace>
oc logs deploy/<llama-stack-deployment> -n <namespace>
oc get secret -n <namespace>
oc get configmap -n <namespace>
```

Schema checks:

```bash
oc explain datasciencecluster.spec.components.llamastackoperator
oc explain llamastackdistribution.spec
oc explain llamastackdistribution.spec.server
```

## API Checks

Use the correct base URL shape:

```text
OpenAI-compatible clients: <llama-stack-url>/v1
LlamaStackClient: <llama-stack-url>
```

Check:

- Python applications using `llama_stack_client` have a client version
  compatible with the deployed server. A mismatched client returns HTTP 426
  before normal API handling.
- `/v1/models` returns expected models
- `/v1/responses` works for RAG and tool workflows
- For MCP workflows, inspect the Responses API output types. A model-driven
  tool-use claim requires `mcp_list_tools`, `mcp_call`, and a final `message`;
  a model list or plain text response is not sufficient.
- Direct OpenAI-compatible Chat Completions function calling through MaaS does
  not by itself prove Playground MCP behavior. For external GPT models, test
  `/v1/responses` with a bounded MCP tool and check Llama Stack logs for
  provider token-limit errors such as `Request too large`,
  `rate_limit_exceeded`, or `tokens per min`.
- file citation annotations appear when `file_search` is used
- authenticated endpoints reject missing or invalid bearer tokens
- On llama-stack 0.7.x, MCP servers are top-level `connectors:` entries in
  the run config (`registered_resources` silently ignores unknown keys, and
  the connector HTTP API is read-only); Responses API MCP tools reference
  them with `{"type": "mcp", "server_label": ..., "connector_id": ...}`.
- `POST /v1/responses` handlers mount only when `responses` is in the run
  config `apis:` list with its `inline::builtin` provider;
  `/v1/inspect/routes` lists the route either way, so a 404 here is a config
  gap, not a routing fault.
- With Postgres-backed kvstore, verify `GET /v1beta/connectors` actually
  lists registered connectors: kvstore range scans assume bytewise key
  ordering, and non-C database collations (for example `en_US.utf8`) make
  registered rows invisible to list calls while direct gets succeed. Pin the
  key column to `COLLATE "C"`.

## GitOps Review

- Long-lived `DataScienceCluster`, `LlamaStackDistribution`, Secrets,
  ConfigMaps, Routes, Services, and supporting workloads are managed through
  ArgoCD once active implementation exists.
- Dashboard-only or operator-generated fields are not copied into GitOps.
- Secret values are not committed.
- Technology Preview posture is recorded in READMEs and operations notes.
- README claims match implemented providers, vector stores, authentication, and
  model-serving endpoints.

## Fail Conditions

- Llama Stack is presented as production-supported without Technology Preview
  context.
- Provider API keys or database passwords are committed.
- OpenAI-compatible clients omit `/v1` in the base URL.
- `LlamaStackClient` is configured with an extra `/v1` suffix.
- RAG citations are expected from APIs other than Responses with `file_search`.
- Chunk-level or token-level citations are claimed.
- Inline vector stores are described as durable production storage.
- HA is enabled while metadata or vector storage remains single-pod or
  ephemeral.
- Remote providers are used in disconnected environments without an explicit
  exception.
- External GPT MCP failures are diagnosed as model registration problems before
  checking direct MaaS function calling, Responses API output types, and
  external-provider token-limit logs.
