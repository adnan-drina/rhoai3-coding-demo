# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product baseline | `docs/PLATFORM_BASELINE.md` |
| Document title | Monitoring your AI Systems |
| Guide URL | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/monitoring_your_ai_systems/index |
| Documentation category | Monitor / Monitoring your AI systems |
| Retrieved date | 2026-06-10 |
| Sections used | 1 Overview of monitoring your AI systems; 2 Configuring TrustyAI; 2.1 model serving platform monitoring handoff; 2.2 enabling the TrustyAI component; 2.3 database configuration; 2.4 project service installation; 2.5 KServe RawDeployment integration; 3 project setup; 3.1 authentication; 3.2 training data upload; 3.3 sending training data; 3.4 field labeling; 4 monitoring model bias; 4.1 create bias metrics; 4.2 delete bias metrics; 4.3 view bias metrics; 4.4 bias metric interpretation; 5 monitoring data drift; 5.1 create drift metrics; 5.2 delete drift metrics; 5.3 view drift metrics; 5.4 drift metric interpretation; 5.5 credit-card scenario |

## Related Official Sources

| Source | Role |
|--------|------|
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_openshift_ai/managing-observability_managing-rhoai | OpenShift AI observability stack context |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_and_monitoring_models | Deployed model operational monitoring context |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/configuring_your_model-serving_platform | Model-serving platform, runtime, and KServe context |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/evaluating_ai_systems/index | LLM evaluation and automated risk-assessment context |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/enabling_ai_safety_with_guardrails/index | Runtime guardrails and safety-control context |

## Supporting Project Sources

| Source | Role |
|--------|------|
| `docs/PLATFORM_BASELINE.md` | Active RHOAI/OCP baseline and source hierarchy |
| `AGENTS.md` | OpenShift safety guard and GitOps operating constraints |
| `.agents/skills/rhoai-observability/SKILL.md` | Observability stack boundary |
| `.agents/skills/rhoai-model-management-monitoring/SKILL.md` | Deployed model operational metrics boundary |
| `.agents/skills/rhoai-model-serving-platform/SKILL.md` | KServe and serving runtime boundary |
| `.agents/skills/rhoai-evaluation/SKILL.md` | LLM evaluation and risk-assessment boundary |
| `.agents/skills/rhoai-guardrails-safety/SKILL.md` | Runtime guardrails boundary |
| `.agents/skills/rhoai-api-tiers/SKILL.md` | API support posture boundary |

## Source Boundaries

- Product authority: the official Red Hat OpenShift AI 3.4 Monitoring your AI
  systems guide above.
- The guide defines TrustyAI bias and data-drift monitoring product workflows.
- The guide does not replace OpenShift AI observability setup, deployed-model
  operational monitoring, model-serving platform configuration, runtime
  guardrails, or formal evaluation.
- The guide states that TrustyAI monitoring supports OVMS models and that
  non-OVMS models are not supported for this workflow.
- Upstream TrustyAI API links are supplemental endpoint references unless the
  Red Hat guide uses them directly.
- Verification: TrustyAI component state, `TrustyAIService` CR schema,
  service pod readiness, route authentication, training data upload, `/info`,
  `trustyai_model_observations_total`, metric request endpoints, and
  OpenShift Observe `trustyai_*` metrics.

## Unresolved Or Environment-Specific Items

- Active demo use of TrustyAI monitoring with the planned private LLM path.
  Verification: do not claim support for vLLM/Nemotron monitoring unless
  active Red Hat documentation confirms it.
- Active TrustyAI storage backend.
  Verification: choose database or PVC during GitOps design and verify Secret
  ownership before deployment.
- Active model data schema and fairness/drift scenario.
  Verification: review data fields, protected attributes, thresholds, and
  reference tags before metrics are created.
- Active Prometheus/user workload monitoring permissions.
  Verification: use `rhoai-observability` and OpenShift monitoring role checks.
