---
name: rhdh-mcp-tools
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhdh"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Developer Hub"
description: >
  Use when integrating Model Context Protocol (MCP) server with Red Hat
  Developer Hub to enable AI client interaction with the developer portal.
  Covers MCP server plugin installation, tool plugins (Software Catalog,
  TechDocs, Scaffolder), token/endpoint configuration, client setup (Cursor,
  Continue, Lightspeed), and troubleshooting. Do NOT use for Developer
  Lightspeed chat configuration (use rhdh-developer-lightspeed). Do NOT use
  for RHDH installation.
---

# RHDH MCP Tools

Install and configure Model Context Protocol (MCP) server and tool plugins
in Red Hat Developer Hub 1.10 to expose portal capabilities (Software Catalog,
TechDocs, Scaffolder) to AI clients through standardized MCP tools.

## When to Use

- Installing `mcp-actions-backend` plugin
- Installing MCP tool plugins (catalog, techdocs, scaffolder extras)
- Configuring static token authentication for MCP clients
- Setting up MCP endpoints (SSE legacy or Streamable)
- Configuring Cursor, Continue, or Lightspeed as MCP clients
- Enabling Software Catalog, TechDocs, or Scaffolder MCP tools
- Troubleshooting MCP tool execution or authentication issues
- Configuring encryption and database for personal access tokens
- Managing MCP server toggles in the Lightspeed chat interface

## Key Concepts

### Support Status

- MCP plugin is **Developer Preview** — not production-ready
- Requires model with **tool calling** support (incompatible model = errors)
- Recommended: 7B+ parameter model with 32k+ context window

### Plugin Architecture

- **Backend server**: `backstage-plugin-mcp-actions-backend` — runs MCP tools
- **Tool plugins** (extras — replaces deprecated versions):
  - `software-catalog-mcp-extras` — catalog entity queries
  - `techdocs-mcp-extras` — documentation search/retrieval
  - `scaffolder-mcp-extras` — template actions, dry-runs, execution

### Endpoints

| Type | URL Pattern |
|------|-------------|
| Streamable | `https://<domain>/api/mcp-actions/v1` |
| SSE (Legacy) | `https://<domain>/api/mcp-actions/v1/sse` |

### Security Model

- Static token authentication via `backend.auth.externalAccess`
- Scaffolder tools use OBOU (On Behalf Of User) with bearer token
- Personal access tokens can be encrypted and stored in database

## Prerequisites

- RHDH 1.10 instance running
- AI model that supports tool calling
- MCP client (Cursor, Continue, or Lightspeed Core)

## Validation

```bash
# Verify MCP backend plugin installed
oc logs -c install-dynamic-plugins deployment/<rhdh> | grep "mcp-actions-backend"

# Verify tool plugins loaded
oc logs -c install-dynamic-plugins deployment/<rhdh> | grep "mcp"

# Check MCP tool logs
oc logs deployment/<rhdh> -c backstage-backend | grep "software-catalog-mcp-tool"

# Test MCP endpoint
curl -H "Authorization: Bearer $MCP_TOKEN" \
  https://<domain>/api/mcp-actions/v1
```

## Boundaries

- Developer Preview — no Red Hat production SLA
- Deprecated plugins: `software-catalog-mcp-tool`, `techdocs-mcp-tool`
  (use `extras` versions)
- OpenAI models require `mcpActions.namespacedToolNames: false`
- Some clients only support SSE (legacy) endpoint
- Iframe content not accessible through MCP tools

## References

- `references/source-capture.md` — source ledger
- `references/official-doc-extraction.md` — extracted procedures and config
