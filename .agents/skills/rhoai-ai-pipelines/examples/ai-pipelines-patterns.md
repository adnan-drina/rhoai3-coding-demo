# AI Pipelines Patterns

These examples are review patterns. Verify the active baseline, pipeline
server configuration, CRD schema, credentials, and storage before using them in
demo steps.

## Pipeline Server Decision Pattern

```text
Project: <project-name>
Object storage: S3-compatible bucket owned by the project
Database: default on-cluster database | external MySQL/MariaDB
Pipeline definition storage: Kubernetes API | internal database
Caching: configurable per pipeline/task | disabled at server level
```

Review points:

- Use the default on-cluster database only for development/test positioning.
- Use external MySQL/MariaDB for production-positioned pipeline workloads.
- Prefer Kubernetes API storage when GitOps should manage pipeline definitions.
- Treat wrong object storage settings as requiring pipeline server recreation.

## KFP Compile Pattern

```bash
kfp dsl compile \
  --py <pipeline_file>.py \
  --output <compiled_pipeline_file>.yaml
```

Review points:

- Confirm Python 3.11 or later.
- Confirm `kfp` 2.14.3 or later unless the active docs change.
- Verify the generated YAML includes `pipelineSpec`.
- Pair with `rhoai-kfp-pipeline-authoring` when editing repo pipeline code.

## Reusable Component Adoption Pattern

```text
Pipeline goal: <business or demo capability>
Existing component search:
  - kubeflow/pipelines-components: <match | none>
  - red-hat-data-services/pipelines-components: <match | none>
Selected component stability: alpha | beta | stable | local demo-only
Input mode: artifact | S3 URL | local/workspace path | parameter
Validation data set: small fixture | sampled corpus | full corpus
First run: single component | minimal two-step pipeline | full workflow
```

Review points:

- Search reusable component catalogs before writing custom pipeline code.
- Prefer components whose README, metadata, stability, inputs, limitations, and
  last verification status match the demo need.
- Treat alpha or unverified components as implementation references, not
  production-ready building blocks.
- Start with a small run in the OpenShift AI Pipelines UI before scaling to a
  full data set or GPU-backed workload.
- Keep run names, parameters, artifacts, logs, and experiment grouping clear
  enough to compare later.
- Route component code adaptation to `rhoai-kfp-pipeline-authoring`.

## Kubernetes API Storage Pattern

```yaml
apiVersion: pipelines.kubeflow.org/v2beta1
kind: Pipeline
metadata:
  name: <pipeline-name>
  namespace: <project-name>
---
apiVersion: pipelines.kubeflow.org/v2beta1
kind: PipelineVersion
metadata:
  name: <pipeline-version-name>
  namespace: <project-name>
spec:
  pipelineSpec: {}
```

Review points:

- Verify the active CRD before adding fields.
- Use only with a pipeline server configured for Kubernetes API storage.
- Store generated and reviewed manifests in GitOps when the demo requires
  declarative pipeline definitions.

## KFP Client Authentication Pattern

```bash
export NAMESPACE=<project_namespace>
export DSPA_NAME=$(oc -n "$NAMESPACE" get dspa -o jsonpath='{.items[0].metadata.name}')
export API_URL="https://$(oc -n "$NAMESPACE" get route "ds-pipeline-${DSPA_NAME}" -o jsonpath='{.spec.host}')"
export OCP_TOKEN=$(oc whoami --show-token)
```

```python
import os
from kfp.client import Client

client = Client(
    host=os.environ["API_URL"],
    existing_token=os.environ["OCP_TOKEN"],
    namespace=os.environ["NAMESPACE"],
)

print(client.list_experiments())
```

Review points:

- Do not paste tokens as literal arguments.
- Use a trusted certificate bundle when needed.
- Do not commit token values or generated shell history.

## Caching Pattern

Task-level:

```python
task_name.set_caching_options(False)
```

Submit-time:

```python
client.run_pipeline(
    experiment_id=experiment.id,
    pipeline_id=pipeline.id,
    job_name="no-cache-run",
    params={},
    enable_caching=False,
)
```

Compile-time:

```bash
export KFP_DISABLE_EXECUTION_CACHING_BY_DEFAULT=true
kfp dsl compile --disable-execution-caching-by-default
```

Server-level:

```yaml
apiVersion: datasciencepipelinesapplications.opendatahub.io/v1
kind: DataSciencePipelinesApplication
metadata:
  name: <dspa-name>
  namespace: <project-name>
spec:
  apiServer:
    cacheEnabled: false
```

Review points:

- Server-level cache disablement overrides task and pipeline settings.
- Disabling caching can increase compute time and resource usage.
- Cached tasks are marked in the UI and do not have fresh execution logs.

## ODF/NooBaa DSPA Object Storage Pattern

Use a stable bucket name for DSPA artifacts because
`DataSciencePipelinesApplication.spec.objectStorage.externalStorage.bucket`
is a committed field:

```yaml
apiVersion: objectbucket.io/v1alpha1
kind: ObjectBucketClaim
metadata:
  name: private-rag-pipelines-bucket
  namespace: enterprise-rag
spec:
  bucketName: enterprise-rag-pipelines
  storageClassName: openshift-storage.noobaa.io
---
apiVersion: datasciencepipelinesapplications.opendatahub.io/v1
kind: DataSciencePipelinesApplication
metadata:
  name: private-rag-pipelines
  namespace: enterprise-rag
spec:
  apiServer:
    artifactSignedURLExpirySeconds: 60
    caBundleFileMountPath: ""
    caBundleFileName: ""
    cacheEnabled: false
    deploy: true
    enableOauth: true
    enableSamplePipeline: false
    pipelineStore: database
    resourceTTL: 24h0m0s
  database:
    disableHealthCheck: false
    mariaDB:
      deploy: true
      pipelineDBName: mlpipeline
      pvcSize: 10Gi
      username: mlpipeline
  dspVersion: v2
  objectStorage:
    disableHealthCheck: false
    enableExternalRoute: false
    externalStorage:
      bucket: enterprise-rag-pipelines
      basePath: artifacts
      host: s3.openshift-storage.svc
      port: "80"
      region: ""
      scheme: http
      secure: false
      s3CredentialsSecret:
        secretName: private-rag-pipelines-bucket
        accessKey: AWS_ACCESS_KEY_ID
        secretKey: AWS_SECRET_ACCESS_KEY
  persistenceAgent:
    deploy: true
    numWorkers: 2
  podToPodTLS: true
  scheduledWorkflow:
    cronScheduleTimezone: UTC
    deploy: true
```

Review points:

- Verify `bucketName` with the live `ObjectBucketClaim` schema before using it.
- Use `generateBucketName` for normal project source buckets; discover generated
  source bucket names from the OBC ConfigMap in runner scripts.
- Use the in-cluster S3 service for DSPA artifacts. If using HTTPS, validate CA
  trust through DSPA `apiServer.cABundle`; otherwise use the cluster-internal
  HTTP service only when the demo posture allows it.
- Do not commit generated OBC credentials.
- RHOAI defaults several DSPA spec fields after creation. For GitOps-managed
  DSPA resources, verify these fields with the active CRD or a live reconciled
  object and declare stable defaults in Git rather than leaving Argo CD
  permanently `OutOfSync`.

## Workspace Pattern

```python
from kfp import dsl

@dsl.pipeline(
    name="pipeline-with-workspace",
    pipeline_config=dsl.PipelineConfig(
        workspace=dsl.WorkspaceConfig(size="100Mi"),
    ),
)
def pipeline_with_workspace():
    task = write_to_workspace(
        workspace_path=dsl.WORKSPACE_PATH_PLACEHOLDER,
    )
```

Review points:

- Workspace support must be enabled in the pipeline server.
- Use the KFP placeholder rather than a hard-coded path.
- Verify storage class, access mode, and size against the active cluster.

## Experiment And Run Pattern

```text
Experiment: <capability-or-model-name>
Run: <pipeline-version>-<dataset-or-parameter-set>
Pipeline version: <version-name>
Parameters: <reviewed-values>
Schedule: immediate | cron | recurring
Archive policy: retain evidence | delete archived records explicitly
```

Review points:

- Group runs that should be compared in the same experiment.
- Keep run names meaningful for later comparison and evidence review.
- Compare no more than the documented number of runs at once.
- Make catch-up behavior explicit for scheduled runs.

## DSPA Troubleshooting Pattern

```bash
oc get dspa -n <project-name> -o yaml
oc get pods -n <project-name>
oc get events -n <project-name> --sort-by=.lastTimestamp
```

Review points:

- Separate object storage TLS trust, reachability, and credential failures.
- Separate database network, TLS trust, and blocked-host failures.
- Keep project names short enough to avoid route host length failures.
- Check pod logs for CrashLoopBackOff or pod-level failures.
