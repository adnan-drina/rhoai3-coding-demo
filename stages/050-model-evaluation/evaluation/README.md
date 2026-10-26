# Evaluation runs from the terminal

Two task scripts for the governed evaluation path, as an alternative to **Develop & train → Evaluations** in the
dashboard. Both act as the logged-in OpenShift user, run the cluster guard first, and give the user's token to `curl` only
through `--config`. Run them as the installation administrator: besides EvalHub's tenant check they read the EvalHub
and registry Routes and the model's pods, which `rhods-admins` members such as `ai-admin` cannot read.

| Script | When to run | What it changes |
|---|---|---|
| `submit.sh --model-name ID [options]` | To evaluate a MaaS model: by default Coding v1 (lighteval `lcb:codegeneration_v6`, bound it with `--num-examples`), or one native collection with `--collection agentic-coding-latency-v1` and the like. `--help` lists the options. | Creates one EvalHub job in tenant `evaluated-models` (Kueue queue `lq-cpu-default`, MLflow experiment `models-onboarding`, OCI export of the results). Each run submits a new job. |
| `submit.sh ... --dry-run` | To review the job body before submitting. | Nothing. |
| `submit.sh --status JOB_ID [--wait]` | To follow a job until it is completed, failed or cancelled; shows each benchmark's verdict on its own primary metric and threshold. | Nothing. |
| `record.sh --job JOB_ID --model-version VERSION_ID [--dry-run]` | After a job completed, to link it from the model's registry version (`demo-registry`), where the dashboard shows the links under the version's **Properties**. | Writes references to the evidence, keyed per benchmark (`evalhub.<benchmark>.<field>`), and replaces only that benchmark's earlier properties, so the latest `avid_security` and `intents` results stay side by side: the EvalHub job and its results page (`evaluation_url`), a one-line verdict (`result`, `pass`), the MLflow experiment and run, and for `garak-kfp` the pipeline run in the dashboard (`pipeline_run_url`). Refuses a Garak result without per-probe metrics (the results download was skipped). `--dry-run` shows the properties without writing. |

`submit.sh` needs the tenant Secret `evalhub-model-auth-maas` that Stage 050 `deploy.sh` provisions. Run sizing (16
samples per problem, the sidecar's 30-second request limit, the adapter's one-hour limit) is described in the Stage 050
README. Check a completed job together with its MLflow run with `validate.sh --job-id ID --mlflow-run-id RUN`.

For CI, save the body that `submit.sh --dry-run` prints and pass it to the EvalHub CLI: `evalhub eval run --config
<file> --wait` exits non-zero when the job fails (RHOAI 3.5 "Evaluating AI systems" 2.4, 2.10).

## Garak in pipeline mode (`garak-kfp`)

`garak-kfp` runs the scan as a run on this project's pipeline server. Every job carries the model auth Secret
`garak-kfp-model-auth` (`model.auth.secret_ref`) and the benchmark parameters in one of the two files here:

| File | Benchmarks | Verified |
|---|---|---|
| `avid-security.parameters.json` | `avid_security`, `quick`, `owasp_llm_top10`, `cwe` and the other probe-based scans | 2026-10-22 on the former INT4 candidate: `avid_security`, 67 per-probe results in EvalHub; `quick` |
| `intents.parameters.json` | `intents` (generated attack prompts, judge model, attack strategies) | 2026-10-22 on the former INT4 candidate: with GPT-6 Luna as judge and SDG model, through the SPO strategies |

Both name the pipeline server's project and S3 connection and the candidate's in-cluster address:

- `namespace` and `s3_secret_name` are required (3.5 guide, 7.7.4).
- `model_url` is the scanned model's in-cluster address. The scan runs in pipeline pods without the job sidecar, and
  EvalHub hands the adapter only the sidecar address, so the real address must be given. To scan another model,
  change it.
- No `endpoint`. The adapter reaches the pipeline server through the job sidecar with the Secret's `kfp_url` and empty
  `kfp_sa_token` (upstream EvalHub *Model Authentication*, scenario 3); an explicit `endpoint` takes precedence, goes
  around the sidecar and fails with 401. The 3.5 guide's example in 7.3 sets it; that example fails on 3.5.2 (BACKLOG).
- `timeout`, `experiment_name` (the KFP experiment) and `verify_ssl` keep their defaults; `intents` sets `timeout` to
  7200 s because its attack strategies run after the baseline.

`intents.parameters.json` also sets the models the scan uses besides the candidate; every address is in-cluster.

- `judge` and `sdg`: `gemma-2-9b-abliterated`, served in this project
  (`050-model-qualification/risk-assessment-gemma-2-9b-abliterated.yaml`, one L40S; start it with
  `serving.kserve.io/stop: "false"`). Both roles need a model without safety alignment: a safety-aligned judge and SDG
  model (GPT-6 Luna, 2026-10-22) rewrote every harmful intent into a harmless request, so the scan measured nothing.
  Their keys are the Secret's `JUDGE_API_KEY` and `SDG_API_KEY` (the `candidate-model-client` token; guide 7.7.4),
  which the TAP attacker and evaluator also use.
- Translation: with no translator named, the 3.5.2 provider translates with the attacker LLM (`gemma-2-9b-abliterated`;
  the job log shows `Translation mode: attacker LLM`), not with the Helsinki-NLP models guide 7.2 describes. The
  qualification pipeline turns translation off with the guide's `garak_config` (`run.langproviders: null` and a
  `probe_spec` of the four SPO strategies and TAP).
- TAP: in the shipped Garak (`0.15.0+rhaiv.6`) only the first round produces attacks; every later round drops the
  attacker's instructions and sends empty prompts, and the default ten rounds take about 30 minutes per intent. The
  pipeline sets `plugins.probes.tap.TAPIntent.depth: 1` in the same `garak_config`; add both settings to a manual run
  that must finish in time. Until 2026-10-23 an undocumented
  `intents_models.translation` role sent translation to Nemotron 3 Ultra through MaaS.
- Automated risk assessment is a Technology Preview feature in RHOAI 3.5 (guide 7): read its attack success rate as
  advisory, and spot-check the judge's classifications (Complied, Rejected, Alternative, Other) against the answers in
  the HTML report before relying on a verdict.
- `sdg_num_samples: 5` prompts per harm category; `disable_cache: true` so a rerun generates fresh prompts instead of
  reusing the cached SDG step. Do not set `sdg_max_tokens`: in the 3.5.2 provider it rebuilds the SDG block without
  its model and the step fails with `Model not configured for block 'generate_adversarial_prompt'` (TROUBLESHOOTING).

From the terminal:

```bash
stages/050-model-evaluation/evaluation/submit.sh --model-name qwen3-8-27b-nvfp4 \
  --model-url https://qwen3-8-27b-nvfp4-predictor.evaluated-models.svc.cluster.local:8443/v1 \
  --secret-ref garak-kfp-model-auth --provider garak-kfp --benchmark avid_security \
  --parameters stages/050-model-evaluation/evaluation/avid-security.parameters.json \
  --experiment models-onboarding --no-oci-export --wait
```

For `intents`, use `--benchmark intents --parameters …/intents.parameters.json`.
A single benchmark is submitted with the provider catalog's primary metric, its direction and its pass threshold, as
the dashboard form does (for `garak-kfp` `avid_security`: `attack_success_rate`, lower is better, at most 0.3);
`--threshold` overrides the threshold. The Evaluations page shows the attack success rate itself as the score, so a
23% score with Pass means 23% of the attacks succeeded, within the 30% allowed. Record a finished run on the model's
registry version with `record.sh`.

From the dashboard (**Develop & train → Evaluations → Start evaluation run**, a **Garak KFP** benchmark): under
**Model** choose **Other (External endpoint)**, not the project's model, and enter

- **Model name:** `qwen3-8-27b-nvfp4`
- **Endpoint URL:** `https://qwen3-8-27b-nvfp4-predictor.evaluated-models.svc.cluster.local:8443/v1`
- **Authentication secret name:** `garak-kfp-model-auth`
- **Benchmark parameters:** the content of the matching file.

The qualification pipeline (Stage 050 README) submits both benchmarks with these settings and the candidate's URL.

Do not start `garak-kfp` from a model picked in the project's **Model** list. Such a job carries no authentication
Secret (a dashboard limitation fixed in 3.6, BACKLOG): it cannot reach the pipeline server, and where it can, the
adapter cannot read the S3 Secret, skips the results download and reports an empty result as attack success rate 0,
Pass, `num_examples_evaluated` 0. `record.sh` refuses such a result. Cancelling the EvalHub job does not stop the
pipeline run; terminate it under **Pipelines → Runs**.
