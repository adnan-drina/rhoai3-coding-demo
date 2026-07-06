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
  for agentic AI, MCP gateway architecture (router, broker, controller),
  MCPServerRegistration CRs, MCPGatewayExtension, tool aggregation, session
  management, and Envoy ext_proc integration from the official Red Hat
  Connectivity Link 1.3 documentation. Do NOT use for installing MCP gateway
  (use rhcl-install-mcp), configuring MCP servers (use rhcl-mcp-config), or
  general Connectivity Link concepts (use rhcl-about).
---

# RHCL MCP Gateway

Use this skill to ground MCP gateway conceptual guidance in the official Red Hat
Connectivity Link 1.3 MCP gateway documentation. The MCP gateway is a
Technology Preview feature available on the `preview` update channel since
RHCL 1.3.3.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority.

## MCP Gateway Overview

The MCP gateway centralizes and manages connectivity for agentic AI applications
that access Model Context Protocol (MCP) servers. Application teams and platform
engineers can expose MCP servers as secure, protected services — the same way
they manage existing RESTful APIs.

Key capabilities:

- Aggregate MCP servers behind a single endpoint
- Scale agentic AI applications with connectivity outside of application code
- Manage access to and security of AI tools and MCP servers
- Add and remove MCP servers without restarting systems (dynamic state updates)
- Curate MCP server tools by creating virtual MCP servers

## Technology Preview Status

The MCP gateway is a Technology Preview feature. It is not supported with Red
Hat production SLAs and might not be functionally complete. Available on the
`preview` update channel. See Technology Preview Features Support Scope on the
Red Hat Customer Portal.

## Architecture

The MCP gateway extends the Envoy proxy server to handle MCP traffic from
agentic AI clients to backend MCP servers at the gateway ingress. Design goals:

- Works with the Gateway API as a routing configuration
- Envoy controls routing and traffic as the Gateway API implementation
- Istio serves as the gateway control plane in OpenShift with the Gateway API
- Connectivity Link provides AuthPolicy and rate-limiting via custom resources
- The MCP gateway focuses specifically on the MCP Protocol layer

### MCP Router

An Envoy `ext_proc` component that parses the MCP protocol and sets headers to
force correct routing to the correct MCP server.

Responsibilities:

- Parsing and validating the JSON-RPC request object (MCP message body)
- Setting key request headers: `:authority`, `:path`, `x-mcp-method`,
  `x-mcp-servername`, `x-mcp-toolname`, `mcp-session-id`
- Watching for `404` responses and invalidating the session store
- Handling session initialization and storage during tools call requests

### MCP Broker

A backend service that aggregates multiple MCP servers and presents them as a
unified MCP server to clients. Acts as the default backend for the `/mcp`
endpoint.

Responsibilities:

- Handles the handshake (`init`)
- Discovers tools from connected MCP servers and aggregates them into a
  unified list
- Validates that discovered MCP servers meet minimum protocol version and
  capabilities before including their tools
- Listens for updates and changes state dynamically
- Handles `notifications/tools/list_changed` from backend MCP servers
- Proxies notifications between MCP servers and registered clients
- Supports elicitation if the client supports it (interactive user input)

### MCP Discovery Controller

A Kubernetes-based controller that watches for changes to custom resources.

Responsibilities:

- Watches `MCPServerRegistration` CRs
- Maintains configuration from both `HTTPRoute` and `MCPServerRegistration` CRs
- Updates MCP broker and router config secret based on discovered
  `MCPServerRegistration` CRs and their target `HTTPRoutes`
- Reports status of `MCPServerRegistration` CRs

## Custom Resources

| Resource | Purpose |
|----------|---------|
| `MCPServerRegistration` | Register an MCP server with the gateway |
| `MCPGatewayExtension` | Configure the MCP gateway behavior |
| `HTTPRoute` | Gateway API routing (auto-managed or manual) |

## Known Issue (RHCL 1.3.3)

When the default `httpRouteManagement: Enabled` is set on an
`MCPGatewayExtension` CR, the controller only creates a single rule for `/mcp`
endpoints. The `/.well-known/oauth-protected-resource` rule is missing.

Workaround: set `httpRouteManagement: Disabled` in the `MCPGatewayExtension` CR
and use a manually managed `HTTPRoute` CR.

## Workflow

1. Read `references/official-doc-extraction.md` for detailed architecture.
2. Identify the component concern (router, broker, controller, CR).
3. For GitOps manifests, verify CRD availability on the cluster before
   committing (`oc get crd mcpserverregistrations.kuadrant.io`).
4. For live operations, use the repo environment guard.

## Related Skills

- Use `rhcl-about` for general Connectivity Link concepts and policy APIs.
- Use `rhcl-install-mcp` for installing the MCP gateway.
- Use `rhcl-release-notes` for version history and known issues.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
