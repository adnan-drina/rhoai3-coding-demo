---
name: rhcl-mcp-gateway
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhcl"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when explaining MCP gateway concepts, Model Context Protocol connectivity
  for agentic AI applications, and MCP gateway architecture. Do NOT use for
  installing MCP gateway (use rhcl-install-mcp) or configuring MCP servers (use
  rhcl-mcp-config).
---

# RHCL MCP Gateway

Use this skill to ground MCP gateway conceptual and architectural content in
the official RHCL 1.4 MCP gateway documentation.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is the product authority. This skill captures the MCP gateway
introduction, architecture, and component descriptions.

## Support Posture

MCP gateway is a **Technology Preview** feature in RHCL 1.4. Technology Preview
features are not supported with Red Hat production SLAs and might not be
functionally complete. Red Hat does not recommend using them in production.

## Product Definition

The MCP gateway centralizes and manages connectivity for agentic AI
applications that access Model Context Protocol (MCP) servers. Application
teams and platform engineers can expose MCP servers as secure, protected
services — just as with existing RESTful APIs.

Key goals:

- Aggregate MCP servers behind a single endpoint.
- Scale agentic AI applications while keeping connectivity outside application
  code.
- Manage access to and security of AI tools and MCP servers.

The Connectivity Link MCP gateway extends Envoy proxy capabilities to
customized AI agent systems. Envoy handles traffic from agentic AI clients to
backend MCP servers at the gateway ingress and is a conformance-tested
implementation of the Kubernetes Gateway API.

## Architecture

The MCP gateway builds on top of Envoy proxy routing capabilities with
MCP-specific handling.

Design principles:

- Works with Gateway API as routing configuration.
- Envoy controls routing and traffic as the Gateway API implementation.
- MCP gateway focuses on the MCP Protocol layer.
- Istio serves as the gateway control plane in OCP with Gateway API.
- Connectivity Link provides AuthPolicy and rate-limiting CRs.

### Architectural Components

#### MCP Router

An Envoy `ext_proc` component that parses the MCP protocol:

- Parses and validates JSON-RPC request objects (MCP message body).
- Sets key request headers: `:authority`, `:path`, `x-mcp-method`,
  `x-mcp-servername`, `x-mcp-toolname`, `mcp-session-id`.
- Watches for 404 responses and invalidates the session store.
- Handles session initialization and storage during tool call requests.

#### MCP Broker

A backend service that aggregates multiple MCP servers into a unified endpoint:

- Handles the MCP handshake (`init`).
- Discovers tools from connected MCP servers and aggregates them into a
  unified list.
- Validates that discovered servers meet minimum protocol version and
  capabilities before including their tools.
- Listens for updates and maintains current state.
- Handles `notifications/tools/list_changed` from backend servers.
- Proxies notifications between MCP servers and registered clients.

The broker is the default MCP server backend for the `/mcp` endpoint.

#### MCP Discovery Controller

A Kubernetes controller that watches custom resources:

- Watches `MCPServerRegistration` CRs.
- Maintains configuration from both `HTTPRoute` and `MCPServerRegistration`
  CRs.
- Updates the MCP broker and router config secret based on discovered
  registrations and their targeted HTTPRoutes.
- Reports status of `MCPServerRegistration` CRs.

## Custom Resources

| CR | Purpose |
|----|---------|
| `MCPServerRegistration` | Register MCP servers with the gateway |
| `HTTPRoute` | Gateway API routing targeted by registrations |

## Demo Relevance

The MCP gateway enables governed connectivity between agentic AI coding
assistants (Continue, OpenCode) and backend MCP servers through the same
gateway infrastructure used for LLM model access. This aligns with the demo's
trust boundary model where all external AI tool access flows through governed
infrastructure.

## Workflow

1. Confirm the active RHCL baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Identify whether the task concerns:
   - MCP gateway concepts and architecture (this skill)
   - RHCL product overview and API policies (use `rhcl-about`)
   - MCP gateway installation (use `rhcl-install-mcp` when available)
   - MCP server registration and policies (use `rhcl-mcp-config` when
     available)
4. Do not invent MCPServerRegistration fields, controller behavior, or
   protocol handling beyond what is documented.
5. Always note Technology Preview support posture when referencing MCP gateway.

## Related Skills

- Use `rhcl-about` for RHCL product concepts and policy APIs.
- Use `rhcl-release-notes` for MCP gateway feature announcements and changes.
- Use `rhoai-maas-governance` for RHOAI MaaS integration.
- Use `ocp-ingress-gateway-routes` for OCP Gateway API and routing.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
