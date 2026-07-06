---
name: rhoai-chatbot-customization
metadata:
  author: rhoai3-demo
  version: 2.1.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Guide changes to the Stage 230 private RAG chatbot, a vendored Llama Stack
  UI distribution under stage-230-private-data-rag/chatbot/llama_stack_ui.
  Use when the user asks to customize the chatbot, change suggested
  questions, adjust source attribution, tune Direct or Agent-based answer
  behavior, fix llama-stack-client compatibility, or change MCP tool
  selection in the UI. Do NOT use for Llama Stack server/provider/
  vector-store/connector configuration (use rhoai-llama-stack), product
  NeMo/FMS guardrails resources (use rhoai-guardrails-safety), product Gen AI
  studio workflows (use rhoai-gen-ai-playground), or live troubleshooting
  without env-troubleshoot.
---

# Chatbot Customization

Structured workflow for modifying the active Stage 230 private RAG chatbot.
The chatbot is a vendored copy of the upstream Llama Stack UI distribution
(Streamlit), adapted for this demo and backed by the Stage 230
`LlamaStackDistribution`. It provides playground chat with Direct and
Agent-based processing, direct RAG over the RHOAI product-document vector
store with per-guide source attribution, MCP tool calling through registered
connectors, distribution inspection pages, and evaluation previews.

Use `rhoai-llama-stack` for the platform beneath this chatbot:
`LlamaStackDistribution`, providers, vector stores, MCP connectors
(top-level `connectors:` in the run config), OpenAI-compatible APIs, CA
trust, and HA/autoscaling.

Use `rhoai-guardrails-safety` for official NeMo Guardrails, FMS Guardrails,
TrustyAI guardrails CRs, detector services, guardrails endpoints, and API
payload validation. The chatbot only surfaces shields that the server
exposes.

Do not run scripts from `backup/legacy-implementation-2026-06-09/` unless the
user explicitly asks to restore or inspect the legacy implementation.

## Active Implementation Status

- source: `stage-230-private-data-rag/chatbot/llama_stack_ui/` (vendored
  distribution; the demo-owned changes live mostly under
  `distribution/ui/page/playground/` and `distribution/ui/modules/`)
- build resources: `gitops/stage-230-private-data-rag/app/base/build.yaml`
  (binary `BuildConfig` in `enterprise-rag-build`)
- deployment resources: `gitops/stage-230-private-data-rag/app/base/`
- validation: `stage-230-private-data-rag/validate.sh` (includes a
  client/server llama-stack version match check)

The previous repo-owned `rhoai_rag_chatbot/` package was replaced by this
vendored distribution; treat old references to it as historical.

## Architecture At A Glance

```text
private-rag-chatbot (Streamlit, vendored Llama Stack UI)
  distribution/ui/page/playground/chat.py    chat page: model/store/tool selection,
                                             suggestion grid, history, ResponseState
  distribution/ui/page/playground/direct.py  Direct mode: vector_stores.search +
                                             chat completions, sources panel
  distribution/ui/page/playground/agent.py   Agent mode: Responses API, file_search
                                             (include=file_search_call.results),
                                             MCP tools via connector_id
  distribution/ui/modules/utils.py           suggestions, source aggregation
                                             (summarize_search_sources), MCP
                                             connector discovery (/v1beta/connectors)
  distribution/ui/modules/api.py             LlamaStackClient wiring

Llama Stack service: lsd-enterprise-rag-service.enterprise-rag.svc:8321
Demo vector store: stage230-rhoai-34-product-docs-kfp (pgvector)
Generation: nemotron-3-nano-30b-a3b and governed gpt-4o-mini through MaaS
MCP: mcp::openshift toolgroup name in the UI -> `openshift` connector on the server
Config surface: LLAMA_STACK_ENDPOINT, LLAMA_STACK_TIMEOUT, RAG_QUESTION_SUGGESTIONS, RAG_DEFAULT_MODEL, RAG_SHIELD_FAIL_MODE
Guardrails: shield nemotron-3-nano-30b-a3b (Stage 240 NeMo via remote::nvidia); fail-closed on shield error by default
```

Key demo behaviors on top of upstream:

- collections with seeded suggestions are pre-selected on first load, so the
  suggestion grid renders immediately
- RAG answers render a per-guide "📚 Sources" panel (topic tags, relevance,
  docs.redhat.com links) built deterministically from chunk attributes
  (`guide_slug`, `topic`, `source_url`, `product`, `version`); raw chunks
  stay in a separate expander and history replays both
- Direct mode labels context passages with guide titles and instructs the
  model to name source guides in the answer
- Agent mode discovers MCP servers through `/v1beta/connectors` (the 0.7.x
  client has no toolgroups API) and passes
  `{"type": "mcp", "server_label", "connector_id"}` Responses tools
- `RAG_DEFAULT_MODEL` (substring match, default `nemotron`) sorts the
  matching model first in `chat.py` so the sidebar selectbox defaults to
  the local governed model instead of the first list entry
- guardrail selectors run the Stage 240 shield around every turn.
  `client.safety.run_shield()` in llama_stack_client 0.7.x accepts only
  `shield_id` and `messages`; passing the older `params` argument raises
  TypeError before any network call. On a shield error the helpers **fail
  closed** by default (block the turn with a visible message);
  `RAG_SHIELD_FAIL_MODE=open` restores the answer-anyway behavior. Verify
  shield behavior through the app's own helpers (`run_input_shields` /
  `run_output_shields` via `oc exec` + python), not just the server REST API
- the last two suggestion chips are Stage 240 guardrail demo prompts
  (input rail: prompt injection; output rail: generated PII record) — keep
  them aligned with the demo script in
  `stage-240-guardrails-and-safety/README.md`

## When To Use

- Adding, removing, or editing suggested questions or their default selection
- Changing source-attribution rendering (sources panel, context labels,
  citation instruction)
- Tuning Direct vs Agent-based processing behavior or tool selection UI
- Fixing `llama-stack-client` compatibility after a RHOAI/Llama Stack update
- Surfacing additional Llama Stack runtime state in distribution pages

## Key Files

| File | What to edit |
|------|-------------|
| `.../ui/page/playground/chat.py` | Selection UI, suggestion grid, defaults, history rendering, `ResponseState` |
| `.../ui/page/playground/direct.py` | Direct RAG search, context building, citation instruction, sources panel |
| `.../ui/page/playground/agent.py` | Responses API request, streamed tool handling, MCP tool building, fallback search |
| `.../ui/modules/utils.py` | `get_question_suggestions`, `summarize_search_sources`, `format_sources_markdown`, `guide_title_from_slug`, `fetch_mcp_connectors` |
| `stage-230-private-data-rag/chatbot/pyproject.toml` | Pinned `llama-stack-client` (must match the server minor line) |
| `gitops/stage-230-private-data-rag/app/base/configmap-chatbot.yaml` | `RAG_QUESTION_SUGGESTIONS` and endpoint/timeout env |
| `gitops/stage-230-private-data-rag/app/base/deployment-chatbot.yaml` | Image, endpoint, probes, resources, env wiring |
| `gitops/stage-230-private-data-rag/dashboard/base/odhapplication-rag-chatbot.yaml` | Dashboard application tile pointing at the chatbot Route |

## Instructions

### Read Before You Write

1. Read `stage-230-private-data-rag/README.md` (Chatbot Flow) and
   `stage-230-private-data-rag/PLAN.md`.
2. If touching code architecture, read `references/chatbot-architecture.md`.
3. If changing prompts or attribution text, read
   `references/prompt-engineering.md`.
4. If changing `llama-stack-client`, verify the deployed server version. A
   stale client fails with HTTP 426 `Client version ... is not compatible
   with server version ...`; validate.sh checks this by comparing the client
   version in the chatbot pod with the server version in the LSD pod.

### Change Suggested Questions

Suggestions render in the chat page once a collection with seeded questions
is selected; suggestion-backed collections are pre-selected on first page
load. The grid shows four questions, more behind "Show More".

1. Edit `RAG_QUESTION_SUGGESTIONS` in
   `gitops/stage-230-private-data-rag/app/base/configmap-chatbot.yaml`. The
   JSON object is keyed by vector store NAME (for example
   `stage230-rhoai-34-product-docs-kfp`).
2. Prefer questions from the committed AutoRAG benchmark
   (`stage-230-private-data-rag/data/rhoai-product-docs/autorag/benchmark_data.json`)
   so live answers match measured pattern quality. Keep the two Stage 240
   guardrail demo chips (last two entries: prompt-injection input block and
   generated-PII output block) unless the guardrails demo is retired with
   them.
3. Argo CD applies the ConfigMap; restart the deployment to reload env:

   ```bash
   oc rollout restart deployment/private-rag-chatbot -n enterprise-rag
   ```

4. Browser sessions created before the change keep their old Streamlit
   session state; reload the page to see new defaults.

### Change Source Attribution

1. Chunk metadata is the source of truth: `guide_slug`, `topic`,
   `source_url`, `product`, `version` travel with every ingested chunk.
   Aggregation lives in `summarize_search_sources` /
   `format_sources_markdown` in `modules/utils.py`; guide display names come
   from `guide_title_from_slug` (extend `_SLUG_WORD_FIXES` for new acronyms).
2. Direct mode: `search_vector_store_direct` renders the panel and labels
   context entries; the citation instruction lives in `build_rag_messages`.
3. Agent mode: the Responses request sets
   `include=["file_search_call.results"]` and
   `handle_agent_output_item_done` renders the panel from streamed results;
   `state.sources_rendered` suppresses the duplicate fallback search.
4. Relevance figures are raw hybrid-search scores (can exceed 1.0); rank
   with them, do not present them as percentages.

### Change MCP Tool Selection

The server side (connector registration) belongs to `rhoai-llama-stack`. In
this UI:

1. `fetch_mcp_connectors` reads `/v1beta/connectors` directly (the 0.7.x
   client library has no connectors or toolgroups surface).
2. The chat page lists connectors as `mcp::<connector_id>` pills;
   `build_response_tools` maps a selection to
   `{"type": "mcp", "server_label": ..., "connector_id": ...}`.
3. A model-driven tool-use claim requires `mcp_list_tools`, `mcp_call`, and
   a final `message` in the Responses output; a plain answer is not proof.

### Build And Deploy Cycle

Code changes rebuild the image from `stage-230-private-data-rag/chatbot/`
with the GitOps-managed binary BuildConfig, then restart the deployment:

```bash
python3 -m compileall -q stage-230-private-data-rag/chatbot
oc start-build private-rag-chatbot -n enterprise-rag-build \
  --from-dir=stage-230-private-data-rag/chatbot --wait
oc rollout restart deployment/private-rag-chatbot -n enterprise-rag
```

Keep build resources out of the Kueue-managed `enterprise-rag` runtime
namespace; build pods are infrastructure, not AI workloads. Env-only changes
need only an Argo CD sync plus a deployment restart.

Do not switch the active RHOAI 3.4 demo back to
`quay.io/rh-ai-quickstart/llamastack-dist-ui:0.2.45` without retesting
client compatibility. That image pins `llama-stack-client==0.6.0`; Stage 230
uses the `0.7.x` client line for the observed RHOAI 3.4 Llama Stack server.

### Validation

After any code or config change:

1. Run `python3 -m compileall -q stage-230-private-data-rag/chatbot`.
2. Run `./stage-230-private-data-rag/validate.sh` against the guarded target
   cluster after deployment.
3. Ask a seeded suggestion question and confirm the answer names its source
   guides and the "📚 Sources" panel lists them with docs.redhat.com links.
4. In Agent-based mode with `mcp::openshift` selected, ask a bounded cluster
   question and confirm the `mcp_list_tools`/`mcp_call` chain in the output.

For detailed architecture, container constraints, and prompt patterns, read:

- `references/chatbot-architecture.md`
- `references/development-constraints.md`
- `references/prompt-engineering.md`
