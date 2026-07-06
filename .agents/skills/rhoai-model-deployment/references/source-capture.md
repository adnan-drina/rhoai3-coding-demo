# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product baseline | `docs/PLATFORM_BASELINE.md` |
| Document title | Deploying models |
| Guide URL | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/deploying_models/index |
| Documentation category | Deploy / Deploying models |
| Retrieved date | 2026-06-10 |
| Sections used | 1 Storing models; 1.1 OCI containers/modelcars; 1.2 storing a model in an OCI image; 1.3 uploading model files to a PVC; 2 Deploying models; 2.1 automatic serving-runtime selection; 2.2 deployment strategies; 2.3 Deploy a model wizard; 2.4 MLServer runtime; 2.5 OCI model deployment by CLI; 2.6 monitoring model handoff; 3 NVIDIA NIM model deployment and metrics handoff; 4 making inference requests; 4.1 token lookup; 4.2 endpoint lookup; 4.4 runtime-specific inference endpoints |

## Related Official Sources

| Source | Role |
|--------|------|
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/configuring_your_model-serving_platform | Platform, runtime, NIM, vLLM, and deployment strategy configuration boundary |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_and_monitoring_models | Deployed model operations, metrics, autoscaling, and Grafana boundary |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_the_model_catalog/index | Catalog discovery and deploy-from-catalog boundary |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_model_registries/index | Registered model and model version deployment boundary |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/experimenting_with_models_in_the_gen_ai_playground/index | AI asset endpoint and playground testing boundary |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/working_with_accelerators/enabling-nvidia-gpus_accelerators | NVIDIA GPU prerequisite boundary |

## Supporting Project Sources

| Source | Role |
|--------|------|
| `docs/PLATFORM_BASELINE.md` | Active RHOAI/OCP baseline and source hierarchy |
| `AGENTS.md` | OpenShift safety guard and GitOps operating constraints |
| `.agents/skills/rhoai-model-serving-platform/SKILL.md` | Platform and runtime configuration boundary |
| `.agents/skills/rhoai-model-management-monitoring/SKILL.md` | Day-2 deployed model operations and metrics boundary |
| `.agents/skills/rhoai-gen-ai-playground/SKILL.md` | AI asset endpoint testing boundary |
| `.agents/skills/rhoai-model-catalog-workflows/SKILL.md` | Catalog handoff boundary |
| `.agents/skills/rhoai-model-registry-workflows/SKILL.md` | Registry handoff boundary |
| `.agents/skills/rhoai-api-tiers/SKILL.md` | API support posture boundary |

## Source Boundaries

- Product authority: the official Red Hat OpenShift AI 3.4 Deploying models
  guide above.
- The guide defines model storage, deployment, token, endpoint, and inference
  request workflows for users.
- The guide does not replace platform setup, runtime template configuration,
  model-serving day-2 monitoring, TrustyAI monitoring, MaaS, or llm-d product
  guides.
- GitOps authoring must verify dashboard-derived resource fields against
  official docs or CRD schema before committing.
- Verification: project access, connections, storage source, runtime
  availability, hardware profile, route/token settings, deployment readiness,
  `InferenceService` status, endpoint URL, token Secret, and runtime-specific
  inference response.

## Unresolved Or Environment-Specific Items

- Active demo private model deployment API kind.
  Verification: use the official deployment guide and active CRD schema before
  choosing `InferenceService`, `LLMInferenceService`, or another resource.
- Active model artifact storage.
  Verification: decide whether the clean-slate demo uses OCI modelcars, S3, a
  URI repository, PVC model storage, or model registry handoff.
- Active deployment strategy.
  Verification: compare GPU quota and downtime tolerance before choosing
  Rolling update or Recreate.
- Active endpoint exposure and authentication.
  Verification: confirm route, token Secret, and client location before
  exposing endpoints.
