# Source Capture

## Official Product Sources

| Source | Role |
|--------|------|
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_llama_stack/index | Product authority for Llama Stack / OGX support posture, API behavior, `LlamaStackDistribution`, provider configuration, vector stores, ingestion, query, PostgreSQL metadata, pgvector, Milvus, and RAG examples |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/govern_llm_access_with_models-as-a-service/index | Product authority for consuming Nemotron through governed MaaS access |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/deploying_models/index | Product authority for model deployment and endpoint behavior when a reranker is served through OpenShift AI |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_on_projects/index | Product authority for project workbench lifecycle, connections, project storage, and project permissions |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_in_your_data_science_ide/index | Product authority for notebook/IDE Git and `requirements.txt` workflows inside the workbench |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_ai_pipelines/index | Product authority if the ingestion workflow later moves into DSPA/KFP |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/customize_models_for_gen_ai_and_agentic_ai_applications/prepare-your-data-for-ai-consumption_custom-models | Product authority for preparing unstructured data with Docling and automating Docling processing with Kubeflow Pipelines |

## Red Hat Narrative And Implementation Sources

| Source | Role |
|--------|------|
| https://developers.redhat.com/articles/2026/05/26/build-enterprise-rag-system-ogx | Red Hat Developer article for the enterprise RAG pattern: metadata filtering, hybrid search, neural reranking, Llama Stack / OGX |
| https://github.com/abdelhamidfg/agnews-rag-demo | GitHub reference implementation linked from the Red Hat Developer article; use as example notebooks and Helm-chart evidence for RAG API patterns, not product authority |
| https://github.com/opendatahub-io/data-processing/tree/stable | Official-doc-linked data processing examples for Docling notebooks and KFP pipelines; use as baseline implementation evidence for unstructured document processing |
| https://github.com/opendatahub-io/data-processing/tree/main/kubeflow-pipelines | Current Docling Kubeflow Pipeline reference implementation; active Stage 230 intentionally follows this tree for the modular standard/VLM layout, Secret-mounted S3 input, `ParallelFor` conversion, and HybridChunker output |

## Reference Repository Snapshot Reviewed

Repository: `abdelhamidfg/agnews-rag-demo`

Relevant paths:

- `chart/templates/llamastack.yaml`
- `chart/templates/milvus.yaml`
- `chart/templates/postgresql.yaml`
- `chart/templates/llama32.yaml`
- `chart/templates/qwen3-reranker.yaml`
- `notebooks/Ingestion_pipeline_ag_news.ipynb`
- `notebooks/retrieval_pipeline_ag_news.ipynb`

Patterns reused:

- vector-store metadata such as `tenant_id` and `version_no`
- file-level metadata such as `category` and document type
- Files API upload followed by Vector Stores API attachment
- remote Milvus vector store provider from the article, reviewed but not
  selected as the active Stage 230 provider
- remote PostgreSQL with pgvector as the active Stage 230 provider after live
  validation showed filtered hybrid search works through the installed
  pgvector path
- Llama Stack `userConfig` ConfigMap for provider wiring when the `rh-dev`
  distribution alone does not expose the article's reranker provider
- hybrid vector-store search
- LLM tool/function call to extract metadata filters
- Llama Stack `/v1alpha/inference/rerank` before final answer generation
- CPU-hosted Qwen3 reranker with vLLM CPU settings from
  `chart/templates/qwen3-reranker.yaml`; adapt request size and batching to
  the active demo worker-node capacity after checking scheduler headroom

Patterns not copied directly:

- direct Llama generation model deployment; this repo uses Stage 220 Nemotron
  through MaaS instead
- direct `helm install`; this repo uses local GitOps/Kustomize and Argo CD
- hardcoded sample passwords; this repo uses generated or environment-local
  Secrets
- notebook-local `%pip install` as the primary workbench setup; this repo
  preinstalls notebook dependencies into the shared workbench PVC and validates
  imports from the running workbench container
- user-facing claims that example images or model artifacts are Red
  Hat-supported unless a Red Hat source says so
- Llama tool-call behavior when the active MaaS/Llama Stack/Nemotron path does
  not support it; use structured JSON chat completion as the current metadata
  extraction fallback and keep tool-call parity as a validation finding

Repository: `opendatahub-io/data-processing`

Relevant paths:

- `kubeflow-pipelines/README.md`
- `kubeflow-pipelines/common/components.py`
- `kubeflow-pipelines/common/constants.py`
- `kubeflow-pipelines/docling-standard/standard_convert_pipeline.py`
- `kubeflow-pipelines/docling-standard/standard_components.py`
- `kubeflow-pipelines/docling-vlm/vlm_convert_pipeline.py`
- `kubeflow-pipelines/docling-vlm/vlm_components.py`

Patterns reused for the RHOAI product-document pipeline phase:

- choose `docling-standard` first for normal PDF conversion, OCR, table
  structure, enrichments, Markdown output, Docling JSON output, and optional
  HybridChunker chunk output
- adapt the reviewed upstream `docling-standard` shape into local KFP source,
  validate compilation, run through DSPA, review S3 artifacts, and then pass
  the generated chunk output to the same RAG smoke helper
- preserve the end-to-end task graph in Stage 230: `import-pdfs`,
  `create-pdf-splits`, `download-docling-models`, `docling-convert-standard`,
  `docling-chunk-and-upload`, `enrich-and-publish-rhoai-chunks`, and
  `ingest-to-vector-store`
- for routine redeploy validation, let the RAG smoke helper index a bounded
  per-topic subset from the generated chunk output; use full-corpus indexing
  only as an explicit deeper validation run
- reserve `docling-vlm` for complex layouts, scanned/image-heavy documents,
  custom page-level instructions, or remote VLM conversion needs
- use KFP `ParallelFor` over PDF splits for scale-out conversion
- support both HTTP/S and S3-compatible input sources
- mount S3 and remote VLM configuration through a Kubernetes Secret named
  `data-processing-docling-pipeline` when adapting the reference pattern
- enable `docling_chunk_enabled` only when the converted output is ready to
  feed RAG ingestion directly
- tune `num_splits`, `num_threads`, timeout, OCR, table mode, and chunk size
  as pipeline parameters rather than hardcoding them in manifests

Patterns not copied directly:

- remote import of compiled YAML from the upstream repository without local
  review and branch selection
- base images from `common/constants.py` without image provenance review; KFP
  component images are explicit pipeline runtime choices and must be recorded
  as Red Hat image, reviewed custom image, or demo exception
- local `pypdf` article detection as proof that the supported Docling runtime
  conversion has executed
- default sample PDFs as proof of the RHOAI product-document use case
- direct S3 credentials or remote VLM API keys in committed manifests

## Source Boundaries

- The official Llama Stack guide defines product behavior and support posture.
- The official model customization guide defines the Docling and KFP
  data-preparation workflow for unstructured documents.
- The article and GitHub repo define a useful demo pattern.
- The article's Milvus provider choice is reference evidence, not mandatory
  project architecture. The active Stage 230 implementation uses pgvector
  because metadata-filtered hybrid search must be a working acceptance gate.
- The GitHub repo does not define our GitOps layout, secret handling, image
  posture, model choice, or production support claims.
- AutoRAG is a separate product workflow and should not be mixed into the first
  rebuilt Stage 230 implementation.
- The `opendatahub-io/data-processing` examples are Red Hat-documented
  examples, but this repo must still review images, dependencies, credentials,
  pipeline parameters, and generated YAML before adopting them.
- Prefer the official-doc-linked `stable` branch for baseline-aligned demo
  implementation unless the stage plan records a different choice. Active
  Stage 230 intentionally uses `main/kubeflow-pipelines` for the modular
  Docling standard pipeline graph and HybridChunker task shape requested by
  the user.
