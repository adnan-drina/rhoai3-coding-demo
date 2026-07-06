# Official Doc Extraction

Use this extraction to keep MCP gateway content grounded in official Red Hat
sources. When implementation needs exact CR fields, verify the active cluster
schema with `oc explain` or `oc get crd` before authoring GitOps manifests.

## Product Overview

The MCP gateway centralizes and manages connectivity for agentic AI applications
that access Model Context Protocol (MCP) servers. Application teams and platform
engineers operate and collaborate to expose MCP servers with the MCP gateway as
secure and protected services, just as they do with existing RESTful APIs.

The Connectivity Link implementation of the MCP gateway extends the benefits of
the Envoy proxy server to customized AI agent systems. Envoy handles traffic
from agentic AI clients to backend MCP servers at the gateway ingress. Envoy is
a conformance-tested implementation of the Kubernetes Gateway API.

## Technology Preview Status

MCP gateway is a Technology Preview feature only. Technology Preview features
are not supported with Red Hat production service level agreements (SLAs) and
might not be functionally complete. Red Hat does not recommend using them in
production. These features provide early access to upcoming product features,
enabling customers to test functionality and provide feedback during the
development process.

Available on the `preview` update channel since RHCL 1.3.3 (30 April 2026).

## Goals Achieved with MCP Gateway

- Aggregate MCP servers behind a single endpoint
- Grow agentic AI applications at scale, keeping connectivity outside of
  application development
- Manage access to and the security of AI tools and MCP servers
- Standardize access and security governance of MCP servers by setting policies
  that span clusters
- Add and remove MCP servers without restarting systems (dynamic state updates)
- Curate MCP server tools by creating virtual MCP servers

## Architecture Design Principles

- The MCP gateway must work with the Gateway API as a routing configuration
- Envoy controls routing and traffic as the implementation of the Gateway API
- The MCP gateway focuses on the MCP Protocol
- Use Istio as the gateway control plane in OpenShift Container Platform with
  the Gateway API
- Connectivity Link is used for other key features such as `AuthPolicy` and
  rate-limiting custom resources

## Component: MCP Router

The MCP router is an Envoy-focused `ext_proc` component that parses the MCP
protocol. When `ext_proc` parses the MCP Protocol, the router uses the protocol
to set headers to force the correct routing of the request to the correct MCP
server.

Responsibilities:

- Parsing and validating the JSON-RPC request object (the MCP message body)
- Setting key request headers:
  - `:authority`
  - `:path`
  - `x-mcp-method`
  - `x-mcp-servername`
  - `x-mcp-toolname`
  - `mcp-session-id`
- Watching for `404` responses from MCP servers and invalidating the session
  store
- Handling session initialization and storage on behalf of a requesting MCP
  client during a tools call request

## Component: MCP Broker

The MCP broker manages the complexity of connecting to multiple AI services
simultaneously. It aggregates multiple backend MCP servers and presents them as
a unified MCP server to clients. MCP clients or applications do not have to
manage a large set of MCP servers and configurations for each server.

The MCP broker is a backend service that acts as a default MCP server backend
for the `/mcp` endpoint.

Responsibilities:

- Handles the handshake (`init`)
- Discovers tools from connected MCP servers and aggregates them into a unified
  list
- Validates that discovered MCP servers meet minimum protocol version and
  capabilities before including their tools in the list
- Listens for updates and can change its state so that the agentic AI always
  has the latest information
- Handles notifications sent through whichever backend MCP server it is
  connected to, for example `notifications/tools/list_changed`
- Handles notification requests from clients and MCP servers by proxying from
  the MCP server notification to registered clients
- Supports elicitation if the client supports it (interactive user input
  requests from MCP servers)

## Component: MCP Discovery Controller

The MCP discovery controller is a Kubernetes-based controller that watches for
changes to custom resources (CRs). It uses CRs to configure the MCP gateway and
register MCP servers. The CRs are then turned into a configuration consumed by
the MCP gateway to route and present tools from registered MCP servers to
clients.

Responsibilities:

- Watching `MCPServerRegistration` CRs
- Maintaining a configuration from both `HTTPRoute` and `MCPServerRegistration`
  CRs
- Updating the MCP broker and MCP router config secret based on discovered
  `MCPServerRegistration` CRs and the `HTTPRoutes` they target
- Reporting the status of `MCPServerRegistration` CRs

## Custom Resources

### MCPServerRegistration

Registers an MCP server with the MCP gateway. The discovery controller watches
these CRs to configure routing and tool aggregation.

### MCPGatewayExtension

Configures the MCP gateway behavior. Includes `httpRouteManagement` field that
controls whether HTTPRoute objects are automatically created.

### HTTPRoute (Gateway API)

Standard Gateway API routing resource. When `httpRouteManagement: Enabled` is
set on MCPGatewayExtension, the controller auto-creates HTTPRoute rules.

## Known Issue (RHCL 1.3.3)

When the default setting `httpRouteManagement: Enabled` is set on an
`MCPGatewayExtension` custom resource, the MCP controller component
`buildGatewayHTTPRoute()` only creates a single rule for `/mcp` endpoints. The
`/.well-known/oauth-protected-resource` rule is missing.

Workaround: set `httpRouteManagement: Disabled` in the `MCPGatewayExtension` CR
in `config/mcp-gateway/` with a manually managed `HTTPRoute` CR.

## Request Flow

1. Agentic AI client sends MCP request to the gateway `/mcp` endpoint
2. Envoy receives the request at the gateway ingress
3. MCP router (`ext_proc`) parses the JSON-RPC body
4. Router sets routing headers (`x-mcp-servername`, `x-mcp-toolname`, etc.)
5. Envoy routes to the correct backend MCP server based on headers
6. MCP broker handles aggregation, tool discovery, and session management
7. Response flows back through Envoy to the client

## Elicitation Support

Available since RHCL 1.3.3. MCP servers can implement interactive workflows by
enabling user input requests. Requires client support for elicitation. See the
MCP specification for details on the elicitation protocol.

## Verification Commands

```bash
oc get crd mcpserverregistrations.kuadrant.io
oc get mcpserverregistrations -A
oc get mcpgatewayextensions -A
oc get pods -n <mcp-gateway-namespace> -l app=mcp-broker
oc get pods -n <mcp-gateway-namespace> -l app=mcp-router
```
