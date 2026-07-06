---
name: rhoai-kubeflow-spark-operator
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when documenting, reviewing, or rebuilding Red Hat OpenShift AI
  Kubeflow Spark Operator workflows from the official guide: KSO architecture,
  activating kubeflowsparkoperator in the DataScienceCluster, verifying the
  operator pod in redhat-ods-applications, building or importing an
  OpenShift-compatible Spark 4.0.1+ image, authoring SparkApplication
  resources, handling Spark driver and executor resources, removing
  runAsGroup/runAsUser from example YAML, copying Spark Operator RBAC into a
  custom namespace, and classifying sparkoperator.k8s.io/v1beta2 API stability.
  Do NOT use for general distributed training with Ray/Kueue/PyTorchJob (use
  rhoai-distributed-workload-workflows), AI Pipelines/KFP workflows (use
  rhoai-ai-pipelines and rhoai-kfp-pipeline-authoring), generic project
  lifecycle (use rhoai-project-workflows), generic image build policy (use
  project-gitops-authoring and project-manifest-review), or live cluster
  changes without the OpenShift safety guard.
---

# RHOAI Kubeflow Spark Operator

Use this skill for Red Hat OpenShift AI Kubeflow Spark Operator workflows on
the active product baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product workflow details.
Official Red Hat documentation is product authority. This skill adapts the
official Kubeflow Spark Operator guide to this repo's GitOps and demo workflow
model.

## Scope

This skill covers:

- Kubeflow Spark Operator purpose and architecture
- activation through the OpenShift AI `DataScienceCluster` custom resource
- verification of the Spark Operator pod in `redhat-ods-applications`
- Spark 4.0.1+ image requirements and OpenShift `restricted-v2` SCC
  compatibility notes from the official example
- `SparkApplication` CR authoring for Spark driver and executor pods
- key SparkApplication fields: namespace, type, mode, image,
  mainApplicationFile, sparkVersion, restartPolicy, driver, executor,
  volumes, volumeMounts, and serviceAccount
- custom namespace RBAC handoff for `ServiceAccount`, `Role`, and
  `RoleBinding`
- API-tier and support posture review for `sparkoperator.k8s.io/v1beta2`

Use other skills for adjacent work:

- `rhoai-api-tiers` for API tier classification and upgrade-risk review
- `rhoai-distributed-workloads` and `rhoai-distributed-workload-workflows` for
  Ray, Kueue, Training Operator, PyTorchJob, and general distributed workload
  guidance
- `rhoai-ai-pipelines` and `rhoai-kfp-pipeline-authoring` for AI Pipelines and
  KFP workflows
- `rhoai-project-workflows` for project and namespace ownership
- `rhoai-storage-classes` for PVC storage class and access-mode review
- `project-gitops-authoring` and `project-manifest-review` for GitOps
  structure, image provenance, and Kubernetes manifest review

## Demo Policy

For this repo:

- Treat Kubeflow Spark Operator as a specialized distributed data processing
  capability, not as the default distributed training path.
- Confirm `rhoai-api-tiers` before treating `sparkoperator.k8s.io/v1beta2` as a
  stable demo contract. In the active RHOAI API tier table, this API is Alpha.
- Keep KSO activation in the platform GitOps layer as a
  `DataScienceCluster.spec.components.kubeflowsparkoperator.managementState`
  change after schema verification.
- Do not author unsupported `SparkApplication` fields from memory. Verify the
  active CRD or official docs before adding fields.
- Use a Spark image that includes the Spark runtime version declared in
  `spec.sparkVersion`.
- If following the official Apache Spark image example, document it as an
  official-doc-sourced non-Red Hat image exception and review provenance before
  using it in demo GitOps.
- Remove `runAsGroup` and `runAsUser` from imported Spark example YAMLs as the
  official guide warns that they can cause jobs to crash in OpenShift AI.
- Use the automatically created `spark-operator-spark` service account only in
  namespaces where the required RBAC exists.
- For custom namespaces, copy and review the default `ServiceAccount`, `Role`,
  and `RoleBinding` resources rather than assuming cross-namespace access.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/source-capture.md` and
   `references/official-doc-extraction.md`.
3. Decide whether the task is:
   - KSO activation in `DataScienceCluster`
   - operator pod verification
   - Spark image build/import review
   - `SparkApplication` manifest authoring
   - custom namespace RBAC setup
   - API tier and upgrade-risk review
4. Use `examples/kubeflow-spark-operator-patterns.md` for focused review
   patterns.
5. For live cluster work, follow the OpenShift safety guard in `AGENTS.md`.
6. Validate with `references/validation-checklist.md`.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/kubeflow-spark-operator-patterns.md`
