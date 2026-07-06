# TrustyAI Monitoring Patterns

These are review patterns derived from the official Monitoring your AI systems
guide. Verify CRDs, TrustyAI support posture, model runtime support, storage,
Secrets, routes, and OpenShift monitoring permissions before copying anything
into GitOps or runbooks.

## TrustyAIService With Database Storage

```yaml
apiVersion: trustyai.opendatahub.io/v1
kind: TrustyAIService
metadata:
  name: trustyai-service
spec:
  storage:
    format: "DATABASE"
    size: "1Gi"
    databaseConfigurations: db-credentials
  metrics:
    schedule: "5s"
```

Review points:

- Use one `TrustyAIService` per monitored project.
- Keep database credentials in the referenced Secret.
- Prefer database storage for production-shaped narratives.
- Verify the monitored model is OVMS-supported before deployment.

## TrustyAIService With PVC Storage

```yaml
apiVersion: trustyai.opendatahub.io/v1
kind: TrustyAIService
metadata:
  name: trustyai-service
spec:
  storage:
    format: "PVC"
    folder: "/inputs"
    size: "1Gi"
  data:
    filename: "data.csv"
    format: "CSV"
  metrics:
    schedule: "5s"
    batchSize: 5000
```

Review points:

- Use PVC storage for development, testing, or small demo flows.
- The guide states CSV is the current data format for the PVC example.
- Batch size controls the observation history window used for metric
  calculation.

## KServe RawDeployment Logger Handoff

```json
{
  "caBundle": "kserve-logger-ca-bundle",
  "caCertFile": "service-ca.crt",
  "tlsSkipVerify": false
}
```

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: kserve-logger-ca-bundle
  namespace: <model-namespace>
  annotations:
    service.beta.openshift.io/inject-cabundle: "true"
data: {}
```

Review points:

- The logger ConfigMap update happens in `redhat-ods-applications`.
- The CA bundle ConfigMap exists in the model namespace.
- Redeploy the model pod if TrustyAI logs do not show captured data.

## Bias Metric Request

```bash
curl -sk -H "Authorization: Bearer ${TOKEN}" \
  -X POST "${TRUSTY_ROUTE}/metrics/group/fairness/spd/request" \
  -H "Content-Type: application/json" \
  --data '{
    "modelId": "demo-model",
    "protectedAttribute": "protected-feature",
    "privilegedAttribute": 1.0,
    "unprivilegedAttribute": 0.0,
    "outcomeName": "prediction",
    "favorableOutcome": 1,
    "batchSize": 5000
  }'
```

Review points:

- Confirm field names through `/info` or `/info/names`.
- Record threshold choice and batch size.
- Do not treat the default SPD example threshold as a universal policy.

## Drift Metric Request

```bash
curl -sk -H "Authorization: Bearer ${TOKEN}" \
  -X POST "${TRUSTY_ROUTE}/metrics/drift/meanshift/request" \
  -H "Content-Type: application/json" \
  --data '{
    "modelId": "demo-model",
    "referenceTag": "TRAINING"
  }'
```

Review points:

- Upload training data with the reference tag before creating the metric.
- Use MeanShift only when normal-distribution assumptions are acceptable.
- Query OpenShift Observe for `trustyai_*` metrics after creation.

## Evidence Record

```text
TrustyAI service namespace: <namespace>
Model runtime: OVMS | unsupported/deferred
Model ID: <model-id>
Storage: DATABASE | PVC
Training/reference data tag: <tag>
Bias metric: <metric/type/threshold/batch-size>
Drift metric: <metric/referenceTag/batch-size>
OpenShift metric observed: <trustyai_* query>
Limitations: <runtime, data, threshold, and interpretation limits>
```

Review points:

- Keep enough evidence for README and presentation claims without exposing
  training data, tokens, or protected attributes that should not be public.
- Link LLM safety and benchmark evidence to `rhoai-evaluation` rather than
  TrustyAI monitoring when the model is not OVMS-supported.
