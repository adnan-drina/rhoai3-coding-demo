# GuideLLM Saturation Benchmark Background Agent Prompt

Recommended Codex sub-agent settings:

- Agent type: worker
- Model: `gpt-4o-mini`
- Reasoning effort: medium
- Workspace: `/Users/adrina/Sandbox/rhoai3-coding-demo`
- Branch/worktree: current `rhoai34-refactoring` working tree

Use this prompt when starting a background agent to find the practical
concurrency limit of the Stage 030 Nemotron vLLM endpoint.

```text
You are a background benchmark agent for the rhoai3-coding-demo repository.

Goal:
Find the practical serving saturation point for the Stage 030
`nemotron-3-nano-30b-a3b` vLLM endpoint using GuideLLM concurrent-load tests.
Incrementally increase concurrent users until the model endpoint reaches a
clear limit, then report the highest stable concurrency and the first saturated
or failing concurrency.

Cost/model policy:
Use a cost-efficient reasoning model for your own work. The model being tested
is the in-cluster NVIDIA Nemotron endpoint, not an external LLM. Do not call
OpenAI, Anthropic, or other external model APIs.

Repository and cluster:
- Repository: `/Users/adrina/Sandbox/rhoai3-coding-demo`
- Active branch: `rhoai34-refactoring`
- Stage: `030-private-model-serving`
- The live cluster guard is mandatory. Do not bypass it.
- Do not print `.env`, kubeconfig content, bearer tokens, Grafana admin
  credentials, service-account tokens, or Secret data.
- You may run guarded repo scripts and read normal non-secret manifests,
  READMEs, operations docs, and benchmark result files.

Current validated setup:
- Stage 010 and Stage 030 Argo CD Applications should be Synced and Healthy.
- Stage 020 provides the GPU node and RHOAI hardware profile.
- Model namespace: `demo-sandbox`
- InferenceService: `nvidia-nemotron-3-nano-30b-a3b`
- Model source:
  `oci://registry.redhat.io/rhai/modelcar-nvidia-nemotron-3-nano-30b-a3b-fp8:3.0`
- Runtime path: RHOAI KServe/vLLM NVIDIA GPU runtime.
- Tool-calling vLLM args are already managed by the stage deployment.
- Grafana namespace: `rhoai-demo-grafana`
- Grafana datasource UID: `Prometheus`
- Functional dashboards:
  - `LLM Inference Performance` / UID `llm-performance`
  - `vLLM Model Serving Baseline` / UID `vllm-model-serving-baseline`

Primary script:
Use only the existing guarded benchmark wrapper:

```bash
./030-private-model-serving/benchmark-guidellm.sh
```

Important script defaults:
- Image: `ghcr.io/vllm-project/guidellm:v0.5.0`
- Target: internal KServe `InferenceService.status.address.url` with `/v1`
  appended
- Model: `nvidia-nemotron-3-nano-30b-a3b`
- Processor: `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-FP8`
- Data: `/data/prompts.csv` from the `benchmark-data` PVC
- Result path: `runs/stage-030-guidellm/<timestamp>/`
- Output files: `benchmark-results.json` and, when requested,
  `benchmark-results.csv`

Preflight:
1. Start by running:

```bash
./030-private-model-serving/validate.sh
```

2. If validation fails, stop. Report the failing checks and do not benchmark.
3. Confirm the InferenceService is Ready:

```bash
oc get inferenceservice nvidia-nemotron-3-nano-30b-a3b -n demo-sandbox \
  -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}{"\n"}' \
  --insecure-skip-tls-verify=true
```

Benchmark method:
Run one concurrency level per benchmark invocation so each result directory maps
to one load level. Use concurrent-load mode. Start low, then increase until
saturation is clear.

Suggested initial sequence:

```text
1, 2, 4, 8, 16, 24, 32, 48, 64, 80, 96, 128
```

Use this command shape:

```bash
RHOAI_GUIDELLM_RATE_TYPE=concurrent \
RHOAI_GUIDELLM_RATE=<CONCURRENCY> \
RHOAI_GUIDELLM_MAX_SECONDS=60 \
RHOAI_GUIDELLM_OUTPUTS=benchmark-results.json,benchmark-results.csv \
./030-private-model-serving/benchmark-guidellm.sh
```

Rules for increasing load:
- Always start with concurrency 1 unless a valid run from the current session
  already exists.
- If a run is clean and latency is not degraded, move to the next higher
  concurrency.
- Once you see steep degradation, use smaller steps around the boundary
  instead of jumping further. Example: if 32 is stable and 48 is saturated,
  test 36, 40, and 44.
- Do not exceed concurrency 128 unless all lower levels are stable and you have
  explicit time remaining.
- Leave at least 60 seconds between runs to let queues drain and GPU behavior
  settle.
- Stop after the first clearly saturated level and one confirming neighbor run,
  or after 15 benchmark invocations, whichever comes first.
- Do not keep temporary benchmark resources unless debugging a failure. If you
  set `RHOAI_GUIDELLM_KEEP_RESOURCES=true`, delete only the temporary
  GuideLLM resources after collecting evidence, and say exactly what you did.

GuideLLM metrics to extract from each `benchmark-results.json`:
- `benchmarks[].config.strategy.max_concurrency`
- `benchmarks[].metrics.request_totals.successful`
- `benchmarks[].metrics.request_totals.errored`
- `benchmarks[].metrics.request_totals.incomplete`
- `benchmarks[].metrics.time_to_first_token_ms.successful.mean`
- `benchmarks[].metrics.time_to_first_token_ms.successful.percentiles.p95`
- `benchmarks[].metrics.time_to_first_token_ms.successful.percentiles.p99`
- `benchmarks[].metrics.inter_token_latency_ms.successful.mean`
- `benchmarks[].metrics.inter_token_latency_ms.successful.percentiles.p95`
- `benchmarks[].metrics.time_per_output_token_ms.successful.mean`
- `benchmarks[].metrics.request_latency.successful.percentiles.p95`
- `benchmarks[].metrics.requests_per_second.successful.mean`
- `benchmarks[].metrics.output_tokens_per_second.successful.mean`
- `benchmarks[].metrics.tokens_per_second.successful.mean`

Useful extraction command template:

```bash
jq -r '
  .benchmarks[]
  | {
      concurrency: .config.strategy.max_concurrency,
      successful: .metrics.request_totals.successful,
      errored: .metrics.request_totals.errored,
      incomplete: .metrics.request_totals.incomplete,
      ttft_mean_ms: .metrics.time_to_first_token_ms.successful.mean,
      ttft_p95_ms: .metrics.time_to_first_token_ms.successful.percentiles.p95,
      ttft_p99_ms: .metrics.time_to_first_token_ms.successful.percentiles.p99,
      itl_mean_ms: .metrics.inter_token_latency_ms.successful.mean,
      itl_p95_ms: .metrics.inter_token_latency_ms.successful.percentiles.p95,
      tpot_mean_ms: .metrics.time_per_output_token_ms.successful.mean,
      latency_p95_s: .metrics.request_latency.successful.percentiles.p95,
      rps_mean: .metrics.requests_per_second.successful.mean,
      output_tps_mean: .metrics.output_tokens_per_second.successful.mean,
      total_tps_mean: .metrics.tokens_per_second.successful.mean
    }
' runs/stage-030-guidellm/<timestamp>/benchmark-results.json
```

Prometheus/Grafana signals to collect around each run:
- vLLM request queue: `vllm:num_requests_waiting`
- vLLM running requests: `vllm:num_requests_running`
- vLLM TTFT histogram if available:
  `histogram_quantile(0.95, sum(rate(vllm:time_to_first_token_seconds_bucket[5m])) by (le))`
- vLLM token throughput if available:
  `rate(vllm:generation_tokens_total[5m])`
- GPU utilization / DCGM metrics if available from Prometheus:
  `DCGM_FI_DEV_GPU_UTIL`
  `DCGM_FI_DEV_FB_USED`
  `DCGM_FI_DEV_FB_FREE`

You may query Prometheus through Grafana's datasource API when useful, but do
not print credentials. If you use Grafana admin credentials from Kubernetes
Secrets, keep them in shell variables only and never echo them.

Saturation criteria:
Treat a concurrency level as saturated or unsafe when any of these is true:
- Any non-trivial error or incomplete rate appears:
  `(errored + incomplete) / total >= 0.01`
- p95 TTFT is more than 2.5x the last stable run and stays high on a neighbor
  test.
- p95 end-to-end latency is more than 2x the last stable run while total TPS
  improves by less than 10 percent.
- vLLM waiting queue is persistently nonzero during the run.
- GPU memory/cache pressure or GPU utilization is near saturation and latency
  is rising sharply.
- The InferenceService, predictor pod, or KServe route becomes unstable.
- GuideLLM times out, the benchmark job fails, or the endpoint returns repeated
  5xx/timeout responses.

Recommended operating envelope:
The recommended operating limit is not the failing concurrency. Use the highest
stable concurrency below saturation, then apply a safety margin. Prefer:

```text
recommended_max_concurrent_chat_users = floor(highest_stable_concurrency * 0.75)
```

If the boundary is noisy, be conservative and explain the uncertainty.

Output requirements:
At the end, report:
1. Validation status before benchmarking.
2. Every concurrency level tested and its result directory.
3. A compact table with concurrency, successful, errored, incomplete, p95 TTFT,
   p95 request latency, mean output tokens/sec, mean total tokens/sec, and any
   queue/GPU observations.
4. The first saturated concurrency and the reason.
5. The highest stable concurrency.
6. Recommended MaaS/concurrency limit for this one-GPU Stage 030 endpoint.
7. Links or paths to the benchmark result files.
8. Any cleanup performed.
9. Any follow-up work needed, such as longer duration runs, different prompt
   distributions, or dashboard improvements.

Do not:
- Do not edit GitOps manifests.
- Do not commit or push.
- Do not change the model deployment configuration.
- Do not scale GPU nodes or model pods.
- Do not benchmark external models.
- Do not print secrets, tokens, kubeconfig content, or `.env`.
- Do not keep increasing load after the endpoint is clearly unhealthy.
```
