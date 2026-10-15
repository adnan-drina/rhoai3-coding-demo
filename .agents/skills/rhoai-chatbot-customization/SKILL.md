---
name: rhoai-chatbot-customization
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when someone asks to customize "the chatbot" in this repo (suggested
  questions, system prompt, source attribution, Direct or Agent mode, MCP tool
  selection) or cites the former Stage 230 Streamlit RAG chatbot. That chatbot
  is not in this repo; the deployed chat surface is the Gen AI playground and
  its saved agent. Do NOT use for playground configuration, the saved agent
  and its MLflow prompt (use rhoai-gen-ai-playground), OGX servers (use
  rhoai-llama-stack), or guardrails (use rhoai-guardrails-safety).
---

# Chatbot Customization

Repo-specific skill. **Not deployed in this demo.** The vendored Llama Stack UI
chatbot (`stage-230-private-data-rag/chatbot/`, `gitops/stage-230-private-data-rag/`)
belonged to the predecessor repository. None of those paths exist here, and
the Llama Stack operator it depended on is kept `Removed`
(`gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-platform/datasciencecluster.yaml`).

## What to use instead

| Request | Deployed surface | Where in Git | Skill |
|---|---|---|---|
| Chat with a governed model, test prompts and MCP tools | Gen AI playground in `demo-sandbox` | `gitops/stages/040-governed-models-as-a-service/040-genai-studio/` | `rhoai-gen-ai-playground` |
| A reusable assistant with a reviewed system prompt and limited tools | Saved agent "OpenShift Ops Assistant" (Developer Preview) | `gitops/stages/040-governed-models-as-a-service/040-genai-studio/agent-profile-openshift-ops-assistant.yaml`, `openshift-ops-assistant-prompt.yaml` | `rhoai-gen-ai-playground`, `rhoai-mlflow` |
| Coding chat in the IDE | Dev Spaces workspaces with MaaS keys | `gitops/stages/070-advanced-app-platform/070-devspaces/` | `manage-devspaces` |
| A RAG chatbot over documents | none | not in Git | `rhoai-enterprise-rag` |

## If a custom chatbot is added

1. It belongs to a new stage planned with `project-demo-stage-authoring`
   (README, `deploy.sh`, `validate.sh`, GitOps component and README).
2. Call models only through MaaS with a subscription-scoped key; call OGX APIs
   with an OpenAI-compatible client ([OpenAI-compatible APIs][openai]).
3. Keep prompts and suggested questions in Git; for a playground agent prompt,
   use the MLflow prompt Job pattern of Stage 040.
4. Build images on Red Hat UBI bases; record any upstream image as a demo
   exception in the stage README.

## Official documentation (OpenShift AI 3.5)

| Topic | Section |
|---|---|
| Playground saved agents | [Saved agents][agents] |
| OGX APIs for an application | [OpenAI-compatible APIs][openai] |

## Related skills

`rhoai-gen-ai-playground`, `rhoai-llama-stack`, `rhoai-enterprise-rag`,
`rhoai-guardrails-safety`, `rhoai-mlflow`, `project-demo-stage-authoring`.

[agents]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/experimenting_with_models_in_the_gen_ai_playground/index#saved-agents-in-the-gen-ai-playground_rhoai-user
[openai]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ogx/index#openai-compatible-apis-in-ogx_rag
