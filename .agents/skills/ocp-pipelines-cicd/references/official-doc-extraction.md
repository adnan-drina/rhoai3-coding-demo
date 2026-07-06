# Official Doc Extraction

Extracted from: Red Hat OpenShift Pipelines 1.22 — Creating CI/CD pipelines

## Chapter 1: Creating CI/CD Solutions for Applications

### Pipeline Service Account

The Red Hat OpenShift Pipelines Operator automatically creates a `pipeline`
service account with permissions to build and push images. `PipelineRun`
objects use this service account.

```bash
oc get serviceaccount pipeline
```

### Pipeline Tasks

Install reusable tasks from Git repositories or catalogs:

```bash
oc create -f https://raw.githubusercontent.com/openshift/pipelines-tutorial/pipelines-1.22/01_pipeline/01_apply_manifest_task.yaml
oc create -f https://raw.githubusercontent.com/openshift/pipelines-tutorial/pipelines-1.22/01_pipeline/02_update_deployment_task.yaml
```

Verify: `tkn task list`

### Assembling a Pipeline

Pipeline definition example (`tekton.dev/v1`):

```yaml
apiVersion: tekton.dev/v1
kind: Pipeline
metadata:
  name: build-and-deploy
spec:
  workspaces:
    - name: shared-workspace
  params:
    - name: deployment-name
      type: string
    - name: git-url
      type: string
    - name: git-revision
      type: string
      default: "pipelines-1.22"
    - name: IMAGE
      type: string
  tasks:
    - name: fetch-repository
      taskRef:
        resolver: cluster
        params:
          - name: kind
            value: task
          - name: name
            value: git-clone
          - name: namespace
            value: openshift-pipelines
      workspaces:
        - name: output
          workspace: shared-workspace
      params:
        - name: URL
          value: $(params.git-url)
        - name: REVISION
          value: $(params.git-revision)
    - name: build-image
      taskRef:
        resolver: cluster
        params:
          - name: kind
            value: task
          - name: name
            value: buildah
          - name: namespace
            value: openshift-pipelines
      workspaces:
        - name: source
          workspace: shared-workspace
      params:
        - name: IMAGE
          value: $(params.IMAGE)
      runAfter:
        - fetch-repository
    - name: apply-manifests
      taskRef:
        name: apply-manifests
      workspaces:
        - name: source
          workspace: shared-workspace
      runAfter:
        - build-image
    - name: update-deployment
      taskRef:
        name: update-deployment
      params:
        - name: deployment
          value: $(params.deployment-name)
        - name: IMAGE
          value: $(params.IMAGE)
      runAfter:
        - apply-manifests
```

Create: `oc create -f <pipeline.yaml>` or from Git URL.
Verify: `tkn pipeline list`

### Running a Pipeline

```bash
tkn pipeline start build-and-deploy \
  -w name=shared-workspace,volumeClaimTemplateFile=pvc.yaml \
  -p deployment-name=pipelines-vote-api \
  -p git-url=https://github.com/openshift/pipelines-vote-api.git \
  -p IMAGE='image-registry.openshift-image-registry.svc:5000/pipelines-tutorial/pipelines-vote-api' \
  --use-param-defaults
```

- `volumeClaimTemplateFile` creates a PVC automatically for pipeline execution
- Track progress: `tkn pipelinerun logs <pipelinerun_id> -f`
- List runs: `tkn pipelinerun list`
- Rerun last: `tkn pipeline start build-and-deploy --last`

### Mirroring Images for Restricted Environments

For disconnected clusters or restricted environments:

1. Mirror the builder image:
   ```bash
   oc image mirror registry.redhat.io/ubi9/python-39:latest <mirror_registry>:<port>/ubi9/python-39
   ```

2. Import and tag with scheduled re-import:
   ```bash
   oc tag <mirror_registry>:<port>/ubi9/python-39 python:latest --scheduled -n openshift
   ```

3. Verify import:
   ```bash
   oc describe imagestream python -n openshift
   ```

Repeat for each required builder image (Python, Go, CLI).

### Adding Triggers

#### TriggerBinding

```yaml
apiVersion: triggers.tekton.dev/v1
kind: TriggerBinding
metadata:
  name: vote-app
spec:
  params:
    - name: git-repo-url
      value: $(body.repository.url)
    - name: git-repo-name
      value: $(body.repository.name)
    - name: git-revision
      value: $(body.head_commit.id)
```

#### TriggerTemplate

```yaml
apiVersion: triggers.tekton.dev/v1
kind: TriggerTemplate
metadata:
  name: vote-app
spec:
  params:
    - name: git-repo-url
    - name: git-revision
      default: pipelines-1.22
    - name: git-repo-name
  resourcetemplates:
    - apiVersion: tekton.dev/v1
      kind: PipelineRun
      metadata:
        generateName: build-deploy-$(tt.params.git-repo-name)-
      spec:
        taskRunTemplate:
          serviceAccountName: pipeline
        pipelineRef:
          name: build-and-deploy
        params:
          - name: deployment-name
            value: $(tt.params.git-repo-name)
          - name: git-url
            value: $(tt.params.git-repo-url)
          - name: git-revision
            value: $(tt.params.git-revision)
          - name: IMAGE
            value: image-registry.openshift-image-registry.svc:5000/pipelines-tutorial/$(tt.params.git-repo-name)
        workspaces:
          - name: shared-workspace
            volumeClaimTemplate:
              spec:
                accessModes:
                  - ReadWriteOnce
                resources:
                  requests:
                    storage: 500Mi
```

#### Trigger

```yaml
apiVersion: triggers.tekton.dev/v1
kind: Trigger
metadata:
  name: vote-trigger
spec:
  serviceAccountName: pipeline
  bindings:
    - ref: vote-app
  template:
    ref: vote-app
```

#### EventListener

```yaml
apiVersion: triggers.tekton.dev/v1
kind: EventListener
metadata:
  name: vote-app
spec:
  serviceAccountName: pipeline
  triggers:
    - triggerRef: vote-trigger
```

For HTTPS: label namespace with `operator.tekton.dev/enable-annotation=enabled`
and create re-encrypt TLS route.

For HTTP: `oc expose svc el-vote-app`

### Multi-Tenant Event Listeners

Configure with `namespaceSelector.matchNames`, ClusterRole with trigger
resource permissions plus `serviceaccounts` impersonation, and
ClusterRoleBinding.

### GitHub Interceptor: Filter by Changed Files

```yaml
interceptors:
  - ref:
      name: "github"
      kind: ClusterInterceptor
      apiVersion: triggers.tekton.dev
    params:
      - name: "eventTypes"
        value: ["pull_request", "push"]
      - name: "addChangedFiles"
        value:
          enabled: true
  - ref:
      name: cel
    params:
      - name: filter
        value: extensions.changed_files.matches('controllers/')
```

Private repos add `personalAccessToken` secret reference.

### GitHub Interceptor: Validate Owners

```yaml
interceptors:
  - ref:
      name: "github"
      kind: ClusterInterceptor
      apiVersion: triggers.tekton.dev
    params:
      - name: "eventTypes"
        value: ["pull_request", "issue_comment"]
      - name: "githubOwners"
        value:
          enabled: true
          checkType: none
```

`checkType` values: `orgMembers`, `repoMembers`, `all`.

### Event Listener Monitoring

ServiceMonitor for event listener metrics:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  labels:
    app.kubernetes.io/managed-by: EventListener
    app.kubernetes.io/part-of: Triggers
    eventlistener: github-listener
  name: el-monitor
  namespace: test
spec:
  endpoints:
    - interval: 10s
      port: http-metrics
  namespaceSelector:
    matchNames:
      - test
  selector:
    matchLabels:
      app.kubernetes.io/managed-by: EventListener
      app.kubernetes.io/part-of: Triggers
      eventlistener: github-listener
```

Metrics: `eventlistener_http_duration_seconds`,
`eventlistener_event_count`, `eventlistener_triggered_resources`.

## Chapter 2: Working with Pipelines in the Web Console

### Developer Perspective

- **Pipeline builder** (`+Add` -> `Pipeline` -> `Pipeline builder`): create
  pipelines with tasks from cluster resolver and Tekton Hub
- **From Git** (`+Add` -> `From Git`): create pipelines with templates
  alongside applications
- **Repository** (`Create` -> `Repository`): add GitHub repositories with
  `.tekton` directories for Pipelines as Code

Pipeline interactions in Developer perspective:

- View pipeline details, metrics, YAML, and pipeline runs
- Start pipelines from Pipelines view, Pipeline Details, or Topology view
- View task run details, logs, and events
- Edit and delete pipelines
- Debug failed runs via Log Snippets

### Administrator Perspective — Pipeline Templates

Templates must be in the `openshift` namespace with required labels:

```yaml
apiVersion: tekton.dev/v1
kind: Pipeline
metadata:
  namespace: openshift
  labels:
    pipeline.openshift.io/runtime: <runtime>
    pipeline.openshift.io/type: <pipeline_type>
```

- Accepted `runtime` values: `nodejs`, `golang`, `dotnet`, `java`, `php`,
  `ruby`, `perl`, `python`, `nginx`, `httpd`
- Accepted `type` values: `openshift`, `knative`, `kubernetes`

### Pipeline Execution Statistics

Requires Tekton Results + OpenShift Pipelines console plugin (OCP 4.15+).

Enable via: `Operators` -> `Installed Operators` -> `Red Hat OpenShift
Pipelines` -> `Console plugin` -> `Enable`.

View consolidated statistics: `Pipelines` -> `Overview`.
Per-pipeline metrics: pipeline details -> `Metrics` tab.

Statistics include: pipeline run count/status graphs, total/average/maximum
duration, success rate.

## Chapter 3: Resolvers

### Hub Resolver

Configuration in `TektonConfig`:

```yaml
spec:
  pipeline:
    hub-resolver-config:
      default-tekton-hub-catalog: Tekton
      default-artifact-hub-task-catalog: tekton-catalog-tasks
      default-artifact-hub-pipeline-catalog: tekton-catalog-pipelines
      default-kind: pipeline
      default-type: artifact
```

Public Tekton Hub (`hub.tekton.dev`) is deprecated. Use Artifact Hub.

Parameters: `catalog`, `type` (`artifact` | `tekton`), `kind`
(`task` | `pipeline`), `name`, `version`.

If `default-type` is `tekton`, you must configure your own Tekton Hub
instance via `tekton-hub-api`.

### Bundles Resolver

Configuration:

```yaml
spec:
  pipeline:
    bundles-resolver-config:
      default-service-account: pipelines
      default-kind: task
```

Parameters: `serviceAccount`, `bundle` (OCI image URL), `name`, `kind`.

### Git Resolver — Anonymous Cloning

Configuration:

```yaml
spec:
  pipeline:
    git-resolver-config:
      default-revision: main
      fetch-timeout: 1m
      default-url: https://github.com/tektoncd/catalog.git
```

Parameters: `url`, `revision`, `pathInRepo`.

Global maximum timeout: 1 minute on all resolution requests.

### Git Resolver — Authenticated SCM API

Configuration:

```yaml
spec:
  pipeline:
    git-resolver-config:
      scm-type: github
      server-url: api.internal-github.com
      api-token-secret-name: github-auth-secret
      api-token-secret-key: github-auth-key
      api-token-secret-namespace: github-auth-namespace
      default-org: tektoncd
```

Required fields: `scm-type`, `api-token-secret-name`, `api-token-secret-key`.

Supported providers: GitHub/GitHub Enterprise, GitLab/self-hosted GitLab,
Gitea, Bitbucket Data Center, Bitbucket Cloud.

Parameters: `org`, `repo`, `revision`, `pathInRepo`.

Do not use `url` and `repo` together.

#### Multiple Git Providers

Use prefixed keys (e.g., `test1.scm-type`, `test2.scm-type`) in
`git-resolver-config`. Reference with `configKey` parameter in `taskRef`
or `pipelineRef`. Values with `.` in `configKey` are not supported.

#### Override Resolver Configuration

Override per-run using inline parameters: `token`, `tokenKey`, `scmType`,
`serverURL`.

### HTTP Resolver

Configuration:

```yaml
spec:
  pipeline:
    http-resolver-config:
      fetch-timeout: "1m"
```

Parameter: `url` (fully qualified HTTP/HTTPS URL to YAML file).

### Cluster Resolver

Configuration:

```yaml
spec:
  pipeline:
    cluster-resolver-config:
      default-kind: task
      default-namespace: openshift-pipelines
```

Parameters: `kind` (`task` | `pipeline`), `name`, `namespace`.

Standard tasks installed by the Operator are in `openshift-pipelines`
namespace.
