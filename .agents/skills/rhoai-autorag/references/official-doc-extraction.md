# Official Documentation Extraction

This extraction is derived from the official RHOAI 3.4 guide captured in
`source-capture.md`.

## Support Posture

AutoRAG is Technology Preview in Red Hat OpenShift AI 3.4. Technology Preview
features are not supported with Red Hat production SLAs, might not be
functionally complete, and are not recommended by Red Hat for production use.

## Concept Model

AutoRAG optimizes retrieval-augmented generation configurations for a document
set and use case. The user provides documents and ground-truth test data.
AutoRAG tests combinations of chunking, embedding, retrieval, and generation
settings, ranks resulting RAG patterns by metrics, and generates Jupyter
notebooks for running selected patterns.

Key terms:

- RAG pattern: an optimized configuration with metrics, leaderboard position,
  and generated indexing and inference notebooks
- search space: the parameter combinations AutoRAG evaluates across chunking,
  embedding, retrieval, and generation settings

AutoRAG samples up to 1 GiB of relevant documents based on the test data and
prioritizes documents referenced by the evaluation data.

## Technology Preview Limits

Captured limits:

- only English-language documents are supported
- only remote Milvus vector databases are supported
- inline Milvus is not supported
- maximum per run is three foundation models and two embedding models
- embedded images in documents are not processed
- OCR is not available for PDF documents
- table structure detection is not available for PDF documents

## Test Data

AutoRAG evaluates RAG configurations against JSON test data. Each item should
include:

- `question`: the question submitted to each RAG configuration
- `correct_answers`: one or more expected answers
- `correct_answer_document_ids`: base file names for documents that contain
  the answer

Review rules:

- Include questions that cover the intended document topics.
- Include both factual questions and questions requiring synthesis when the use
  case needs synthesis.
- Prefer answer phrasing grounded in the source documents.
- Use base file names only for document IDs, not folder paths.
- Validate JSON before creating the optimization run.

## Prerequisites

Before creating an AutoRAG optimization run, verify:

- the user has editor access to an OpenShift AI project
- Gen AI studio is enabled in the OpenShift AI dashboard
- a Llama Stack instance is available and configured with foundation and
  embedding models
- a remote Milvus vector database is registered with the Llama Stack instance
- a Llama Stack connection exists in the project and includes base URL and API
  key
- documents are available in an S3-compatible bucket or locally for upload
- when multiple documents are stored in S3, they are in one folder in the
  bucket
- documents use supported formats: PDF, DOCX, PPTX, Markdown, HTML, or TXT
- the JSON evaluation data set is prepared

## Optimization Run Workflow

Dashboard path:

```text
Gen AI studio -> AutoRAG
```

The user selects a project, creates an optimization run, enters name and
description, selects a Llama Stack connection, and configures optimization
settings:

- S3 connection and input documents, or direct file upload
- remote Milvus vector database
- JSON evaluation data set from S3 or upload
- optimization metric
- maximum RAG patterns, from 4 to 20 with default 8
- optional exclusion of foundation and embedding models

Document upload limit:

- locally uploaded files can be up to 32 MiB
- documents selected through the S3 file browser are not subject to the
  dashboard upload size limit captured in the guide

Optimization metrics:

- answer faithfulness
- answer correctness
- context correctness

Run behavior:

- all available Llama Stack foundation and embedding models are selected by
  default
- selecting more than three foundation models or two embedding models can make
  a run fail
- optimization runs cannot be edited after creation
- stopping, archiving, or deleting the underlying run is an AI Pipelines run
  lifecycle operation

## Externally Created Runs

AutoRAG can show runs created from imported AutoRAG pipelines when the imported
pipeline uses the documented names:

- pipeline name: `documents-rag-optimization-pipeline`
- version name pattern: `documents-rag-optimization-pipeline-<version>`

Use `rhoai-ai-pipelines` for importing pipelines and managing runs.

## Evaluation Workflow

After a run completes, the user reviews the AutoRAG leaderboard and pattern
details.

Pattern detail views include:

- metric scores with mean, confidence interval high, and confidence interval
  low values
- configuration settings grouped by chunking, embedding, retrieval, and
  generation
- sample Q&A results with per-question scores, expected answers, and generated
  answers

Review rules:

- Compare all metric columns, not only the optimization metric.
- Review sample Q&A responses before selecting a pattern.
- Save both indexing and inference notebooks for the chosen pattern when the
  pattern will be run from a workbench.

## Running A RAG Pattern

After choosing a pattern, the user runs generated notebooks in a workbench.

Prerequisites:

- selected RAG pattern from a completed AutoRAG optimization run
- downloaded indexing and inference notebooks
- running workbench in the OpenShift AI project
- S3-compatible object storage connection details
- Llama Stack connection details
- foundation and embedding models used by the pattern remain available on the
  Llama Stack instance

Workflow:

- attach the same S3 connection and Llama Stack connection used by the
  optimization run to the workbench
- optionally upload and run the indexing notebook to index additional
  documents
- upload and run the inference notebook
- enter a question and verify grounded answers

The vector database is already populated by the optimization run.

## Metrics

AutoRAG scores each optimization run on three metrics. Scores are from 0 to 1,
and higher is better. Each score includes mean, confidence interval high, and
confidence interval low values.

Metric intent:

- answer faithfulness: whether generated answers are grounded in retrieved
  context rather than model training data
- answer correctness: whether generated answers match expected answers from
  the evaluation data
- context correctness: whether retrieval finds documents relevant to the
  question

Metric interpretation:

- high faithfulness with low answer correctness can indicate grounded but
  incomplete or less accurate context
- high correctness with low faithfulness can indicate reliance on model
  training data instead of retrieved documents
- low context correctness with high answer correctness can indicate the model
  compensates for poor retrieval and may not generalize outside the test set

## Configuration Parameters

User-configurable parameters:

- optimization metric: answer faithfulness, answer correctness, or context
  correctness
- maximum RAG patterns: 4 to 20, default 8
- foundation models discovered from Llama Stack
- embedding models discovered from Llama Stack
- remote Milvus vector database registered with Llama Stack
- input documents
- JSON evaluation data set

Search-space defaults that are not configurable through the dashboard:

- chunking method: recursive character text splitting
- chunk sizes: 1024 and 2048 characters
- chunk overlaps: 128 and 256 characters
- retrieval method: direct chunk retrieval
- number of chunks: 3, 5, and 10
- search modes: vector and hybrid

Hybrid search is available only with Milvus.

Recommended embedding model:

- `BAAI/bge-m3`

## Verification Signals

Expected signals:

- optimization run appears on the AutoRAG page with Running or Pending status
- optimization run progresses to Complete
- completed run opens to a leaderboard
- selected pattern has reviewed metric scores and sample Q&A results
- indexing and inference notebooks download successfully
- workbench can use the S3-compatible connection and Llama Stack connection
- inference notebook returns answers grounded in the selected documents

Failure signals:

- Gen AI studio or AutoRAG page is unavailable
- Llama Stack connection lacks base URL or API key
- no remote Milvus provider is available from Llama Stack
- inline Milvus is used or promised
- selected models exceed the documented maximums
- documents are not English or use unsupported formats
- test data is invalid JSON or document IDs do not match base file names
- generated notebook cannot access S3 or Llama Stack connection details
