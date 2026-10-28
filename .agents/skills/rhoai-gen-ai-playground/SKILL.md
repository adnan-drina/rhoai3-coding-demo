---
name: rhoai-gen-ai-playground
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when changing, reviewing, or debugging the Stage 040 Gen AI playground in
  demo-sandbox: the 040-genai-studio Application, MCP discovery ConfigMap
  gen-ai-aa-mcp-servers (OpenShift-MCP, OpenShift-MCP-ReadWrite), the GPT-6
  Luna custom endpoint workaround, the saved agent OpenShift Ops Assistant and
  its MLflow prompt, the genai-playground-state PVC, playground dashboard flags,
  or a playground that gets no answer from a governed model. Do NOT use for
  MaaS subscriptions and API keys (use rhoai-maas-governance), MCP server
  runtimes in Stage 060, or MLflow itself (use rhoai-mlflow).
---

# RHOAI Gen AI Playground

Thin skill: repo decisions and pitfalls here, product behavior in the linked
OpenShift AI 3.5 sections. Detailed record:
`gitops/stages/040-governed-models-as-a-service/040-genai-studio/README.md`.

## When to use

- A playground in `demo-sandbox` (AI Coding Sandbox) shows no models, no MCP
  servers, or no answer.
- Someone changes the MCP list, the saved agent, its prompt, or the custom
  endpoint Job.
- A playground flag (`genAiStudio`, `aiAssetCustomEndpoints`,
  `agentConfigManagement`, `promptManagement`, `genAiTracing`) is in question.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Users create the playground from the dashboard; Git pre-provisions only platform-owned parts. The 3.5 playground runs on the OGX component (`OGXServer`), enabled with MaaS | `gitops/stages/040-governed-models-as-a-service/040-maas-platform/jobs/enable-maas-job.yaml` | [Prerequisites][prereq], [Configure a playground][configure] |
| Playground and MaaS dashboard flags are set by the Stage 040 enablement Job, not in the Stage 010 manifest | same Job | [Prerequisites][prereq] |
| Custom endpoints on, `externalProviders: false`, cluster ingress domain in `clusterDomains`, so endpoints may target the MaaS hostname but not third-party providers | same Job | [Enable custom endpoints][customon] |
| GPT-6 Luna reached through a Job-provisioned custom endpoint (`gen-ai-aa-custom-model-endpoints`, Secret `endpoint-api-key-gpt-6-luna-maas`) on subscription `playground-sandbox`: workaround for RHOAIENG-90257 (`max_tokens`) in 3.5.1 | `gitops/stages/040-governed-models-as-a-service/040-genai-studio/playground-endpoint-provisioner-job.yaml` | [Create custom endpoints][customuse] |
| MCP servers published to every playground: Git owns an empty `gen-ai-aa-mcp-servers` in `redhat-ods-applications`; `stages/040-governed-models-as-a-service/deploy.sh` writes the two keys from Stage 060, protected by `ignoreDifferences` | `gitops/stages/040-governed-models-as-a-service/040-genai-studio/mcp/`, `stages/040-governed-models-as-a-service/deploy.sh` | [Configuring MCP servers][mcp] |
| Saved agent "OpenShift Ops Assistant" (Developer Preview) as an `AgentProfile` ConfigMap on `qwen3-8-27b`, with an `allowedTools` list on `OpenShift-MCP` | `gitops/stages/040-governed-models-as-a-service/040-genai-studio/agent-profile-openshift-ops-assistant.yaml` | [Saved agents][agents] |
| Agent system prompt registered in the project's MLflow prompt registry by a hook Job | `gitops/stages/040-governed-models-as-a-service/040-genai-studio/openshift-ops-assistant-prompt.yaml`, `agent-prompt-provisioner-job.yaml` | [Reusable system instructions][prompts] |
| Retained 1 Gi state PVC `genai-playground-state`, mounted by the `playground-state-attacher` CronJob into a newly created playground (or re-attached when it already holds state) | `gitops/stages/040-governed-models-as-a-service/040-genai-studio/genai-playground-state-pvc.yaml` | [Resources created][resources] |
| Guardrails: Git-managed `NemoGuardrails` `nemoguardrails` with a real MaaS judge (pick **Qwen 3.8** as Guardrail model); see `rhoai-guardrails-safety` | `gitops/stages/040-governed-models-as-a-service/040-genai-studio/nemoguardrails.yaml` | [Guardrails][guardrails] |
| Tracing (Technology Preview) only per session, by explicit user choice | `stages/040-governed-models-as-a-service/README.md` ("Optional Studio Tracing") | [How tracing works][tracing] |

## Procedure

1. Change files under `gitops/stages/040-governed-models-as-a-service/040-genai-studio/`;
   MCP entries change only through `stages/040-governed-models-as-a-service/deploy.sh` (a reviewed
   change of a published value: `stages/040-governed-models-as-a-service/studio-mcp/publish.sh --replace`).
2. Deploy and validate after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   ./stages/040-governed-models-as-a-service/deploy.sh
   ./stages/040-governed-models-as-a-service/validate.sh --readiness
   ```

   The model-free persona qualification of the read-write entry is
   `stages/040-governed-models-as-a-service/catalog/qualify-mcp.sh`.

   Readiness checks the Application and the two MCP keys only; the custom
   endpoint, prompt and agent are user acceptance in the dashboard.
3. Read-only inspection (never print Secrets):

   ```bash
   oc get configmap gen-ai-aa-mcp-servers -n redhat-ods-applications -o jsonpath='{.data}'
   oc get configmap gen-ai-aa-custom-model-endpoints -n demo-sandbox
   oc get ogxservers.ogx.io -n demo-sandbox
   ```

## Pitfalls

- Playground (TP), custom endpoints, tracing (TP) and saved agents (Developer
  Preview) are preview features ([Overview][overview], [Saved agents][agents]).
- Deleting a playground removes it, and its auto-provisioned pgvector data,
  for every user of the project ([Delete a playground][delete]).
- Exported code is a template, not a runnable script ([Export][export]).
- Claude and GPT-6 Luna need Temperature 1 in the playground; GPT-6 Luna
  rejects `max_tokens` on the MaaS provider path (`040-external-models/README.md`).
- The custom endpoint ConfigMap format is the dashboard backend's internal
  format, not a documented API; re-check it on every upgrade.
- No answer from external models:
  `docs/TROUBLESHOOTING.md#gen-ai-playground-gets-no-answer-from-external-models`;
  local models fail:
  `docs/TROUBLESHOOTING.md#gen-ai-playground-external-model-works-but-local-models-fail`.
- MCP tools missing or failing:
  `docs/TROUBLESHOOTING.md#gen-ai-playground-mcp-tools-fail-or-return-no-tools`
  and `docs/TROUBLESHOOTING.md#application-outofsync-on-delegated-configmaps-or-playground-mcp-entries-vanish`.

## Official documentation (OpenShift AI 3.5)

| Topic | Section |
|---|---|
| Overview and support status | [Playground overview][overview] |
| Prerequisites, MCP, model requirements, AI asset endpoints | [Prerequisites][prereq], [MCP servers][mcp], [Model and runtime requirements][modelreq], [AI asset endpoints][aae] |
| Custom endpoints | [Enable][customon], [Create and use][customuse] |
| RAG and vector stores | [Test with RAG][rag], [Resources created][resources] |
| Guardrails, tracing | [Guardrails][guardrails], [Tracing][tracing] |
| Prompts, MCP testing, saved agents | [Reusable system instructions][prompts], [Test with MCP][mcptest], [Saved agents][agents] |
| Export, update, delete | [Export][export], [Update][update], [Delete][delete] |
| Troubleshooting | [Troubleshoot playground issues][ts] |

## Related skills

`rhoai-maas-governance`, `rhoai-mlflow`, `rhoai-guardrails-safety`,
`rhoai-dashboard-customization`, `rhoai-llama-stack`, `rhoai-troubleshoot`.

[overview]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/experimenting_with_models_in_the_gen_ai_playground/index#playground-overview_rhoai-user
[prereq]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/experimenting_with_models_in_the_gen_ai_playground/index#playground-prerequisites_rhoai-user
[mcp]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/experimenting_with_models_in_the_gen_ai_playground/index#configuring-model-context-protocol-servers_rhoai-user
[modelreq]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/experimenting_with_models_in_the_gen_ai_playground/index#model-and-runtime-requirements-for-the-playground_rhoai-user
[aae]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/experimenting_with_models_in_the_gen_ai_playground/index#About-the-ai-assets-endpoints-page_rhoai-user
[configure]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/experimenting_with_models_in_the_gen_ai_playground/index#configuring-a-playground-for-your-project_rhoai-user
[customon]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/experimenting_with_models_in_the_gen_ai_playground/index#enable-custom-endpoints-for-the-playground_rhoai-user
[customuse]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/experimenting_with_models_in_the_gen_ai_playground/index#create-and-use-custom-endpoints-in-the-playground_rhoai-user
[rag]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/experimenting_with_models_in_the_gen_ai_playground/index#testing-your-model-with-rag_rhoai-user
[resources]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/experimenting_with_models_in_the_gen_ai_playground/index#resources-created-when-you-create-a-playground_rhoai-user
[guardrails]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/experimenting_with_models_in_the_gen_ai_playground/index#configure-guardrails-in-the-playground_rhoai-user
[tracing]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/experimenting_with_models_in_the_gen_ai_playground/index#how-tracing-works-in-the-playground_rhoai-user
[prompts]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/experimenting_with_models_in_the_gen_ai_playground/index#reusable-system-instructions_rhoai-user
[mcptest]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/experimenting_with_models_in_the_gen_ai_playground/index#testing-with-model-context-protocol-servers_rhoai-user
[agents]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/experimenting_with_models_in_the_gen_ai_playground/index#saved-agents-in-the-gen-ai-playground_rhoai-user
[export]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/experimenting_with_models_in_the_gen_ai_playground/index#exporting-your-playground-configuration_rhoai-user
[update]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/experimenting_with_models_in_the_gen_ai_playground/index#updating-your-playground-configuration_rhoai-user
[delete]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/experimenting_with_models_in_the_gen_ai_playground/index#Deleting-a-playground-from-your-project_rhoai-user
[ts]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/experimenting_with_models_in_the_gen_ai_playground/index#troubleshooting-playground-issues_rhoai-user
