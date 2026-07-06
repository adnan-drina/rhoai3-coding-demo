# AutoRAG Patterns

These examples are review patterns. Verify active dashboard behavior, Llama
Stack providers, remote Milvus registration, object storage credentials,
pipeline server state, generated notebooks, and project access before copying
anything into GitOps or runbooks.

## AutoRAG Run Design Record

```text
Project: <data-science-project>
AutoRAG run: <run-name>
Llama Stack connection: <project-connection-name>
Document source: s3://<bucket>/<single-folder>/ or local upload
Vector database: <remote-milvus-provider>
Evaluation data: s3://<bucket>/<path>/eval.json or local upload
Optimization metric: answer faithfulness | answer correctness | context correctness
Maximum RAG patterns: <4-20>
Foundation models selected: <max-3>
Embedding models selected: <max-2>
Technology Preview label: required
```

Review points:

- Confirm Gen AI studio is enabled before promising the workflow.
- Confirm Llama Stack exposes the intended foundation and embedding models.
- Confirm the vector provider is remote Milvus, not inline Milvus.
- Use the run description to capture the business question and corpus version.

## Evaluation Data Shape

```json
[
  {
    "question": "Which policy controls model approval?",
    "correct_answers": [
      "The model governance policy defines approval gates."
    ],
    "correct_answer_document_ids": [
      "governance-policy.md"
    ]
  }
]
```

Review points:

- Keep document IDs as base file names.
- Include alternative expected answers when multiple phrasings are valid.
- Validate JSON before creating the run.
- Avoid sensitive customer data in committed example evaluation sets.

## External AutoRAG Pipeline Naming

```text
Pipeline name:
  documents-rag-optimization-pipeline

Pipeline version:
  documents-rag-optimization-pipeline-<product-version>
```

Review points:

- Use `rhoai-ai-pipelines` for importing pipeline definitions and managing
  pipeline runs.
- Replace `<product-version>` with the active RHOAI product version from
  `docs/PLATFORM_BASELINE.md` when the imported pipeline is version-specific.

## Pattern Selection Review

```text
Metric review:
  Answer faithfulness: <mean / CI low / CI high>
  Answer correctness: <mean / CI low / CI high>
  Context correctness: <mean / CI low / CI high>

Configuration review:
  Chunking: <method, size, overlap>
  Embedding: <model>
  Retrieval: <method, chunk count, search mode>
  Generation: <model>

Sample Q&A review:
  Question: <representative-question>
  Expected answer: <ground-truth-answer>
  Generated answer: <pattern-answer>
  Retrieved document: <source-document>
```

Review points:

- Do not select a pattern from the optimization metric alone.
- Check whether high correctness is coming from retrieval or from model prior
  knowledge.
- Prefer patterns that can explain their answers from the retrieved document
  context.

## Generated Notebook Handoff

```text
1. Save indexing notebook from the selected pattern.
2. Save inference notebook from the selected pattern.
3. Open a running workbench in the same project.
4. Attach the S3-compatible connection used for documents.
5. Attach the Llama Stack connection used for the run.
6. Optional: run indexing notebook for additional documents.
7. Run the inference notebook and ask a question.
8. Confirm the answer is grounded in the documents.
```

Review points:

- The optimization run already populates the vector database.
- Run the indexing notebook only when additional documents must be indexed.
- Do not commit notebooks containing credentials or local output with
  sensitive data.

## Search Space Reminder

```text
Chunking method: recursive character text splitting
Chunk sizes: 1024, 2048
Chunk overlaps: 128, 256
Retrieval method: direct chunk retrieval
Number of chunks: 3, 5, 10
Search modes: vector, hybrid
Recommended embedding model: BAAI/bge-m3
```

Review points:

- These are default search-space values from the captured guide, not arbitrary
  demo tuning choices.
- Hybrid search is available only with Milvus.
