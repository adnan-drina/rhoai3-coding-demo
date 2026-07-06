# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product baseline | `docs/PLATFORM_BASELINE.md` |
| Document title | Ensuring AI safety with guardrails |
| Guide URL | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/enabling_ai_safety_with_guardrails/index |
| Documentation category | Maintain Safety / Ensuring AI safety with guardrails |
| Retrieved date | 2026-06-10 |
| Sections used | 1 Enabling AI safety with NeMo Guardrails; 1.1 NeMo Guardrails standalone quickstart; 1.2 Deploying the NeMo Guardrails service with an LLM; 1.2.1 authentication; 1.2.2 basic deployment; 1.2.3 custom Python actions; 1.2.4 self-check guardrails; 1.2.5 separate self-check model; 1.2.6 `NemoGuardrails` reference; 1.2.7 OpenTelemetry; 1.3 validation-only checks; 1.4 library flows; 1.5 common examples; 1.6 industry examples; 2 FMS Guardrails; 2.1 detectors; 2.2 orchestrator configuration; 2.3 Guardrails Gateway; 2.4 deployment; 2.5 AutoConfig; 2.6 OpenTelemetry; 2.7 metrics; 3 FMS usage scenarios |

## Related Official Sources

| Source | Role |
|--------|------|
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/configuring_your_model-serving_platform | KServe, vLLM, serving runtime, and OpenAI-compatible endpoint context |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_llama_stack/index | Llama Stack platform and API context |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_openshift_ai/managing-observability_managing-rhoai | OpenTelemetry, metrics, and platform observability context |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/evaluating_ai_systems/index | EvalHub, LM-Eval, and automated risk assessment context |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_model_registries/index | OCI model artifact and model lifecycle context |

## Supporting Project Sources

| Source | Role |
|--------|------|
| `docs/PLATFORM_BASELINE.md` | Active RHOAI/OCP baseline and source hierarchy |
| `AGENTS.md` | OpenShift safety guard and GitOps operating constraints |
| `.agents/skills/rhoai-model-serving-platform/SKILL.md` | Model-serving endpoint and runtime boundary |
| `.agents/skills/rhoai-llama-stack/SKILL.md` | Llama Stack platform boundary |
| `.agents/skills/rhoai-evaluation/SKILL.md` | Formal evaluation and risk-assessment boundary |
| `.agents/skills/rhoai-observability/SKILL.md` | Observability stack boundary |
| `.agents/skills/rhoai-api-tiers/SKILL.md` | API support posture boundary |

## Source Boundaries

- Product authority: the official Red Hat OpenShift AI 3.4 Guardrails guide
  above.
- The guide defines product behavior for NeMo Guardrails, FMS Guardrails,
  TrustyAI-managed guardrails resources, detector workflows, validation
  endpoints, and examples.
- The guide does not replace model-serving platform setup, Llama Stack
  platform setup, broader observability setup, or formal evaluation guidance.
- Upstream NVIDIA NeMo Guardrails and FMS links in the guide are supplemental
  background unless the Red Hat guide explicitly uses them for configuration
  structure.
- Verification: CRD schema checks, TrustyAI component state, route readiness,
  guardrails response status, detector health, metric endpoints, and Secret
  references.

## Unresolved Or Environment-Specific Items

- Active demo guardrails namespace and model endpoint.
  Verification: decide during clean-slate GitOps design and verify target
  routes before applying manifests.
- Active enterprise policy prompts.
  Verification: review with project documentation and business scenario
  ownership before use.
- Active detector images and detector model artifacts.
  Verification: prefer Red Hat registry images where documented and record any
  demo exception before committing.
- Active OpenTelemetry destination.
  Verification: use `rhoai-observability` once observability is introduced.
