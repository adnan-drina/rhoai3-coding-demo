# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product baseline | `docs/PLATFORM_BASELINE.md` |
| Document title | Managing and monitoring models |
| Guide URL | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/managing_and_monitoring_models/index |
| Documentation category | Administer / Managing and monitoring models |
| Retrieved date | 2026-06-10 |
| Sections used | 1 Managing model-serving runtimes; 1.1 Adding a custom model-serving runtime; 2 Managing and monitoring models; 2.1 Setting a timeout for KServe; 2.2 Deploying models by using multiple GPU nodes; 2.3 Configuring an inference service for Kueue; 2.4 Configuring an inference service for Spyre; 2.5 Optimizing performance and tuning; 2.5.1 GPU requirements; 2.5.2 RAG and summarization considerations; 2.5.3 Inference performance metrics; 2.5.4 Metrics-based autoscaling; 2.5.5 Autoscaling guidelines; 2.6 Monitoring models; 2.7 Grafana model performance dashboards; 3 NVIDIA NIM model serving platform model selection and metrics |

## Related Official Sources

| Source | Role |
|--------|------|
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/configuring_your_model-serving_platform/index | Model-serving platform and runtime configuration context |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_openshift_ai/managing-workloads-with-kueue | Kueue workload management context |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_openshift_ai/managing-observability_managing-rhoai | OpenShift AI observability stack context |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/working_with_accelerators/enabling-nvidia-gpus_accelerators | NVIDIA GPU monitoring and accelerator prerequisite context |
| https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/monitoring | User Workload Monitoring context |
| https://access.redhat.com/support/offerings/techpreview | Technology Preview support scope |

## Supporting Implementation Sources

| Source | Role |
|--------|------|
| https://rhpds.github.io/llm-d-showroom/modules/workshop/llm-d/04-module-02.html | Workshop pattern for observing single-GPU vLLM behavior with metrics, Grafana, a pre-provisioned `benchmark-data` PVC, `prompts.csv`, and a short GuideLLM concurrent benchmark. |
| https://github.com/rhpds/llm-d-showroom | Workshop source repository for llm-d showroom exercises, images, and notebooks. |
| https://github.com/rh-aiservices-bu/rhaoi3-llm-d | Red Hat AI services reference repository containing shared-prefix GuideLLM prompt data and `grafana-dashboard-llm-performance.json`. Treat as an implementation pattern, not product API authority. |

## Supporting Project Sources

| Source | Role |
|--------|------|
| `docs/PLATFORM_BASELINE.md` | Active RHOAI/OCP baseline and source hierarchy |
| `AGENTS.md` | OpenShift safety guard and GitOps operating constraints |
| `.agents/skills/rhoai-model-serving-platform/SKILL.md` | Model-serving platform boundary |
| `.agents/skills/rhoai-observability/SKILL.md` | General observability stack boundary |
| `.agents/skills/rhoai-nvidia-gpu-accelerators/SKILL.md` | NVIDIA GPU prerequisite boundary |
| `.agents/skills/rhoai-kueue-workload-management/SKILL.md` | Queue management boundary |
| `.agents/skills/rhoai-model-evaluation/SKILL.md` | Model evaluation and benchmark evidence boundary |

## Source Boundaries

- Product authority: the official Red Hat OpenShift AI 3.4 Managing and
  monitoring models guide above.
- This guide defines deployed-model administration, monitoring, autoscaling,
  Grafana dashboards, and NVIDIA NIM model/metrics operations.
- It does not replace model-serving platform installation or enablement,
  general OpenShift AI observability setup, GPU Operator enablement, TrustyAI
  quality/fairness monitoring, or evaluation workflow implementation.
- Multi-node vLLM and metrics-based autoscaling are Technology Preview in the
  captured guide.
- Verification: `InferenceService`, `ServingRuntime`, `LocalQueue`,
  `ScaledObject`, User Workload Monitoring ConfigMaps, `ServiceMonitor`,
  `PodMonitor`, GrafanaDashboard resources, NIM `Account` CRs, and runtime
  endpoint smoke tests.
- The llm-d showroom and Red Hat AI services repositories are source-grounded
  implementation patterns for benchmarks and dashboards. They do not override
  official RHOAI/OCP docs for CR fields, supported features, API tiers, or
  operator support posture.

## Unresolved Or Environment-Specific Items

- Active demo autoscaling metrics and SLO thresholds.
  Verification: define after load tests with representative input/output token
  distributions.
- Active Grafana deployment model.
  Verification: define whether Grafana dashboards are part of active GitOps or
  an operator runbook.
- Whether multi-node vLLM belongs in the demo.
  Verification: decide per hardware plan; current default GPU intent is one
  GPU worker node.
- NVIDIA NIM adoption.
  Verification: only add NIM model list and metrics workflows after explicit
  demo adoption and credential handling decisions.
