---
name: rhoai-autorag
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when documenting, reviewing, or operating Red Hat OpenShift AI AutoRAG
  workflows from the official Working with AutoRAG guide: Technology Preview
  posture, RAG pattern optimization, JSON ground-truth evaluation data,
  English document and file-format limits, Llama Stack and remote Milvus
  prerequisites, Gen AI studio AutoRAG dashboard runs, externally imported
  AutoRAG pipeline naming, leaderboard evaluation, faithfulness/correctness/
  context-correctness metrics, generated indexing and inference notebooks,
  search-space defaults, and recommended embedding model guidance. Do NOT use
  for Llama Stack server/provider/vector-store configuration (use
  rhoai-llama-stack), generic Gen AI playground workflows (use
  rhoai-gen-ai-playground), AI Pipelines server administration (use
  rhoai-ai-pipelines), S3 object operations outside AutoRAG (use
  rhoai-s3-object-storage-data), workbench/IDE workflows outside generated
  AutoRAG notebooks (use rhoai-data-science-ide-workflows), or live cluster
  changes without the OpenShift safety guard.
---

# RHOAI AutoRAG

Use this skill for Red Hat OpenShift AI AutoRAG user workflows on the active
product baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product workflow details.
Official Red Hat documentation is product authority. This skill adapts the
official Working with AutoRAG guide to this repo's demo workflow and governance
review model.

## Scope

This skill covers:

- AutoRAG Technology Preview support posture
- AutoRAG concept model, RAG patterns, and search space terminology
- English-only document support and Technology Preview limitations
- JSON evaluation data with questions, expected answers, and source document
  IDs
- Gen AI studio AutoRAG optimization run creation
- Llama Stack connection, foundation model, embedding model, and remote Milvus
  prerequisites
- document source rules for S3-compatible storage and local upload
- externally imported AutoRAG pipeline naming rules
- leaderboard review and pattern detail interpretation
- faithfulness, answer correctness, and context correctness metrics
- generated indexing and inference notebook handoff to a workbench
- user-configurable parameters and non-configurable search-space defaults
- recommended embedding model guidance from the official docs

Use other skills for adjacent work:

- `rhoai-llama-stack` for Llama Stack Operator activation,
  `LlamaStackDistribution`, providers, vector stores, Milvus registration,
  model availability, API behavior, OAuth/ABAC, CA trust, and HA/autoscaling
- `rhoai-gen-ai-playground` for product playground RAG uploads, prompt
  management, MCP testing, custom endpoints, and AI asset endpoint workflows
- `rhoai-ai-pipelines` for pipeline server configuration, imported pipeline
  management, pipeline run lifecycle, logs, and DSPA troubleshooting
- `rhoai-s3-object-storage-data` for object storage operations from
  workbenches
- `rhoai-project-workflows` for projects, workbenches, project connections,
  access, and cluster storage
- `rhoai-data-science-ide-workflows` for running generated indexing and
  inference notebooks in a workbench
- `rhoai-model-evaluation` for formal evaluation evidence outside the product
  AutoRAG leaderboard

## Demo Policy

For this repo:

- Label AutoRAG as Technology Preview in READMEs, runbooks, presentations, and
  demo scripts. Do not present it as production SLA-backed.
- Treat AutoRAG as a product workflow for exploring and selecting RAG
  configurations, not as a substitute for governed application implementation.
- Require Gen AI studio, a data science project, Llama Stack connection, and
  remote Milvus before promising an AutoRAG run.
- Do not claim inline Milvus support for AutoRAG. The official AutoRAG guide
  requires remote Milvus.
- Use English-language documents for AutoRAG demos unless the active official
  baseline changes.
- Keep documents in supported formats: PDF, DOCX, PPTX, Markdown, HTML, or
  TXT.
- Do not claim OCR, embedded-image processing, or PDF table-structure
  detection during Technology Preview.
- Keep at most three foundation models and two embedding models selected for a
  run.
- Treat optimization runs as immutable after creation. Use AI Pipelines run
  workflows to stop, archive, or delete the underlying pipeline run.
- Use generated indexing and inference notebooks as reviewable handoff
  artifacts. Do not treat them as the final production RAG application.
- Use leaderboard scores together with sample Q&A review. Do not select a
  pattern solely because one metric is high.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/source-capture.md` and
   `references/official-doc-extraction.md`.
3. Confirm Technology Preview posture is acceptable for the requested demo
   surface.
4. Decide whether the task is:
   - AutoRAG concept or README authoring
   - prerequisite review for Gen AI studio, Llama Stack, Milvus, S3, and
     workbench access
   - JSON evaluation data design
   - optimization run design
   - external AutoRAG pipeline import review
   - leaderboard and pattern selection
   - indexing or inference notebook handoff
   - metric and search-space interpretation
5. Use `examples/autorag-patterns.md` for focused review patterns.
6. For live cluster work, follow the OpenShift safety guard in `AGENTS.md`.
7. Validate with `references/validation-checklist.md`.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/autorag-patterns.md`
