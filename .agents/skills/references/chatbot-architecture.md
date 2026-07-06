# Chatbot Architecture Reference

## Component Map

```text
stage-230-private-data-rag/chatbot/
├── Containerfile                 # UBI python-312, installs the vendored package
├── pyproject.toml                # pins llama-stack-client (0.7.x line)
├── start.sh                      # streamlit entrypoint
└── llama_stack_ui/               # vendored Llama Stack UI distribution
    └── distribution/ui/
        ├── modules/
        │   ├── api.py            # LlamaStackClient wiring (LLAMA_STACK_ENDPOINT/TIMEOUT)
        │   └── utils.py          # suggestions, source aggregation, MCP connector
        │                         # discovery, citation stripping, shield helpers
        └── page/
            ├── playground/
            │   ├── chat.py       # chat page: model/store/tool selection UI,
            │   │                 # suggestion grid, ResponseState, history
            │   ├── direct.py     # Direct mode: vector_stores.search + chat
            │   │                 # completions + sources panel
            │   └── agent.py      # Agent mode: Responses API, streamed
            │                     # file_search/MCP handling, fallback search
            ├── distribution/     # models/vector stores/providers/shields pages
            └── evaluations/      # evaluation preview pages
```

The previous repo-owned `rhoai_rag_chatbot/` package (app.py, config.py,
llama_stack_gateway.py, prompts.py, mcp.py, guardrails.py) was replaced by
this vendored distribution. The UI is discovery-driven: models, vector
stores, shields, and MCP connectors come live from the Stage 230 Llama Stack
service; the product-document corpus is populated by the GitOps/DSPA/KFP
path, not by browser uploads.

## Processing Modes

| Aspect | Direct mode | Agent-based mode |
|--------|-------------|------------------|
| API | `vector_stores.search()` then `chat.completions.create(stream=True)` | `responses.create(stream=True)` |
| Retrieval | explicit per-store search; context injected into the prompt | `file_search` tool with `include=["file_search_call.results"]` |
| Tools | none | `file_search`, `web_search`, `mcp` (via `connector_id`) |
| Sources panel | built in `search_vector_store_direct` from search results | built from streamed `file_search_call` results; fallback search runs only when the stream carried none (`state.sources_rendered`) |
| Citations | context entries labeled with guide titles; prompt instructs the model to name source guides | inline file-citation tokens stripped; attribution comes from the sources panel |
| Guardrails | server shields selectable when exposed | server shields selectable when exposed |

## Source Attribution Contract

Every ingested chunk carries corpus metadata attributes: `guide_slug`,
`topic`, `source_url`, `product`, `version`, plus record ids. The UI
aggregates retrieved chunks per guide (`summarize_search_sources`), renders a
markdown reference list (`format_sources_markdown`) with topic tags, best
relevance score, chunk count, and docs.redhat.com link, and persists it in
`state.tool_results` with type `markdown` so chat history replays it. Guide
display names come from `guide_title_from_slug` (`_SLUG_WORD_FIXES` handles
acronyms such as AutoRAG, Gen AI, RHOAI). Attribution is deterministic —
derived from what retrieval returned, not from model claims. Relevance
figures are raw hybrid-search scores and can exceed 1.0.

## MCP Integration (llama-stack 0.7.x)

- Server side: MCP servers are top-level `connectors:` entries in the run
  config (owned by `rhoai-llama-stack`); the HTTP surface is read-only
  (`GET /v1beta/connectors`, `GET /v1beta/connectors/{id}/tools`).
- The 0.7.x client library exposes neither toolgroups nor connectors, so
  `fetch_mcp_connectors` calls `/v1beta/connectors` with httpx directly.
- The chat page lists connectors as `mcp::<connector_id>` pills;
  `build_response_tools` maps a selection to
  `{"type": "mcp", "server_label": ..., "connector_id": ...}` and the server
  resolves the URL and calls the MCP server from the Llama Stack pod.
- Stage 230 registers Stage 220's read-only OpenShift MCP server as the
  `openshift` connector.

## State And Session Behavior

- `ResponseState` (chat.py) carries UI containers, streamed text, tool
  results, and `sources_rendered` for one assistant turn.
- Suggestion-backed collections are pre-selected by initializing
  `chat_vector_db_selector` from `RAG_QUESTION_SUGGESTIONS` keys. Streamlit
  session state persists across reruns, so config changes need a browser
  page reload to affect existing sessions.
- Conversations persist server-side (`/v1/conversations`, Postgres-backed).

## ConfigMap And Env Vars

| Env Var | Purpose |
|---------|---------|
| `LLAMA_STACK_ENDPOINT` | Llama Stack service URL without `/v1` |
| `LLAMA_STACK_TIMEOUT` | client request timeout (seconds) |
| `RAG_QUESTION_SUGGESTIONS` | JSON object keyed by vector-store name |

## Deployment Topology

```text
Namespace: enterprise-rag
Deployment: private-rag-chatbot
Image: image-registry.openshift-image-registry.svc:5000/enterprise-rag-build/private-rag-chatbot:latest
Build namespace: enterprise-rag-build
BuildConfig: private-rag-chatbot (binary; oc start-build --from-dir)
Route: private-rag-chatbot
OpenShift AI dashboard tile: redhat-ods-applications/rhoai-demo-private-rag-chatbot

Dependencies:
- lsd-enterprise-rag LlamaStackDistribution (responses API enabled)
- private-rag-postgres pgvector database
- stage230-rhoai-34-product-docs-kfp vector store populated by the Stage 230 KFP ingestion pipeline
- Stage 220 MaaS-backed Nemotron and governed gpt-4o-mini models
- Stage 220 openshift-mcp server (rhoai-mcp namespace) for tool calling
```

The dashboard tile is an `OdhApplication`, not an OpenShift `ConsoleLink`.
Keep it in `redhat-ods-applications`, point `spec.route` at
`enterprise-rag/private-rag-chatbot`, and preserve the documented dashboard
labels `app: odh-dashboard` and `app.kubernetes.io/part-of: odh-dashboard`.

The OpenShift BuildConfig and ImageStream live in `enterprise-rag-build`
instead of `enterprise-rag`. The runtime service account has
`system:image-puller` on that build namespace. This prevents Kueue from
admitting OpenShift build pods as plain RAG workload pods while preserving
queue enforcement for the RAG runtime project.
