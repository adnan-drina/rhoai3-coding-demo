---
name: rhoai-distributed-workloads
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when deciding whether to enable the OpenShift AI distributed workloads
  components in this demo: the default-dsc ray, trainingoperator and trainer
  states (all Removed in Stage 010), their Kueue and cert-manager prerequisites
  (already provided by Stage 020), and how a stage would delegate those DSC
  fields. Do NOT use for the Kueue integration and queues (use
  rhoai-kueue-workload-management), quota examples, RDMA or Ray administrator
  troubleshooting (use rhoai-distributed-workload-operations), user Ray or
  training jobs (use rhoai-distributed-workload-workflows), or Spark (use
  rhoai-kubeflow-spark-operator).
---

# RHOAI Distributed Workloads

Thin skill: repo decisions and pitfalls here, product behavior in the linked
OpenShift AI 3.5 sections. Detailed record:
`gitops/stages/010-openshift-ai-platform-foundation/rhoai-platform/README.md`
(DSC components and delegated fields).

## When to use

- A stage proposes Ray, Kubeflow Training Operator or Trainer workloads.
- A change touches `ray`, `trainingoperator` or `trainer` in
  `gitops/stages/010-openshift-ai-platform-foundation/rhoai-platform/datasciencecluster.yaml`.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Distributed workloads are not part of this demo: `ray`, `trainingoperator`, `trainer` and `sparkoperator` are `Removed` in `default-dsc` | `gitops/stages/010-openshift-ai-platform-foundation/rhoai-platform/datasciencecluster.yaml` | [Install the distributed workloads components][dw-install] |
| The Kueue prerequisite is met for other reasons: Red Hat build of Kueue Operator, DSC `kueue: Unmanaged`, `autoCreateQueues: false` (GPU quota for model serving and workbenches) | `gitops/stages/020-gpu-infrastructure-private-ai/kueue/` | [Install the distributed workloads components][dw-install]; see `rhoai-kueue-workload-management` |
| cert-manager is a cluster prerequisite checked by Stage 020 `deploy.sh` (`cert-manager-operator.v1.20.*`), not declared in Git | `stages/020-gpu-infrastructure-private-ai/deploy.sh` | [Install the distributed workloads components][dw-install] |
| `dashboard` and `workbenches` are `Managed` in Stage 010; `aipipelines` is enabled by Stage 050 through a delegated field | `gitops/stages/010-openshift-ai-platform-foundation/rhoai-platform/datasciencecluster.yaml`, `.../README.md` | [Install the distributed workloads components][dw-install] |
| A DSC component is turned on only by the owning stage's hook Job after the field is delegated in the Stage 010 Application (`ignoreDifferences` + `RespectIgnoreDifferences`) | `gitops/stages/010-openshift-ai-platform-foundation/rhoai-platform/README.md` | [Install and manage components][components] |

## Procedure

To introduce distributed workloads in a future stage:

1. Read the component prerequisites for the release: the install chapter
   lists the per-launch-surface states, and [Component requirements][comp-req]
   lists extra operators (for example the JobSet Operator for `trainer`).
2. Delegate the field in the Stage 010 Application, add an enablement hook in
   the new stage (pattern: `gitops/stages/020-gpu-infrastructure-private-ai/kueue/dsc-enablement/`),
   and add the Kueue frameworks' queues and flavors with
   `rhoai-distributed-workload-operations`.
3. Validate Stage 010 (`./stages/010-openshift-ai-platform-foundation/validate.sh`,
   which requires the non-delegated 3.5 components `Removed`) and the new stage.
4. Read-only check after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get datasciencecluster default-dsc \
     -o jsonpath='{range .status.conditions[*]}{.type}={.status} {end}{"\n"}'
   oc get datasciencecluster default-dsc -o jsonpath='{.spec.components.ray}{"\n"}{.spec.components.trainingoperator}{"\n"}'
   ```

## Pitfalls

- Never edit `default-dsc` by hand: Argo CD restores the Git value
  (`Removed`) for any field that is not delegated, which uninstalls it.
- Removing a delegated pointer from `ignoreDifferences` also reverts the field
  to `Removed`.
- GPU-backed distributed jobs would compete with the model servers for the two
  exclusive GPUs per ClusterQueue; plan quota before enabling them.
- The live `Kueue` CR already lists Ray and training frameworks; that does not
  mean the operators behind them are installed.

## Official documentation (OpenShift AI 3.5)

| Topic | Section |
|---|---|
| Distributed workloads install | [Install the distributed workloads components][dw-install] |
| Component prerequisites | [Component requirements][comp-req] |
| Component management | [Install and manage components][components] |

## Related skills

`rhoai-kueue-workload-management`, `rhoai-distributed-workload-operations`,
`rhoai-distributed-workload-workflows`, `rhoai-kubeflow-spark-operator`,
`rhoai-dsci-dsc-configuration`, `ocp-ai-workloads`.

[dw-install]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#installing-the-distributed-workloads-components_install
[comp-req]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#component_requirements
[components]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#installing-and-managing-openshift-ai-components_component-install
