# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product baseline | `docs/PLATFORM_BASELINE.md` |
| Chapter title | Govern LLM access with Models-as-a-Service |
| Chapter URL | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/govern_llm_access_with_models-as-a-service/index |
| Documentation category | Deploy |
| Retrieved date | 2026-06-10 |
| Sections used | Deploy and manage Models-as-a-Service; overview; custom resources; prerequisites; database secret; TLS; deployment verification; publish models; subscriptions; authorization policies; API keys; CLI and API; observability; external OIDC; external models; administration troubleshooting; use models-as-a-service; user troubleshooting |

## Related Official Sources

| Source | Role |
|--------|------|
| `docs/PLATFORM_BASELINE.md` | Active RHOAI and OCP version gate |
| Configuring your model-serving platform | Serving platform and runtime prerequisite context |
| Deploying models | Direct model deployment and AI asset endpoint handoff before MaaS exposure |
| Deploy models using Distributed Inference with llm-d | llm-d model-serving prerequisite context when MaaS publishes llm-d models |
| Working with Llama Stack | Adjacent RAG/provider workflows that must not replace MaaS governance for shared external model access |
| Managing OpenShift AI dashboard customization | `OdhDashboardConfig` feature flag context |
| Managing observability | Platform observability context for MaaS usage metrics |
| Red Hat OpenShift AI API tiers | Support posture review for MaaS CRDs and preview features |
| Red Hat Connectivity Link 1.3 installing guide | RHCL installation, supported component prerequisites, and Kuadrant/Authorino context for the active demo cluster package while Stage 220 pins `rhcl-operator.v1.3.4` |
| Red Hat Connectivity Link 1.4 release notes | RHCL 1.4.0 deprecation notice and instruction to pin Connectivity Link plus dependent operators to the latest 1.3.z version |
| OpenShift 4.20 cert-manager Operator documentation | cert-manager prerequisite installation and `CertManager` operand behavior |
| Red Hat Ecosystem Catalog PostgreSQL 16 RHEL 9 image | Demo-local PostgreSQL 16 container image and environment-variable contract for the MaaS API-key database |

## Supporting Implementation References

| Source | Role |
|--------|------|
| https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant | Red Hat AI quickstart narrative for private code assistant, Nemotron 3 Nano, MaaS, vLLM/llm-d, Grafana, and AWS `g6e.2xlarge`/L40S requirements |
| https://github.com/rh-ai-quickstart/maas-code-assistant/tree/feat/upgrade-to-rhoai-3.4 | Source repository branch for RHOAI 3.4 MaaS implementation evidence, including `LLMInferenceService`, Gateway references, model resource sizing, Grafana examples, and the known-good `rhcl-operator.v1.3.4` pin |
| https://developers.redhat.com/articles/2026/05/25/route-external-and-local-llms-models-as-a-service | Red Hat Developer example for centralized routing across external and self-hosted LLMs, including `gpt-4o-mini`; use for narrative and model-choice context, not as CRD authority |
| `rhoai3-coding-demo/gitops/stages/030-private-model-serving/base/models/nemotron-3-nano-30b.yaml` | Working local reference for publishing Nemotron through `LLMInferenceService` with Gateway, scheduler pool, tool-calling args, reasoning parser args, prefix caching, resources, and `/dev/shm` |
| `rhoai3-coding-demo/gitops/stages/040-governed-models-as-a-service/base/models-maas-crds/local-modelrefs.yaml` | Working local reference for MaaSModelRef resources that publish local `LLMInferenceService` backends |

## Source Boundaries

- Product configuration truth: the official RHOAI 3.4 MaaS guide and related
  active-baseline Red Hat product documentation.
- Demo policy: this skill may state rhoai3-demo preferences such as using
  MaaS for governed OpenAI `gpt-4o-mini` access and local Nemotron exposure,
  but CR fields and product behavior still require official docs or schema
  checks.
- Red Hat articles, blogs, and `rh-brain` are supporting narrative and example
  sources only. Do not use them to override official product docs.
- Red Hat quickstarts and `rh-ai-quickstart` repositories are supporting
  implementation evidence only. Do not use them to override RHOAI 3.4 official
  docs or installed CRD schemas.
- The Red Hat Developer LiteLLM article is supporting narrative and model-choice
  evidence. It demonstrates an alternate gateway pattern; this demo uses the
  native RHOAI 3.4 MaaS `ExternalModel` path for external OpenAI governance.
- `rhoai3-coding-demo` references are sibling-demo implementation evidence
  only. Verify API versions, field names, Gateway, scheduler, and MaaS CRDs in
  the active cluster before committing Stage 220 GitOps.
- External provider examples such as OpenAI are governed external-access
  patterns. Provider credential scopes, rate limits, and model availability
  must be verified with the provider outside this skill.
- The active Stage 220 implementation pins Red Hat Connectivity Link to
  `rhcl-operator.v1.3.4` with manual InstallPlan approval. Do not relax the pin
  until RHOAI/RHCL/Gateway validation proves the newer operator version works
  end to end without generated-resource patches.

## Verified For The Active Demo Cluster

- See `working-configuration.md` for the validated Stage 220 design decisions,
  regression gates, and implementation traps discovered during live rollout.
- The active `rhoai3-demo` RHOAI 3.4 cluster exposes `Tenant`,
  `MaaSModelRef`, `ExternalModel`, `MaaSSubscription`, and `MaaSAuthPolicy` as
  `maas.opendatahub.io/v1alpha1`.
- Stage 220 uses `ExternalModel.metadata.name: gpt-4o-mini` and
  `MaaSModelRef.metadata.name: gpt-4o-mini` for the external OpenAI model,
  while keeping `ExternalModel.spec.targetModel: gpt-4o-mini`. This avoids a
  resource-name/provider-name split because the upstream model ID is also a
  valid Kubernetes Service name. The live MaaS controller creates a Kubernetes
  `Service` from the `ExternalModel` name, so dotted provider IDs must use a
  DNS-safe resource alias.
- Continue to verify installed CRD schemas before committing long-lived GitOps
  manifests after any RHOAI or RHCL upgrade:
  `oc api-resources | grep -i maas`,
  `oc get crd maasmodelrefs.maas.opendatahub.io`,
  `oc explain maasmodelrefs.maas.opendatahub.io.spec`,
  `oc explain maassubscriptions.maas.opendatahub.io.spec`,
  `oc explain maasauthpolicies.maas.opendatahub.io.spec`,
  `oc explain externalmodels.maas.opendatahub.io.spec`, and
  `oc explain tenants.maas.opendatahub.io.spec`.

## Unresolved Or Verify Before GitOps

- The official RHOAI 3.4 MaaS guide contains a group-name discrepancy that
  must be resolved from installed CRDs before authoring GitOps. The YAML
  examples for `MaaSModelRef`, `MaaSSubscription`, and `MaaSAuthPolicy` use
  `apiVersion: models.opendatahub.io/v1alpha1`, while the deployment
  verification section lists CRDs under `*.maas.opendatahub.io`. Treat the
  docs examples as schema examples that must be converted to the installed
  group/version for the target cluster.
- Verify the active `OdhDashboardConfig` field casing for vLLM MaaS enablement
  in the installed schema before authoring GitOps.
- The official guide shows MaaS resources in examples across
  `models-as-a-service`, model namespaces, and troubleshooting snippets. Use
  the active deployment's CRD and controller behavior to confirm the correct
  namespace for each resource before implementation.
- Use a phase-gated implementation when MaaS CRDs are absent: first deploy
  RHCL/Kuadrant/Authorino/Gateway/PostgreSQL, verify cert-manager as a platform
  prerequisite, enable
  `DataScienceCluster.spec.components.kserve.modelsAsService`, enable the
  required `OdhDashboardConfig` flags, and then rerun CRD/schema checks before
  authoring `MaaSModelRef`, `ExternalModel`, `MaaSSubscription`, or
  `MaaSAuthPolicy`.
- If the live cluster already installed an RHCL CSV newer than the Stage 220
  pin, perform an explicit operator lifecycle remediation. Do not work around
  the resulting Gateway failure by patching generated Kuadrant `AuthPolicy` or
  `EnvoyFilter` resources.
