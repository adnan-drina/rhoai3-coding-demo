---
name: rhdh-developer-lightspeed
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhdh
  docs-version: "1.10"
  skill-group: "Developer Hub"
description: >
  Use when deciding or reviewing Developer Lightspeed for RHDH in this demo:
  it is enabled by default in 1.10, but the repo neither configures an LLM
  for it nor disables it (a recorded Gap), so the Operator still injects the
  unconfigured sidecar. Use it to close the Gap either by disabling the
  lightspeed flavour on the Backstage CR or by pointing it at the governed
  MaaS gateway. Do NOT use for Developer Lightspeed for MTA (use
  mta-lightspeed), MCP tools (use rhdh-mcp-tools), or OpenShift Lightspeed.
---

# RHDH Developer Lightspeed

Thin skill: the repo's open decision and its constraints; configuration
procedures are in the linked Developer Hub 1.10 sections. Detailed record:
`gitops/stages/070-advanced-app-platform/rhdh/README.md` (Alignment row
"Developer Lightspeed").

## When to use

- Closing the Developer Lightspeed Gap of `070-rhdh`.
- Someone asks why the portal shows (or should show) an AI chat.
- Reviewing extra containers in the `backstage-developer-hub` pod.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Current state: Backstage `developer-hub` declares no `spec.flavours`, no Lightspeed Secret, no `lightspeed-core` config; the product default (enabled) applies (Gap) | `gitops/stages/070-advanced-app-platform/rhdh/rhdh-instance/backstage.yaml` | [Configure to initialize the assistant][configure] |
| Option A, disable: `spec.flavours` entry `name: lightspeed`, `enabled: false`, which also stops the unconfigured sidecar injection | would change `backstage.yaml` | [Disable by using the Operator][disable] |
| Option B, configure: any model must be reached through the governed MaaS gateway with an owner-bound MaaS subscription and key, never a direct provider key (platform rule) | would add a Secret writer like the other Stage 070 hooks; see `rhoai-maas-governance` | [Configure by using the Operator][operator], [vLLM integration][vllm], [OpenAI integration][openai] |
| No decision recorded yet; the component README lists it as a Gap | `rhdh/README.md` | — |

## Procedure

1. Decide A or B with the architect; record the choice in the component
   README Alignment table in the same change.
2. Option A: add the flavour entry to `backstage.yaml`; Option B: add the
   Secret (env names per the 1.10 Operator section, values written at runtime,
   never in Git) and a MaaS subscription/auth policy pair for a dedicated
   owner, following the MTA pattern in `gitops/stages/070-advanced-app-platform/mta/jobs/configure-ai.yaml`.
3. Static checks: `./stages/070-advanced-app-platform/validate.sh --static`.
4. After the OpenShift safety guard in `AGENTS.md`, deploy with
   `./stages/070-advanced-app-platform/deploy.sh`; read-only checks:

   ```bash
   oc get backstage developer-hub -n rhdh -o jsonpath='{.spec.flavours}{"\n"}'
   oc get deployment backstage-developer-hub -n rhdh -o jsonpath='{.spec.template.spec.containers[*].name}{"\n"}'
   ```

## Pitfalls

- The 1.10 guide does not state a support level for the chat assistant; its
  Notebooks feature is Developer Preview. Do not present it as GA.
- Any `Backstage` change restarts the portal; keep `maxSurge: 0`.
- Option B adds model traffic and a credential: treat it as security
  sensitive (MaaS auth, API key handling) per `AGENTS.md`.
- Custom `lightspeed-stack.yaml` belongs in a ConfigMap mounted for the
  `lightspeed-core` container, or later changes (for example MCP servers) are
  overwritten ([Configure by using the Operator][operator]).

## Official documentation (Developer Hub 1.10)

| Topic | Section |
|---|---|
| Overview and architecture | [Chat assistance][chat], [Architecture][arch], [RAG embeddings][rag] |
| Configure or disable (Operator) | [Configure][configure], [Operator configuration][operator], [Disable][disable] |
| Responses, history, feedback | [Customize AI responses][customize] |
| Safety and model choice | [Safety guards][safety], [Model evaluation data][eval], [LLM requirements][llm] |
| Data handling | [User data security][data] |

## Related skills

`rhdh-configure`, `rhdh-mcp-tools`, `rhdh-getting-started-navigate`,
`rhoai-maas-governance`, `mta-lightspeed`.

[chat]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/interacting_with_red_hat_developer_lightspeed_for_red_hat_developer_hub/index#chat-assistance-with_interacting-with-developer-lightspeed-for-rhdh
[arch]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/interacting_with_red_hat_developer_lightspeed_for_red_hat_developer_hub/index#architecture-for-your-ai-backend-deployment_interacting-with-developer-lightspeed-for-rhdh
[rag]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/interacting_with_red_hat_developer_lightspeed_for_red_hat_developer_hub/index#retrieval-augmented-generation-rag-embeddings-for-grounded-ai-responses_interacting-with-developer-lightspeed-for-rhdh
[configure]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/interacting_with_red_hat_developer_lightspeed_for_red_hat_developer_hub/index#configure-to-initialize-the-ai-assistant_interacting-with-developer-lightspeed-for-rhdh
[operator]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/interacting_with_red_hat_developer_lightspeed_for_red_hat_developer_hub/index#configure-by-using-the-operator_configure-to-initialize-the-ai-assistant
[disable]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/interacting_with_red_hat_developer_lightspeed_for_red_hat_developer_hub/index#disable-by-using-the-operator_configure-to-initialize-the-ai-assistant
[customize]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/interacting_with_red_hat_developer_lightspeed_for_red_hat_developer_hub/index#customize-ai-responses_configure-to-initialize-the-ai-assistant
[safety]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/interacting_with_red_hat_developer_lightspeed_for_red_hat_developer_hub/index#configure-safety-guards-in-rhdh_get-ai-assisted-help-for-your-development-tasks
[eval]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/interacting_with_red_hat_developer_lightspeed_for_red_hat_developer_hub/index#ai-model-evaluation-data-to-select-the-right-ai-model_get-ai-assisted-help-for-your-development-tasks
[llm]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/interacting_with_red_hat_developer_lightspeed_for_red_hat_developer_hub/index#large-language-model-llm-requirements_appendix-llm-requirements
[vllm]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/interacting_with_red_hat_developer_lightspeed_for_red_hat_developer_hub/index#vllm-model-integration-for-high-throughput-inference_appendix-llm-requirements
[openai]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/interacting_with_red_hat_developer_lightspeed_for_red_hat_developer_hub/index#openai-model-integration-for-your-deployment_appendix-llm-requirements
[data]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/interacting_with_red_hat_developer_lightspeed_for_red_hat_developer_hub/index#appendix-manage-user-data-security_get-ai-assisted-help-for-your-development-tasks
