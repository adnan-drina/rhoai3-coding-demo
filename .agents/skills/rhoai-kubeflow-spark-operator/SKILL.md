---
name: rhoai-kubeflow-spark-operator
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when someone proposes Spark data processing on OpenShift AI: the
  Kubeflow Spark Operator, the default-dsc `sparkoperator` component,
  SparkApplication resources, or Spark Connect from a workbench. Not deployed
  in this demo (`sparkoperator: Removed`, enforced by Stage 010 validate.sh).
  Do NOT use for Ray or training jobs (use
  rhoai-distributed-workload-workflows), AI pipelines (use
  rhoai-ai-pipelines), or Feature Store compute engines (use
  rhoai-feature-store).
---

# RHOAI Kubeflow Spark Operator

Thin skill: Spark on OpenShift AI 3.5. **Not deployed in this demo.**

## When to use

- A stage proposes SparkApplication or Spark Connect workloads.
- A change touches `sparkoperator` in `default-dsc`.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| `sparkoperator.managementState: Removed`; the field is not delegated, so Stage 010 `validate.sh` requires it `Removed` | `gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-platform/datasciencecluster.yaml`, `stages/010-openshift-ai-platform-foundation/validate.sh` | [Activate the Kubeflow Spark Operator][activate] |
| The live `Kueue` CR lists `SparkApplication` among its frameworks; that does not install Spark | `gitops/stages/020-gpu-infrastructure-private-ai/020-kueue/README.md` | see `rhoai-kueue-workload-management` |

## If enabled

1. Delegate `/spec/components/sparkoperator` in the Stage 010 Application
   (`ignoreDifferences` plus `RespectIgnoreDifferences`; Stage 010
   `validate.sh` then stops requiring `Removed`), and set it `Managed` from a Sync hook in the owning stage (pattern:
   `gitops/stages/050-model-evaluation/050-model-qualification/evaluation-enablement/enable-job.yaml`).
   See `rhoai-distributed-workloads` for the delegation rules.
2. Put SparkApplications, the namespace RBAC and any Spark Connect server in
   that stage's GitOps folder; verify fields with `oc explain` against the
   installed CRD before committing.
3. Give the namespace a LocalQueue if Spark jobs should be admitted by Kueue.
4. Read-only check after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get datasciencecluster default-dsc -o jsonpath='{.spec.components.sparkoperator}{"\n"}'
   ```

## Pitfalls

- Field name: the 3.5 activate chapter uses `kubeflowsparkoperator`, while
  its workbench chapter and this repo's `datasciencecluster.opendatahub.io/v2`
  DSC use `sparkoperator`. Unresolved: verify with
  `oc explain datasciencecluster.spec.components` before use in GitOps.
- Editing `default-dsc` by hand is reverted by Argo CD while the field is
  not delegated.
- Spark images are a runtime dependency of the workload; record their
  provenance as for any non-operator image.
- Check the API tier of `sparkoperator.k8s.io` with `rhoai-api-tiers` before
  presenting it as stable.

## Official documentation (OpenShift AI 3.5)

| Topic | Section |
|---|---|
| Overview | [The Kubeflow Spark Operator][overview], [Architecture][arch] |
| Enable | [Activate the operator][activate] |
| Use | [Use the operator][use], [Custom namespace][namespace] |
| Workbenches | [Spark workloads from workbenches][connect], [Spark Connect troubleshooting][connect-ts] |

## Related skills

`rhoai-distributed-workloads`, `rhoai-dsci-dsc-configuration`,
`rhoai-api-tiers`, `rhoai-kueue-workload-management`, `rhoai-feature-store`.

[overview]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/creating_distributed_data_processing_applications_with_the_kubeflow_spark_operator/index#overview-of-kubeflow-operator_data-processing
[arch]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/creating_distributed_data_processing_applications_with_the_kubeflow_spark_operator/index#kubeflow_spark_operator_kso_architecture
[activate]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/creating_distributed_data_processing_applications_with_the_kubeflow_spark_operator/index#activate-the-ks-operator_data-processing
[use]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/creating_distributed_data_processing_applications_with_the_kubeflow_spark_operator/index#using-the-ks-operator_data-processing
[namespace]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/creating_distributed_data_processing_applications_with_the_kubeflow_spark_operator/index#creating-kubeflow-spark-namespace_data-processing
[connect]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/creating_distributed_data_processing_applications_with_the_kubeflow_spark_operator/index#running-spark-workloads-from-rhoai-workbenches_data-processing
[connect-ts]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/creating_distributed_data_processing_applications_with_the_kubeflow_spark_operator/index#troubleshooting-spark-connect-workbench-connectivity_running-spark-workloads-from-rhoai-workbenches
