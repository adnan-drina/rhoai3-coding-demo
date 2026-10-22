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

`submit.sh` needs the tenant Secret `evalhub-model-auth-maas` that Stage 050 `deploy.sh` provisions.

**Garak in pipeline mode (`garak-kfp`).** `garak-kfp-quick.json` (one DAN probe, a few minutes) and
`garak-kfp-avid-security.json` are benchmark parameter files for `--parameters`. They name the pipeline server's
namespace, S3 connection, KFP experiment and the candidate's in-cluster `model_url` for the pipeline pods, and
deliberately no `endpoint`: the job reaches the pipeline server through its sidecar with Secret `garak-kfp-model-auth`
(`050-model-qualification` README, "Garak in pipeline mode"). To scan another model, change `model_url`. Against the
candidate:

```bash
stages/050-model-evaluation/evaluation/submit.sh --model-name qwen3-8-27b-int4 \
  --model-url https://qwen3-8-27b-int4-predictor.evaluated-models.svc.cluster.local:8443/v1 \
  --secret-ref garak-kfp-model-auth --provider garak-kfp --benchmark quick \
  --parameters stages/050-model-evaluation/evaluation/garak-kfp-quick.json \
  --experiment models-onboarding --no-oci-export --wait
```

With `--parameters`, the provider's own pass criterion applies unless `--threshold` is given (Garak's attack success
rate is lower-is-better). Run sizing (16
samples per problem, the sidecar's 30-second request limit, the adapter's one-hour limit) is described in the Stage 050
README. Check a completed job together with its MLflow run with `validate.sh --job-id ID --mlflow-run-id RUN`.
