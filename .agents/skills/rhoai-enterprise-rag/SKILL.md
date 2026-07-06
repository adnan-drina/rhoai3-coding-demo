---
name: rhoai-enterprise-rag
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when planning, documenting, implementing, or reviewing enterprise RAG on
  Red Hat OpenShift AI with Llama Stack or OGX: metadata-aware retrieval,
  OpenAI-compatible Files and Vector Stores APIs, PostgreSQL with pgvector
  vector storage, PostgreSQL Llama Stack metadata storage, hybrid search,
  neural reranking,
  RAG notebooks or ingestion jobs, Docling data preparation for unstructured
  documents, Kubeflow Pipeline automation for repeatable document processing,
  and Nemotron generation through the demo MaaS layer. Use for Stage 230
  private-data RAG, official RHOAI product documentation Q&A, and RAG
  architecture reviews.
  Do NOT use for AutoRAG optimization runs (use rhoai-autorag), generic Llama
  Stack platform configuration (use rhoai-llama-stack), model-serving runtime
  details (use rhoai-model-serving-platform), MaaS policy details (use
  rhoai-maas-governance), chatbot UI changes (use
  rhoai-chatbot-customization), or live cluster work without the environment
  safety guard.
---

# RHOAI Enterprise RAG

Use this skill for metadata-aware enterprise RAG implementations on the active
OpenShift AI baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read these references before authoring RAG GitOps, notebooks, scripts, README
content, or validation:

- `references/source-capture.md`
- `references/implementation-pattern.md`
- `references/validation-checklist.md`

Official Red Hat documentation is product authority. Red Hat Developer
articles and linked GitHub repositories are implementation evidence, not API
or support-posture authority.

## Scope

This skill covers:

- enterprise RAG architecture using OpenShift AI Llama Stack / OGX
- metadata at vector-store, document, and chunk levels
- file ingestion with OpenAI-compatible Files and Vector Stores APIs
- remote PostgreSQL with pgvector as the active Stage 230 vector-store target
- PostgreSQL as required Llama Stack metadata storage
- hybrid retrieval with metadata filters
- neural reranking with a cross-encoder reranker
- Nemotron generation through the governed Stage 220 MaaS endpoint
- official RHOAI product-document corpora stored under the stage data folder
  and mirrored into project-scoped S3 during deployment
- Docling-based conversion, chunking, extraction, and subset selection for
  unstructured enterprise documents
- Kubeflow Pipeline automation for repeatable Docling data processing

Adjacent skills:

- `rhoai-llama-stack`: Llama Stack Operator activation, `LlamaStackDistribution`
  fields, provider configuration, API base URL rules, OAuth, ABAC, and HA.
- `rhoai-maas-governance`: governed model access, subscriptions, auth policy,
  API keys, and MaaS telemetry.
- `rhoai-model-serving-platform`: KServe, vLLM, `InferenceService`, and
  serving runtime configuration.
- `rhoai-model-customization-training`: official Docling data-preparation
  workflow, Red Hat Python index posture, and data-processing example
  repositories.
- `rhoai-ai-pipelines` and `rhoai-kfp-pipeline-authoring`: AI Pipelines
  product behavior and repo KFP implementation when ingestion moves from
  notebooks/jobs into DSPA/KFP.
- `rhoai-autorag`: product AutoRAG experiments and leaderboard review.
- `rhoai-chatbot-customization`: Streamlit or custom RAG UI behavior.

## Demo Policy

For this repo:

- Treat Llama Stack / OGX features as Technology Preview unless the active
  baseline changes.
- Use Nemotron from Stage 220 MaaS for generation. Do not deploy a duplicate
  Llama model just because an example uses one.
- Start with the RHOAI product documentation corpus to prove metadata,
  hybrid retrieval, reranking, and end-to-end answer generation.
- Treat repo-stored official RHOAI 3.4 PDFs as the primary audience Q&A corpus
  for this stage. Refresh them from `docs.redhat.com` only when the active
  product baseline or source manifest changes.
- Do not drop the reranking or metadata extraction steps
  without explicit user agreement and a recorded stage-plan decision.
- Keep the audience demo focused on repo-stored official RHOAI product
  documentation unless the stage plan is explicitly changed.
- Prefer remote PostgreSQL with pgvector for rebuilt Stage 230 because the
  active environment must prove metadata-filtered hybrid search and the
  installed pgvector provider enforces filters for vector, keyword, and hybrid
  search paths.
- Treat the Red Hat Developer article's Milvus path as implementation evidence,
  not the active Stage 230 provider, unless a future RHOAI/Llama Stack version
  proves filtered hybrid search works with the selected Milvus path.
- Keep PostgreSQL metadata storage separate from the vector store decision.
- Do not commit Hugging Face tokens, database passwords, MaaS API
  keys, or OpenAI keys.
- Do not copy Helm output blindly. Re-author example resources into local
  Kustomize/GitOps manifests and validate fields against official docs or live
  schema.
- Record non-Red Hat images or model artifacts as demo exceptions unless a Red
  Hat source validates or supports them.

## Workflow

1. Confirm active product versions in `docs/PLATFORM_BASELINE.md`.
2. Read `references/source-capture.md`.
3. Route product details through:
   - `rhoai-llama-stack` for Llama Stack provider and API behavior
   - `rhoai-maas-governance` for Nemotron access through MaaS
   - `rhoai-model-serving-platform` for reranker serving if deployed with
     KServe/vLLM
   - `rhoai-model-customization-training` for Docling and data-processing
     examples
   - `rhoai-ai-pipelines` and `rhoai-kfp-pipeline-authoring` for KFP
     automation
   - `project-demo-stage-authoring` for Stage 230 lifecycle
4. Use `references/implementation-pattern.md` to choose the stage architecture.
5. Validate all RAG changes with `references/validation-checklist.md`.

## Stage 230 Target Pattern

The rebuilt Stage 230 proves this flow:

```text
RHOAI product PDFs
  -> Docling conversion and chunking
  -> optional extraction or subset selection
  -> DSPA/KFP automation for repeatable processing
  -> reviewed S3 pipeline artifacts
  -> Files API upload
  -> Vector Stores API attachment with metadata
  -> Llama Stack chunking and embedding
  -> pgvector indexing
  -> query metadata extraction with Nemotron
  -> hybrid vector-store search
  -> reranker scoring
  -> final Nemotron answer through MaaS
```

## RAG Depth: Scripts vs Chatbot

The acceptance and smoke scripts (`rhoai_product_docs_rag_smoke.py`) exercise
the full metadata-aware pipeline: LLM-based query metadata extraction,
topic-filtered hybrid search, neural reranking, and grounded answer generation.

The Streamlit chatbot uses a simplified RAG path: vector-store search with
optional reranking, but without query-time LLM metadata extraction or
topic-based filtering. This is intentional -- the chatbot serves
general-purpose product-doc Q&A where users do not specify metadata categories.

## Vector Store Naming

Stage 230 names each product-document vector store after its producer:

- `stage230-rhoai-34-product-docs-kfp` -- the demo store, populated from
  DSPA/KFP pipeline-generated output; the chatbot question suggestions key
  on this name
- `stage230-rhoai-34-product-docs-dev` -- created by the workbench
  ingestion notebook flow
- `stage230-rhoai-34-product-docs-smoke` -- disposable validation store
  used by scripts when indexing from the repo-committed prepared JSONL;
  it only exists after a script-path smoke run

The suffixes keep pipeline, notebook, and validation content separate so
all can coexist during development without ambiguity about provenance.

## References

- `references/source-capture.md`
- `references/implementation-pattern.md`
- `references/validation-checklist.md`
