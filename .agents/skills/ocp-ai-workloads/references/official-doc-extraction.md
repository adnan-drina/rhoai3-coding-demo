# Official Doc Extraction

Use this extraction to keep OCP AI workload content grounded in the official
OCP source. When implementation needs exact CR fields, verify the active
cluster schema with `oc explain` or `oc get crd` before authoring GitOps
manifests.

## Overview

OpenShift Container Platform provides a secure, scalable foundation for AI
workloads across training, inference, and data science workflows. The official
guide identifies three OCP-side operators for AI workloads:

- Red Hat build of Kueue for structured queues, prioritization, fair use, and
  efficient resource handling.
- Leader Worker Set Operator for large-scale AI inference workloads that need
  leader and worker process coordination.
- JobSet Operator for large-scale coordinated workloads such as HPC and AI
  training.

## Red Hat Build Of Kueue

Red Hat build of Kueue is a Kubernetes-native system that manages access to job
resources. It decides whether a job waits, is admitted, or is preempted.

Official behavior to preserve:

- Kueue does not replace the Kubernetes API server, scheduler, or cluster
  autoscaler; it integrates with them.
- Kueue supports all-or-nothing semantics for jobs.
- Kueue version 1.1 and later is supported on ARM64, 64-bit x86, ppc64le, and
  s390x, and on OpenShift Container Platform and Hosted control planes.
- Kueue is not supported on Red Hat build of MicroShift.
- Installation uses the Red Hat Build of Kueue Operator from OperatorHub and
  requires cert-manager Operator for Red Hat OpenShift.
- The `openshift-kueue-operator` namespace must be monitored with the
  `openshift.io/cluster-monitoring: "true"` label.
- The `Kueue` custom resource uses `apiVersion: kueue.openshift.io/v1`, kind
  `Kueue`, name `cluster`, and namespace `openshift-kueue-operator` in the
  official examples.
- The default Kueue framework integration is `BatchJob`; documented additional
  types include `Pod`, `Deployment`, and `StatefulSet`.
- Fair sharing is enabled by setting `spec.config.preemption.preemptionPolicy`
  or the documented `preemptionPolicy` value to `FairSharing`, depending on the
  current CR schema and example context. Verify exact field placement before
  authoring.
- Existing Kueue deployments must be manually upgraded by uninstalling and
  reinstalling the Operator. Do not select "Delete all operand instances" when
  upgrading if existing `Kueue`, queue, or resource flavor resources must be
  retained.

## Namespace Opt-In

Red Hat build of Kueue uses an opt-in webhook mechanism. Namespaces where Kueue
should manage jobs must be labeled:

```bash
oc label namespace <namespace> kueue.openshift.io/managed=true
```

This label causes Kueue webhook admission controllers to validate and mutate
Kueue resources in that namespace.

## RBAC

The Red Hat build of Kueue Operator deploys these cluster roles by default:

- `kueue-batch-admin-role`: manage cluster queues, local queues, workloads, and
  resource flavors.
- `kueue-batch-user-role`: manage jobs and view local queues and workloads.

Use cluster role bindings for batch administrators and namespace role bindings
for users, following the official examples. Do not grant broad cluster access
to demo users without documenting the operational reason.

## Queue And Quota Model

The official quota flow is:

1. Configure a `ClusterQueue`.
2. Configure a `ResourceFlavor`.
3. Configure a `LocalQueue`.
4. Submit workloads to the local queue.

Important resource behavior:

- `ClusterQueue` is cluster scoped and governs a pool of resources such as CPU,
  memory, pods, and GPU.
- `ResourceFlavor` represents resource variations associated with node labels,
  taints, and tolerations.
- `LocalQueue` is namespaced and points workloads in that namespace to a
  `ClusterQueue`.
- The documented Kueue API group for queue resources is
  `kueue.x-k8s.io/v1beta2`.
- Jobs must specify the local queue through the
  `kueue.x-k8s.io/queue-name` label and include resource requests for each pod.
- Kueue suspends the job until resources are available and creates a
  corresponding `Workload` object.

Do not claim that a GPU queue is valid until GPU node capacity, NFD labels, and
device-plugin resources are verified.

## Visibility, Cohorts, Fair Sharing, And Gang Scheduling

The guide documents:

- pending workload visibility through the
  `visibility.kueue.x-k8s.io/v1beta2` API
- cohort sharing through `ClusterQueue.spec.cohortName`
- fair sharing through Kueue preemption policy and `ClusterQueue` weights
- gang scheduling through the `Kueue` custom resource `gangScheduling` spec

Gang scheduling is useful for limited expensive resources such as GPUs. The
documented `policy` values include `ByWorkload`, `None`, and empty. When
`ByWorkload` is used, job admission settings are required; documented
admission values include `Parallel`, `Sequential`, and empty. Verify exact
schema before committing.

## Leader Worker Set Operator

Leader Worker Set Operator manages multi-node AI/ML inference deployments by
treating groups of pods as a single unit. The official guide describes:

- cert-manager Operator for Red Hat OpenShift as a prerequisite
- default monitoring through OpenShift Prometheus
- installation in the `openshift-lws-operator` namespace on the `stable-v1.0`
  channel in the official web-console flow
- `LeaderWorkerSetOperator` operand creation
- `LeaderWorkerSet` resources with `apiVersion:
  leaderworkerset.x-k8s.io/v1`
- group size, replicas, restart policy, shared or unique headless service
  policy, rollout strategy, startup policy, and topology-aware placement
- Kueue integration by adding `LeaderWorkerSet` to
  `Kueue.spec.config.integrations.frameworks`

Use this skill for OCP platform behavior. Use RHOAI serving and distributed
inference skills for RHOAI-specific model serving.

## JobSet Operator

JobSet Operator manages large-scale coordinated workloads such as HPC and AI
training by modeling a distributed batch workload as a group of Kubernetes
Jobs.

The official guide describes:

- cert-manager Operator for Red Hat OpenShift as a prerequisite
- installation in the `openshift-jobset-operator` namespace on the
  `stable-v1.0` channel in the official web-console flow
- `JobSetOperator` operand creation with name `cluster` and
  `managementState: Managed`
- `JobSet` resources with `apiVersion: jobset.x-k8s.io/v1alpha2`
- Kueue integration by adding `JobSet` to
  `Kueue.spec.config.integrations.frameworks`
- JobSet examples that request `nvidia.com/gpu`
- coordinator configuration for distributed workload communication

The source overview labels JobSet Operator as Technology Preview, while the
release-note section states that JobSet Operator 1.0 is an initial Generally
Available release. Verify the installed Operator, channel, release notes, and
support posture before making demo support claims.

## Support Data Collection

For Red Hat build of Kueue support, the official guide uses `oc adm must-gather`
with the Kueue must-gather image:

```bash
oc adm must-gather --image=registry.redhat.io/kueue/kueue-must-gather-rhel9:<version>
```

Collecting support data is a live-cluster operation and must follow the repo
environment guard.
