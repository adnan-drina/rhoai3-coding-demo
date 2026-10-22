# Evaluation runs from the terminal

Two task scripts for the governed evaluation path, as an alternative to **Develop & train → Evaluations** in the
dashboard. Both act as the logged-in OpenShift user (an Evaluated Models administrator, `rhods-admins`), run the
cluster guard first, and give the user's token to `curl` only through `--config`.

| Script | When to run | What it changes |
|---|---|---|
| `submit.sh --model-name ID [options]` | To evaluate a MaaS model: by default Coding v1 (lighteval `lcb:codegeneration_v6`, bound it with `--num-examples`), or one native collection with `--collection agentic-coding-latency-v1` and the like. `--help` lists the options. | Creates one EvalHub job in tenant `evaluated-models` (Kueue queue `lq-cpu-default`, MLflow experiment `model-evaluations`, OCI export of the results). Each run submits a new job. |
| `submit.sh ... --dry-run` | To review the job body before submitting. | Nothing. |
| `submit.sh --status JOB_ID [--wait]` | To follow a job until it is completed, failed or cancelled. | Nothing. |
| `record.sh --job JOB_ID --model-version VERSION_ID` | After a job completed, to put its results on the model's registry version (`demo-registry`), where the dashboard shows them under the version's **Properties**. | Merges `evalhub.*` custom properties (one per numeric metric, plus the job, experiment and MLflow references) into that model version. Rerunning rewrites the same properties. |

`submit.sh` needs the tenant Secret `evalhub-model-auth-maas` that Stage 050 `deploy.sh` provisions. Run sizing (16
samples per problem, the sidecar's 30-second request limit, the adapter's one-hour limit) is described in the Stage 050
README. Check a completed job together with its MLflow run with `validate.sh --job-id ID --mlflow-run-id RUN`.

## Garak in pipeline mode (`garak-kfp`)

`garak-kfp` runs the scan as a run on this project's pipeline server. A job needs the model auth Secret
`garak-kfp-model-auth` (`model.auth.secret_ref`) and three benchmark parameters, the ones in `garak-kfp-quick.json` and
`garak-kfp-avid-security.json`:

```json
{
  "kfp_config": {
    "namespace": "evaluated-models",
    "s3_secret_name": "evaluation-models-pipelines-connection",
    "model_url": "https://qwen3-8-27b-int4-predictor.evaluated-models.svc.cluster.local:8443/v1"
  }
}
```

- `namespace` and `s3_secret_name` are required (3.5 guide, 7.7.4).
- `model_url` is the scanned model's in-cluster address. The scan runs in pipeline pods without the job sidecar, and
  EvalHub hands the adapter only the sidecar address, so the real address must be given. To scan another model,
  change it.
- No `endpoint`. The adapter reaches the pipeline server through the job sidecar with the Secret's `kfp_url` and empty
  `kfp_sa_token` (upstream EvalHub *Model Authentication*, scenario 3); an explicit `endpoint` takes precedence, goes
  around the sidecar and fails with 401. The 3.5 guide's example in 7.3 sets it; that example fails on 3.5.2 (BACKLOG).

From the terminal:

```bash
stages/050-model-evaluation/evaluation/submit.sh --model-name qwen3-8-27b-int4 \
  --model-url https://qwen3-8-27b-int4-predictor.evaluated-models.svc.cluster.local:8443/v1 \
  --secret-ref garak-kfp-model-auth --provider garak-kfp --benchmark quick \
  --parameters stages/050-model-evaluation/evaluation/garak-kfp-quick.json \
  --experiment models-onboarding --no-oci-export --wait
```

With `--parameters`, the provider's own pass criterion applies unless `--threshold` is given (Garak's attack success
rate is lower-is-better).

From the dashboard (**Develop & train → Evaluations → Start evaluation run**): select the benchmark suite
**Candidate security scan (pipeline) v1** (`candidate-security-pipeline-v1`, `050-evaluation-content`), which carries
the three parameters for the candidate. Under **Model** choose **Other (External endpoint)**, not the project's model,
and enter

- **Model name:** `qwen3-8-27b-int4`
- **Endpoint URL:** `https://qwen3-8-27b-int4-predictor.evaluated-models.svc.cluster.local:8443/v1`
- **Authentication secret name:** `garak-kfp-model-auth`

Leave **Benchmark parameters** empty: the form replaces a suite's parameters key by key, so a typed `kfp_config`
replaces the preset one whole. For a single **Garak KFP** benchmark instead of the suite, paste the JSON above.

A model picked from the project's **Model** list is submitted without an authentication Secret, so the job cannot
reach the pipeline server; Red Hat support confirmed this as a dashboard limitation fixed in 3.6 (BACKLOG). Cancelling
the EvalHub job does not stop the pipeline run; terminate it under **Pipelines → Runs**.
