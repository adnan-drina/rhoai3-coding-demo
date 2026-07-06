# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product baseline | `docs/PLATFORM_BASELINE.md` |
| Chapter title | Deploy models using Distributed Inference with llm-d |
| Chapter URL | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/deploy_models_using_distributed_inference_with_llm-d/index |
| Documentation category | Deploy |
| Retrieved date | 2026-06-10 |
| Sections used | Preface; Deploying models by using Distributed Inference with llm-d; Gateway discovery; Configuring authentication with Red Hat Connectivity Link; Enabling authentication and authorization; vLLM arguments reference; Configuring scheduler settings; Automatically scale Distributed Inference with llm-d; Managing mixed workloads with priority queuing; Distributed Inference with llm-d Observability |

## Related Official Sources

| Source | Role |
|--------|------|
| `docs/PLATFORM_BASELINE.md` | Active RHOAI and OCP version gate |
| Configuring your model-serving platform | KServe/vLLM platform and runtime prerequisite context |
| Deploying models | Standard model deployment workflow boundary before choosing llm-d |
| Govern LLM access with Models-as-a-Service | MaaS governance layer for llm-d endpoints |
| Managing resources: dashboard customization | Dashboard feature flags related to llm-d, Gateway discovery, and YAML preview |
| Working with accelerators | NVIDIA GPU and hardware profile prerequisite context; route profile lifecycle details to `rhoai-hardware-profiles` |
| Red Hat OpenShift AI API tiers | API stability review for alpha APIs and preview features |

## Source Boundaries

- Product configuration truth: the official RHOAI 3.4 llm-d guide and related
  active-baseline Red Hat product documentation.
- Demo policy: this skill can state rhoai3-demo preferences for when llm-d is
  appropriate, but CR fields and product behavior still require official docs
  or schema checks.
- Upstream Gateway API, llm-d, KServe, vLLM, or Kubernetes documentation is
  supplemental background only unless Red Hat docs link to it for the active
  product path.
- Red Hat articles, blogs, and `rh-brain` are supporting narrative and example
  sources only.

## Unresolved Or Verify Before GitOps

- Verify installed CRD schemas before committing long-lived GitOps manifests:
  `oc explain llminferenceservices.serving.kserve.io.spec`,
  `oc explain variantautoscalings.serving.kserve.io.spec`, and
  `oc explain inferenceobjectives.inference.networking.x-k8s.io.spec`.
- The official guide includes alpha API versions and multiple example shapes.
  Preserve the version used by the active docs only after validating the
  installed CRD supports it.
- Confirm dashboard flag field names in the installed `OdhDashboardConfig`
  schema before GitOps authoring.
- Confirm cluster-specific Gateway names, namespaces, listener
  `allowedRoutes`, and trusted namespace boundaries before using a shared
  Gateway.
