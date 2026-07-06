# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product baseline | `docs/PLATFORM_BASELINE.md` |
| Document title | Working with MLflow |
| Guide URL | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_mlflow/index |
| Documentation category | Develop / Working with MLflow |
| Retrieved date | 2026-06-10 |
| Sections used | 1 About MLflow; 2 Install and configure MLflow; 2.1 MLflow and MLflowConfig configuration parameters; 2.2 Aggregate cluster roles; 2.3 RBAC model for MLflow API usage; 3 Install and authenticate the MLflow SDK; 3.1 Configuring the MLflow SDK for a local workstation; 3.2 Configuring MLflow SDK environment variables for pods; 3.3 Upstream MLflow SDK reference; 3.4 MLflow SDK troubleshooting reference; 3.5 MLflow version compatibility; 3.6 MLflow storage and database compatibility; 3.7 Tracking experiments with MLflow SDK; 3.8 Configure project-specific S3 artifact storage |

## Related Official Sources

| Source | Role |
|--------|------|
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/working_on_projects | OpenShift AI project and workspace lifecycle context |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_data_in_an_s3-compatible_object_store/index | S3-compatible object storage context |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_in_your_data_science_ide/index | Workbench notebook and SDK execution context |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_resources/managing-connection-types | Connection type and S3 connection context |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/experimenting_with_models_in_the_gen_ai_playground/index | Prompt persistence context that depends on MLflow availability |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_model_registries/index | Distinguishes OpenShift AI model registry user workflows from MLflow model registry APIs |

## Supporting Project Sources

| Source | Role |
|--------|------|
| `docs/PLATFORM_BASELINE.md` | Active RHOAI/OCP baseline and source hierarchy |
| `AGENTS.md` | OpenShift safety guard and GitOps operating constraints |
| `.agents/skills/rhoai-project-workflows/SKILL.md` | Project, workspace, and connection lifecycle boundary |
| `.agents/skills/rhoai-s3-object-storage-data/SKILL.md` | S3-compatible data operation boundary |
| `.agents/skills/rhoai-gen-ai-playground/SKILL.md` | Prompt management workflow boundary |
| `.agents/skills/rhoai-model-registry/SKILL.md` | OpenShift AI model registry admin boundary |
| `.agents/skills/rhoai-model-registry-workflows/SKILL.md` | OpenShift AI model registry user workflow boundary |
| `.agents/skills/rhoai-model-evaluation/SKILL.md` | Custom evaluation and MLflow-backed evidence boundary |
| `.agents/skills/rhoai-api-tiers/SKILL.md` | MLflow API support posture boundary |

## Source Boundaries

- Product authority: the official Red Hat OpenShift AI 3.4 Working with MLflow
  guide above.
- The guide defines the shared MLflow instance, workspace mapping, RBAC
  authorization, MLflow/MLflowConfig resources, SDK authentication, storage
  choices, and troubleshooting signals.
- The guide does not replace project/workbench lifecycle guidance, generic S3
  object operations, OpenShift AI model registry workflows, or custom
  evaluation implementation guidance.
- Verification: MLflow Operator component state, `MLflow` CR, MLflow UI tile,
  workspace selection, SDK connectivity, RBAC behavior, experiment logging,
  and project-specific artifact override behavior.

## Unresolved Or Environment-Specific Items

- Active demo MLflow storage mode.
  Verification: decide whether the clean-slate implementation uses
  development/test SQLite/PVC storage or production-shaped PostgreSQL and S3.
- Active dashboard route for `MLFLOW_TRACKING_URI`.
  Verification: derive from the running OpenShift AI dashboard route before
  live use.
- Active project artifact bucket names and access policy.
  Verification: define per demo project and store credentials through
  project-scoped connections or Secrets.
- Whether MLflow is enabled as active GitOps desired state or a later optional
  capability.
  Verification: decide during the clean-slate GitOps reimplementation.
- Current MLflow CRD schema in the target cluster.
  Verification: run `oc explain mlflow.spec` and
  `oc explain mlflowconfig.spec` after following the safety guard.
