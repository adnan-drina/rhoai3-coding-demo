# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product baseline | `docs/PLATFORM_BASELINE.md` |
| Document title | Configuring your model-serving platform |
| Chapter URL | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/configuring_your_model-serving_platform/index |
| Documentation category | Administer / Configuring your model-serving platform |
| Retrieved date | 2026-06-10 |
| Sections used | 1 About model-serving platforms; 1.1 About model serving; 1.1.1 Model serving platform; 1.1.2 NVIDIA NIM model serving platform; 1.2 Model-serving runtimes; 1.2.1 ServingRuntime; 1.2.2 InferenceService; 1.3 Model-serving runtimes for accelerators; 1.3.5 Supported model-serving runtimes; 1.3.6 Tested and verified model-serving runtimes; 2 Configuring model servers; 2.1 Enabling the model serving platform; 2.2 Enabling speculative decoding and multi-modal inferencing; 2.3 Adding a custom model-serving runtime; 2.4 Adding a tested and verified runtime; 3 Configuring model servers on the NVIDIA NIM model serving platform; 3.1 Enabling the NVIDIA NIM model serving platform; 4 Customizing model deployments; 4.1 Customizing runtime parameters; 4.2 Customizable runtime parameters; 4.3 Customizing the vLLM runtime; 4.4 Setting a default cluster-wide deployment strategy |

## Related Official Sources

| Source | Role |
|--------|------|
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/installing_and_uninstalling_openshift_ai_self-managed/installing-and-deploying-openshift-ai_install | KServe and model-serving component installation context |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/working_with_accelerators/enabling-nvidia-gpus_accelerators | NVIDIA GPU prerequisite path |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/working_with_accelerators/working-with-hardware-profiles_accelerators | Hardware profile context for accelerator-backed serving |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_resources/customizing-the-dashboard | Dashboard flags that expose or hide model serving features |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_openshift_ai/creating-project-scoped-resources_managing-rhoai | Project-scoped serving runtime template context |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/deploying_models | User-facing model deployment workflows |
| https://access.redhat.com/articles/rhoai-supported-configs-3.x | Supported and tested runtime posture |
| https://access.redhat.com/articles/7089743 | Tested and verified runtimes support context |

## Supporting Project Sources

| Source | Role |
|--------|------|
| `docs/PLATFORM_BASELINE.md` | Active RHOAI/OCP baseline and source hierarchy |
| `AGENTS.md` | OpenShift safety guard and GitOps operating constraints |
| `.agents/skills/rhoai-self-managed-installation/SKILL.md` | KServe and model serving component install boundary |
| `.agents/skills/rhoai-nvidia-gpu-accelerators/SKILL.md` | NVIDIA-only accelerator readiness policy |
| `.agents/skills/rhoai-hardware-profiles/SKILL.md` | Hardware profile and recommended accelerator tag policy |
| `.agents/skills/rhoai-project-scoped-resources/SKILL.md` | Project-scoped serving runtime template boundary |
| `.agents/skills/rhoai-dashboard-customization/SKILL.md` | Dashboard feature visibility flags |
| `.agents/skills/project-gitops-authoring/SKILL.md` | GitOps authoring conventions for manifests |

## Supporting Implementation References

| Source | Role |
|--------|------|
| https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant | Red Hat AI quickstart narrative for Nemotron 3 Nano, MaaS, vLLM/llm-d, Grafana, and AWS `g6e.2xlarge`/L40S testing context |
| https://github.com/rh-ai-quickstart/maas-code-assistant | Source repository for model-specific Nemotron vLLM args, resource sizing, `LLMInferenceService`, MaaS tier, RBAC, and Grafana examples |
| `rhoai3-coding-demo/gitops/stages/030-private-model-serving/base/models/nemotron-3-nano-30b.yaml` | Working local reference for the demo Nemotron modelcar source, vLLM image, tool-calling args, reasoning parser args, prefix caching, batched-token budget, scheduler shape, probes, resources, and `/dev/shm` volume |

## Source Boundaries

- Product authority: the official Red Hat OpenShift AI 3.4 model-serving
  platform configuration guide above.
- This skill defines administrator configuration of the model-serving platform,
  runtimes, runtime parameters, NIM enablement, and deployment strategy.
- It does not replace the installation documentation for KServe or OpenShift AI
  components.
- It does not define the full user flow for deploying a model, testing model
  endpoints, or creating a MaaS offering.
- It summarizes official example manifests. Do not copy long upstream examples
  into GitOps without checking the active CRD schema and image provenance.
- `rhoai3-coding-demo` references are sibling-demo implementation evidence
  only. Use them to preserve working demo intent, then verify against current
  official docs and installed CRDs.
- Verification: dashboard enablement, runtime enabled state, `ServingRuntime`
  and `InferenceService` YAML, deployment status, runtime arguments in
  `spec.predictor.model.args`, environment variables in
  `spec.predictor.model.env`, and endpoint smoke tests where appropriate.

## Unresolved Or Environment-Specific Items

- Active demo serving API shape for `nemotron-3-nano-30b-a3b`.
  Current decision: Stage 210 uses direct `InferenceService`; Stage 220 should
  use `LLMInferenceService` for MaaS after RHOAI 3.4 schema verification.
- Exact Red Hat-supported vLLM image reference for the active baseline and
  model.
  Verification: use official docs, installed runtime templates, Red Hat
  registry metadata, or active cluster resources. Do not pin an image unless
  Red Hat documentation or validated artifact guidance requires it.
- Dashboard backing fields for model serving platform enablement and default
  deployment strategy.
  Verification: use official docs or installed schema before automating these
  dashboard settings.
- NIM adoption in this demo.
  Verification: decide separately and document NGC credential handling before
  enabling the NIM application.
- Runtime parameters for models not listed in the official chapter.
  Verification: use official model/runtime documentation and record the source
  before adding arguments.
