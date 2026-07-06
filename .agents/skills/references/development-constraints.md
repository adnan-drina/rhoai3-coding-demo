# Chatbot Development Constraints

Use these constraints when changing
`stage-230-private-data-rag/chatbot/llama_stack_ui/**`.

## Architecture Constraints

The active chatbot is a vendored Llama Stack UI distribution talking to the
Stage 230 `lsd-enterprise-rag` Llama Stack service. Keep demo-owned changes
small and localized so future upstream refreshes stay reviewable:

- `page/playground/chat.py` owns selection UI, suggestion defaults, history
  rendering, and `ResponseState`.
- `page/playground/direct.py` owns the Direct RAG flow: search, context
  building, citation instruction, sources panel.
- `page/playground/agent.py` owns the Responses API flow: request kwargs,
  streamed tool handling, MCP tool building, fallback search.
- `modules/utils.py` owns shared helpers: suggestions, source aggregation
  (`summarize_search_sources`/`format_sources_markdown`),
  `guide_title_from_slug`, `fetch_mcp_connectors`.
- Server-side concerns (connectors, providers, vector stores, responses API
  enablement) belong to `rhoai-llama-stack` and GitOps, not this app.

## Container Image Standards

The chatbot `Containerfile` should stay aligned with OpenShift image guidance:

- Use a Red Hat base image such as `registry.access.redhat.com/ubi9/python-312:latest`.
- Run as `USER 1001` for OpenShift random UID compatibility.
- Keep a single foreground process: `streamlit run` via `start.sh`.
- Do not use `hostPath`, privileged capabilities, or Docker Hub base images.
- Pin `llama-stack-client` to the deployed server's minor line; a mismatch
  fails with HTTP 426 on the first API call while the health endpoint stays
  green (validate.sh compares pod versions for exactly this reason).

## Build And Restart

Code changes require the Stage 230 OpenShift binary build:

```bash
python3 -m compileall -q stage-230-private-data-rag/chatbot
oc start-build private-rag-chatbot -n enterprise-rag-build \
  --from-dir=stage-230-private-data-rag/chatbot --wait
oc rollout restart deployment/private-rag-chatbot -n enterprise-rag
```

(`./stage-230-private-data-rag/deploy.sh` performs the same build as part of
a full deploy.) Env-only changes, such as `RAG_QUESTION_SUGGESTIONS`,
require an Argo CD sync plus the deployment restart. Browser sessions keep
their Streamlit session state; reload the page after config changes.

Before suggesting or running live cluster commands, follow the OpenShift
safety guard in `AGENTS.md`.

## Do Not Change Without Full Testing

- `llama-stack-client` version pin in `pyproject.toml`
- `LLAMA_STACK_ENDPOINT` base URL shape; `LlamaStackClient` expects no `/v1`
- the `include=["file_search_call.results"]` request parameter (removing it
  silently empties the Agent-mode sources panel and re-triggers the
  fallback search)
- the `mcp::` naming convention between the tool pills and
  `build_response_tools`
- the upstream image alternative `quay.io/rh-ai-quickstart/llamastack-dist-ui`
  (pins `llama-stack-client==0.6.0`, incompatible with the 0.7.x server)

## References

- Llama Stack platform skill: `.agents/skills/rhoai-llama-stack/SKILL.md`
- Guardrails skill: `.agents/skills/rhoai-guardrails-safety/SKILL.md`
- Current baseline Llama Stack docs: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_llama_stack/index
- Current baseline Guardrails docs: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/enabling_ai_safety_with_guardrails/index
- Current OCP image guidance: https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/images/creating-images
