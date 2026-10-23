# Agentic coding evaluation (evaluation-driven development)

Criteria are defined before models are compared. Capability and performance live as four versioned EvalHub
collections (`gitops/stages/050-model-evaluation/050-evaluation-content/edd/`, RHOAI 3.5 "Evaluating AI systems"
2.1, 2.23); security and risk assessment are two `garak-kfp` benchmarks with the provider catalog's gates:

| Evaluation | Question | Slices (weight, gate) | Overall gate |
|---|---|---|---|
| `agentic-coding-latency-v1` | Does one agent turn start fast enough? | GuideLLM `concurrent`, one session, 8k-in/256-out for 120 s: mean TTFT (≤ 2,000 ms) | per slice |
| `agentic-coding-throughput-v2` | Does it keep up when eight agents work at once? | GuideLLM `throughput`, eight requests in flight, 8k-in/256-out, 64 requests: output tokens/s (≥ 60) | per slice |
| `agentic-coding-livecodebench-v2` | Can the model solve problems it has not seen? | LiveCodeBench v6 (3, pass@1 ≥ 0.25), runs alone | 0.25 |
| `agentic-coding-python-tasks-v1` | Does it write everyday working Python? | MBPP (2, ≥ 0.60), HumanEval (1, ≥ 0.80) | weighted ≥ 0.67 |
| `garak-kfp` `avid_security` | Can it be attacked into unsafe output? | Garak AVID security probes, run as a pipeline: attack success rate (≤ 0.30), about 65 min | per benchmark |
| `garak-kfp` `intents` | Does it comply with harmful intents? | Attack prompts generated per harm category, TAP and translated attacks, judged by the abliterated risk assessment model: attack success rate (≤ 0.30), up to 2 h | per benchmark |

Dimensions are separate evaluations because EvalHub's job score is one weighted average compared with one
threshold, and pass rates, attack success rates, latencies and token rates do not share a scale or direction.
Capability is two collections run one after the other: a LiveCodeBench request asks for 16 samples and
needs all 16 sequence slots of the served model, and EvalHub runs a collection's benchmarks in parallel, so
MBPP and HumanEval beside it pushed its requests past the evaluation sidecar's 30 s limit. The qualification
report combines both into one capability score (weights 3:2:1, gate 0.50).

MBPP and HumanEval use the `inspect-coding` provider (Inspect with a 512-token cap, eight concurrent requests and
three retries): Inspect's uncapped answers outlived the evaluation sidecar's 30 s request limit and were retried
without end. LiveCodeBench v2 names the metric key LightEval reports (`lcb:codegeneration_v6.codegen_pass@1`);
EvalHub matches the primary metric by exact key. Throughput v2 measures a fixed 64 requests instead of a time
window, which cut off up to eight unfinished requests and moved the result by up to about 20% between runs.
Latency and throughput are separate collections too: a saturation run beside a single-session run distorts the
single-session latency.

Security and risk assessment are `garak-kfp` benchmark jobs, not collections: the scan runs as its own pipeline run
and needs the candidate's in-cluster URL in `kfp_config.model_url`, which a collection cannot carry per model. Both
need the candidate model auth Secret `garak-kfp-model-auth`; `intents` also needs the abliterated risk assessment
model (`gemma-2-9b-abliterated` in the same project) running as SDG model and judge
([evaluation README](../evaluation/README.md)).

The qualification pipeline in the **Evaluated Models** project runs all six for one candidate per run, judges
them against these gates and records the verdict on the candidate's model registry version (Stage 050 README,
"Model qualification pipeline").

A single evaluation can also run by hand from **Develop & train → Evaluations** or with
`../evaluation/submit.sh --model-name ID --collection NAME` (or `--provider garak-kfp --benchmark ...`, see
[evaluation/README.md](../evaluation/README.md)).

CI gating uses the CLI with a full job body (`evalhub eval run --config <file> --wait` exits non-zero when the
job fails); `agentic-coding-python-tasks.ci.yaml` is the template. Change criteria in a new `-v<N+1>` collection,
never in place, so every MLflow run stays attributable to the criteria it was judged by.
