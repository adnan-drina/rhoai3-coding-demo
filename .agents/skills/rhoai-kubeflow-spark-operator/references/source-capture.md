# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product baseline | `docs/PLATFORM_BASELINE.md` |
| Document title | Creating distributed data processing applications with the Kubeflow Spark Operator |
| Guide URL | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/creating_distributed_data_processing_applications_with_the_kubeflow_spark_operator/index |
| Documentation category | Develop / Creating distributed data processing applications with the Kubeflow Spark Operator |
| Retrieved date | 2026-06-10 |
| Sections used | 1 Overview of the Kubeflow Spark Operator (KSO); 1.1 Kubeflow Spark Operator (KSO) architecture; 2 Activating the Kubeflow Spark Operator; 3 Using the Kubeflow Spark Operator; 3.1 Using the Kubeflow Spark Operator in a custom namespace |

## Related Official Sources

| Source | Role |
|--------|------|
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/installing_and_uninstalling_openshift_ai_self-managed/installing-and-deploying-openshift-ai_install | DataScienceCluster and platform install context |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_distributed_workloads/index | Distributed workload user workflow boundary |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_ai_pipelines/index | AI Pipelines/KFP boundary |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_resources/managing-storage-classes | PVC and storage class context |

## Supporting Project Sources

| Source | Role |
|--------|------|
| `docs/PLATFORM_BASELINE.md` | Active RHOAI/OCP baseline and source hierarchy |
| `AGENTS.md` | OpenShift safety guard and GitOps operating constraints |
| `.agents/skills/rhoai-api-tiers/SKILL.md` | API tier support posture for `sparkoperator.k8s.io/v1beta2` |
| `.agents/skills/rhoai-self-managed-installation/SKILL.md` | `DataScienceCluster` installation and component management boundary |
| `.agents/skills/rhoai-distributed-workloads/SKILL.md` | Distributed workload platform component boundary |
| `.agents/skills/rhoai-distributed-workload-workflows/SKILL.md` | Ray/Kueue/Training Operator workflow boundary |
| `.agents/skills/rhoai-ai-pipelines/SKILL.md` | AI Pipelines product workflow boundary |
| `.agents/skills/project-gitops-authoring/SKILL.md` | GitOps authoring and image provenance boundary |
| `.agents/skills/project-manifest-review/SKILL.md` | Kubernetes manifest review boundary |

## Source Boundaries

- Product authority: the official Red Hat OpenShift AI 3.4 Kubeflow Spark
  Operator guide above.
- The guide defines KSO activation, architecture, basic Spark image build
  requirements, `SparkApplication` usage, and custom namespace RBAC setup.
- It does not replace complete Spark application development, production Spark
  tuning, generic distributed training workflows, AI Pipelines, KFP, data lake
  design, object storage administration, or enterprise image supply-chain
  policy.
- Verification: `DataScienceCluster` component state, KSO pod status,
  `SparkApplication` resource status, driver/executor pods, `spark-submit`
  submission behavior, namespace RBAC, and API tier review.

## Unresolved Or Environment-Specific Items

- Active demo need for Spark.
  Verification: document the concept, data-processing use case, and why KSO is
  needed before adding active GitOps content.
- Spark image provenance.
  Verification: choose and document the image source. If using the official
  Apache Spark example, record it as a source-backed non-Red Hat image
  exception and review it with project manifest rules.
- Custom namespace strategy.
  Verification: decide whether Spark applications run in
  `redhat-ods-applications` or a demo namespace, then add required RBAC.
- Storage and data paths.
  Verification: define PVCs, object storage, or other data sources before
  authoring production-like SparkApplication examples.
