# Official Doc Extraction

Use this extraction to keep OpenShift Pipelines installation and configuration
content grounded in official Red Hat sources. When implementation needs exact
CR fields, verify the active cluster schema with `oc explain` or `oc get crd`
before authoring GitOps manifests.

## Installation Prerequisites

- Access to an OpenShift Container Platform cluster with `cluster-admin`
  permissions.
- `oc` CLI installed.
- OpenShift Pipelines (`tkn`) CLI installed locally.
- Cluster has the Marketplace capability enabled or the Red Hat Operator
  catalog source configured manually.
- Red Hat OpenShift Pipelines runs on Linux nodes only in mixed-OS clusters.

## Web Console Installation

Install via Operators > OperatorHub:

- Search for "Red Hat OpenShift Pipelines" and click Install.
- Installation Mode: All namespaces on the cluster (default); installs to
  `openshift-operators` namespace.
- Approval Strategy: Automatic (recommended) or Manual.
- Update Channel: `latest` (most recent stable) or `pipelines-<version>` for a
  specific version.

The Operator automatically creates a `TektonConfig` CR on install.

Verification:

```shell
oc get tektonconfig config
```

Expected output shows `READY: True`. Additionally:

```shell
oc get tektonpipeline,tektontrigger,tektonchain,tektonaddon,pac
```

## CLI Installation

Create a Subscription:

```yaml
apiVersion: operators.coreos.com/v1alpha1
kind: Subscription
metadata:
  name: openshift-pipelines-operator
  namespace: openshift-operators
spec:
  channel: <channel_name>
  name: openshift-pipelines-operator-rh
  source: redhat-operators
  sourceNamespace: openshift-marketplace
```

Apply with `oc apply -f sub.yaml`. The Operator installs into
`openshift-operators` and deploys OpenShift Pipelines into the
`openshift-pipelines` target namespace.

## Installation Profiles

The TektonConfig CR supports three profiles:

| Profile | Components installed |
|---------|---------------------|
| Lite | Tekton Pipelines |
| Basic | Tekton Pipelines, Tekton Triggers, Tekton Chains, Tekton Results |
| All (default) | All Tekton components: Pipelines, Triggers, Chains, Results, Pipelines as Code, and Tekton add-ons (ClusterTriggerBindings, ConsoleCLIDownload, ConsoleQuickStart, ConsoleYAMLSample, cluster resolver tasks and step action definitions from `openshift-pipelines` namespace) |

## CRDs

The default CRD `config.operator.tekton.dev` is replaced by
`tektonconfigs.operator.tekton.dev`. Additional CRDs manage components
individually:

- `tektonpipelines.operator.tekton.dev`
- `tektontriggers.operator.tekton.dev`
- `tektonaddons.operator.tekton.dev`

## Restricted Environment

The Operator installs a proxy webhook that sets proxy environment variables in
pod containers created by tekton-controllers, based on the `cluster` proxy
object. The webhook also sets variables in `TektonPipelines`,
`TektonTriggers`, `Controllers`, `Webhooks`, and `Operator Proxy Webhook`
resources.

The proxy webhook is disabled for the `openshift-pipelines` namespace by
default. Disable for other namespaces with the label:

```
operator.tekton.dev/disable-proxy: "true"
```

## Uninstallation

Three ordered steps:

1. **Delete CRs**: Delete `TektonHub` and `TektonResult` CRs (if they exist),
   then delete `TektonConfig` CR. Deleting CRs also deletes all Red Hat
   OpenShift Pipelines components, tasks, and pipelines on the cluster.
   Skipping optional CR deletion before Operator removal prevents later
   component cleanup.

2. **Uninstall Operator**: From Operators > OperatorHub, find Red Hat OpenShift
   Pipelines, click Uninstall, select "Delete all operand instances", confirm.
   This deletes all resources in the `openshift-pipelines` namespace including
   configured secrets.

3. **Delete CRDs**: In Administration > CustomResourceDefinitions, filter by
   `operator.tekton.dev`, delete each CRD.

## Performance Tuning

Configure under `spec.pipeline.performance` in the TektonConfig CR:

```yaml
apiVersion: operator.tekton.dev/v1alpha1
kind: TektonConfig
metadata:
  name: config
spec:
  pipeline:
    performance:
      disable-ha: false
      buckets: 7
      replicas: 5
      threads-per-controller: 2
      kube-api-qps: 5.0
      kube-api-burst: 10
```

All fields are optional. The Operator includes most fields as arguments in the
`openshift-pipelines-controller` deployment. The `buckets` field updates the
`config-leader-election` config map.

| Field | Description | Default |
|-------|-------------|---------|
| disable-ha | Enable or disable HA mode | false |
| buckets | Number of buckets for controller operations (max 10) | 1 |
| replicas | Number of pods for controller operations (set <= buckets) | 1 |
| threads-per-controller | Worker threads for the controller work queue | 2 |
| kube-api-qps | Max QPS to the cluster control plane | 5.0 |
| kube-api-burst | Max burst for throttle | 10 |

HA mode distributes controller operations across multiple replicas using
bucket-based assignment with internal leader election. HA mode does not affect
task run execution after pod creation.

The Operator does not directly control replicas; use:

```shell
oc --namespace openshift-pipelines scale deployment openshift-pipelines-controller --replicas=3
```

The controller multiplies `kube-api-qps` and `kube-api-burst` by 2 internally.

## Control Plane Configuration

### Modifiable Fields With Defaults

Configure under `spec.pipeline` in the TektonConfig CR:

| Field | Default | Description |
|-------|---------|-------------|
| running-in-environment-with-injected-sidecars | true | Set to false if no injected sidecars (e.g. Istio); reduces task run start time |
| await-sidecar-readiness | true | Set to false to skip waiting for TaskRun sidecar containers |
| default-service-account | pipeline | Default SA for TaskRun and PipelineRun |
| require-git-ssh-secret-known-hosts | false | Require known_hosts in Git SSH secrets |
| enable-tekton-oci-bundles | false | Enable experimental Tekton OCI bundles |
| enable-api-fields | stable | API field gate: stable, beta, or alpha (alpha not supported by Red Hat) |
| enable-provenance-in-status | false | Populate provenance field in TaskRun/PipelineRun status |
| enable-custom-tasks | true | Enable custom tasks in pipelines |
| disable-creds-init | false | Prevent scanning SAs and injecting credentials |
| disable-affinity-assistant | true | Disable affinity assistant for PVC workspace sharing |
| metrics.taskrun.duration-type | histogram | Duration metric type for task runs (histogram or gauge) |
| metrics.pipelinerun.duration-type | histogram | Duration metric type for pipeline runs (histogram or gauge) |
| metrics.taskrun.level | task | Task run metrics level (taskrun, task, or namespace) |
| metrics.pipelinerun.level | pipeline | Pipeline run metrics level (pipelinerun, pipeline, or namespace) |

### Optional Configuration Fields

Not set by default; the Operator only applies them if configured:

- `default-timeout-minutes`: Default timeout for TaskRun/PipelineRun
- `default-managed-by-label-value`: Default `app.kubernetes.io/managed-by` label for TaskRun pods
- `default-pod-template`: Default TaskRun/PipelineRun pod template
- `default-cloud-events-sink`: Default CloudEvents sink
- `default-task-run-workspace-binding`: Default workspace config for undeclared TaskRun workspaces
- `default-affinity-assistant-pod-template`: Default PipelineRun pod template for affinity assistant pods
- `default-max-matrix-combinations-count`: Max matrix combinations

## Service Account Configuration

```yaml
apiVersion: operator.tekton.dev/v1alpha1
kind: TektonConfig
metadata:
  name: config
spec:
  pipeline:
    default-service-account: pipeline
  trigger:
    default-service-account: pipeline
    enable-api-fields: stable
```

## Namespace Labels And Annotations

Configure via `spec.targetNamespaceMetadata`:

```yaml
apiVersion: operator.tekton.dev/v1
kind: TektonConfig
metadata:
  name: config
spec:
  targetNamespaceMetadata:
    labels: {"example-label": "example-value"}
    annotations: {"example-annotation": "example-value"}
```

Renaming the `openshift-pipelines` namespace is not supported.

## Resync Period

The default resync period is 10 hours. For clusters with many pipeline/task
runs, configure a longer period:

```yaml
apiVersion: operator.tekton.dev/v1alpha1
kind: TektonConfig
metadata:
  name: config
spec:
  pipeline:
    options:
      deployments:
        tekton-pipelines-controller:
          spec:
            template:
              spec:
                containers:
                - name: tekton-pipelines-controller
                  args:
                    - "-resync-period=24h"
```

## Service Monitor

Disable with `enableMetrics: 'false'`:

```yaml
apiVersion: operator.tekton.dev/v1alpha1
kind: TektonConfig
metadata:
  name: config
spec:
  pipeline:
    params:
       - name: enableMetrics
         value: 'false'
```

## Pipeline Resolvers

Enable or disable resolvers:

```yaml
apiVersion: operator.tekton.dev/v1alpha1
kind: TektonConfig
metadata:
  name: config
spec:
  pipeline:
    enable-bundles-resolver: true
    enable-cluster-resolver: true
    enable-git-resolver: true
    enable-hub-resolver: true
```

Resolver-specific configuration:

```yaml
spec:
  pipeline:
    bundles-resolver-config:
      default-service-account: pipelines
    cluster-resolver-config:
      default-namespace: test
    git-resolver-config:
      server-url: localhost.com
    hub-resolver-config:
      default-tekton-hub-catalog: tekton
```

## Resolver Tasks And Pipeline Templates

Disable default installation of `resolverTasks` and `pipelineTemplates`:

```yaml
spec:
  addon:
    params:
      - name: resolverTasks
        value: 'false'
      - name: pipelineTemplates
        value: 'false'
```

`pipelineTemplates` can only be `true` when `resolverTasks` is `true`.

## Tekton Triggers Toggle

Disable Tekton Triggers installation:

```yaml
spec:
  trigger:
    disabled: true
```

## Tekton Hub Integration

Disable developer console integration:

```yaml
spec:
  hub:
    params:
      - name: enable-devconsole-integration
        value: false
```

## Tekton Hub To Artifact Hub Migration

Tekton Hub is deprecated. The hub resolver now defaults to the `artifact` type.
Tekton Hub (`type: tekton`) requires additional configuration to keep
functioning.

Migration steps:

1. Remove `type: tekton` parameter (do not add `type: artifact`; it is the
   default).
2. Update catalog names:
   - Tasks: `catalog: Tekton` -> `catalog: tekton-catalog-tasks`
   - Pipelines: `catalog: Tekton` -> `catalog: tekton-catalog-pipelines`
   - StepActions: `catalog: Tekton` -> `catalog: tekton-catalog-stepactions`
3. Update versions to full semver (e.g. `0.8` -> `0.8.0`).

For private Artifact Hub instances, configure:

```yaml
spec:
  pipeline:
    hub-resolver-config:
      default-artifact-hub-url: "https://artifacthub.io"
```

When using a private Artifact Hub: verify network connectivity from resolver
pods, configure TLS certificates, configure authentication if required, and
ensure catalog names match the private hub.

## RBAC Resource Creation

The default installation creates RBAC resources for all namespaces except those
matching `^(openshift|kube)-*`. The `pipelines-scc-rolebinding` SCC role
binding uses the `pipelines-scc` SCC with `RunAsAny` privilege.

Disable with:

```yaml
spec:
  params:
  - name: createRbacResource
    value: "false"
```

## Inline Specification Controls

Disable inline specification of tasks and pipelines:

```yaml
spec:
  pipeline:
    disable-inline-spec: "pipeline,pipelinerun,taskrun"
```

| Value | Effect |
|-------|--------|
| pipeline | Must use `taskRef` instead of `taskSpec` inside Pipeline CR |
| pipelinerun | Must use `pipelineRef` instead of `pipelineSpec` inside PipelineRun CR |
| taskrun | Must use `taskRef` instead of `taskSpec` inside TaskRun CR |

## RBAC And Trusted CA Flags

| Parameter | Description | Default |
|-----------|-------------|---------|
| createRbacResource | Controls RBAC resource creation only | true |
| createCABundleConfigMaps | Controls Trusted CA bundle and Service CA bundle config map creation | true |

```yaml
spec:
  profile: all
  targetNamespace: openshift-pipelines
  params:
    - name: createRbacResource
      value: "true"
    - name: createCABundleConfigMaps
      value: "true"
    - name: legacyPipelineRbac
      value: "true"
```

## Job-Based Pruner

Configure automatic pruning of stale TaskRun and PipelineRun resources:

```yaml
spec:
  pruner:
    resources:
      - taskrun
      - pipelinerun
    keep: 100
    prune-per-resource: false
    schedule: "* 8 * * *"
    startingDeadlineSeconds: 60
```

| Parameter | Description |
|-----------|-------------|
| schedule | Cron schedule (default: daily at 08:00) |
| resources | Resource types to prune: `taskrun` and/or `pipelinerun` |
| keep | Number of most recent resources to keep per type |
| prune-per-resource | If true, keep N per unique pipeline/task; if false, keep N total |
| keep-since | Max age in minutes (mutually exclusive with `keep`) |
| startingDeadlineSeconds | Max delay in seconds before a missed job is skipped |

Namespace annotations override cluster-wide settings:

- `operator.tekton.dev/prune.schedule`
- `operator.tekton.dev/prune.resources` (comma-separated: `"taskrun, pipelinerun"`)
- `operator.tekton.dev/prune.keep`
- `operator.tekton.dev/prune.prune-per-resource`
- `operator.tekton.dev/prune.keep-since`
- `operator.tekton.dev/prune.skip` (set to `true` to skip namespace)
- `operator.tekton.dev/prune.strategy` (set to `keep` or `keep-since`)

## Event-Driven Pruner

The event-based pruner deletes completed PipelineRun and TaskRun resources in
near real-time. The job-based pruner must be disabled first; both cannot run
simultaneously.

Enable:

```yaml
spec:
  pruner:
    disabled: true
  tektonpruner:
    disabled: false
    options: {}
```

The Operator deploys `tekton-pruner-controller` and `tekton-pruner-webhook`
pods in the `openshift-pipelines` namespace.

Required config maps in `openshift-pipelines`:

| Config map | Purpose |
|------------|---------|
| tekton-pruner-default-spec | Default pruning behavior |
| pruner-info | Internal runtime data |
| config-logging-tekton-pruner | Logging settings |
| config-observability-tekton-pruner | Observability features |

### Global Configuration

```yaml
spec:
  tektonpruner:
    disabled: false
    global-config:
      enforcedConfigLevel: global
      failedHistoryLimit: 5
      historyLimit: 10
      successfulHistoryLimit: 5
      ttlSecondsAfterFinished: 3600
    options: {}
```

| Parameter | Description |
|-----------|-------------|
| ttlSecondsAfterFinished | Delete resources N seconds after completion |
| successfulHistoryLimit | Retain N most recent successful runs |
| failedHistoryLimit | Retain N most recent failed runs |
| historyLimit | Generic history limit when status-specific limits are undefined |
| enforcedConfigLevel | Level at which pruner applies config: `global` or `namespace` |
| namespaces | Per-namespace pruning policies (when `enforcedConfigLevel: namespace`) |

TTL and history limits operate independently.

### Namespace-Level Configuration

Set `enforcedConfigLevel: namespace` and define per-namespace policies:

```yaml
spec:
  tektonpruner:
    disabled: false
    global-config:
      enforcedConfigLevel: namespace
      ttlSecondsAfterFinished: 300
      namespaces:
        dev-project:
          ttlSecondsAfterFinished: 60
        staging:
          ttlSecondsAfterFinished: 60
```

### Resource-Level Configuration

Create a `tekton-pruner-namespace-spec` ConfigMap in the target namespace with
required labels:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: tekton-pruner-namespace-spec
  namespace: user-specified-namespace
  labels:
    app.kubernetes.io/part-of: tekton-pruner
    pruner.tekton.dev/config-type: namespace
data:
  ns-config: |
    ttlSecondsAfterFinished: 300
    historyLimit: 5
```

Resource-level rules take precedence over global and namespace-level config.
The ConfigMap must use the exact name `tekton-pruner-namespace-spec` and both
labels to be processed.

### Resource-Level With Selectors

Apply pruning rules only when resources match specific labels and annotations:

```yaml
data:
  ns-config: |
    ttlSecondsAfterFinished: 3600
    pipelineRuns:
      - selector:
        - matchLabels:
            priority: high
          matchAnnotations:
            compliance: required
        ttlSecondsAfterFinished: 7776000
        successfulHistoryLimit: 100
        failedHistoryLimit: 100
```

### Recommended TTL Values

| Time period | Seconds | Use case |
|-------------|---------|----------|
| 5 minutes | 300 | Development and testing |
| 30 minutes | 1800 | Short-lived experiments |
| 1 hour | 3600 | CI pipelines |
| 6 hours | 21600 | Daily builds |
| 1 day | 86400 | Staging environments |
| 7 days | 604800 | Production, short retention |
| 30 days | 2592000 | Compliance, auditing |
| 90 days | 7776000 | Regulated industries |

### Recommended History Limits

| Environment | successfulHistoryLimit | failedHistoryLimit | Reason |
|-------------|----------------------|-------------------|--------|
| Development | 3-5 | 5-10 | Fast feedback, low storage |
| Staging | 5-10 | 10-20 | Balance retention and resources |
| Production | 10-50 | 20-100 | Audit trail and debugging |
| CI/CD | 3-5 | 10-20 | Recent context for failure analysis |

### Observability Metrics

The `tekton-pruner-controller` exposes OpenTelemetry-format metrics.

Common metric labels:

| Label | Description |
|-------|-------------|
| namespace | Kubernetes namespace of the PipelineRun or TaskRun |
| resource_type | Tekton resource type |
| status | Outcome of processing a resource |
| operation | Pruning method that deleted a resource |
| reason | Specific cause for skipping or error outcomes |

Resource processing metrics:

| Metric | Type | Description |
|--------|------|-------------|
| tekton_pruner_controller_resources_processed_total | Counter | Total resources processed |
| tekton_pruner_controller_resources_deleted_total | Counter | Total resources deleted |

Performance timing metrics (histogram, 0.1-30s buckets):

| Metric | Type | Description |
|--------|------|-------------|
| tekton_pruner_controller_reconciliation_duration_seconds | Histogram | Time in reconciliation |
| tekton_pruner_controller_ttl_processing_duration_seconds | Histogram | Time processing TTL |
| tekton_pruner_controller_history_processing_duration_seconds | Histogram | Time processing history limits |

State tracking metrics:

| Metric | Type | Description |
|--------|------|-------------|
| kn_workqueue_adds_total | Counter | Total resources queued |
| kn_workqueue_depth | Gauge | Current items in queue |

Error monitoring metrics:

| Metric | Type | Description |
|--------|------|-------------|
| tekton_pruner_controller_resources_errors_total | Counter | Total processing errors |

## Webhook Configuration

Configure failure policies, timeouts, and side effects for mutating and
validating webhooks. Settings are applied under
`spec.<component>.options.webhookConfigurationOptions`. Operator webhooks
cannot be configured. All settings are optional.

Pipelines controller example:

```yaml
spec:
  pipeline:
    options:
      webhookConfigurationOptions:
        validation.webhook.pipeline.tekton.dev:
          failurePolicy: Fail
          timeoutSeconds: 20
          sideEffects: None
        webhook.pipeline.tekton.dev:
          failurePolicy: Fail
          timeoutSeconds: 20
          sideEffects: None
```

Triggers controller example:

```yaml
spec:
  triggers:
    options:
      webhookConfigurationOptions:
        validation.webhook.triggers.tekton.dev:
          failurePolicy: Fail
          timeoutSeconds: 20
          sideEffects: None
        webhook.triggers.tekton.dev:
          failurePolicy: Fail
          timeoutSeconds: 20
          sideEffects: None
```

Pipelines as Code controller example:

```yaml
spec:
  pipelinesAsCode:
    options:
      webhookConfigurationOptions:
        validation.pipelinesascode.tekton.dev:
          failurePolicy: Fail
          timeoutSeconds: 20
          sideEffects: None
```

Tekton Hub controller example:

```yaml
spec:
  hub:
    options:
      webhookConfigurationOptions:
        validation.webhook.hub.tekton.dev:
          failurePolicy: Fail
          timeoutSeconds: 20
          sideEffects: None
        webhook.hub.tekton.dev:
          failurePolicy: Fail
          timeoutSeconds: 20
          sideEffects: None
```

List webhooks with:

```shell
oc get MutatingWebhookConfiguration
oc get ValidatingWebhookConfiguration
```
