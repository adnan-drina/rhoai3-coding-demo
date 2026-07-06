# Validation Checklist

Use this checklist when reviewing OCP AI workload documentation, GitOps
manifests, or live operations.

## Source And Baseline

- The task references the active OCP baseline in `docs/PLATFORM_BASELINE.md`.
- Kueue, Leader Worker Set, and JobSet behavior is traced to the official OCP
  AI workloads guide.
- RHOAI component configuration is handled by the relevant `rhoai-*` skill
  rather than being copied into this OCP skill.

## Manifest Review

- Operator namespaces, channels, install modes, and operand CRs match the
  official source or active cluster catalog.
- cert-manager Operator for Red Hat OpenShift is accounted for before
  installing Kueue, Leader Worker Set, or JobSet operators.
- `openshift-kueue-operator` has monitoring enabled when required.
- `Kueue` CR fields are verified against `kueue.openshift.io/v1`.
- Kueue framework integrations include only documented or verified values.
- Managed namespaces are explicitly labeled with
  `kueue.openshift.io/managed=true`.
- `ClusterQueue`, `ResourceFlavor`, `LocalQueue`, and `Workload` resources use
  verified `kueue.x-k8s.io` API versions.
- Job manifests that use Kueue include the `kueue.x-k8s.io/queue-name` label
  and pod resource requests.
- GPU quotas reference verified GPU resources such as `nvidia.com/gpu` only
  after GPU capacity and labels are confirmed.
- `ResourceFlavor` node labels, taints, and tolerations are verified against
  live node state or official examples.
- Cohort, fair-sharing, and gang-scheduling settings include an explicit
  scheduling rationale.
- `LeaderWorkerSet` manifests use verified `leaderworkerset.x-k8s.io` API
  versions and account for group size, replicas, restart policy, networking,
  rollout, and startup behavior.
- `JobSet` manifests use verified `jobset.x-k8s.io` API versions and account
  for coordinator, replicated jobs, GPU requests, and failure behavior.
- JobSet support posture is verified against the installed Operator and current
  release notes before claiming GA or Technology Preview behavior.

## Read-Only Cluster Checks

Run only after the repo environment guard confirms the target cluster:

```bash
oc get subscription -A | grep -Ei 'kueue|leader|jobset'
oc get csv -A | grep -Ei 'kueue|leader|jobset'
oc get kueue -A
oc get clusterqueues
oc get resourceflavors
oc get localqueues -A
oc get workloads -A
oc get pods -n openshift-kueue-operator
oc get pods -n openshift-lws-operator
oc get pods -n openshift-jobset-operator
```

For schema verification:

```bash
oc explain kueue.spec
oc explain clusterqueue.spec
oc explain resourceflavor.spec
oc explain localqueue.spec
oc explain leaderworkerset.spec
oc explain jobset.spec
oc get crd | grep -Ei 'kueue|leaderworkerset|jobset'
```

For Kueue visibility:

```bash
oc get --raw /apis/visibility.kueue.x-k8s.io/v1beta2/clusterqueues/<cluster-queue>/pendingworkloads
oc get --raw /apis/visibility.kueue.x-k8s.io/v1beta2/namespaces/<namespace>/localqueues/<local-queue>/pendingworkloads
```

## Live Operation Review

- The repo-local OpenShift safety guard is used before any `oc` or `kubectl`
  command that touches the cluster.
- Operator installation, upgrade, uninstall, namespace opt-in, RBAC bindings,
  quota changes, queue changes, fair sharing, gang scheduling, and workload
  submissions have explicit user approval when run against a live environment.
- Upgrade workflows preserve operand instances unless deletion is intentional.
- Queue policy changes are reviewed for impact on GPU utilization, preemption,
  fairness, and team access.
- RHOAI-specific distributed workload behavior is reviewed with `rhoai-*`
  skills before changes are claimed as OpenShift AI behavior.

## Fail Conditions

Stop and ask for verification if:

- the documentation version does not match `docs/PLATFORM_BASELINE.md`
- a manifest includes unverified API versions or CR fields
- the task mixes OCP Kueue behavior with RHOAI DataScienceCluster behavior
  without an explicit handoff
- GPU queue examples are written before GPU capacity is verified
- JobSet support posture is ambiguous and not checked against installed
  Operator metadata or current release notes
