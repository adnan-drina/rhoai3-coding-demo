---
name: rhdh-developer-lightspeed
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhdh"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Developer Hub"
description: >
  Use when integrating Developer Lightspeed AI assistant with Red Hat Developer
  Hub for AI-driven developer portal interaction. Covers LCORE sidecar
  architecture, LLM provider configuration (vLLM, OpenAI, Ollama, Vertex AI),
  RAG embeddings, safety guards, chat history, user feedback, Notebooks, and
  air-gapped mirroring. Do NOT use for MCP tool configuration (use
  rhdh-mcp-tools). Do NOT use for RHDH installation (use rhdh-install-*).
---

# RHDH Developer Lightspeed

Configure Red Hat Developer Lightspeed for Red Hat Developer Hub 1.10 — an
AI-powered virtual assistant providing chat assistance, RAG-grounded responses,
Notebooks for private research, and model evaluation capabilities.

## When to Use

- Configuring LLM provider connections (vLLM, OpenAI, Ollama, Vertex AI)
- Setting up Developer Lightspeed via Operator or Helm chart
- Configuring RBAC for `lightspeed.chat.read` / `lightspeed.chat.create`
- Enabling/disabling the Lightspeed floating action button (FAB)
- Configuring RAG embeddings and vector database
- Setting up safety guards (Llama Guard)
- Enabling user feedback collection and chat history persistence
- Configuring Notebooks (Developer Preview)
- Mirroring images for air-gapped environments
- Customizing system prompts for LLM behavior

## Architecture

- **LCORE (Lightspeed Core Service)**: Sidecar container managing LLM
  interactions, MCP tool runtime, safety providers, vector DB, chat history
- **RAG init container**: Copies embedding data to shared volume
- **FAB interface**: Floating action button on all RHDH pages
- **BYOM (Bring Your Own Model)**: No bundled model; connect any
  OpenAI-compatible inference provider

## Supported LLM Providers

| Provider | Env Variable | Notes |
|----------|-------------|-------|
| vLLM | `ENABLE_VLLM` | Append `/v1` to URL manually; used for RHOAI |
| OpenAI | `ENABLE_OPENAI` | Cloud-based inference |
| Ollama | `ENABLE_OLLAMA` | Desktop/cluster inference |
| Vertex AI | `ENABLE_VERTEX_AI` | Google Cloud Gemini models |

**Important**: Set `ENABLE_*` variables to `"true"` to activate. Leaving
unset disables. Setting to `"false"` does NOT disable (system checks if
defined).

## Prerequisites

- RHDH 1.10 deployed (Operator or Helm)
- Active API key/credentials for chosen LLM provider
- Cluster administrator privileges

## Validation

```bash
# Verify LCORE sidecar running
oc get pods -l app=backstage -o jsonpath='{.items[*].spec.containers[*].name}'

# Verify FAB appears (functional check in browser)
# Check RBAC permissions
oc logs deployment/<rhdh> -c backstage-backend | grep lightspeed
```

## Boundaries

- Lightspeed is enabled by default in RHDH 1.10
- Notebooks are Developer Preview — not production-ready
- Model evaluation framework is Developer Preview
- Red Hat does not collect or access feedback/chat data
- MCP server configuration within LCORE is covered by rhdh-mcp-tools skill
- Vertex AI has limited testing and custom architecture mapping

## References

- `references/source-capture.md` — source ledger
- `references/official-doc-extraction.md` — extracted procedures and config
