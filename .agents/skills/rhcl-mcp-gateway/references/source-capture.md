# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product family | Red Hat Connectivity Link |
| Product version | 1.3 (demo pins rhcl-operator.v1.3.4) |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Documentation category | Discover |
| Official guide | MCP gateway |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.3/html-single/mcp_gateway/index |
| Multi-page URL | https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.3/html/mcp_gateway/index |
| Capture date | 2026-07-06 |

## Captured Sections

From MCP gateway guide:

- Chapter 1: Introduction to the MCP gateway
  - About the MCP gateway (purpose, goals, Envoy proxy extension)
  - MCP gateway architecture (design goals, Istio control plane, Gateway API)
  - MCP gateway architectural components:
    - MCP router (ext_proc, JSON-RPC parsing, header setting, session management)
    - MCP broker (aggregation, tool discovery, notifications, elicitation)
    - MCP discovery controller (MCPServerRegistration CRs, HTTPRoute, config secret)

## Source Boundaries

This skill covers the "MCP gateway" conceptual guide only. It provides
understanding of the MCP gateway architecture, components, and their
responsibilities. It does not cover:

- Installing and deploying the MCP gateway (separate guide)
- Configuring MCP servers and MCPServerRegistration CRs (separate guide)
- General Connectivity Link policy APIs (separate guide)
- Release notes (separate guide)

## Custom Resources Documented

| Resource | API Group | Purpose |
|----------|-----------|---------|
| MCPServerRegistration | `kuadrant.io` | Register MCP servers with the gateway |
| MCPGatewayExtension | `kuadrant.io` | Configure MCP gateway behavior |
| HTTPRoute | `gateway.networking.k8s.io` | Gateway API routing |

## Technology Preview Notice

The MCP gateway is a Technology Preview feature introduced in RHCL 1.3.3
(released 30 April 2026). It is available on the `preview` update channel and
is not supported with Red Hat production SLAs.

## Version Deprecation Notice

RHCL 1.4.0 is deprecated. The demo stays on RHCL 1.3.4. All guidance in this
skill is grounded in RHCL 1.3 documentation only.

## Related Official Sources To Add Later

- Installing the MCP gateway
- Configuring MCP server registrations
- MCP gateway operational procedures
- MCP specification (external)
