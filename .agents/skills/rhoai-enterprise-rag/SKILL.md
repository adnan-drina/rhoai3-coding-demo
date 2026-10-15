---
name: rhoai-enterprise-rag
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when someone asks for an enterprise RAG application on OpenShift AI in
  this repo (metadata-aware retrieval, Files and Vector Stores APIs, pgvector,
  hybrid search, reranking, document ingestion pipelines) or cites the former
  "Stage 230 private-data RAG" material. No RAG application is deployed here;
  the skill states what exists and where a RAG stage would go. Do NOT use for
  OGX platform enablement and the playground server (use rhoai-llama-stack),
  playground RAG uploads (use rhoai-gen-ai-playground), AutoRAG (use
  rhoai-autorag), or MaaS access (use rhoai-maas-governance).
---

# RHOAI Enterprise RAG

Repo-specific skill. **Not deployed in this demo.** The former Stage 230
private-data RAG (Llama Stack distribution, pgvector store, Docling pipeline,
reranker, Streamlit chatbot) came from the predecessor repository and is not
in this repo: there is no `stage-230-*` directory, no `enterprise-rag`
project, and no vector store in Git. The current stage list ends at 130
(`AGENTS.md`), and none of the stages is about RAG.

## What exists that a RAG stage could build on

| Building block | Where in Git | Official section |
|---|---|---|
| OGX enabled (`ogx` Managed) by the Stage 040 enablement Job; Llama Stack operator kept Removed | `gitops/stages/040-governed-models-as-a-service/maas-platform/jobs/enable-maas-job.yaml` | [Overview of OGX][overview] |
| Playground OGX server with dashboard-generated pgvector storage in `demo-sandbox` | `gitops/stages/040-governed-models-as-a-service/genai-studio/README.md` | [Resources created with a playground][playres] |
| Governed generation models through MaaS (`qwen3-8-27b`, approved external models) | `gitops/stages/040-governed-models-as-a-service/local-models/`, `gitops/stages/040-governed-models-as-a-service/external-models/` | [OGX API provider support][providers] |
| AI pipelines (DSC `aipipelines` Managed) for repeatable ingestion | `gitops/stages/050-model-evaluation/mlflow/dsc-enablement/` | see `rhoai-ai-pipelines` |
| S3 buckets through ObjectBucketClaims | `gitops/stages/010-openshift-ai-platform-foundation/sandbox-storage/` | see `rhoai-s3-object-storage-data` |

No embedding model or reranker is served by this repo.

## If a RAG stage is added

1. Plan it with `project-demo-stage-authoring`: a new stage number after 130,
   README with selection rationale, `deploy.sh`/`validate.sh`, and GitOps
   components under `gitops/stages/<stage>/`.
2. Run a dedicated OGX server per project (not the playground's), with a
   PostgreSQL metadata store and a vector database chosen from
   [Select a vector database][vectordb]; read the [security reference][security].
3. Reach generation and embedding models only through MaaS subscriptions;
   keep keys in Secrets created from `.env` helpers.
4. Validate mechanically: retrieval returns the expected document for known
   questions, and answers cite files ([file citations][citations]).
5. Record any non-Red Hat image or model as a demo exception in the stage
   README.

## Official documentation (OpenShift AI 3.5)

| Topic | Section |
|---|---|
| OGX overview, APIs | [Overview][overview], [OpenAI-compatible APIs][openai], [Provider support][providers] |
| Vector stores | [Select a vector database][vectordb], [PostgreSQL in OGX][postgres] |
| Citations | [File citation annotations][citations] |
| Security, tenancy | [Security reference][security], [Multi-tenancy][tenancy] |

## Related skills

`rhoai-llama-stack`, `rhoai-gen-ai-playground`, `rhoai-autorag`,
`rhoai-ai-pipelines`, `rhoai-maas-governance`,
`rhoai-model-customization-training`, `project-demo-stage-authoring`.

[overview]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ogx/index#overview-of-ogx_rag
[openai]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ogx/index#openai-compatible-apis-in-ogx_rag
[providers]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ogx/index#ogx-provider-support_rag
[playres]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ogx/index#resources-created-when-you-create-a-playground_rag
[vectordb]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ogx/index#select-and-deploy-a-vector-database_rag
[postgres]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ogx/index#using-postgresql-in-ogx_rag
[citations]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ogx/index#openai-compatible-file-citation-annotations_rag
[security]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ogx/index#ogx-security-guide_rag
[tenancy]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ogx/index#ogx-multi-tenancy_rag
