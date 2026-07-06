# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product baseline | `docs/PLATFORM_BASELINE.md` |
| Document title | Experimenting with models in the gen AI playground |
| Guide URL | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/experimenting_with_models_in_the_gen_ai_playground/index |
| Documentation category | Develop / Experimenting with models in the gen AI playground |
| Retrieved date | 2026-06-10 |
| Sections used | Preface; 1 Playground overview; 2 Playground prerequisites; 2.1 Cluster administrator prerequisites; 2.2 User prerequisites; 2.3 Configuring Model Context Protocol servers; 2.4 Model and runtime requirements; 2.5 AI assets endpoints page; 3 Configure a playground; 4 Enable custom endpoints; 5 Create and use custom endpoints; 6 Model experimentation; 6.1 Test model responses; 7 Test with RAG; 8 RAG settings; 9 Reusable system instructions; 9.1 Save prompts; 9.2 Reuse prompts; 10 Testing with MCP servers; 11 Exporting configuration; 12 Updating configuration; 13 Deleting playground; 15 Troubleshooting playground issues |

## Related Official Sources

| Source | Role |
|--------|------|
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_resources/customizing-the-dashboard | Dashboard configuration options and `OdhDashboardConfig` context |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_llama_stack/index | Llama Stack Operator, RAG, MCP, Responses API, and provider context |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/configuring_your_model-serving_platform | vLLM and model-serving runtime context |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_the_model_catalog/index | Catalog deployment and Add as AI asset endpoint handoff |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_and_monitoring_models | Deployed model operations context |
| https://access.redhat.com/support/offerings/techpreview | Technology Preview support scope |
| https://www.redhat.com/en/blog/model-context-protocol-server-red-hat-openshift-now-available-technology-preview | Red Hat blog for the newer MCP server for Red Hat OpenShift and preview posture |
| https://github.com/openshift/openshift-mcp-server | OpenShift-specific MCP server source, Helm chart defaults, read-only configuration, denied-resource guidance, and image source |

## Supporting Project Sources

| Source | Role |
|--------|------|
| `docs/PLATFORM_BASELINE.md` | Active RHOAI/OCP baseline and source hierarchy |
| `AGENTS.md` | OpenShift safety guard and GitOps operating constraints |
| `.agents/skills/rhoai-llama-stack/SKILL.md` | Llama Stack, RAG, MCP, provider, and API boundary |
| `.agents/skills/rhoai-model-serving-platform/SKILL.md` | vLLM runtime and model-serving boundary |
| `.agents/skills/rhoai-dashboard-customization/SKILL.md` | Dashboard configuration boundary |
| `.agents/skills/rhoai-model-catalog-workflows/SKILL.md` | Catalog-to-AI-asset endpoint workflow boundary |
| `.agents/skills/rhoai-chatbot-customization/SKILL.md` | Custom demo chatbot boundary |

## Source Boundaries

- Product authority: the official Red Hat OpenShift AI 3.4 gen AI playground
  guide above.
- The guide defines product dashboard workflows for exploratory model testing,
  RAG uploads, prompt reuse, MCP tool testing, custom endpoints, and exported
  code templates.
- It does not replace Llama Stack server configuration, model-serving runtime
  configuration, full MaaS governance, formal evaluation evidence, or custom
  chatbot application implementation.
- Verification: dashboard feature visibility, AI asset endpoints, selected
  models, playground loading, RAG document use, prompt save/load status, MCP
  server visibility and authorization, custom endpoint verification, exported
  template contents, and playground troubleshooting logs.
- For OpenShift MCP demos, use the newer `openshift/openshift-mcp-server`
  source and Red Hat preview material before falling back to generic Kubernetes
  MCP examples. The RHOAI integration point remains the platform-level
  `gen-ai-aa-mcp-servers` ConfigMap.

## Unresolved Or Environment-Specific Items

- Active demo default playground models.
  Verification: choose after the private Nemotron and external MaaS endpoint
  design is implemented.
- Active embedding model and embedding dimension for RAG experiments.
  Verification: list available AI asset endpoints and confirm the embedding
  endpoint metadata before use.
- External provider governance for OpenAI or other providers.
  Verification: define under MaaS governance before enabling external provider
  custom endpoints in shared demo environments.
- Project MLflow availability for prompt management.
  Verification: confirm MLflow service and prompt registry availability in the
  selected project before promising persistent prompts.
- MCP server list and authentication model.
  Verification: define the platform-level MCP `ConfigMap` and any token
  expectations before presenting MCP tools in the demo.
