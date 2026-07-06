# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product baseline | `docs/PLATFORM_BASELINE.md` |
| Document title | Build AI/Agentic Applications with Llama Stack |
| Guide URL | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_llama_stack/index |
| Documentation category | Administer / Working with Llama Stack |
| Retrieved date | 2026-06-10 |
| Sections used | 1 Overview of Llama Stack; 1.1 Llama Stack APIs; 1.2 OpenAI-compatible APIs; 1.3 file citation annotations; 1.4 API provider support; 2 Activating the Llama Stack Operator; 3 Deploying a Llama Stack server; 4 Llama Stack application examples; 4.1 RAG stack; 4.1.2 vector databases; 4.1.6 LlamaStackDistribution examples; 4.1.7 ingestion; 4.1.8 querying; 4.1.9 Docling; 4.1.10 search modes; 4.2 RAG evaluation; 4.3 PostgreSQL; 4.4 Qdrant; 4.5 OAuth; 4.6 ABAC; 4.7 self-signed certificates; 4.8 HA and autoscaling |

## Related Official Sources

| Source | Role |
|--------|------|
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/configuring_your_model-serving_platform | vLLM and model-serving platform context |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/working_with_accelerators/enabling-nvidia-gpus_accelerators | NVIDIA GPU prerequisite path |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/installing_and_uninstalling_openshift_ai_self-managed/working-with-certificates_certs | CA bundle handling for Llama Stack |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/working_with_ai_pipelines | Pipeline context for Docling ingestion |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/evaluating_ai_systems | Evaluation context outside the Llama Stack guide |
| https://access.redhat.com/articles/rhoai-supported-configs-3.x | Active Llama Stack Operator version and support information |
| https://access.redhat.com/support/offerings/techpreview | Technology Preview support scope |

## Supporting Project Sources

| Source | Role |
|--------|------|
| `docs/PLATFORM_BASELINE.md` | Active RHOAI/OCP baseline and source hierarchy |
| `AGENTS.md` | OpenShift safety guard and GitOps operating constraints |
| `.agents/skills/rhoai-model-serving-platform/SKILL.md` | vLLM/model serving boundary |
| `.agents/skills/rhoai-nvidia-gpu-accelerators/SKILL.md` | NVIDIA GPU prerequisite boundary |
| `.agents/skills/rhoai-chatbot-customization/SKILL.md` | Chatbot UI and prompt boundary |
| `.agents/skills/rhoai-certificate-management/SKILL.md` | Broader certificate handling boundary |
| `.agents/skills/rhoai-kfp-pipeline-authoring/SKILL.md` | Pipeline implementation boundary |
| `.agents/skills/rhoai-model-evaluation/SKILL.md` | Evaluation implementation boundary |

## Source Boundaries

- Product authority: the official Red Hat OpenShift AI 3.4 Llama Stack guide
  above.
- Llama Stack is documented as Technology Preview in RHOAI 3.4.
- This guide defines Llama Stack APIs, supported provider posture, Operator
  activation, `LlamaStackDistribution` configuration, RAG examples, vector
  store choices, authentication, CA trust, and HA/autoscaling.
- It does not replace model-serving platform configuration, GPU enablement,
  KFP pipeline authoring, full production database administration, or chatbot
  application behavior.
- Verification: `DataScienceCluster` component state, Llama Stack Operator pod,
  `LlamaStackDistribution` state, server logs, provider configuration, vector
  store operations, Responses API requests, OAuth/ABAC status checks, and
  autoscaling resource state.

## Unresolved Or Environment-Specific Items

- Active demo Llama Stack model and embedding provider IDs.
  Verification: list models from the deployed Llama Stack server and align
  with the active model-serving implementation.
- Active vector store choice for Stage 230: resolved to remote PostgreSQL with
  pgvector. Validated with metadata-filtered hybrid search in `cluster-qt67m`.
  Inline Milvus and FAISS remain options for development or future stages.
- GitOps representation for Keycloak/OIDC or another identity provider.
  Verification: define only after the demo authentication model is chosen.
- Production database topology for PostgreSQL metadata and pgvector.
  Verification: define backup, HA, retention, monitoring, and ownership in
  `docs/OPERATIONS.md` when implemented.
- Direct external OpenAI provider use from Llama Stack.
  Verification: use only after project governance approves it; otherwise route
  external models through MaaS.
