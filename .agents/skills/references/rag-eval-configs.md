# RAG Evaluation Configs Reference

## Table of Contents

- [Test YAML Structure](#test-yaml-structure)
- [Scenarios](#scenarios)
- [Scoring Configuration](#scoring-configuration)
- [Judge Prompt Template](#judge-prompt-template)
- [Report Format](#report-format)
- [Pipeline Architecture](#pipeline-architecture)

## Test YAML Structure

```yaml
name: "Human-readable scenario name"
description: "What this scenario tests"
vector_db_id: acme_corporate          # vector store name, or null for pre-RAG
model_id: nemotron-3-nano-30b-a3b     # candidate model
mode: post-rag                  # pre-rag | post-rag

scoring_params:
  "llm-as-judge::base":
    type: llm_as_judge
    judge_model: gpt-5
    prompt_template: scoring-templates/judge_prompt.txt
    judge_score_regexes:
      - "Answer: (A|B|C|D|E)"

tests:
  - prompt: "What products does ACME Corp manufacture?"
    expected_result: "ACME manufactures semiconductor lithography equipment..."
    expected_tools: ["builtin::rag/knowledge_search"]  # empty for pre-RAG
  - prompt: "..."
    expected_result: "..."
    expected_tools: []
```

### Field Reference

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Display name in HTML report |
| `description` | Yes | What the scenario tests |
| `vector_db_id` | Yes | Vector store name (null for pre-RAG) |
| `model_id` | Yes | Candidate model ID |
| `mode` | Yes | `pre-rag` or `post-rag` |
| `scoring_params` | Yes | Judge configuration |
| `tests` | Yes | Array of test cases |
| `tests[].prompt` | Yes | Question to ask the model |
| `tests[].expected_result` | Yes | Reference answer for judging |
| `tests[].expected_tools` | No | Tools the model should use (for logging) |

## Scenarios

| File | Mode | Vector DB | Tests | Purpose |
|------|------|-----------|-------|---------|
| `acme_corporate_pre_rag_tests.yaml` | pre-rag | null | 6 | Baseline: model's pre-training knowledge of ACME |
| `acme_corporate_post_rag_tests.yaml` | post-rag | acme_corporate | 6 | Same questions with RAG context — expect A/B grades |
| `whoami_pre_rag_tests.yaml` | pre-rag | null | 4 | Baseline: model knows nothing about the candidate |
| `whoami_post_rag_tests.yaml` | post-rag | whoami | 4 | Same questions with CV context — expect A/B grades |

Pre-RAG and post-RAG scenarios use the **same questions and expected answers**. The only
difference is whether document context is provided. This makes the comparison meaningful:
improvement is due to RAG, not different questions.

## Scoring Configuration

### Judge Model

| Field | Value |
|-------|-------|
| Model | OpenAI `gpt-5.4-mini` through MaaS using resource alias `gpt-5-4-mini`, when approved external processing is allowed |
| Endpoint | MaaS OpenAI-compatible endpoint for the approved external model |
| Transport | MaaS, with centralized credentials, subscription policy, rate limits, token limits, and telemetry |

Using a separate judge is a design decision: the same model for both candidate
and judge can produce biased judgments. For private-only runs, document the
fallback judge strategy and expected bias risk.

### Scoring Scale

| Grade | Meaning | Report Color |
|-------|---------|-------------|
| A | Same key facts as expected answer | Green |
| B | Superset — contains all expected facts plus additional correct details | Green |
| C | Subset — partially correct, missing some key facts | Yellow |
| D | Minor differences, no factual errors | Grey |
| E | Contradicts or is factually wrong compared to expected answer | Red |

### Extraction

The judge's response is parsed with regex: `Answer: (A|B|C|D|E)`. The judge prompt
must end with "Answer: " to anchor this extraction.

## Judge Prompt Template

Located at `eval-configs/scoring-templates/judge_prompt.txt`:

```
Given the following query, expected answer, and generated answer, evaluate
the quality of the generated answer.

Query: {input_query}
Expected Answer: {expected_answer}
Generated Answer: {generated_answer}

Rate the generated answer using ONLY one of these grades:
A - Contains the same key facts as the expected answer
B - Contains all expected facts plus additional correct information
C - Contains only a subset of the expected facts
D - Has minor differences but no factual errors
E - Contradicts or is factually incorrect compared to expected answer

Provide a brief justification, then end with:
Answer: <grade>
```

Placeholders `{input_query}`, `{expected_answer}`, `{generated_answer}` are filled
by the pipeline at runtime.

## Report Format

Each scenario produces an HTML report with columns:

| # | Question | Generated Answer | Expected | Judge Score | Tools |

Reports are uploaded to MinIO:
- Path: `s3://rhoai-storage/eval-results/{run_id}/{safe_name}_report.html`
- `run_id` is a timestamp-based ID
- `safe_name` is derived from the scenario `name` field

## Pipeline Architecture

### KFP Pipeline (`run-eval.sh`)

```
eval_pipeline
  ├── scan_tests        # Finds *_tests.yaml in /shared-data/eval-configs
  └── run_and_score_tests  # For each config:
        ├── Generate answers (via LlamaStack or direct vLLM)
        ├── Judge each answer (via approved MaaS judge)
        ├── Produce HTML report
        └── Upload to MinIO S3
```

Infrastructure:
- DSPA: `dspa-rag` (reuses step-07 Data Science Pipelines)
- PVC: `rag-pipeline-workspace` (shared between pipeline components)
- Test configs: copied from ConfigMap to PVC via PostSync Job `eval-config-sync`

### Pod-Based (`run-eval-report.sh`)

Runs the same logic inside the `lsd-rag` pod directly:
1. Copies test configs from local filesystem to the pod
2. Executes evaluation inline
3. Downloads HTML reports locally

Useful for debugging because you can see stdout/stderr directly.
