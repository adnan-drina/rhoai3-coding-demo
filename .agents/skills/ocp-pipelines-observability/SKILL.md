---
name: ocp-pipelines-observability
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "ocp"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when configuring OpenShift Pipelines observability: Tekton Results for
  log and result storage, metrics collection, ServiceMonitor configuration,
  log forwarding, pipeline run result aggregation, database configuration,
  and observability dashboards for OpenShift Pipelines 1.22. Do NOT use for
  installing pipelines (use ocp-pipelines-install-config), creating CI/CD
  pipelines (use ocp-pipelines-cicd), or security (use
  ocp-pipelines-security).
---

# OCP Pipelines Observability

Use this skill to ground OpenShift Pipelines observability guidance in the
official Red Hat OpenShift Pipelines 1.22 observability guide for the active
baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority. This skill captures the Tekton Results
architecture, LokiStack log forwarding configuration, external database setup,
retention policies, observability metrics, and the `opc` CLI for querying
results, records, and logs.

## Tekton Results Architecture

Tekton Results archives completed `PipelineRun` and `TaskRun` CRs as results
and records in a PostgreSQL database. Key concepts:

- A **result** corresponds to a pipeline run and includes records for the
  `PipelineRun` CR and all `TaskRun` CRs it started.
- A **record** contains the full YAML manifest of a `TaskRun` or `PipelineRun`
  CR as it existed after completion.
- Result name format: `<namespace>/results/<parent_run_uuid>`
- Record name format: `<namespace>/results/<parent_run_uuid>/records/<run_uuid>`
- Tekton Results preserves manifests after CR deletion and makes them available
  for viewing and searching via CEL queries.
- Log forwarding to `LokiStack` is optional but required for log queries.

## Configuring Tekton Results

Installing OpenShift Pipelines enables Tekton Results by default. Additional
configuration is available for:

- **LokiStack forwarding** — requires OpenShift Logging and `LokiStack`;
  configure a `ClusterLogForwarder` CR (v6 or v5 API) and set
  `spec.result.loki_stack_name` and `spec.result.loki_stack_namespace` in
  `TektonConfig`.
- **External database** — for production, configure `spec.result.is_external_db`,
  `spec.result.db_host`, and `spec.result.db_port` in `TektonConfig` and create
  a `tekton-results-postgres` Secret in `openshift-pipelines`.
- **Retention policy** — configure via
  `spec.result.options.configMaps.config-results-retention-policy` with `runAt`
  (cron schedule) and `maxRetention` (days).

## Observability Metrics

The `tekton-results-watcher` exposes metrics on port `9090` at `/metrics`.
Prometheus Operator discovers these via `ServiceMonitor` resources.

Metric categories:

- **Storage performance**: `watcher_run_storage_latency_seconds` (histogram)
- **Storage failures**: `runs_not_stored_count` (counter)
- **Deletion duration**: `watcher_pipelinerun_delete_duration_seconds`,
  `watcher_taskrun_delete_duration_seconds` (histograms)
- **Deletion count**: `watcher_pipelinerun_delete_count`,
  `watcher_taskrun_delete_count` (counters)

Common labels: `kind`, `namespace`, `pipeline`, `status`, `task`, `taskrun`.

## Querying Tekton Results

Use the `opc` CLI (installed with the `tkn` package) to query results and
records:

- **By name**: `opc results result list`, `opc results records list`,
  `opc results records get`, `opc results logs get`
- **By CEL query**: `--filter="<cel_query>"` on result and record list commands
- **By pipeline/task run name** (Technology Preview): `opc results pipelinerun
  list`, `opc results taskrun list`, `opc results pipelinerun describe`,
  `opc results taskrun describe`, `opc results pipelinerun logs`,
  `opc results taskrun logs`

Environment setup requires setting `RESULTS_API` to the Tekton Results API
route and creating an authentication token via `oc create token`.

## Retention Policy

Fine-grained retention policies are configured via the
`tekton-results-config-results-retention-policy` ConfigMap in
`openshift-pipelines`:

- `runAt` — cron schedule for pruning
- `defaultRetention` — fallback retention period (days or duration string)
- `maxRetention` — deprecated, use `defaultRetention`
- `policies` — ordered list of fine-grained rules with `name`, `selector`
  (`matchNamespaces`, `matchLabels`, `matchAnnotations`, `matchStatuses`), and
  `retention`

Policies are evaluated in order; first match wins.

## Workflow

1. Confirm the active OpenShift Pipelines baseline in
   `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Identify whether the task concerns:
   - Tekton Results architecture and concepts
   - LokiStack log forwarding configuration
   - external database configuration for production
   - retention policy configuration
   - observability metrics and ServiceMonitor setup
   - querying results and records via `opc` CLI
   - querying by pipeline/task run names (Technology Preview)
   - fine-grained retention policies
4. For `TektonConfig` changes, verify the exact `spec.result` fields against
   the official documentation or active cluster schema.
5. For `ClusterLogForwarder` configuration, match the OpenShift Logging version
   (v5 vs v6 API).
6. Validate the output with `references/source-capture.md`.

## Related Skills

- Use `ocp-pipelines-release-notes` for OpenShift Pipelines 1.22 release notes,
  version compatibility, and breaking changes.
- Use `ocp-observability` for OCP platform observability, monitoring stack, and
  logging architecture.
- Use `ocp-cicd-builds` for OpenShift build strategies and BuildConfig.
- Use `ocp-grafana-operator` for Grafana Operator, instances, datasources, and
  dashboards.
- Use future `ocp-pipelines-install-config` for general OpenShift Pipelines
  installation and configuration.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
