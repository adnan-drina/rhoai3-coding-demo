# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product baseline | `docs/PLATFORM_BASELINE.md` |
| Document title | Working with AutoRAG |
| Guide URL | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_autorag/index |
| Documentation category | Develop / Working with AutoRAG |
| Retrieved date | 2026-06-10 |
| Sections used | Preface; 1 AutoRAG overview; 1.1 AutoRAG workflow; 1.2 AutoRAG terminology; 1.3 Technology Preview limitations; 1.4 Viewing externally created runs; 2 Prepare test data for AutoRAG; 3 Create an AutoRAG optimization run; 4 Evaluate AutoRAG results; 5 Run the RAG pattern; 6 AutoRAG evaluation metrics; 6.1 Metric combinations; 7 AutoRAG configuration parameters; 7.1 User-configurable parameters; 7.2 Search space defaults; 7.3 Recommended embedding models |

## Related Official Sources

| Source | Role |
|--------|------|
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_llama_stack/index | Llama Stack provider, vector database, model, connection, RAG, and API context |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/experimenting_with_models_in_the_gen_ai_playground/index | Gen AI studio feature context and adjacent playground RAG boundary |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_ai_pipelines/index | Imported pipeline naming and underlying run lifecycle context |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_data_in_an_s3-compatible_object_store/index | S3-compatible object storage and workbench data access context |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/working_on_projects | Project, workbench, and connection lifecycle context |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_in_your_data_science_ide/index | Generated indexing and inference notebook execution in a workbench |
| https://access.redhat.com/support/offerings/techpreview | Technology Preview support scope |

## Reference Implementation Sources

| Source | Role | Retrieved |
|--------|------|-----------|
| https://github.com/red-hat-data-services/red-hat-ai-examples/tree/main/examples/autorag | Example-only AutoRAG walkthrough: Llama Stack connection type creation, S3 layout, benchmark data example, UI and KFP-native run paths | 2026-07-02 |
| https://github.com/red-hat-data-services/pipelines-components/tree/rhoai-3.4/pipelines/training/autorag/documents_rag_optimization_pipeline | Authoritative compiled `documents-rag-optimization-pipeline` and parameter contract for the active baseline (`llama_stack_vector_io_provider_id`, S3 secret env keys, `LLAMA_STACK_CLIENT_BASE_URL`/`LLAMA_STACK_CLIENT_API_KEY` secret keys) | 2026-07-02 |
| https://www.redhat.com/en/blog/introducing-auto-ml-and-auto-rag-guided-experience-ai-engineers-red-hat-openshift-ai | Positioning-only source for AutoRAG next to AutoML | 2026-07-02 |

Recorded source conflict: the red-hat-ai-examples tutorial (older, Developer
Preview era) states that only `inline::milvus` is supported and names the
parameter `llama_stack_vector_database_id`. The official RHOAI 3.4 guide
states that only remote Milvus is supported and inline Milvus is not, and the
`rhoai-3.4` pipelines-components branch names the parameter
`llama_stack_vector_io_provider_id`. The official guide and the `rhoai-3.4`
pipeline source win. Verify the accepted provider id against the live
pipeline on the first run.

## Supporting Project Sources

| Source | Role |
|--------|------|
| `docs/PLATFORM_BASELINE.md` | Active RHOAI/OCP baseline and source hierarchy |
| `AGENTS.md` | OpenShift safety guard and GitOps operating constraints |
| `.agents/skills/rhoai-llama-stack/SKILL.md` | Llama Stack, model, provider, and vector database boundary |
| `.agents/skills/rhoai-gen-ai-playground/SKILL.md` | Gen AI studio playground boundary |
| `.agents/skills/rhoai-ai-pipelines/SKILL.md` | Pipeline server and run lifecycle boundary |
| `.agents/skills/rhoai-s3-object-storage-data/SKILL.md` | S3-compatible data boundary |
| `.agents/skills/rhoai-project-workflows/SKILL.md` | Project, workbench, and connection boundary |
| `.agents/skills/rhoai-data-science-ide-workflows/SKILL.md` | Generated notebook execution boundary |
| `.agents/skills/rhoai-model-evaluation/SKILL.md` | Formal evaluation evidence boundary outside AutoRAG |

## Source Boundaries

- Product authority: the official Red Hat OpenShift AI 3.4 Working with
  AutoRAG guide above.
- The guide defines dashboard workflows for AutoRAG optimization runs,
  evaluation data preparation, leaderboard review, generated indexing and
  inference notebooks, and metric interpretation.
- AutoRAG is Technology Preview in the captured guide.
- The guide does not replace the Llama Stack guide, Gen AI playground guide,
  AI Pipelines guide, S3 object storage guide, or workbench IDE guide.
- Verification: AutoRAG page run status, completed leaderboard, pattern
  details, generated notebook download, workbench notebook execution, grounded
  responses, and metric interpretation.

## Active Stage 230 Implementation

Stage 230 (`stage-230-private-data-rag`) implements AutoRAG on the active
baseline:

- Corpus: scoped AutoRAG input under `autorag/rhoai-product-docs/input/`
  (Evaluating AI systems, Guardrails, and AutoRAG guides); the full 6-guide
  corpus remains the chatbot/pgvector application path.
- Ground-truth data: 12-question validate-and-protect benchmark at
  `stage-230-private-data-rag/data/rhoai-product-docs/autorag/benchmark_data.json`,
  mirrored to `autorag/rhoai-product-docs/` by `deploy.sh`.
- Generation: Nemotron plus governed external `gpt-4o-mini`, both through
  MaaS with quota from the dedicated `enterprise-rag-autorag`
  MaaSSubscription sized for optimization bursts.
- Embeddings: `granite-embedding-30m` and `all-minilm-l6-v2` served as vLLM
  CPU KServe InferenceServices (chunked pooling for long inputs, `Recreate`
  strategy) registered as `remote::vllm` Llama Stack providers; inline
  sentence-transformers keeps only the nomic app-path model and the
  GPU-oriented `BAAI/bge-m3` registration. Remote Milvus registered as the
  `milvus` vector_io provider (pgvector remains the app retrieval path).
- Connection: `autorag-llama-stack-connection` Secret using the GitOps
  `llama-stack-connection` dashboard connection type.
- Runner: `stage-230-private-data-rag/run-autorag-pipeline.sh` imports the
  vendored `rhoai-3.4` compiled pipeline under the documented name (CSV
  image alignment, `SSL_CERT_FILE` injection, explicit bucket-root
  `pipeline_root`), pre-warms embedding models, flushes the MaaS
  external-model gateway connection pool, and stores evidence in
  `stage230-autorag-pipeline-evidence`.
- Dashboard contract (verified live): `spec.dashboardConfig.autorag: true`
  feature flag, documented pipeline display name, HTTPS DSPA object
  storage, and run artifacts at the KFP default bucket-root layout.

## Unresolved Or Environment-Specific Items

- Placeholder `LLAMA_STACK_CLIENT_API_KEY` acceptance against an
  unauthenticated Llama Stack service.
  Verification: first live Stage 230 AutoRAG run.
- Accepted vector_io provider id for the shipped pipeline.
  Verification: first live Stage 230 AutoRAG run with provider id `milvus`.
- Imported AutoRAG pipeline version string.
  Verification: align imported pipeline version names with the active RHOAI
  product version in `docs/PLATFORM_BASELINE.md`.
