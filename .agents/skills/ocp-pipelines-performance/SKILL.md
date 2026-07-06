---
name: ocp-pipelines-performance
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "ocp"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when managing OpenShift Pipelines performance, resource consumption,
  compute resource quotas, pod eviction protection, step-level resource
  overrides, priority class resource quotas, LimitRange configuration, and
  multicluster pipeline support (hub-spoke architecture, Kueue, MultiKueue,
  spoke cluster setup) for OpenShift Pipelines 1.22. Do NOT use for installing
  or configuring the operator (use ocp-pipelines-install-config), creating
  CI/CD pipelines (use ocp-pipelines-cicd), Pipelines as Code (use
  ocp-pipelines-as-code), or pipeline concepts (use ocp-pipelines-about).
---

# OCP Pipelines Performance

Use this skill to ground OpenShift Pipelines performance and resource
management guidance in the official Red Hat OpenShift Pipelines 1.22
managing performance and resource use guide for the active baseline in
`docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority.

## Performance Management

OpenShift Pipelines can degrade under high concurrency. Red Hat benchmarks show
up to 60 simple pipelines running concurrently on a 3-node AWS m6a.2xlarge
cluster without significant failures or delays. Beyond that threshold, failed
runs, average duration, pod creation latency, work queue depth, and pending
pods all increase.

Improving performance:

- Monitor node resource usage and scale out when high.
- Enable high-availability mode via `TektonConfig` CR:
  - `pipeline.performance.disable-ha: false`
  - `pipeline.performance.buckets`: 5–10
  - `pipeline.performance.replicas`: >2 and <= buckets value

Read `references/official-doc-extraction.md` for exact settings and benchmark
context.

## Resource Consumption

Each task runs as a pod; each step runs as a container within that pod. Step
resource requests default to BestEffort (zero) or to the project LimitRange
minimums if set. When a LimitRange defines container minimums, OpenShift
Pipelines uses those minimums instead of zero.

Pipelines request the maximum CPU, memory, and ephemeral storage of any single
step for the pod, setting all other step requests to zero. This keeps one-step-
at-a-time execution efficient but can over-allocate when LimitRange minimums
apply across many steps.

Mitigation strategies:

- Consolidate steps in a single task using script blocks and a shared image.
- Distribute independent steps across multiple tasks so pods are smaller.

Step-level compute resource overrides in a `PipelineRun` allow adjusting CPU
and memory for specific steps in referenced tasks without modifying the original
Task definition, via `spec.taskRunSpecs[*].stepSpecs`.

Read `references/official-doc-extraction.md` for LimitRange interaction
examples and step override YAML.

## Resource Quotas

`ResourceQuota` objects control total resource consumption per namespace.
OpenShift Pipelines does not support per-pipeline resource quotas directly.
Alternative approaches:

- Set requests/limits on each step in a task.
- Use project-level `LimitRange` defaults.
- Use `PriorityClass`-based `ResourceQuota` scoping as a workaround.

The PriorityClass approach:

1. Create a `PriorityClass` for the pipeline.
2. Create a `ResourceQuota` scoped to that PriorityClass via `scopeSelector`.
3. Set `taskRunTemplate.podTemplate.priorityClassName` in the `PipelineRun`.

Since OpenShift Pipelines 1.17, the priority class applies to all pods created
for a task, including affinity assistant pods.

Read `references/official-doc-extraction.md` for full procedure and YAML.

## Pod Eviction Protection

During node drains or upgrades, Tekton workload pods can be evicted. Labels on
a `PipelineRun` propagate automatically to `TaskRun` resources and their pods.
A `PodDisruptionBudget` (PDB) targeting those labels prevents voluntary eviction
while the protected pods are running.

Key behavior:

- While a labeled Tekton pod runs, node drains and voluntary evictions are
  blocked.
- After the pod completes, the PDB no longer blocks disruption operations.
- The PDB is a one-time namespace configuration reusable across runs.

Read `references/official-doc-extraction.md` for PDB YAML and verification.

## Multicluster Support (Technology Preview)

Multicluster support distributes pipeline workloads across multiple OpenShift
Pipelines clusters using a hub-and-spoke architecture. This is a Technology
Preview feature in OpenShift Pipelines 1.22; Red Hat does not recommend
production use.

Architecture:

- **Hub cluster**: central control plane; runs Kueue with MultiKueue,
  Tekton Kueue plugin, proxy-aee, and syncer-service; does not execute
  pipeline workloads.
- **Spoke clusters**: execute pipeline runs; run Kueue with MultiKueue
  disabled; report status back to the hub.
- **Kueue/MultiKueue**: Kubernetes-native job queuing and cross-cluster
  workload scheduling using ResourceFlavor, ClusterQueue, LocalQueue,
  AdmissionCheck, MultiKueueConfig, and MultiKueueCluster resources.

Hub cluster setup requires:

- Red Hat Build of Kueue operator 1.3+
- RBAC for Kueue controller to manage Tekton PipelineRuns
- Spoke kubeconfig secrets in `openshift-kueue-operator` namespace
- NetworkPolicy allowing egress from Kueue pods
- TektonConfig: `spec.scheduler.multi-cluster-role: Hub`

Spoke cluster setup requires:

- Red Hat Build of Kueue operator 1.3+
- Service account and RBAC for MultiKueue
- NetworkPolicy allowing egress from Kueue pods
- TektonConfig: `spec.scheduler.multi-cluster-role: Spoke`
- Generated kubeconfig for hub cluster authentication

Known limitations:

- Stop/Cancel actions in web console do not work for multicluster runs
- `tkn` CLI has limited functionality on hub clusters
- Pipeline names must not exceed 45 characters
- Namespaces must be pre-created on spoke clusters
- `pipelineRef`/`taskRef` with cluster resolver not supported; use embedded
  specs or remote resolvers (Git, HTTP, Bundle)
- Only `tekton.dev/v1` API version is supported

Read `references/official-doc-extraction.md` for full configuration procedures,
Kueue resource definitions, verification commands, and known limitations.

## Related Skills

- Use `ocp-pipelines-release-notes` for OpenShift Pipelines 1.22 release
  notes, compatibility matrix, and known issues.
- Use `ocp-cicd-builds` for OpenShift build strategies and BuildConfig.
- Use `ocp-gitops-operator` for OpenShift GitOps and Argo CD behavior.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
