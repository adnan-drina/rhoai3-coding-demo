---
name: rhoai-model-evaluation
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Guide RHOAI evaluation workflows once active evaluation content exists;
  during the reimplementation, use this skill to rebuild EvalHub, RAG
  evaluation, KFP/MLflow evidence, RAGAS patterns, and standard model
  benchmarking workflows from legacy references. Use when the user asks to run
  evaluation, evaluate a model, benchmark model performance, check RAG quality,
  compare pre-RAG vs post-RAG answers, run LM-Eval, create an LMEvalJob,
  interpret eval results, add new test questions, or modify the judge prompt.
  Also use when eval pipelines fail, LMEvalJob pods are stuck, or evaluation
  reports show unexpected scores.
  Do NOT use for official product EvalHub, LM-Eval, LMEvalJob, or automated
  risk assessment workflows from the Red Hat evaluation guide (use
  rhoai-evaluation), product AutoRAG dashboard optimization runs, leaderboard
  review, or generated notebooks (use rhoai-autorag), MLflow platform
  installation, SDK authentication, or artifact storage configuration (use
  rhoai-mlflow), Training Hub, SDG Hub, Docling, or ITS Hub model
  customization workflows (use rhoai-model-customization-training), chatbot UI
  changes (use rhoai-chatbot-customization), deployment issues (use
  env-troubleshoot), or inference performance tuning (see step-06 GuideLLM
  benchmarks).
---

# Model Evaluation

Structured workflow for running model evaluations in the active-baseline RHOAI demo — both
RAG quality assessment (LLM-as-judge) and standard benchmarks (LM-Eval).

## Reimplementation Status

The active implementation is being rewritten. No active evaluation scripts,
EvalHub GitOps content, LMEvalJob templates, or Step 08 README exists yet.
Treat the file paths and command examples in this skill as legacy reference
material for rebuilding evaluation, not as active-project instructions.

Do not run or modify scripts from `backup/legacy-implementation-2026-06-09/`
unless the user explicitly asks to restore or inspect the legacy implementation.

## Two Evaluation Paths

```
Path A: RAG Evaluation (LLM-as-Judge)
  ┌────────────┐    ┌──────────────┐    ┌────────────┐    ┌──────────┐
  │ Test YAML  │ →  │ Generate     │ →  │ Judge with │ →  │ HTML     │
  │ questions  │    │ answers via  │    │ approved   │    │ report   │
  │ + expected │    │ Nemotron     │    │ MaaS judge │    │ → MinIO  │
  └────────────┘    └──────────────┘    └────────────┘    └──────────┘

Path B: Standard Benchmarks (LM-Eval)
  ┌────────────┐    ┌──────────────┐    ┌────────────┐
  │ LMEvalJob  │ →  │ TrustyAI     │ →  │ Dashboard  │
  │ CR applied │    │ runs tasks   │    │ results    │
  │ on demand  │    │ via vLLM     │    │ + PVC logs │
  └────────────┘    └──────────────┘    └────────────┘
```

## When to Use

- Running RAG evaluation (pre-RAG vs post-RAG comparison)
- Running LM-Eval standard benchmarks (hellaswag, arc_challenge, etc.)
- Adding or modifying test questions
- Changing the judge prompt or scoring scale
- Interpreting evaluation reports
- Debugging failed eval pipelines or stuck LMEvalJob pods
- Creating custom LMEvalJob CRs for new models or tasks

## Key Files

| File | Purpose |
|------|---------|
| `backup/legacy-implementation-2026-06-09/steps/step-08-model-evaluation/run-rag-eval.sh` | Run RAG eval via KFP pipeline |
| `backup/legacy-implementation-2026-06-09/steps/step-08-model-evaluation/run-eval-report.sh` | Run RAG eval as pod (simpler debugging) |
| `backup/legacy-implementation-2026-06-09/steps/step-08-model-evaluation/run-evalhub-smoke.sh` | Run EvalHub smoke evaluation |
| `backup/legacy-implementation-2026-06-09/steps/step-08-model-evaluation/run-evalhub-rag-scenarios.sh` | Run EvalHub RAG scenario collection |
| `backup/legacy-implementation-2026-06-09/steps/step-08-model-evaluation/materialize-evalhub-rag-mlflow.sh` | Materialize EvalHub RAG results into MLflow evidence |
| `backup/legacy-implementation-2026-06-09/steps/step-08-model-evaluation/run-lmeval.sh` | Submit LMEvalJob CR |
| `backup/legacy-implementation-2026-06-09/steps/step-08-model-evaluation/eval-configs/*.yaml` | Test question sets (4 scenarios) |
| `backup/legacy-implementation-2026-06-09/steps/step-08-model-evaluation/eval-configs/scoring-templates/judge_prompt.txt` | Judge prompt template |
| `backup/legacy-implementation-2026-06-09/steps/step-08-model-evaluation/kfp/eval_pipeline.py` | Optional KFP pipeline definition |
| `backup/legacy-implementation-2026-06-09/gitops/step-08-model-evaluation/base/evalhub/` | EvalHub CR, PostgreSQL, route, tenant RBAC, and provider configuration |
| `backup/legacy-implementation-2026-06-09/gitops/step-08-model-evaluation/base/lmeval/*.yaml` | LMEvalJob CR templates |
| `backup/legacy-implementation-2026-06-09/gitops/step-08-model-evaluation/base/eval-configs/` | GitOps-managed test configs |
| `backup/legacy-implementation-2026-06-09/steps/step-08-model-evaluation/README.md` | Design decisions, architecture |

## Instructions

### Read Before You Write

1. Read `backup/legacy-implementation-2026-06-09/steps/step-08-model-evaluation/README.md`
2. For RAG eval details, read `references/rag-eval-configs.md`
3. For LM-Eval templates, read `references/lmeval-templates.md`

### Path A: Run RAG Evaluation

**Prerequisites:** Steps 01-05 and 07 deployed. Vector stores populated with
`acme_corporate` and `whoami` data.

```bash
# Via KFP pipeline (platform-native, uses DSPA)
./backup/legacy-implementation-2026-06-09/steps/step-08-model-evaluation/run-rag-eval.sh

# Via pod (simpler, good for debugging)
./backup/legacy-implementation-2026-06-09/steps/step-08-model-evaluation/run-eval-report.sh
```

**Output:** HTML reports uploaded to MinIO at `s3://rhoai-storage/eval-results/{run_id}/`

**Scoring scale:**
| Grade | Meaning | Color |
|-------|---------|-------|
| A | Same key facts as expected | Green |
| B | Superset of expected (more detail) | Green |
| C | Subset of expected (partial) | Yellow |
| D | Minor differences, no factual error | Grey |
| E | Contradicts expected answer | Red |

### Path B: Run LM-Eval Benchmark

**Prerequisites:** Steps 01-05 deployed. Model InferenceService ready.

```bash
# Benchmark nemotron-3-nano-30b-a3b (default 50 samples/task)
./backup/legacy-implementation-2026-06-09/steps/step-08-model-evaluation/run-lmeval.sh nemotron-3-nano-30b-a3b

# Benchmark with 200 samples
./backup/legacy-implementation-2026-06-09/steps/step-08-model-evaluation/run-lmeval.sh nemotron-3-nano-30b-a3b 200
```

**Tasks:** hellaswag, arc_challenge, winogrande, boolq

**Results:** RHOAI Dashboard → Develop & train → Evaluations, or:
```bash
oc get lmevaljob -n private-ai
oc get lmevaljob <name> -n private-ai -o yaml
```

### Adding New Test Questions

1. Edit the relevant test YAML in `backup/legacy-implementation-2026-06-09/steps/step-08-model-evaluation/eval-configs/`
2. Copy to `backup/legacy-implementation-2026-06-09/gitops/step-08-model-evaluation/base/eval-configs/` (files must match)
3. Follow the test YAML structure documented in `references/rag-eval-configs.md`
4. Re-run evaluation to verify

### Modifying the Judge Prompt

1. Edit `backup/legacy-implementation-2026-06-09/steps/step-08-model-evaluation/eval-configs/scoring-templates/judge_prompt.txt`
2. Copy to `backup/legacy-implementation-2026-06-09/gitops/step-08-model-evaluation/base/eval-configs/scoring-templates/`
3. The prompt uses placeholders: `{input_query}`, `{expected_answer}`, `{generated_answer}`
4. Must end with "Answer: " to anchor the A-E extraction regex

### Critical Constraints

For the full set of constraints, read
`references/evaluation-development-patterns.md`: judge model selection,
test question integrity, on-demand LMEvalJob pattern, EvalHub/KFP/pod path
selection, and judge prompt anchoring. Post-RAG eval depends on vector stores —
run step-07 ingestion first.

### Validation

```bash
# Check RAG eval pipeline runs
oc get pipelinerun -n private-ai -l pipeline-name=rag-evaluation

# Check LMEvalJob status
oc get lmevaljob -n private-ai

# Check eval reports in MinIO
oc exec deploy/minio -n private-ai -- mc ls local/rhoai-storage/eval-results/
```

For detailed test YAML structure, see `references/rag-eval-configs.md`.
For LMEvalJob CR patterns, see `references/lmeval-templates.md`.
For development constraints, see `references/evaluation-development-patterns.md`.
