---
name: ocp-pipelines-cicd
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "ocp"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when creating CI/CD solutions with OpenShift Pipelines: building
  applications, deploying with pipelines, using resolvers (cluster, hub,
  bundle, git, HTTP), creating pipeline templates, mirroring images for
  restricted environments, and building applications with the web console
  for OpenShift Pipelines 1.22. Do NOT use for pipeline concepts (use
  ocp-pipelines-about), installing pipelines (use
  ocp-pipelines-install-config), Pipelines as Code (use
  ocp-pipelines-as-code), or security (use ocp-pipelines-security).
---

# OCP Pipelines CI/CD

Use this skill to ground CI/CD pipeline creation guidance in the
official Red Hat OpenShift Pipelines 1.22 creating CI/CD pipelines guide
for the active baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority.

## Creating CI/CD Solutions

### Pipeline Workflow Overview

A full CI/CD pipeline requires:

1. Create custom tasks or install existing reusable tasks
2. Create and define the delivery pipeline
3. Specify storage (volumeClaimTemplate or existing PVC) attached to a workspace
4. Create a `PipelineRun` to instantiate and invoke the pipeline
5. Add triggers to capture events from the source repository

### Project Setup

The `pipeline` service account is automatically added by the Operator with
permissions to build and push images. Verify with:

```bash
oc get serviceaccount pipeline
```

### Pipeline Tasks

Install reusable tasks from Git repositories or catalogs. List tasks with:

```bash
tkn task list
```

### Assembling a Pipeline

Pipelines specify task interaction and execution order using `from` and
`runAfter` parameters, and `workspaces` for shared storage volumes.

Key fields: `apiVersion: tekton.dev/v1`, `kind: Pipeline`, `spec.tasks`,
`spec.workspaces`, `spec.params`, `spec.finally`.

Tasks reference cluster-scoped tasks using the cluster resolver:

```yaml
taskRef:
  resolver: cluster
  params:
    - name: kind
      value: task
    - name: name
      value: git-clone
    - name: namespace
      value: openshift-pipelines
```

### Running a Pipeline

Start a pipeline with `tkn pipeline start`, specifying workspace storage
and parameters. Use `volumeClaimTemplateFile` to create a PVC automatically.

```bash
tkn pipeline start build-and-deploy \
  -w name=shared-workspace,volumeClaimTemplateFile=pvc.yaml \
  -p deployment-name=my-app \
  -p git-url=https://github.com/org/repo.git \
  -p IMAGE='image-registry.openshift-image-registry.svc:5000/ns/app' \
  --use-param-defaults
```

### Triggers

Triggers capture external events (push, pull request) and create pipeline
resources. Components:

- **TriggerBinding** (`triggers.tekton.dev/v1`): extracts fields from event
  payload
- **TriggerTemplate** (`triggers.tekton.dev/v1`): creates resources from
  parameters
- **Trigger** (`triggers.tekton.dev/v1`): combines binding + template +
  interceptors
- **EventListener** (`triggers.tekton.dev/v1`): HTTP endpoint for JSON payloads

Secure EventListener connections use re-encrypt TLS termination routes.
Label the namespace for HTTPS: `operator.tekton.dev/enable-annotation=enabled`.

Multi-tenant event listeners use `namespaceSelector.matchNames` with
appropriate RBAC (ClusterRole, ClusterRoleBinding, service account
impersonation).

### GitHub Interceptor Capabilities

- Filter pull request events by changed files (`addChangedFiles: true` +
  CEL filter on `extensions.changed_files`)
- Validate pull requests against repository owners (`githubOwners: true`,
  `checkType: orgMembers | repoMembers | all`)
- Private repos require `personalAccessToken` secret reference

### Event Listener Monitoring

Create a `ServiceMonitor` (`monitoring.coreos.com/v1`) for event listeners
to gather metrics: `eventlistener_http_duration_seconds`,
`eventlistener_event_count`, `eventlistener_triggered_resources`.

## Web Console Pipelines

### Developer Perspective

- **Pipeline builder**: `+Add` -> `Pipeline` -> `Pipeline builder` to create
  customized pipelines with existing tasks via cluster resolver
- **From Git**: `+Add` -> `From Git` to create pipelines using pipeline
  templates alongside applications
- **Repository**: Add GitHub repositories containing `.tekton` directories for
  Pipelines as Code integration

Interactions: view pipeline details, metrics (success ratio, run count,
duration), YAML editing, pipeline run details, task run details, logs, events.

Start pipelines from Pipelines view, Pipeline Details page, or Topology view.

### Administrator Perspective

#### Pipeline Templates

Create pipeline templates in the `openshift` namespace with required labels:

```yaml
apiVersion: tekton.dev/v1
kind: Pipeline
metadata:
  namespace: openshift
  labels:
    pipeline.openshift.io/runtime: <runtime>
    pipeline.openshift.io/type: <pipeline_type>
```

Accepted runtimes: `nodejs`, `golang`, `dotnet`, `java`, `php`, `ruby`,
`perl`, `python`, `nginx`, `httpd`.

Accepted types: `openshift`, `knative`, `kubernetes`.

#### Pipeline Execution Statistics

Requires Tekton Results and the OpenShift Pipelines console plugin (OCP 4.15+).
View consolidated statistics in `Pipelines` -> `Overview` or per-pipeline
metrics in the `Metrics` tab.

## Resolvers

Resolvers retrieve pipeline, task, or `StepAction` definitions from remote
sources at run time. Available resolvers:

### Hub Resolver

Retrieves from Artifact Hub or Tekton Hub catalogs. Configured via
`pipeline.hub-resolver-config` in `TektonConfig`. Public Tekton Hub is
deprecated; use Artifact Hub.

```yaml
resolver: hub
params:
  - name: catalog
    value: tekton-catalog-tasks
  - name: type
    value: artifact
  - name: kind
    value: task
  - name: name
    value: golang-build
  - name: version
    value: "0.5.0"
```

### Bundles Resolver

Retrieves from OCI images (Tekton bundles). Configured via
`pipeline.bundles-resolver-config`.

```yaml
resolver: bundles
params:
  - name: bundle
    value: registry.example.com:5000/simple/pipeline:latest
  - name: name
    value: hello-pipeline
  - name: kind
    value: pipeline
```

### Git Resolver (Anonymous)

Retrieves via anonymous Git clone. Configured via
`pipeline.git-resolver-config`.

```yaml
resolver: git
params:
  - name: url
    value: https://github.com/tektoncd/catalog.git
  - name: revision
    value: main
  - name: pathInRepo
    value: task/git-clone/0.6/git-clone.yaml
```

### Git Resolver (Authenticated SCM API)

Uses authenticated API with supported providers: GitHub, GitLab, Gitea,
Bitbucket. Requires `scm-type`, `api-token-secret-name`, and
`api-token-secret-key` in `TektonConfig`. Supports multiple Git provider
configurations via prefixed keys (e.g., `test1.scm-type`).

```yaml
resolver: git
params:
  - name: org
    value: tektoncd
  - name: repo
    value: catalog
  - name: revision
    value: main
  - name: pathInRepo
    value: task/git-clone/0.6/git-clone.yaml
```

Do not mix `url` (anonymous) and `repo` (authenticated) parameters.

### HTTP Resolver

Retrieves from HTTP/HTTPS URLs. Configured via
`pipeline.http-resolver-config`.

```yaml
resolver: http
params:
  - name: url
    value: https://raw.githubusercontent.com/org/repo/main/task.yaml
```

### Cluster Resolver

Retrieves resources already created on the same cluster in a specific
namespace. Standard tasks are in `openshift-pipelines` namespace.

```yaml
resolver: cluster
params:
  - name: kind
    value: task
  - name: name
    value: git-clone
  - name: namespace
    value: openshift-pipelines
```

## Mirroring Images for Restricted Environments

For disconnected clusters, mirror builder images:

1. Mirror images: `oc image mirror <source> <mirror_registry>:<port>/<path>`
2. Import and tag: `oc tag <mirror>/<path> <imagestream>:latest --scheduled -n openshift`
3. Verify: `oc describe imagestream <name> -n openshift`

The `--scheduled` flag enables automatic periodic re-import.

## Workflow

1. Confirm the active OpenShift baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Identify the relevant CI/CD topic (pipeline creation, triggers, resolvers,
   templates, web console, restricted environments).
4. For GitOps manifests, verify all API versions and fields against the
   extraction before committing.
5. For live operations, use the repo environment guard.
6. Validate with `references/source-capture.md` boundaries.

## Related Skills

- Use `ocp-pipelines-about` for pipeline concepts and architecture.
- Use `ocp-pipelines-install-config` for installation and configuration.
- Use `ocp-pipelines-as-code` for Pipelines as Code workflows.
- Use `ocp-pipelines-security` for pipeline security concerns.
- Use `ocp-pipelines-observability` for pipeline monitoring.
- Use `ocp-cicd-builds` for OpenShift Builds (BuildConfig, Shipwright).

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
