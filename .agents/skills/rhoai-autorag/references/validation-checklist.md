# Validation Checklist

Use this checklist before accepting AutoRAG README content, runbooks, notebooks,
GitOps manifests, or demo scripts.

## Source Alignment

- Product links use the active baseline in `docs/PLATFORM_BASELINE.md`.
- The official Working with AutoRAG source is recorded when the workflow is
  introduced.
- AutoRAG is labeled Technology Preview in user-facing material.
- Llama Stack and vector-store prerequisites are checked with
  `rhoai-llama-stack`.
- Gen AI studio feature context is checked with `rhoai-gen-ai-playground`.
- AI Pipelines run lifecycle is checked with `rhoai-ai-pipelines`.
- S3-compatible storage and project connections are checked with
  `rhoai-project-workflows` and `rhoai-s3-object-storage-data`.
- Workbench notebook behavior is checked with
  `rhoai-data-science-ide-workflows`.
- Formal evaluation claims outside the AutoRAG leaderboard are checked with
  `rhoai-model-evaluation`.

## Prerequisite Review

- User has editor access to the selected OpenShift AI project.
- Gen AI studio is enabled in the dashboard.
- Llama Stack instance is available.
- Llama Stack has foundation and embedding models available.
- Remote Milvus vector database is registered with Llama Stack.
- Inline Milvus is not used for AutoRAG.
- Project has a Llama Stack connection with base URL and API key.
- Documents are available in S3-compatible storage or locally for upload.
- Multiple S3 documents for a run are in a single bucket folder.
- JSON evaluation data exists and is valid.

## Document Review

- Documents are in English.
- File formats are limited to PDF, DOCX, PPTX, Markdown, HTML, or TXT.
- Local uploads are 32 MiB or smaller.
- The workflow does not rely on embedded images in documents.
- The workflow does not rely on OCR for PDFs.
- The workflow does not rely on PDF table structure detection.

## Evaluation Data Review

- JSON root is an array.
- Each item has a `question`.
- Each item has one or more `correct_answers`.
- Each item has `correct_answer_document_ids` using base file names.
- Questions cover the intended document topics.
- Expected answers are grounded in the source documents.
- Document IDs match files in the document set.

## Run Configuration Review

- Optimization run name and description are meaningful for later evidence.
- Llama Stack connection is the intended one.
- S3 connection and document selection are the intended inputs.
- Selected remote Milvus provider is the intended one.
- Optimization metric is chosen intentionally:
  - answer faithfulness for grounded answers
  - answer correctness for matching expected answers
  - context correctness for retrieval quality
- Maximum RAG patterns is between 4 and 20.
- No more than three foundation models are selected.
- No more than two embedding models are selected.
- Run immutability is understood before creation.
- Stop/archive/delete operations are routed through AI Pipelines run lifecycle
  guidance.
- Externally imported AutoRAG pipeline names match the documented pattern.

## Evaluation And Notebook Review

- Leaderboard is reviewed only after the run status is Complete.
- The number of leaderboard patterns is compared against the requested
  maximum: the underlying engine exports only successful evaluations, so
  embedding timeouts, input-length rejections, generation errors, and MaaS
  rate limits remove patterns without any UI trace. When the leaderboard is
  thinner than the budget, review the `rag-templates-optimization` pod logs
  for `IndexingError` and `GenerationError` warnings.
- Embedding serving meets the engine's fixed request shape: batches up to
  2048 chunks within a 60-second client timeout, and long inputs accepted
  (served vLLM embedding models need chunked pooling; inline
  sentence-transformers truncates silently).
- All metric columns are reviewed, not only the optimization metric.
- Pattern details are checked for metric confidence intervals.
- Chunking, embedding, retrieval, and generation settings are captured when
  used as evidence.
- Sample Q&A results are reviewed before selecting a pattern.
- Both indexing and inference notebooks are downloaded when the pattern will be
  used in a workbench.
- Workbench has the same S3-compatible connection and Llama Stack connection
  used for the optimization run.
- Inference notebook returns answers grounded in the documents.

## Optional Read-Only Checks

Run only after following the OpenShift safety guard in `AGENTS.md`:

```bash
oc get datasciencepipelinesapplications -A
oc get pipelinerun -A | rg -i 'autorag|rag|documents-rag'
oc get llamastackdistribution -A
oc get secret -n <project> | rg -i 'llama|s3|milvus'
```

Schema or route checks:

```bash
oc get odhdashboardconfig -A -o yaml
oc get route -A | rg -i 'llama|milvus'
```

## Fail Conditions

Stop and correct the work if any of these are true:

- AutoRAG is presented as production-supported without Technology Preview
  context.
- Inline Milvus is claimed or configured for AutoRAG.
- Non-English documents are used without an official baseline exception.
- Unsupported document formats are used.
- OCR, embedded-image processing, or PDF table detection is promised.
- More than three foundation models or two embedding models are selected.
- JSON evaluation data omits questions, expected answers, or document IDs.
- Document IDs include folder paths instead of base file names.
- A run is treated as editable after creation.
- S3, Llama Stack, or provider credentials are committed.
- A pattern is selected solely from one metric without sample Q&A review.
