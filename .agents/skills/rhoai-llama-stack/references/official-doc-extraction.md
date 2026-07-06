# Official Documentation Extraction

This extraction is derived from the official RHOAI 3.4 guide captured in
`source-capture.md`.

## Support Posture

Llama Stack integration is Technology Preview in Red Hat OpenShift AI 3.4.
Technology Preview features are not supported with Red Hat production SLAs,
might not be functionally complete, and are not recommended by Red Hat for
production use.

Platform notes:

- The Llama Stack Operator is not currently supported on IBM Z.
- Llama Stack is supported on IBM Power with limited functionality.
- On IBM Power, the GenAI playground is unavailable, and listed `milvus-lite`
  and PostgreSQL with pgvector vector stores are not currently available on
  `ppc64le`.

## Concept Model

Llama Stack is a unified AI runtime environment for generative AI workloads on
OpenShift AI. The Llama Stack Operator manages server lifecycle operations such
as deployment, scaling, and updates.

Core components:

- Llama Stack Operator
- `LlamaStackDistribution`
- `run.yaml` provider configuration
- inference model providers
- embedding model providers
- vector store providers
- metadata storage
- retrieval and agentic APIs

## Native And OpenAI-Compatible APIs

Native APIs documented by the guide include Dataset_IO, Evaluation, Inference,
Safety, Tool Runtime, and Vector_IO. Most native Inference API usage is
deprecated in favor of OpenAI-compatible Completions and Chat Completions.

OpenAI-compatible APIs documented by the guide include:

- `/v1/models`
- `/v1/chat/completions`
- `/v1/completions`
- `/v1/embeddings`
- `/v1/files`
- `/v1/vector_stores/`
- `/v1/vector_stores/{vector_store_id}/files`
- `/v1/responses`

Base URL rule:

- OpenAI SDKs and raw HTTP requests must use a base URL that includes `/v1`.
- `LlamaStackClient` uses the Llama Stack base URL without `/v1`.

## File Citation Annotations

OpenShift AI supports OpenAI-compatible file citation annotations for RAG
queries through Responses API.

Supported behavior:

- annotations are returned only through Responses API
- annotations are returned only with the `file_search` tool
- supported annotation type is `file_citation`
- attribution is document-level
- chunk-level and token-level attribution are not supported
- `url_citation` is part of the OpenAI schema but is not produced by Llama
  Stack in the captured OpenShift AI documentation

`file_citation` fields:

- `type`
- `file_id`
- `filename`
- `index`

## Provider Support And Enablement

Provider support status can change across OpenShift AI releases. Recheck the
active product baseline before making support claims.

Provider enablement details from the guide:

| Provider area | Provider | Enablement |
|---------------|----------|------------|
| Agents | `inline::meta-reference` | enabled by default; Responses API is accessible from Agents |
| Dataset_IO | `inline::localfs` | enabled by default |
| Dataset_IO | `remote::huggingface` | enabled by default; not disconnected |
| Evaluation | `inline::ragas` | set `EMBEDDING_MODEL` |
| Evaluation | `remote::ragas` | use Ragas remote provider guidance |
| Evaluation | `remote::lmeval` | enabled by default |
| Files | `inline::localfs` | enabled by default |
| Inference | `remote::vllm` | set `VLLM_URL`; disconnected supported |
| Inference | `inline::sentence-transformers` | set `ENABLE_SENTENCE_TRANSFORMERS` to `"true"` |
| Inference | `remote::openai` | set `OPENAI_API_KEY`; disconnected not supported |
| Safety | `remote::trustyai_fms` | enabled by default |
| Scoring | `basic::subset_of` | enabled by default |
| Scoring | `llm-as-judge::base` | enabled by default |
| Scoring | `braintrust::braintrust` | set `BRAINTRUST_API_KEY` |
| Scoring | `llm-as-judge::openai` | set `OPENAI_API_KEY`; disconnected not supported |
| Tool runtime | `remote::model-context-protocol` | enabled by default |
| Tool runtime | `builtin::rag-runtime` | enabled by default |
| Tool runtime | `remote::brave-search` | enabled by default; disconnected not supported |
| Tool runtime | `remote::tavily-search` | enabled by default; disconnected not supported |
| Tool runtime | `inline::websearch` | set `TAVILY_SEARCH_API_KEY`; disconnected not supported |
| Tool runtime | `inline::wolfram_alpha` | set `WOLFRAM_ALPHA_API_KEY`; disconnected not supported |
| Vector_IO | `inline::milvus` | set `MILVUS_DB_PATH` |
| Vector_IO | `inline::faiss` | set `FAISS_INDEX_PATH` |
| Vector_IO | `remote::pgvector` | set `PGVECTOR_HOST`, `PGVECTOR_PORT`, `PGVECTOR_DB`, `PGVECTOR_USER`, and `PGVECTOR_PASSWORD` |
| Vector_IO | `remote::milvus` | set `MILVUS_URL`, `MILVUS_TOKEN`, `MILVUS_DB_NAME`, and `MILVUS_TIMEOUT` |
| Vector_IO | `remote::qdrant` | set `QDRANT_URL`, `QDRANT_API_KEY`, and `QDRANT_VECTOR_SIZE` |

## Activating The Llama Stack Operator

The Llama Stack Operator is activated through the `DataScienceCluster` custom
resource.

Prerequisites:

- OpenShift AI is installed.
- The operator has `cluster-admin`.

Configuration:

```yaml
spec:
  components:
    llamastackoperator:
      managementState: Managed
```

Verification:

- A `llama-stack-operator-controller-manager` pod is running in
  `redhat-ods-applications`.

## Deploying A Llama Stack Server

A Llama Stack server is deployed with a `LlamaStackDistribution` custom
resource in the target project.

Important fields from the official guide:

- `apiVersion: llamastack.io/v1alpha1`
- `kind: LlamaStackDistribution`
- `spec.replicas`
- `spec.server.containerSpec.env`
- `spec.server.containerSpec.name`
- `spec.server.containerSpec.port`
- `spec.server.distribution.name`
- `spec.server.storage`

The official examples use `distribution.name: rh-dev` and port `8321`.

Common environment variables in examples:

- `VLLM_URL`
- `INFERENCE_MODEL`
- `VLLM_TLS_VERIFY`
- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_DB`
- `PGVECTOR_HOST`
- `PGVECTOR_PORT`
- `PGVECTOR_DB`
- `PGVECTOR_USER`
- `PGVECTOR_PASSWORD`
- `EMBEDDING_MODEL`
- `EMBEDDING_PROVIDER`
- vector provider variables such as `MILVUS_DB_PATH`, `MILVUS_URL`,
  `MILVUS_TOKEN`, `MILVUS_DB_NAME`, `FAISS_INDEX_PATH`, `QDRANT_URL`,
  `QDRANT_API_KEY`, and `QDRANT_VECTOR_SIZE`

## RAG Stack Pattern

The guide describes a RAG stack made of:

- inference model deployed with vLLM
- embedding model
- vector database
- Llama Stack server
- document ingestion workflow
- query workflow through Responses API or Llama Stack client

OpenShift AI can host the model and embedding providers, and Llama Stack can
coordinate retrieval and response generation.

## Vector Store Options

| Vector store | Provider | Use case |
|--------------|----------|----------|
| Inline Milvus | `inline::milvus` | local development and testing; uses `MILVUS_DB_PATH` |
| Remote Milvus | `remote::milvus` | external Milvus service; uses URL, token, database name, and timeout |
| Inline FAISS | `inline::faiss` | local file-based vector index; uses `FAISS_INDEX_PATH` |
| PostgreSQL with pgvector | `remote::pgvector` | durable PostgreSQL-backed vector storage; uses `PGVECTOR_HOST`, `PGVECTOR_PORT`, `PGVECTOR_DB`, `PGVECTOR_USER`, and `PGVECTOR_PASSWORD` |
| Qdrant | `remote::qdrant` | external Qdrant service; uses URL, API key, and vector size |

For OpenShift AI deployments, PostgreSQL metadata storage is required, and
PostgreSQL with pgvector is a common durable option for RAG vector storage.

## Ingestion And Query

The guide uses `llama_stack_client` for ingestion and query examples.

Ingestion concepts:

- create or select a vector database
- upload documents
- insert documents into the vector database
- choose embedding model and chunking configuration

Query concepts:

- use Responses API with `file_search`
- specify vector store IDs
- optionally use OpenAI-compatible clients
- inspect returned file citation annotations

Search modes:

- keyword search
- vector search
- hybrid search

## Docling

The guide includes a Docling pattern for converting and preparing documents
before ingestion. Treat Docling as document preparation in the data-ingestion
workflow, not as the Llama Stack server itself.

## Evaluation Providers

The guide includes RAG evaluation context with providers such as Ragas, BEIR,
and TrustyAI. Evaluation API coverage in the captured guide is Developer
Preview. Use `rhoai-model-evaluation` for demo evaluation implementation
details and evidence workflows.

## PostgreSQL Metadata Storage

OpenShift AI Llama Stack deployments require PostgreSQL for metadata storage.
The official examples configure PostgreSQL connection settings through
environment variables and Secrets.

Review points:

- keep database credentials in Secrets
- define backup and retention before treating the storage as durable
- document ownership and operations in `docs/OPERATIONS.md`

## OAuth And ABAC

The guide includes OAuth/OIDC authentication configuration for Llama Stack.

Common environment variables:

- `AUTH_ISSUER`
- `AUTH_AUDIENCE`
- `AUTH_JWKS_URI`
- `AUTH_JWKS_RECHECK_PERIOD`
- `AUTH_VERIFY_TLS`

Bearer tokens are passed to Llama Stack requests when authentication is
enabled. ABAC policies control access to resources. Validate user and service
account access before exposing authenticated endpoints in the demo.

## Self-Signed Certificates

Llama Stack can trust custom CAs through the
`LlamaStackDistribution` server TLS configuration.

Official field:

```yaml
spec:
  server:
    tlsConfig:
      caBundle:
        caCertConfigMapName: <configmap-name>
```

After changing the CA bundle, restart the Llama Stack pod so the server picks
up the trusted CA bundle.

## High Availability And Autoscaling

The guide describes high availability and autoscaling on
`LlamaStackDistribution`.

Relevant fields:

- `spec.replicas`
- `spec.server.podDisruptionBudget.maxUnavailable`
- `spec.server.topologySpreadConstraints`
- `spec.autoscaling.minReplicas`
- `spec.autoscaling.maxReplicas`
- `spec.autoscaling.targetCPUUtilizationPercentage`
- `spec.autoscaling.targetMemoryUtilizationPercentage`

Use HA only after database, vector store, authentication, and model endpoint
behavior are ready for multiple Llama Stack replicas.

## Out Of Scope For This Guide

This guide does not define:

- full vLLM runtime configuration
- GPU Operator installation
- complete PostgreSQL production administration
- complete Qdrant or Milvus operations
- chatbot UI implementation
- AI Pipelines implementation
- production support for Technology Preview capabilities
- full MaaS governance for external models
