# Official Doc Extraction

Use this extraction to keep OpenShift Pipelines observability content grounded
in the official Red Hat OpenShift Pipelines 1.22 observability guide. All
configuration fields, metric names, CLI commands, and behavioral details are
taken directly from the official documentation.

## Tekton Results Concepts

Tekton Results archives completed pipeline runs and task runs as results and
records:

- For every completed `PipelineRun` and `TaskRun` CR, Tekton Results creates a
  record.
- A result can contain one or several records; a record belongs to exactly one
  result.
- A result corresponds to a pipeline run and includes records for the
  `PipelineRun` CR itself and all `TaskRun` CRs the pipeline run started.
- A standalone task run (not started by a pipeline) gets its own result with a
  single record.
- Result name format: `<namespace_name>/results/<parent_run_uuid>`
- Record name format:
  `<namespace_name>/results/<parent_run_uuid>/records/<run_uuid>`
- Records contain the full YAML manifest of the CR after run completion,
  including specification, annotations, and completion status.
- Tekton Results preserves manifests after CR deletion.
- CEL queries and run-name-based queries can search results and records.
- Log forwarding to `LokiStack` is optional; without it, Tekton Results does
  not store or serve logging information.

## Configuring LokiStack Forwarding

Prerequisites: OpenShift Logging and `LokiStack` installed on the cluster.

### ClusterLogForwarder CR (OpenShift Logging v6)

```yaml
apiVersion: observability.openshift.io/v1
kind: ClusterLogForwarder
metadata:
  name: collector
  namespace: openshift-logging
spec:
  inputs:
  - application:
      selector:
        matchExpressions:
          - key: app.kubernetes.io/managed-by
            operator: In
            values: ["tekton-pipelines", "pipelinesascode.tekton.dev"]
    name: only-tekton
    type: application
  managementState: Managed
  outputs:
  - lokiStack:
      labelKeys:
        application:
          ignoreGlobal: true
          labelKeys:
          - log_type
          - kubernetes.namespace_name
          - openshift_cluster_id
      authentication:
        token:
          from: serviceAccount
      target:
        name: logging-loki
        namespace: openshift-logging
    name: default-lokistack
    tls:
      ca:
        configMapName: openshift-service-ca.crt
        key: service-ca.crt
    type: lokiStack
  pipelines:
  - inputRefs:
    - only-tekton
    name: default-logstore
    outputRefs:
    - default-lokistack
  serviceAccount:
    name: collector
```

### ClusterLogForwarder CR (OpenShift Logging v5)

```yaml
apiVersion: "logging.openshift.io/v1"
kind: ClusterLogForwarder
metadata:
  name: instance
  namespace: openshift-logging
spec:
  inputs:
  - name: only-tekton
    application:
      selector:
        matchLabels:
          app.kubernetes.io/managed-by: tekton-pipelines
  pipelines:
    - name: enable-default-log-store
      inputRefs: [ only-tekton ]
      outputRefs: [ default ]
```

### TektonConfig LokiStack Settings

```yaml
apiVersion: operator.tekton.dev/v1alpha1
kind: TektonConfig
metadata:
  name: config
spec:
  result:
    loki_stack_name: logging-loki
    loki_stack_namespace: openshift-logging
```

- `loki_stack_name`: name of the `LokiStack` CR (typically `logging-loki`)
- `loki_stack_namespace`: namespace where `LokiStack` is deployed (typically
  `openshift-logging`)

## Configuring an External Database Server

The default internal PostgreSQL instance is for testing and nonproduction use.
For production, configure an external PostgreSQL-compatible database.

Create the credentials Secret:

```shell
oc create secret generic tekton-results-postgres \
  --namespace=openshift-pipelines \
  --from-literal=POSTGRES_USER=<user> \
  --from-literal=POSTGRES_PASSWORD=<password>
```

TektonConfig settings:

```yaml
apiVersion: operator.tekton.dev/v1alpha1
kind: TektonConfig
metadata:
  name: config
spec:
  result:
    is_external_db: true
    db_host: database.example.com
    db_port: 5342
```

- `db_host`: hostname of the PostgreSQL server
- `db_port`: port number of the PostgreSQL server

## Configuring the Retention Policy

Default behavior: Tekton Results stores data indefinitely. Configure pruning via
`TektonConfig`:

```yaml
apiVersion: operator.tekton.dev/v1alpha1
kind: TektonConfig
metadata:
  name: config
spec:
  result:
    options:
      configMaps:
        config-results-retention-policy:
          data:
            runAt: "3 5 * * 0"
            maxRetention: "30"
```

- `runAt`: cron schedule for the pruning job
- `maxRetention`: days to retain data

## Observability Metrics

The `tekton-results-watcher` exposes metrics on port `9090` at `/metrics`.
`ServiceMonitor` resources enable automatic Prometheus discovery.

### Common Labels

| Label | Description |
|-------|-------------|
| `kind` | Tekton resource type: `pipelinerun` or `taskrun` |
| `namespace` | Kubernetes namespace of the run |
| `pipeline` | Name of the pipeline (optional) |
| `status` | Completion status of the run |
| `task` | Name of the task (optional, TaskRuns only) |
| `taskrun` | Name of the TaskRun (optional, TaskRuns only) |

### Storage Performance Metrics

| Name | Type | Description | Labels | Buckets |
|------|------|-------------|--------|---------|
| `watcher_run_storage_latency_seconds` | Histogram | Duration between run completion and successful storage | kind, namespace | 0.1, 0.5, 1, 2, 5, 10, 30, 60, 120, 300, 600, 1800s |

When `DisableStoringIncompleteRuns` is `false`, storage latency is only recorded
when the run completes and the watcher stores it again.

### Storage Failure Metrics

| Name | Type | Description | Labels |
|------|------|-------------|--------|
| `runs_not_stored_count` | Counter | Total runs deleted without successful storage | kind, namespace |

May show inflated values during reconciliation retries.

### Deletion Duration Metrics

| Name | Type | Description | Labels |
|------|------|-------------|--------|
| `watcher_pipelinerun_delete_duration_seconds` | Histogram | Deletion duration since PipelineRun completion | pipeline, status, namespace |
| `watcher_taskrun_delete_duration_seconds` | Histogram | Deletion duration since TaskRun completion | pipeline, status, task, taskrun, namespace |

### Deletion Count Metrics

| Name | Type | Description | Labels |
|------|------|-------------|--------|
| `watcher_pipelinerun_delete_count` | Counter | Total deleted PipelineRuns | status, namespace |
| `watcher_taskrun_delete_count` | Counter | Total deleted TaskRuns | status, namespace |

## Querying Tekton Results via opc CLI

### Environment Setup

```shell
export RESULTS_API=$(oc get route tekton-results-api-service \
  -n openshift-pipelines --no-headers -o custom-columns=":spec.host"):443

oc create token <service_account>
```

Optional persistent config file: `~/.config/tkn/results.yaml`

```yaml
address: <tekton_results_route>
token: <authentication_token>
ssl:
   roots_file_path: /home/example/cert.pem
   server_name_override: tekton-results-api-service.openshift-pipelines.svc.cluster.local
service_account:
   namespace: service_acc_1
   name: service_acc_1
```

### Query by Name

```shell
# List results in a namespace
opc results result list --addr ${RESULTS_API} <namespace>

# List records in a result
opc results records list --addr ${RESULTS_API} <result_name>

# Get record YAML manifest
opc results records get --addr ${RESULTS_API} <record_name> \
  | jq -r .data.value | base64 -d | \
  xargs -0 python3 -c 'import sys, yaml, json; j=json.loads(sys.argv[1]); print(yaml.safe_dump(j))'

# Get task run logs
opc results logs get --addr ${RESULTS_API} <log_record_name> | jq -r .data | base64 -d
```

### CEL Queries for Results

| Purpose | CEL Query |
|---------|-----------|
| All failed runs | `!(summary.status == SUCCESS)` |
| Pipeline runs with specific annotations | `summary.annotations.contains('ann1') && summary.annotations.contains('ann2') && summary.type=='PIPELINE_RUN'` |

CEL result fields: `parent`, `uid`, `annotations`, `summary`, `create_time`,
`update_time`. The `summary.status` field values: `UNKNOWN`, `SUCCESS`,
`FAILURE`, `TIMEOUT`, `CANCELLED` (no quotes in queries).

### CEL Queries for Records

| Purpose | CEL Query |
|---------|-----------|
| Failed runs | `!(data.status.conditions[0].status == 'True')` |
| By CR name | `data.metadata.name == 'run1'` |
| Task runs from a specific pipeline run | `data_type == 'TASK_RUN' && data.metadata.labels['tekton.dev/pipelineRun'] == 'run1'` |
| By pipeline name | `data.metadata.labels['tekton.dev/pipeline'] == 'pipeline1'` |
| Pipeline runs only for a pipeline | `data.metadata.labels['tekton.dev/pipeline'] == 'pipeline1' && data_type == 'PIPELINE_RUN'` |
| Task run name prefix | `data.metadata.name.startsWith('hello') && data_type=='TASK_RUN'` |
| Runs longer than 5 minutes | `data.status.completionTime - data.status.startTime > duration('5m') && data_type == 'PIPELINE_RUN'` |
| Runs completed on a specific date | `data.status.completionTime.getDate() == 7 && data.status.completionTime.getMonth() == 10 && data.status.completionTime.getFullYear() == 2023` |
| Pipeline runs with 3+ tasks | `size(data.status.pipelineSpec.tasks) >= 3 && data_type == 'PIPELINE_RUN'` |
| Runs with specific annotations | `data.metadata.annotations.contains('ann1') && data_type == 'PIPELINE_RUN'` |

CEL record fields: `name`, `data_type` (`tekton.dev/v1.TaskRun` or `TASK_RUN`,
`tekton.dev/v1.PipelineRun` or `PIPELINE_RUN`,
`results.tekton.dev/v1alpha2.Log`), `data` (full YAML data).

## Querying by Pipeline Run and Task Run Names (Technology Preview)

This feature is Technology Preview and not supported with Red Hat production
SLAs.

### opc Configuration for Name-Based Queries

```shell
# Interactive
opc results config set

# CLI
opc results config set --host="https://tekton-results.example.com" --token="<token>"

# Verify
opc results config view
```

### Pipeline Run Commands

```shell
opc results pipelinerun list -n <namespace>
opc results pipelinerun list <pipeline_name> -n <namespace>
opc results pipelinerun describe -n <namespace> <pipelinerun_name>
opc results pipelinerun describe -n <namespace> --uid <pipelinerun_uuid>
opc results pipelinerun describe -n <namespace> --output yaml <pipelinerun_name>
opc results pipelinerun logs -n <namespace> <pipelinerun_name>
```

Pipeline run logs do NOT include logs of child task runs. Use
`opc results taskrun list --pipelinerun` then `opc results taskrun logs` for
task-level logs.

### Task Run Commands

```shell
opc results taskrun list -n <namespace>
opc results taskrun list --pipelinerun <pipelinerun_name> -n <namespace>
opc results taskrun describe -n <namespace> <taskrun_name>
opc results taskrun describe -n <namespace> --output yaml <taskrun_name>
opc results taskrun logs -n <namespace> <taskrun_name>
```

### Short Names

| Full Name | Short Name |
|-----------|------------|
| `pipelinerun` | `pr` |
| `taskrun` | `tr` |
| `describe` | `desc` |

## Fine-Grained Retention Policies

Configured via the `tekton-results-config-results-retention-policy` ConfigMap
in the `openshift-pipelines` namespace (or via `TektonConfig`
`spec.result.options.configMaps`).

### ConfigMap Fields

| Field | Description | Default |
|-------|-------------|---------|
| `runAt` | Cron schedule for pruning | `"7 7 * * 7"` (example) |
| `defaultRetention` | Fallback retention period (days or duration string) | `30d` |
| `maxRetention` | Deprecated; same as `defaultRetention` | N/A |
| `policies` | Ordered list of fine-grained retention rules | None |

### Policy Fields

| Field | Description |
|-------|-------------|
| `name` | Descriptive name for the policy |
| `selector` | Matching criteria (all conditions use AND logic) |
| `selector.matchNamespaces` | List of namespaces (OR within list) |
| `selector.matchLabels` | Map of label keys to value lists |
| `selector.matchAnnotations` | Map of annotation keys to value lists |
| `selector.matchStatuses` | List of statuses: `Succeeded`, `Failed`, `Cancelled`, `Running`, `Pending` |
| `retention` | Retention period (days or duration string like `24h`, `7d`) |

Policies are evaluated in order; the first matching policy wins. Results not
matching any policy use `defaultRetention`.

### Example ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: tekton-results-config-results-retention-policy
  namespace: openshift-pipelines
data:
  runAt: "0 2 * * *"
  defaultRetention: "30d"
  policies: |
    - name: "retain-critical-failures-long-term"
      selector:
        matchNamespaces:
          - "production"
          - "prod-east"
        matchLabels:
          "criticality": ["high"]
        matchStatuses:
          - "Failed"
      retention: "180d"
    - name: "retain-annotated-for-debug"
      selector:
        matchAnnotations:
          "debug/retain": ["true"]
      retention: "14d"
    - name: "default-production-policy"
      selector:
        matchNamespaces:
          - "production"
          - "prod-east"
      retention: "60d"
    - name: "short-term-ci-retention"
      selector:
        matchNamespaces:
          - "ci"
      retention: "7d"
```

## Verification Before Implementation

Before implementing Tekton Results observability:

- Confirm OpenShift Pipelines operator version and Tekton Results component
  version
- Check `TektonConfig` CR for current `spec.result` configuration
- Verify OpenShift Logging and `LokiStack` installation if log forwarding is
  needed
- Confirm `ServiceMonitor` resources exist for Tekton Results
- Verify `opc` CLI availability and authentication
- Check external database connectivity if configuring production storage
