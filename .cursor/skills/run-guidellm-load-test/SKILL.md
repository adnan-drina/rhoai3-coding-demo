---
name: run-guidellm-load-test
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  rhoai-version: "3.4"
  ocp-version: "4.20"
description: >
  Run an on-demand GuideLLM load test against a Stage 040 MaaS-published
  model endpoint. Use when the user asks to benchmark a private model,
  generate MaaS traffic, compare model latency or throughput, rerun a
  GuideLLM test with different prompt/rate/token settings, or collect
  short load evidence for Grafana and MaaS observability. Do NOT use for
  Stage 020/030 GPU recovery (use resume-gpu-demo), broad cluster
  troubleshooting (use rhoai-troubleshoot), or generic stage validation
  unless the user explicitly wants the GuideLLM load path exercised.
---

# Run GuideLLM Load Test

Use the Stage 040 wrapper script as the source of truth. Do not recreate the
Kubernetes `Job` manually unless the script itself is being debugged.

## Preconditions

- Confirm `oc whoami` succeeds against the intended OpenShift cluster.
- Confirm Stage 040 is deployed and the MaaS Gateway hostname is not a placeholder.
- Confirm the target model is ready through MaaS.
- Confirm a MaaS API key is available through `GUIDELLM_API_KEY`, `MAAS_API_KEY`, or the `kai-api-keys` Secret created by Stage 080.

Never print, summarize, or store API key values. The wrapper creates a temporary
in-cluster Secret, deletes it on exit, and stores only a safe console summary in
a labeled `ConfigMap`.

## Default Command

Run the default short test against the default model:

```bash
./stages/040-governed-models-as-a-service/run-guidellm-load-test.sh
```

The default is intentionally small for demo environments:

- Model: `nemotron-3-nano-30b-a3b`
- Profile: `constant`
- Rate: `1`
- Maximum duration: `20` seconds
- Prompt samples: `5`
- Output tokens: `64`

## Common Variants

Compare both local models:

```bash
./stages/040-governed-models-as-a-service/run-guidellm-load-test.sh gpt-oss-20b
./stages/040-governed-models-as-a-service/run-guidellm-load-test.sh nemotron-3-nano-30b-a3b
```

Run a small custom prompt:

```bash
GUIDELLM_REQUESTS=3 \
GUIDELLM_OUTPUT_TOKENS=32 \
GUIDELLM_PROMPT="Explain governed model access for enterprise AI teams." \
./stages/040-governed-models-as-a-service/run-guidellm-load-test.sh
```

Increase load carefully:

```bash
GUIDELLM_PROFILE=constant \
GUIDELLM_RATE=2 \
GUIDELLM_MAX_SECONDS=60 \
GUIDELLM_REQUESTS=30 \
GUIDELLM_OUTPUT_TOKENS=128 \
./stages/040-governed-models-as-a-service/run-guidellm-load-test.sh nemotron-3-nano-30b-a3b
```

Use a file or dataset supported by GuideLLM:

```bash
GUIDELLM_DATA=/path/to/prompts.jsonl \
./stages/040-governed-models-as-a-service/run-guidellm-load-test.sh gpt-oss-20b
```

## Evidence To Capture

After the run, report:

- Target model and endpoint path, without secrets.
- Profile, rate, max duration, prompt sample count, and output token setting.
- Completed request count, incomplete request count, and error count from the GuideLLM console summary.
- Median or p95 request latency and token throughput if present in the console summary.
- Result `ConfigMap` name.

Useful retrieval command:

```bash
oc get configmap -n maas -l app.kubernetes.io/name=guidellm-load-test
```

Inspect one result without exposing secrets:

```bash
oc get configmap <result-name> -n maas -o jsonpath='{.data.summary\.log}'
```

## Safety Notes

- Keep the first run small. Increase `GUIDELLM_RATE`, `GUIDELLM_REQUESTS`, or `GUIDELLM_MAX_SECONDS` only when the user asks for more load.
- Do not use raw GuideLLM JSON/CSV result files from inside the pod as shared artifacts; they can include backend arguments. Use the wrapper's stored console summary.
- If prerequisites are missing, the wrapper exits with code `2` and should be treated as a skipped load test, not a model failure.
- If the model is cold-starting after GPU resume, wait for Stage 030 validation before running larger tests.
