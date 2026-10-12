# Agentic coding evaluation (evaluation-driven development)

Criteria are defined before models are compared and live as five versioned EvalHub collections
(`gitops/stages/050-model-evaluation/base/edd/`, RHOAI 3.5 "Evaluating AI systems" 2.1, 2.23):

| Collection | Question | Slices (weight, gate) | Overall gate |
|---|---|---|---|
| `agentic-coding-capability-v1` | Does the model write working code? | LiveCodeBench v6 (3, pass@1 ≥ 0.25), MBPP (2, ≥ 0.60), HumanEval (1, ≥ 0.80) | weighted ≥ 0.50 |
| `agentic-coding-security-quick-v1` | Per change: can it be steered into injected code or exfiltration? | Garak CWE (attack success ≤ 0.20), about 4 min | per slice |
| `agentic-coding-security-full-v1` | Nightly or pre-promotion: the full OWASP LLM Top 10 picture | Garak OWASP LLM Top 10, 72 probes incl. package hallucination (≤ 0.30), about 2 h | per slice |
| `agentic-coding-latency-v1` | Does one agent turn start fast enough? | GuideLLM `concurrent`, one session, 8k-in/256-out for 120 s: mean TTFT (≤ 2,000 ms) | per slice |
| `agentic-coding-throughput-v1` | Does it keep up when eight agents work at once? | GuideLLM `throughput`, eight requests in flight, 8k-in/256-out for 180 s: output tokens/s (≥ 60) | per slice |

Dimensions are separate collections because EvalHub's job score is one weighted average compared with one
threshold, and pass rates, attack success rates, latencies and token rates do not share a scale or direction.
Latency and throughput are separate collections too: EvalHub runs a collection's benchmarks in parallel, and a
saturation run beside a single-session run distorts the single-session latency.

The qualification pipeline in the **Evaluated Models** project runs all five collections for one model per run
and ranks the results on a leaderboard (Stage 050 README, "Model qualification pipeline").

Run a model against the per-change set (add `agentic-coding-security-full-v1` nightly or before promotion) (each job: MaaS key, Kueue queue, MLflow experiment with model, collection and
accelerator tags, OCI export of results and evaluation card):

```bash
for c in agentic-coding-capability-v1 agentic-coding-security-quick-v1 agentic-coding-latency-v1 agentic-coding-throughput-v1; do
  stages/050-model-evaluation/submit-evaluation.sh --model-name publishers/internal-models/models/qwen3-8-27b-int4 --collection "$c"
done
```

CI gating uses the CLI with a full job body (`evalhub eval run --config <file> --wait` exits non-zero when the
job fails); `agentic-coding-capability.ci.yaml` is the template. Change criteria in a new `-v2` collection,
never in place, so every MLflow run stays attributable to the criteria it was judged by.
