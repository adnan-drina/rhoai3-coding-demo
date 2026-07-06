---
name: ocp-pipelines-about
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "ocp"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when documenting, reviewing, or explaining OpenShift Pipelines concepts,
  architecture, and Tekton CRDs: Task, TaskRun, Pipeline, PipelineRun,
  Workspace, StepAction, Trigger, TriggerBinding, TriggerTemplate,
  EventListener, when expressions, finally tasks, and pod templates from the
  official OpenShift Pipelines 1.22 documentation. Do NOT use for installing or
  configuring pipelines (use ocp-pipelines-install-config), creating CI/CD
  pipelines (use ocp-pipelines-cicd), Pipelines as Code (use
  ocp-pipelines-as-code), security (use ocp-pipelines-security), or
  observability (use ocp-pipelines-observability).
---

# OCP Pipelines About

Use this skill to ground OpenShift Pipelines conceptual guidance in the
official Red Hat OpenShift Pipelines 1.22 about guide for the active
baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority.

## Pipelines Concepts

### Tasks

A `Task` resource defines a set of sequentially executed steps. Each task runs
as a pod; each step runs as a container within that pod. Steps share the same
volumes for caching files, config maps, and secrets. Tasks are reusable across
many pipelines and can run individually or as part of a pipeline.

Key fields: `apiVersion: tekton.dev/v1`, `kind: Task`, `spec.steps`,
`spec.workspaces`, `spec.params`.

### Steps

Steps are the sequential commands within a task. Each step specifies a container
image and commands to execute. Since OpenShift Pipelines 1.6, steps no longer
default `HOME` to `/tekton/home` or `workingDir` to `/workspace`.

### When Expressions

When expressions guard task execution. Components:

- `input`: static inputs or variables (parameter, task result, execution status)
- `operator`: `in` or `notin`
- `values`: array of string values (static values, parameters, results, workspace bound state)

Evaluation: `True` runs the task; `False` skips it. When expressions also work
in `finally` tasks.

### Finally Tasks

Tasks specified in the `finally` field always execute after all pipeline tasks
complete, regardless of success or failure. Finally tasks run in parallel with
each other. They can consume results from earlier tasks and use when expressions
for conditional execution.

### TaskRun

A `TaskRun` instantiates a task for execution with specific inputs, outputs, and
execution parameters. It runs steps in order until all succeed or a failure
occurs. A `PipelineRun` automatically creates a `TaskRun` for each task.

Key fields: `apiVersion: tekton.dev/v1`, `kind: TaskRun`, `spec.taskRef`,
`spec.workspaces`, `spec.podTemplate`.

### Pipelines

A `Pipeline` arranges a collection of tasks in a specific execution order. Each
pipeline definition must contain at least one task. Pipelines can include
workspaces, parameters, and conditions.

Key fields: `apiVersion: tekton.dev/v1`, `kind: Pipeline`, `spec.tasks`,
`spec.workspaces`, `spec.params`, `spec.finally`.

Task ordering uses `runAfter` to define sequential dependencies. Tasks without
`runAfter` constraints run in parallel.

### PipelineRun

A `PipelineRun` binds a pipeline to workspaces, credentials, and parameter
values for execution. It creates a `TaskRun` for each task. The `status` field
tracks progress for monitoring and auditing.

Key fields: `apiVersion: tekton.dev/v1`, `kind: PipelineRun`, `spec.pipelineRef`,
`spec.params`, `spec.workspaces`, `spec.taskRunTemplate`.

### Pod Templates

Define a pod template in `PipelineRun` or `TaskRun` to configure every pod
created during execution. Any `Pod` spec parameter is available.

- PipelineRun: `spec.taskRunTemplate.podTemplate`
- TaskRun: `spec.podTemplate`

Common use: security context (`runAsNonRoot`, `runAsUser`), scheduler name.

### Workspaces

Workspaces declare shared storage volumes needed at runtime. They separate
volume declaration from runtime storage, making tasks reusable.

Workspace capabilities:
- Store task inputs and outputs
- Share data among tasks
- Mount credentials (secrets), configurations (config maps), and tools
- Cache build artifacts

Backing storage options:
- Read-only ConfigMap or Secret
- Existing PersistentVolumeClaim
- PVC from volumeClaimTemplate
- `emptyDir` (discarded after task run)

### StepActions

A `StepAction` CR defines a reusable action that a step performs. Steps
reference `StepAction` objects via `ref`. StepActions can be resolved from
external sources using resolvers.

Key fields: `apiVersion: tekton.dev/v1`, `kind: StepAction`, `spec.params`,
`spec.results`, `spec.image`, `spec.script`, `spec.env`.

Security: parameter values must NOT appear directly in `script`. Use `env:` to
pass parameter values to the script as environment variables.

### Triggers

Triggers capture external events and process them to create pipeline resources.

Components:
- **TriggerBinding**: extracts fields from event payload as parameters
- **TriggerTemplate**: creates resources (e.g., PipelineRun) from parameters
- **Trigger**: combines TriggerBinding + TriggerTemplate + optional interceptors
- **EventListener**: HTTP endpoint that receives JSON payloads and dispatches to triggers

Interceptor types: Webhook, GitHub, GitLab, Bitbucket, CEL.

All trigger resources use `apiVersion: triggers.tekton.dev/v1`.

## Key Features

- Serverless CI/CD running pipelines in isolated containers
- Designed for decentralized teams and microservice architectures
- Standard CI/CD definitions extensible and integrable with Kubernetes tools
- Image building with S2I, Buildah, Buildpacks, and Kaniko
- OpenShift Developer console integration for Tekton resource management

## Workflow

1. Confirm the active OpenShift baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Identify the relevant concept (Task, Pipeline, Trigger, etc.).
4. For GitOps manifests, verify all API versions and fields against the
   extraction before committing.
5. For live operations, use the repo environment guard.
6. Validate with `references/source-capture.md` boundaries.

## Related Skills

- Use `ocp-pipelines-install-config` for installation and configuration.
- Use `ocp-pipelines-cicd` for creating CI/CD solutions with pipelines.
- Use `ocp-pipelines-as-code` for Pipelines as Code workflows.
- Use `ocp-pipelines-security` for pipeline security concerns.
- Use `ocp-pipelines-observability` for pipeline monitoring.
- Use `ocp-cicd-builds` for OpenShift Builds (BuildConfig, Shipwright).

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
