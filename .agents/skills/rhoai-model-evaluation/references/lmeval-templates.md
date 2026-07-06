# LM-Eval Templates Reference

## Table of Contents

- [Overview](#overview)
- [LMEvalJob CR Structure](#lmevaljob-cr-structure)
- [Available Templates](#available-templates)
- [Task Selection](#task-selection)
- [Running Benchmarks](#running-benchmarks)
- [Interpreting Results](#interpreting-results)
- [Troubleshooting](#troubleshooting)

## Overview

LM-Eval benchmarks use the TrustyAI operator's `LMEvalJob` custom resource
(`trustyai.opendatahub.io/v1alpha1`). Templates are in
`backup/legacy-implementation-2026-06-09/gitops/step-08-model-evaluation/base/lmeval/` and applied on-demand (not
ArgoCD-managed).

## LMEvalJob CR Structure

```yaml
apiVersion: trustyai.opendatahub.io/v1alpha1
kind: LMEvalJob
metadata:
  name: <model>-eval-<timestamp>
  namespace: private-ai
spec:
  model: local-completions
  modelArgs:
    - name: base_url
      value: "http://<model>-predictor.private-ai.svc.cluster.local:8080/v1/completions"
    - name: model
      value: "<model>"
    - name: tokenizer
      value: "<hf-tokenizer-id>"
    - name: num_concurrent
      value: "4"
    - name: max_retries
      value: "5"
    - name: tokenized_requests
      value: "false"
  taskList:
    taskNames:
      - hellaswag
      - arc_challenge
      - winogrande
      - boolq
  limit: "50"
  logSamples: true
  batchSize: "1"
  allowOnline: true
  allowCodeExecution: true
  outputs:
    pvcManaged:
      size: 2Gi
```

### Key Fields

| Field | Description | Notes |
|-------|-------------|-------|
| `model` | Always `local-completions` | Uses vLLM's OpenAI-compatible endpoint |
| `modelArgs.base_url` | vLLM completions endpoint | Must be cluster-internal URL |
| `modelArgs.tokenizer` | HuggingFace tokenizer ID | Must match the served model |
| `taskList.taskNames` | Evaluation tasks | See [Task Selection](#task-selection) |
| `limit` | Samples per task | `"50"` for demos, remove for full runs |
| `batchSize` | Inference batch size | `"1"` is safest for vLLM |
| `outputs.pvcManaged.size` | Storage for results | 2Gi is sufficient |

## Available Templates

The active reimplementation should create a Nemotron template after the
`LLMInferenceService` internal endpoint and tokenizer settings are verified.

### nemotron-3-nano-30b-a3b-eval.yaml

| Field | Value |
|-------|-------|
| base_url | Verify from the active `LLMInferenceService` or MaaS endpoint before writing the template |
| tokenizer | Verify against the Red Hat modelcar or validated model documentation |
| limit | 50 |

## Task Selection

Standard tasks included in the demo:

| Task | Category | Measures | Metric |
|------|----------|----------|--------|
| hellaswag | Commonsense | Sentence completion reasoning | acc_norm |
| arc_challenge | Science | Grade-school science questions | acc_norm |
| winogrande | Commonsense | Pronoun resolution | acc |
| boolq | Reading | Yes/no reading comprehension | acc |

These four tasks provide a balanced assessment across reasoning categories.
Full benchmark suites (MMLU, GSM8K, etc.) can be added to `taskNames` but
increase runtime significantly.

## Running Benchmarks

### Via script

```bash
# Default: nemotron-3-nano-30b-a3b, 50 samples
./backup/legacy-implementation-2026-06-09/steps/step-08-model-evaluation/run-lmeval.sh nemotron-3-nano-30b-a3b

# Custom: 200 samples
./backup/legacy-implementation-2026-06-09/steps/step-08-model-evaluation/run-lmeval.sh nemotron-3-nano-30b-a3b 200
```

### Legacy manual CR application reference

Do not run this as an active project command. Recreate the equivalent through
the new stage GitOps owner before use.

```bash
oc apply -f backup/legacy-implementation-2026-06-09/gitops/step-08-model-evaluation/base/lmeval/nemotron-3-nano-30b-a3b-eval.yaml
```

### Monitoring

```bash
# Watch job status
oc get lmevaljob -n private-ai -w

# Check pod logs
oc logs -n private-ai -l app=lmeval --tail=50 -f
```

### Runtime Estimates

| Model | Tasks | Limit | Approximate Time |
|-------|-------|-------|-----------------|
| nemotron-3-nano-30b-a3b | 4 | 50 | Measure during reimplementation |
| nemotron-3-nano-30b-a3b | 4 | full | Measure during reimplementation |

## Interpreting Results

### Via Dashboard

RHOAI Dashboard → Develop & train → Evaluations

Shows per-task accuracy scores in a tabular view.

### Via CLI

```bash
oc get lmevaljob <name> -n private-ai -o jsonpath='{.status.results}'
```

### Score Expectations (50-sample approximation)

| Model | hellaswag | arc_challenge | winogrande | boolq |
|-------|-----------|---------------|------------|-------|
| nemotron-3-nano-30b-a3b | Measure | Measure | Measure | Measure |

Record measured values after the new evaluation templates are rebuilt. 50-sample
runs have high variance. Full runs are more stable.

## Troubleshooting

### LMEvalJob stuck in Pending

```bash
# Check pod status
oc get pods -n private-ai -l app=lmeval

# Common cause: no available compute
oc describe pod <lmeval-pod> -n private-ai
```

LMEvalJob pods run on CPU — they don't need GPU. If stuck, check resource quotas.

### Connection refused to model endpoint

```bash
# Verify model is serving
oc get llminferenceservice -n maas
oc get pods -n maas -l app.kubernetes.io/part-of=llminferenceservice
```

The model must have `READY=True` before starting LM-Eval.

### Results empty or zero

- Check `logSamples: true` is set
- Verify `tokenizer` matches the model (wrong tokenizer = garbage results)
- Check `batchSize: "1"` — larger batches can OOM on some models
