# Validation Checklist

Use this checklist before approving distributed workloads GitOps or install
automation.

## Prerequisite Review

- RHOAI is installed and reachable.
- Current user has `cluster-admin`.
- Red Hat build of Kueue Operator is installed or planned in an earlier GitOps
  layer.
- cert-manager Operator is installed or planned in an earlier GitOps layer.
- Additional distributed workload infrastructure resources are available.
- GPU support is enabled before GPU-backed distributed workloads are used.
- NVIDIA or AMD GPU path is documented when accelerators are used.
- Self-signed certificate requirements are handled through the central CA
  bundle, when applicable.

## DataScienceCluster Review

- `dashboard.managementState` is `Managed`.
- `kueue.managementState` is `Unmanaged`.
- `ray.managementState` is `Managed` when Ray/KubeRay workloads are required.
- `trainingoperator.managementState` is `Managed` when Kubeflow Training
  Operator workloads are required.
- `aipipelines.managementState` is `Managed` for pipeline-launched workloads and
  `Removed` for workbench-only usage.
- `workbenches.managementState` is `Managed` for workbench-launched workloads
  and `Removed` for pipeline-only usage.
- Component choices match the README and operations notes.

## GitOps Review

- Prerequisite Operators and RHOAI component state are applied in dependency
  order through ArgoCD.
- No long-lived distributed workload resources are manually applied outside
  GitOps.
- Kueue queue design is kept separate from component installation unless a step
  explicitly implements both.
- Any GPU or RDMA claims are backed by official docs and validation checks.

## Readonly Cluster Checks

Run only after following the OpenShift safety guard in `AGENTS.md`:

```bash
oc get datasciencecluster default-dsc -o yaml
oc get deployment kubeflow-training-operator -n redhat-ods-applications
oc get deployment kuberay-operator -n redhat-ods-applications
oc get deployment kueue-controller-manager -n openshift-kueue-operator
oc get deployment openshift-kueue-operator -n openshift-kueue-operator
oc get pods -n redhat-ods-applications | rg "kubeflow-training|kuberay"
oc get pods -n openshift-kueue-operator
```

For GPU-backed distributed workloads, use the relevant official GPU enablement
documentation or accelerator skill for concrete node labels, Operator status,
and accelerator health checks. Do not infer GPU labels from this distributed
workloads install chapter.

## Fail Conditions

- `kueue.managementState` is set to `Managed`.
- Distributed workloads are enabled before Red Hat build of Kueue Operator or
  cert-manager are available.
- GPU distributed workload claims are made without GPU support validation.
- README claims queue behavior that is not implemented in GitOps.
- Queue configuration is inferred from this install chapter instead of the
  managing distributed workloads documentation.
