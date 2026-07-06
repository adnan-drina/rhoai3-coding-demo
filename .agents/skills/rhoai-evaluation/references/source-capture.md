# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product baseline | `docs/PLATFORM_BASELINE.md` |
| Document title | Evaluating AI systems |
| Guide URL | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/evaluating_ai_systems/index |
| Documentation category | Evaluate / Evaluating AI systems |
| Retrieved date | 2026-06-10 |
| Sections used | 1 Overview of evaluating AI systems; 2 Evaluate LLMs with EvalHub; 2.1 Understanding EvalHub; 2.2 EvalHub architecture; 2.3 Deploy EvalHub with the TrustyAI Operator; 2.4 EvalHub SDK and CLI; 2.5 EvalHub multi-tenancy; 2.6 Providers and benchmarks; 2.7 Submit an evaluation job; 2.8 Track jobs and results; 2.9 Cancel and delete jobs; 2.10 Built-in collections; 2.11 Custom collections; 2.12 API key authentication; 2.13 ServiceAccount token authentication; 2.14 S3 custom data; 2.15 OCI result export; 2.16 MLflow tracking; 2.17-2.20 custom providers, ConfigMaps, collections, adapters; 2.21 API endpoints; 2.22 configuration; 2.23-2.26 tenant RBAC; 3 Evaluating LLMs with LM-Eval; 3.1-3.7 setup, external access, jobs, dashboard, metrics, scenarios; 4 Automated risk assessment; 4.1-4.7 overview, disconnected preparation, EvalHub execution, KFP SDK execution, results, custom harm categories, configuration |

## Related Official Sources

| Source | Role |
|--------|------|
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_mlflow/index | MLflow platform, SDK auth, workspaces, and artifact storage context |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_ai_pipelines/index | AI Pipelines server, runs, artifacts, and KFP context |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/configuring_your_model-serving_platform | KServe, vLLM, serving runtime, and OpenAI-compatible endpoint context |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_data_in_an_s3-compatible_object_store/index | S3-compatible object storage context |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_autorag/index | Product AutoRAG evaluation-adjacent workflow boundary |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/customize_models_for_gen_ai_and_agentic_ai_applications/index | Training, SDG, and model customization context |

## Supporting Project Sources

| Source | Role |
|--------|------|
| `docs/PLATFORM_BASELINE.md` | Active RHOAI/OCP baseline and source hierarchy |
| `AGENTS.md` | OpenShift safety guard and GitOps operating constraints |
| `.agents/skills/rhoai-model-evaluation/SKILL.md` | Legacy/demo-specific evaluation boundary |
| `.agents/skills/rhoai-mlflow/SKILL.md` | MLflow platform and tracking boundary |
| `.agents/skills/rhoai-ai-pipelines/SKILL.md` | AI Pipelines product boundary |
| `.agents/skills/rhoai-s3-object-storage-data/SKILL.md` | S3 data operation boundary |
| `.agents/skills/rhoai-model-serving-platform/SKILL.md` | KServe/vLLM serving endpoint boundary |
| `.agents/skills/rhoai-model-customization-training/SKILL.md` | SDG and Training Hub boundary |
| `.agents/skills/rhoai-api-tiers/SKILL.md` | API support posture boundary |

## Source Boundaries

- Product authority: the official Red Hat OpenShift AI 3.4 Evaluating AI
  systems guide above.
- The guide defines EvalHub, LM-Eval, and automated risk assessment product
  workflows.
- The guide does not replace MLflow deployment guidance, AI Pipelines server
  administration, model-serving platform configuration, AutoRAG optimization,
  or legacy demo Step 08 rebuild details.
- Verification: EvalHub health and providers, EvalHub job states and results,
  tenant RBAC, MLflow logging, OCI export, `LMEvalJob` pod status/results,
  dashboard evaluations, risk assessment report artifacts, S3 outputs, and
  disconnected translation cache behavior.

## Unresolved Or Environment-Specific Items

- Active EvalHub namespace and database ownership.
  Verification: decide during clean-slate GitOps design and verify with
  `oc explain evalhub.spec`.
- Active evaluation provider set.
  Verification: list providers and benchmarks from the deployed EvalHub
  instance before promising benchmark coverage.
- Active model, judge, attacker, evaluator, and SDG endpoints.
  Verification: align with model serving and MaaS design before live runs.
- Active MLflow tracking and OCI export destinations.
  Verification: use `rhoai-mlflow` and registry credential review.
- Active disconnected translation-model cache location.
  Verification: pre-download and upload Helsinki-NLP model cache only when
  translation attack strategies are required.
