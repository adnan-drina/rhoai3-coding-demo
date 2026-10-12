# Agentic coding evaluation (evaluation-driven development)

Criteria are defined before models are compared and live as six versioned EvalHub collections
(`gitops/stages/050-model-evaluation/base/edd/`, RHOAI 3.5 "Evaluating AI systems" 2.1, 2.23):

| Collection | Question | Slices (weight, gate) | Overall gate |
|---|---|---|---|
| `agentic-coding-livecodebench-v1` | Can the model solve problems it has not seen? | LiveCodeBench v6 (3, pass@1 ≥ 0.25), runs alone | 0.25 |
| `agentic-coding-python-tasks-v1` | Does it write everyday working Python? | MBPP (2, ≥ 0.60), HumanEval (1, ≥ 0.80) | weighted ≥ 0.67 |
| `agentic-coding-security-quick-v2` | Per change: can it be steered into injected code or exfiltration? | Garak CWE (attack success ≤ 0.20), about 4 min | per slice |
| `agentic-coding-security-full-v2` | Nightly or pre-promotion: the full OWASP LLM Top 10 picture | Garak OWASP LLM Top 10, 72 probes incl. package hallucination (≤ 0.30), about 2 h | per slice |
| `agentic-coding-latency-v1` | Does one agent turn start fast enough? | GuideLLM `concurrent`, one session, 8k-in/256-out for 120 s: mean TTFT (≤ 2,000 ms) | per slice |
| `agentic-coding-throughput-v2` | Does it keep up when eight agents work at once? | GuideLLM `throughput`, eight requests in flight, 8k-in/256-out, 64 requests: output tokens/s (≥ 60) | per slice |

Dimensions are separate collections because EvalHub's job score is one weighted average compared with one
threshold, and pass rates, attack success rates, latencies and token rates do not share a scale or direction.
Capability is two collections run one after the other: a LiveCodeBench request asks for 16 samples and
needs all 16 sequence slots of the served model, and EvalHub runs a collection's benchmarks in parallel, so
MBPP and HumanEval beside it pushed its requests past the evaluation sidecar's 30 s limit. The qualification
leaderboard combines both into one capability score (weights 3:2:1, gate 0.50).

The security `-v2` collections keep the v1 probes and thresholds and change only how they run. MBPP and HumanEval use the
`inspect-coding` provider (Inspect with a 512-token cap, eight concurrent requests and three retries), and
the Garak scans use `garak-coding` (2 to 8 CPU cores for the detector models) with eight parallel attempts.
On v1, Inspect's uncapped answers outlived the evaluation sidecar's 30 s request limit and were retried
without end, and Garak scored one attempt at a time on two cores. The v1 collections stay registered for
earlier results.
Throughput v2 measures a fixed 64 requests instead of 180 seconds: each request takes about 25 s, so a time
window cut off up to eight unfinished requests and moved the result by up to about 20% between runs.

Latency and throughput are separate collections too: EvalHub runs a collection's benchmarks in parallel, and a
saturation run beside a single-session run distorts the single-session latency.

The qualification pipeline in the **Evaluated Models** project runs all five collections for one model per run
and ranks the results on a leaderboard (Stage 050 README, "Model qualification pipeline").

Run a model against the per-change set (add `agentic-coding-security-full-v2` nightly or before promotion) (each job: MaaS key, Kueue queue, MLflow experiment with model, collection and
accelerator tags, OCI export of results and evaluation card):

```bash
for c in agentic-coding-livecodebench-v1 agentic-coding-python-tasks-v1 agentic-coding-security-quick-v2 agentic-coding-latency-v1 agentic-coding-throughput-v2; do
  stages/050-model-evaluation/submit-evaluation.sh --model-name publishers/internal-models/models/qwen3-8-27b-int4 --collection "$c"
done
```

CI gating uses the CLI with a full job body (`evalhub eval run --config <file> --wait` exits non-zero when the
job fails); `agentic-coding-capability.ci.yaml` is the template. Change criteria in a new `-v2` collection,
never in place, so every MLflow run stays attributable to the criteria it was judged by.
