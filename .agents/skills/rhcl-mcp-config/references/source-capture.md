# Source Capture

## Official Source

| Field | Value |
|-------|-------|
| Product family | Red Hat Connectivity Link |
| Product version | 1.4 |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Documentation category | Configure |
| Official guide | Registering MCP servers and creating policies |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/registering_mcp_servers_and_creating_policies/index |
| Capture date | 2026-07-06 |

## Captured Sections

- Chapter 1: Registering on-prem MCP servers
  - Understanding MCP server registration
  - Registering an MCP server (HTTPRoute + MCPServerRegistration)
  - MCPServerRegistration CR reference (all fields)
  - Verifying an MCP server registration
- Chapter 2: Registering external MCP servers
  - ServiceEntry for external MCP server
  - DestinationRule for TLS settings
  - HTTPRoute for external MCP server (URLRewrite)
  - Secret for backend credentials
  - AuthPolicy for external MCP server (OAuth pass-through)
  - MCPServerRegistration for external server
  - Verification
- Chapter 3: Creating virtual MCP servers
  - About virtual MCP servers
  - Authorization and filtering interaction
  - MCPVirtualServer CR creation
  - Verification with X-Mcp-Virtualserver header
  - Deleting virtual servers
- Chapter 4: Using authentication with MCP gateway
  - Understanding MCP gateway authentication
  - Configuring with AuthPolicy (JWT/Keycloak)
  - OAuth 2.0 Protected Resource Metadata
  - User-based tool filtering with trusted headers

## Source Boundaries

This skill covers MCP server registration, virtual server curation, and MCP
gateway authentication/authorization. It does not cover MCP gateway operator
installation, Gateway object creation, or general Connectivity Link policies
(DNSPolicy, TLSPolicy, RateLimitPolicy for non-MCP use cases).
