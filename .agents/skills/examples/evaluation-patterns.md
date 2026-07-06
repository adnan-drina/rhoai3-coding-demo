# Evaluation Patterns

These examples are review patterns. Verify active CRDs, TrustyAI state,
EvalHub route, tenant RBAC, model endpoints, Secrets, S3 buckets, MLflow, OCI
registry, KFP endpoint, and project access before copying anything into GitOps
or runbooks.

## EvalHub Deployment Review

```yaml
apiVersion: trustyai.opendatahub.io/v1alpha1
kind: EvalHub
metadata:
  name: evalhub
spec:
  replicas: 1
  database:
    type: postgresql
    secret: evalhub-db-credentials
  providers:
    - lm-evaluation-harness
    - garak
    - guidellm
  collections:
    - safety-and-fairness-v1
```

Review points:

- Use a dedicated namespace unless a documented exception exists.
- Keep PostgreSQL credentials in a Secret with `db-url`.
- Verify `EvalHub` schema before applying.
- Add MLflow and OpenTelemetry configuration only when dependencies are ready.

## EvalHub Job Request Shape

```json
{
  "name": "benchmark-run",
  "model": {
    "url": "https://model.example/v1",
    "name": "model-name",
    "auth": {
      "secret_ref": "model-api-key"
    }
  },
  "benchmarks": [
    {
      "id": "mmlu",
      "provider_id": "lm_evaluation_harness"
    }
  ],
  "experiment": {
    "name": "evaluation-demo"
  }
}
```

Review points:

- Send tenant context with `X-Tenant` or SDK/CLI tenant configuration.
- Keep API keys in Kubernetes Secrets.
- Choose provider and benchmark based on the model claim being evaluated.
- Track pass criteria and threshold choices when they affect go/no-go status.

## LM-Eval Job Review

```yaml
apiVersion: trustyai.opendatahub.io/v1alpha1
kind: LMEvalJob
metadata:
  name: evaljob
spec:
  model: local-completions
  taskList:
    taskNames:
      - mmlu
  logSamples: true
  batchSize: 1
  modelArgs:
    - name: model
      value: <model-name>
    - name: base_url
      value: https://<model-route>/v1/completions
```

Review points:

- Verify the model runtime supports the selected endpoint style.
- Add token Secrets through `env.valueFrom.secretKeyRef` when required.
- Use `allowOnline` and `allowCodeExecution` only when needed and documented.
- Use PVC or S3 scenarios when the task requires local data or artifacts.

## Risk Assessment Request Shape

```json
{
  "name": "intents-scan",
  "model": {
    "url": "https://target-model.example/v1",
    "name": "target-model",
    "auth": {
      "secret_ref": "model-api-key"
    }
  },
  "benchmarks": [
    {
      "id": "intents",
      "provider_id": "garak-kfp",
      "parameters": {
        "kfp_config": {
          "endpoint": "https://ds-pipeline-dspa.<namespace>.svc.cluster.local:8443",
          "namespace": "<namespace>",
          "s3_secret_name": "<s3-secret-name>",
          "verify_ssl": false
        },
        "intents_models": {
          "judge": {
            "url": "https://judge-model.example/v1",
            "name": "judge-model"
          },
          "sdg": {
            "url": "https://sdg-model.example/v1",
            "name": "hosted_vllm/sdg-model"
          }
        }
      }
    }
  ]
}
```

Review points:

- Confirm pipeline server and S3 artifact storage before running.
- Use different target and judge roles unless a deliberate exception exists.
- For disconnected clusters, include `hf_cache_path` or disable translation.
- Group comparable runs with an MLflow experiment name.

## Disconnected Translation Cache

```text
Cache source:
  Helsinki-NLP/opus-mt-zh-en
  Helsinki-NLP/opus-mt-en-zh

Artifact destination:
  s3://<bucket>/<prefix>/

Risk assessment parameter:
  hf_cache_path: s3://<bucket>/<prefix>/
```

Review points:

- Required only when the translation attack strategy is used on a disconnected
  cluster.
- Upload model cache artifacts to S3 before job submission.
- If translation is not needed, disable translation strategy in Garak config.

## Result Evidence Record

```text
Workflow: EvalHub | LM-Eval | Risk assessment
Tenant namespace: <namespace>
Model endpoint: <endpoint>
Provider/benchmark: <provider>/<benchmark>
Job ID or CR name: <id-or-name>
Status: pending | running | completed | failed | cancelled | partially_failed
MLflow experiment: <optional>
OCI export: <optional>
S3 artifact prefix: <optional>
Decision: pass | fail | investigate
```

Review points:

- Keep enough metadata for audit and presentation without exposing secrets.
- Preserve source benchmark names, thresholds, and metric names.
- Link failures to troubleshooting evidence rather than overwriting results.
