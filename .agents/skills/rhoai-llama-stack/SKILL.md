---
name: rhoai-llama-stack
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when documenting, reviewing, or rebuilding Red Hat OpenShift AI Llama
  Stack platform capabilities: Technology Preview support posture, native
  Llama Stack APIs, OpenAI-compatible APIs, file citation annotations, provider
  enablement environment variables, Llama Stack Operator activation through
  DataScienceCluster, LlamaStackDistribution custom resources, RAG stack
  deployment, vector stores with Milvus, FAISS, pgvector, and Qdrant, document
  ingestion, Responses API file_search workflows, keyword/vector/hybrid search,
  RAG evaluation provider posture, PostgreSQL metadata storage, OAuth and ABAC,
  self-signed CA handling, and high availability/autoscaling. Do NOT use for
  chatbot UI prompt changes (use rhoai-chatbot-customization), model serving
  runtime configuration (use rhoai-model-serving-platform), GPU enablement (use
  rhoai-nvidia-gpu-accelerators), AI pipeline authoring (use
  rhoai-kfp-pipeline-authoring), NeMo/FMS Guardrails product configuration or
  Llama Stack PII detector integration (use rhoai-guardrails-safety),
  evaluation implementation details (use rhoai-model-evaluation), or live
  cluster changes without the OpenShift safety guard.
---

# RHOAI Llama Stack

Use this skill for OpenShift AI Llama Stack platform work on the active product
baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior details.
Official Red Hat documentation is product authority. This skill adapts the
official Llama Stack guide to this repo's operations and GitOps review model.

## Scope

This skill covers:

- Llama Stack support posture and architecture in OpenShift AI
- native Llama Stack APIs and OpenAI-compatible APIs
- `/v1` base URL rules for OpenAI SDKs and raw HTTP requests
- file citation annotations returned by the Responses API with `file_search`
- Llama Stack provider support, enablement environment variables, disconnected
  support, and preview status
- activation of the Llama Stack Operator through `DataScienceCluster`
- `LlamaStackDistribution` CR structure and server configuration
- PostgreSQL metadata storage and pgvector provider use
- RAG stack design with inference, embedding, vector storage, retrieval, and
  document ingestion
- vector store options: inline Milvus, remote Milvus, inline FAISS, remote
  PostgreSQL with pgvector, and remote Qdrant
- `llama_stack_client` ingestion and query workflows
- Responses API `file_search` workflows and keyword/vector/hybrid search modes
- Docling document preparation pattern for RAG
- RAG evaluation provider posture, including Ragas, BEIR, and TrustyAI
- OAuth/OIDC authentication, ABAC access policy behavior, and bearer-token
  request requirements
- self-signed/private CA handling through `spec.server.tlsConfig.caBundle`
- high availability and autoscaling fields on `LlamaStackDistribution`

Use other skills for adjacent work:

- `rhoai-chatbot-customization` for the Streamlit chatbot UI, prompts,
  suggestions, and agent/direct mode behavior
- `rhoai-gen-ai-playground` for product Gen AI studio playground RAG, MCP,
  reusable prompt, and custom endpoint user workflows
- `rhoai-enterprise-rag` for metadata-aware enterprise RAG application
  patterns, hybrid search, reranking, provider selection such as pgvector or
  Milvus, and RHOAI product-document ingestion
- `rhoai-autorag` for product AutoRAG optimization runs, JSON evaluation data,
  leaderboard review, and generated indexing/inference notebook handoff
- `rhoai-guardrails-safety` for NeMo Guardrails, FMS Guardrails, detector
  services, and PII detection workflows that use Guardrails with Llama Stack
- `rhoai-model-serving-platform` for vLLM, KServe, and model-serving runtime
  configuration
- `rhoai-nvidia-gpu-accelerators` for NVIDIA GPU Operators and hardware
  profiles
- `rhoai-certificate-management` for broader RHOAI certificate management
- `rhoai-kfp-pipeline-authoring` for pipeline implementation details
- `rhoai-model-evaluation` for evaluation workflow implementation
- `rhoai-maas-governance` for governed MaaS endpoint access and external model
  provider access

## Demo Policy

For this repo:

- Treat Llama Stack as Technology Preview unless the active baseline changes.
  README and presentation material must label that support posture.
- Use official examples as source-grounded patterns, not as the demo's default
  model choices. The active private model direction is governed by the model
  serving skill and project baseline.
- Prefer remote embedding models for production-shaped RAG flows. Inline
  embedding providers are development/testing options and must be enabled
  explicitly.
- Prefer PostgreSQL-backed metadata storage. PostgreSQL is required for Llama
  Stack metadata persistence in OpenShift AI deployments.
- Prefer remote PostgreSQL with pgvector when the demo needs durable,
  production-shaped vector storage that aligns with existing PostgreSQL
  operational models.
- Use inline Milvus or inline FAISS only for development, testing, or small
  single-node experiments.
- Do not put provider API keys or database passwords directly in manifests;
  use Secrets and repo secret-handling rules.
- In disconnected environments, record which providers are supported and avoid
  `websearch`, `wolfram_alpha`, or remote providers that are not available.
- For OpenAI-compatible SDKs, include `/v1` in `base_url`. For
  `LlamaStackClient`, do not append `/v1`.
- Do not route external OpenAI access directly through Llama Stack unless the
  project explicitly approves that path; prefer the governed MaaS design in
  `rhoai-maas-governance`.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/source-capture.md` and
   `references/official-doc-extraction.md`.
3. Decide whether the task is:
   - Llama Stack Operator activation
   - `LlamaStackDistribution` authoring or review
   - RAG stack architecture
   - vector store/provider selection
   - document ingestion and query workflow
   - OpenAI-compatible API use
   - OAuth/ABAC configuration
   - certificate trust
   - HA/autoscaling
4. Use `examples/llama-stack-patterns.md` for focused review patterns.
5. Validate with `references/validation-checklist.md`.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/llama-stack-patterns.md`
