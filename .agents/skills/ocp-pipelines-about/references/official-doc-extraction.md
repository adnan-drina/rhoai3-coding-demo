# Official Doc Extraction

Use this extraction to keep OpenShift Pipelines conceptual content grounded in
official Red Hat sources. When implementation needs exact CR fields, verify the
active cluster schema with `oc explain` or `oc get crd` before authoring GitOps
manifests.

## Product Overview

Red Hat OpenShift Pipelines is a cloud-native CI/CD solution based on
Kubernetes resources. It uses Tekton building blocks to automate deployments
across many platforms. Tekton introduces standard CRDs for defining CI/CD
pipelines portable across Kubernetes distributions.

OpenShift Pipelines releases on a different cadence than OpenShift Container
Platform.

## Key Features

- Serverless CI/CD system running pipelines with all dependencies in isolated
  containers
- Designed for decentralized teams working on microservice-based architecture
- Standard CI/CD pipeline definitions easy to extend and integrate with existing
  Kubernetes tools, enabling on-demand scaling
- Image building with S2I, Buildah, Buildpacks, and Kaniko, portable across any
  Kubernetes platform
- OpenShift Developer console integration for creating Tekton resources, viewing
  logs, and managing pipelines

## Task CRD

```yaml
apiVersion: tekton.dev/v1
kind: Task
metadata:
  name: apply-manifests
spec:
  workspaces:
  - name: source
  params:
    - name: manifest_dir
      description: The directory in source that contains yaml manifests
      type: string
      default: "k8s"
  steps:
    - name: apply
      image: image-registry.openshift-image-registry.svc:5000/openshift/cli:latest
      workingDir: /workspace/source
      command: ["/bin/bash", "-c"]
      args:
        - |-
          echo Applying manifests in $(params.manifest_dir) directory
          oc apply -f $(params.manifest_dir)
          echo -----------------------------------
```

Behavior:
- Each task runs as a pod; each step runs as a container within that pod
- Steps share volumes for caching files, config maps, and secrets
- Tasks are reusable across many pipelines
- Since OpenShift Pipelines 1.6, `HOME` no longer defaults to `/tekton/home`
  and `workingDir` no longer defaults to `/workspace`

## When Expressions

Components:
- `input`: static inputs or variables (parameter, task result, execution status)
- `operator`: `in` or `notin`
- `values`: non-empty array of string values (static values, parameters,
  results, workspace bound state)

Evaluation rules:
- `True` → task runs
- `False` → task is skipped
- Can guard tasks in `finally` section

```yaml
when:
  - input: "$(params.path)"
    operator: in
    values: ["README.md"]
```

```yaml
when:
  - input: "$(tasks.check-file.results.exists)"
    operator: in
    values: ["yes"]
```

```yaml
when:
  - input: "$(tasks.echo-file-exists.status)"
    operator: in
    values: ["Succeeded"]
  - input: "$(tasks.status)"
    operator: in
    values: ["Succeeded"]
```

## Finally Tasks

```yaml
spec:
  tasks:
    - name: clone-app-repo
      taskRef:
        name: git-clone-from-catalog
      ...
  finally:
    - name: cleanup
      taskRef:
        name: cleanup-workspace
      workspaces:
        - name: source
          workspace: git-source
    - name: check-git-commit
      params:
        - name: commit
          value: $(tasks.clone-app-repo.results.commit)
      taskSpec:
        ...
```

Behavior:
- Execute after all pipeline tasks complete, regardless of success/failure
- Run in parallel with each other
- Can consume results from any task in the same pipeline
- Can use when expressions for conditional execution

## TaskRun CRD

```yaml
apiVersion: tekton.dev/v1
kind: TaskRun
metadata:
  name: apply-manifests-taskrun
spec:
  taskRunTemplate:
    serviceAccountName: pipeline
  taskRef:
    kind: Task
    name: apply-manifests
  workspaces:
  - name: source
    persistentVolumeClaim:
      claimName: source-pvc
```

Behavior:
- Instantiates a task for execution with specific inputs, outputs, and
  execution parameters
- Runs steps in order until all succeed or a failure occurs
- Automatically created by PipelineRun for each task in a pipeline

## Pipeline CRD

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
    description: name of the deployment to be patched
  - name: git-url
    type: string
    description: url of the git repo for the code of deployment
  - name: git-revision
    type: string
    description: revision to be used from repo of the code for deployment
    default: "pipelines-1.22"
  - name: IMAGE
    type: string
    description: image to be built from the code
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
    runAfter:
    - fetch-repository
  - name: apply-manifests
    taskRef:
      name: apply-manifests
    runAfter:
    - build-image
```

Behavior:
- Arranges tasks in specific execution order
- `runAfter` defines sequential dependencies
- Tasks without `runAfter` can run in parallel
- Must contain at least one task
- The OpenShift Pipelines Operator installs Buildah task in `openshift-pipelines`
  namespace and creates `pipeline` service account

## PipelineRun CRD

```yaml
apiVersion: tekton.dev/v1
kind: PipelineRun
metadata:
  name: build-deploy-api-pipelinerun
spec:
  pipelineRef:
    name: build-and-deploy
  params:
  - name: deployment-name
    value: vote-api
  - name: git-url
    value: https://github.com/openshift-pipelines/vote-api.git
  - name: IMAGE
    value: image-registry.openshift-image-registry.svc:5000/pipelines-tutorial/vote-api
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

Behavior:
- Binds a pipeline to workspaces, credentials, and parameter values
- Creates a TaskRun for each task in the pipeline
- Executes tasks sequentially until complete or a task fails
- `status` field tracks progress for monitoring and auditing

## Pod Templates

### PipelineRun Pod Template

```yaml
apiVersion: tekton.dev/v1
kind: PipelineRun
metadata:
  name: mypipelinerun
spec:
  pipelineRef:
    name: mypipeline
  taskRunTemplate:
    podTemplate:
      securityContext:
        runAsNonRoot: true
        runAsUser: 1001
```

Location: `spec.taskRunTemplate.podTemplate` (v1 API). The older `v1beta1`
format placed `podTemplate` directly under `spec:` — this is not supported in
v1.

### TaskRun Pod Template

```yaml
apiVersion: tekton.dev/v1
kind: TaskRun
metadata:
  name: mytaskrun
  namespace: default
spec:
  taskRef:
    name: mytask
  podTemplate:
    schedulerName: volcano
    securityContext:
      runAsNonRoot: true
      runAsUser: 1001
```

Location: `spec.podTemplate`.

## Workspaces

Workspaces declare shared storage volumes needed at runtime without specifying
the actual location. The separation of declaration from runtime storage makes
tasks reusable and environment-independent.

Capabilities:
- Store task inputs and outputs
- Share data among tasks
- Mount credentials held in secrets
- Mount configurations held in config maps
- Mount common tools shared by an organization
- Cache build artifacts

Backing storage options for TaskRun or PipelineRun:
- Read-only ConfigMap or Secret
- Existing PersistentVolumeClaim shared with other tasks
- PVC from volumeClaimTemplate
- `emptyDir` (discarded when task run completes)

Pipeline workspace declaration:

```yaml
spec:
  workspaces:
  - name: shared-workspace
```

Task workspace binding:

```yaml
tasks:
- name: build-image
  workspaces:
  - name: source
    workspace: shared-workspace
```

PipelineRun workspace provisioning:

```yaml
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

Recommendation: use at most one writable workspace per task.

## StepAction CRD

```yaml
apiVersion: tekton.dev/v1
kind: StepAction
metadata:
  name: apply-manifests-action
spec:
  params:
  - name: working_dir
    description: The working directory where the source is located
    type: string
    default: "/workspace/source"
  - name: manifest_dir
    description: The directory in source that contains yaml manifests
    default: "k8s"
  results:
  - name: output
    description: The output of the oc apply command
  image: image-registry.openshift-image-registry.svc:5000/openshift/cli:latest
  env:
  - name: MANIFEST_DIR
    value: $(params.manifest_dir)
  workingDir: $(params.working_dir)
  script: |
      #!/usr/bin/env bash
      oc apply -f "$MANIFEST_DIR" | tee $(results.output)
```

Behavior:
- Defines a reusable action that a step performs
- Referenced from a step via `ref`
- Can be resolved from external sources using resolvers
- Does not include workspace definitions (relies on task to provide mounts)
- Parameters and results are defined on the StepAction; results become step results
- **Security**: parameter values must NOT appear directly in `script`; use `env:`
  section to pass parameter values as environment variables

Task referencing a StepAction:

```yaml
steps:
- name: apply
  ref:
    name: apply-manifests-action
  params:
  - name: working_dir
    value: "/workspace/source"
  - name: manifest_dir
    value: $(params.manifest_dir)
- name: display_result
  script: 'echo $(step.apply.results.output)'
```

## Trigger Components

### TriggerBinding

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

Purpose: extracts fields from event payload and stores them as parameters.
Uses JSONPath-like expressions (`$(body.field.path)`) to extract values.

### TriggerTemplate

```yaml
apiVersion: triggers.tekton.dev/v1
kind: TriggerTemplate
metadata:
  name: vote-app
spec:
  params:
  - name: git-repo-url
    description: The git repository url
  - name: git-revision
    description: The git revision
    default: pipelines-1.22
  - name: git-repo-name
    description: The name of the deployment to be created / patched
  resourcetemplates:
  - apiVersion: tekton.dev/v1
    kind: PipelineRun
    metadata:
      name: build-deploy-$(tt.params.git-repo-name)-$(uid)
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

Purpose: creates resources from parameterized data. Uses `$(tt.params.name)`
syntax and `$(uid)` for unique naming. The `resourcetemplates` field lists
Kubernetes resources to create.

### Trigger

```yaml
apiVersion: triggers.tekton.dev/v1
kind: Trigger
metadata:
  name: vote-trigger
spec:
  taskRunTemplate:
    serviceAccountName: pipeline
  interceptors:
    - ref:
        name: "github"
      params:
        - name: "secretRef"
          value:
            secretName: github-secret
            secretKey: secretToken
        - name: "eventTypes"
          value: ["push"]
  bindings:
    - ref: vote-app
  template:
    ref: vote-app
```

Purpose: combines TriggerBinding + TriggerTemplate + optional interceptors.
Interceptors process events before TriggerBinding, performing payload filtering,
event verification, trigger condition testing, and payload modification.

### EventListener

```yaml
apiVersion: triggers.tekton.dev/v1
kind: EventListener
metadata:
  name: vote-app
spec:
  taskRunTemplate:
    serviceAccountName: pipeline
  triggers:
    - triggerRef: vote-trigger
```

Purpose: provides an HTTP endpoint (event sink) that listens for incoming
HTTP-based events with JSON payloads. Dispatches events to referenced triggers.

### Interceptor Types

- Webhook Interceptors
- GitHub Interceptors
- GitLab Interceptors
- Bitbucket Interceptors
- Common Expression Language (CEL) Interceptors

Interceptors use secrets for event verification. They run before TriggerBinding
and can modify the payload before it reaches the trigger.

## Cluster Resolver

Tasks and StepActions can be referenced using resolvers. The cluster resolver
references resources by kind, name, and namespace:

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
