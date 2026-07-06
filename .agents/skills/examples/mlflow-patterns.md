# MLflow Patterns

These examples are review patterns. Verify active CRDs, dashboard route,
Secrets, RBAC, project access, and storage providers before copying anything
into GitOps or runbooks.

## Enable MLflow Operator Component

```yaml
spec:
  components:
    mlflowoperator:
      managementState: Managed
```

Review points:

- Preserve unrelated `DataScienceCluster` fields.
- Verify schema with `oc explain datasciencecluster.spec.components.mlflowoperator`.
- Treat this as cluster-level platform configuration.

## Development/Test MLflow Shape

```yaml
apiVersion: mlflow.opendatahub.io/v1
kind: MLflow
metadata:
  name: mlflow
  namespace: redhat-ods-applications
spec:
  storage:
    accessModes:
      - ReadWriteOnce
    resources:
      requests:
        storage: 10Gi
  backendStoreUri: sqlite:////mlflow/mlflow.db
  artifactsDestination: file:///mlflow/artifacts
  serveArtifacts: true
```

Review points:

- Use only for development, test, or small demo flows.
- Do not present SQLite or file/PVC artifact storage as production-shaped.
- Verify exact fields with `oc explain mlflow.spec`.

## Production-Oriented MLflow Shape

```yaml
apiVersion: mlflow.opendatahub.io/v1
kind: MLflow
metadata:
  name: mlflow
  namespace: redhat-ods-applications
spec:
  replicas: 2
  backendStoreUriFrom:
    name: mlflow-db-credentials
    key: backend-store-uri
  artifactsDestination: s3://<bucket>/<prefix>
  serveArtifacts: true
  envFrom:
    - secretRef:
        name: mlflow-artifact-credentials
```

Review points:

- Store database URI and object storage credentials in Secrets.
- Do not commit Secret values.
- Use PostgreSQL for production-shaped metadata storage.
- Use S3-compatible storage for production-shaped artifact storage.
- When `serveArtifacts` is enabled, do not set `defaultArtifactRoot` to a
  direct `s3://` URI.

## Project Artifact Override

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: mlflow-artifact-connection
  annotations:
    opendatahub.io/connection-type-protocol: s3
type: Opaque
stringData:
  AWS_ACCESS_KEY_ID: <redacted>
  AWS_SECRET_ACCESS_KEY: <redacted>
  AWS_S3_BUCKET: <bucket>
  AWS_S3_ENDPOINT: <endpoint>
  AWS_DEFAULT_REGION: <region>
---
apiVersion: mlflow.kubeflow.org/v1
kind: MLflowConfig
metadata:
  name: mlflow
spec:
  artifactRootSecret: mlflow-artifact-connection
  artifactRootPath: mlflow-artifacts
```

Review points:

- The Secret and `MLflowConfig` live in the data science project namespace.
- The Secret name must be `mlflow-artifact-connection`.
- `artifactRootPath` is optional and must be relative.
- Per-project overrides require clients to access S3 directly.

## SDK Environment

```bash
pip install "mlflow[kubernetes]>=3.11"

export MLFLOW_TRACKING_URI="https://<dashboard-url>/mlflow"
export MLFLOW_TRACKING_AUTH=kubernetes-namespaced
export MLFLOW_TRACKING_INSECURE_TLS=true
```

Review points:

- Use `MLFLOW_TRACKING_INSECURE_TLS=true` only for demo self-signed
  certificate posture.
- Prefer `kubernetes-namespaced` auth over manual token exports.
- Verify the active kubeconfig namespace for workstation use.

## Minimal Tracking Check

```python
import mlflow

mlflow.set_experiment("demo-experiment")

with mlflow.start_run(run_name="demo-run"):
    mlflow.log_param("model_type", "baseline")
    mlflow.log_metric("accuracy", 0.95)
```

Review points:

- Confirm the run appears in the intended project workspace.
- Do not log credentials, tokens, private prompts, or sensitive payloads.
- Use `mlflow.set_workspace("<project-name>")` only when intentionally
  targeting another workspace and RBAC allows it.

## Troubleshooting Pointers

```text
403 or permission denied:
  Check project RoleBinding and effective MLflow pseudo-resource access.

Workspace not found:
  Check active namespace, selected workspace, and MLFLOW_WORKSPACE.

Artifact override not applied:
  Check MLflowConfig name, namespace, and mlflow-artifact-connection Secret.

JSON decode error:
  Check OpenShift login and kubernetes-namespaced authentication settings.
```
