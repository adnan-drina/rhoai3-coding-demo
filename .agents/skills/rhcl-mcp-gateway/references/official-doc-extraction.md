# Official Doc Extraction

Use this extraction to ground MCP gateway content in the official RHCL 1.4
documentation. When implementation needs exact CR fields, controller behavior,
or protocol handling details, verify against the MCP gateway installation and
configuration documentation and active cluster schema.

## Support Posture

MCP gateway is a **Technology Preview** feature in RHCL 1.4. Technology Preview
features:

- Are not supported with Red Hat production SLAs.
- Might not be functionally complete.
- Are not recommended for production use.
- Provide early access to upcoming features for testing and feedback.

## Purpose and Goals

The MCP gateway centralizes and manages connectivity for agentic AI
applications accessing MCP servers. It provides:

- Aggregation of MCP servers behind a single endpoint.
- Scalable agentic AI application connectivity outside application code.
- Access management and security for AI tools and MCP servers.

Application teams and platform engineers operate and collaborate to expose MCP
servers as secure, protected services through the same patterns used for
RESTful APIs.

## Envoy Proxy Foundation

The Connectivity Link MCP gateway extends Envoy proxy capabilities:

- Envoy handles traffic from agentic AI clients to backend MCP servers at the
  gateway ingress.
- Envoy is a conformance-tested implementation of the Kubernetes Gateway API.
- The MCP gateway extends Envoy without manual configuration complexity.

## Architecture Design Principles

1. Must work with Gateway API as routing configuration.
2. Envoy controls routing and traffic as the Gateway API implementation.
3. MCP gateway focuses on the MCP Protocol layer.
4. Istio serves as the gateway control plane in OCP with Gateway API.
5. Connectivity Link provides AuthPolicy and rate-limiting CRs for the MCP
   endpoints.

## Component: MCP Router

The MCP router is an Envoy `ext_proc` (external processing) component that
parses the MCP protocol.

Responsibilities:

- Parse and validate JSON-RPC request objects (MCP message body).
- Set key request headers:
  - `:authority`
  - `:path`
  - `x-mcp-method`
  - `x-mcp-servername`
  - `x-mcp-toolname`
  - `mcp-session-id`
- Watch for 404 responses from MCP servers and invalidate session store.
- Handle session initialization and storage on behalf of requesting MCP
  clients during tool call requests.

## Component: MCP Broker

The MCP broker manages complexity of connecting to multiple AI services. It is
a backend service acting as the default MCP server for the `/mcp` endpoint.

Responsibilities:

- Handle the MCP handshake (`init`).
- Discover tools from connected MCP servers and aggregate into a unified list.
- Validate that discovered MCP servers meet minimum protocol version and
  capabilities before including their tools.
- Listen for updates and change state so agentic AI always has latest info.
- Handle `notifications/tools/list_changed` from backend servers.
- Proxy notification requests between clients and MCP servers.

The broker presents multiple backend MCP servers as a unified MCP server to
clients, eliminating per-server connection management.

## Component: MCP Discovery Controller

A Kubernetes-based controller that watches custom resources.

Responsibilities:

- Watch `MCPServerRegistration` CRs.
- Maintain configuration from both `HTTPRoute` and `MCPServerRegistration` CRs.
- Update the MCP broker and MCP router config secret based on discovered
  `MCPServerRegistration` CRs and the HTTPRoutes they target.
- Report status of `MCPServerRegistration` CRs.

CRs are the configuration interface for registering MCP servers and
configuring the gateway.

## Custom Resource: MCPServerRegistration

The `MCPServerRegistration` CR is the primary interface for registering MCP
servers with the gateway. Key facts from the official documentation:

- Watched by the MCP discovery controller.
- Targets `HTTPRoute` resources.
- Status is reported by the controller.
- The `prefix` field (renamed from `toolPrefix` in 1.4) provides server-level
  namespacing for both tools and prompts.

Do not invent additional fields, annotations, or behavior beyond what is
documented. Verify schema with:

```bash
oc explain mcpserverregistrations.spec
oc get crd mcpserverregistrations.connectivity.kuadrant.io -o yaml
```

## Integration Points

- **Gateway API**: HTTPRoute resources targeted by MCPServerRegistration.
- **Connectivity Link policies**: AuthPolicy and RateLimitPolicy can be
  attached to MCP gateway HTTPRoutes.
- **Istio**: Gateway control plane in OpenShift Container Platform.
- **Envoy**: Data plane handling MCP traffic.

## Verification Before Implementation

Before implementing MCP gateway resources, verify:

- MCP gateway components are installed (Technology Preview)
- MCPServerRegistration CRD exists on cluster
- Gateway and HTTPRoute resources are healthy
- Envoy ext_proc filter chain is configured
- MCP broker endpoint is responsive at `/mcp`

Discovery commands belong in validation checklists; do not run without
confirming the target cluster via the OpenShift safety guard.
