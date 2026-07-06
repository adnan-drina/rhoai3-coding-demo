# Source Capture

## Official Source

| Field | Value |
|-------|-------|
| Product family | Red Hat Connectivity Link |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Documentation category | Discover |
| Official guide | MCP gateway |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/mcp_gateway/index |
| Multi-page URL | https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html/mcp_gateway/index |
| Capture date | 2026-07-06 |

## Captured Sections

- Chapter 1: Introduction to the MCP gateway
  - About the MCP gateway (purpose, goals, Envoy proxy, Gateway API)
  - MCP gateway architecture (design considerations, high-level goals)
  - MCP gateway architectural components:
    - MCP router (ext_proc, JSON-RPC parsing, headers, session handling)
    - MCP broker (aggregation, tool discovery, notifications, init handling)
    - MCP discovery controller (MCPServerRegistration CRs, HTTPRoute, config)

## Source Boundaries

This source covers only the introductory and architectural content. It does not
provide:

- MCP gateway installation procedures
- MCPServerRegistration CR schema or field-level documentation
- MCP server registration and configuration procedures
- AuthPolicy or RateLimitPolicy configuration for MCP endpoints
- Vault credential injection configuration
- Audit trail configuration
- Prompt federation configuration details
- Troubleshooting MCP gateway issues

## Related Official Sources

- RHCL 1.4 Installing the MCP gateway:
  https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html/installing_the_mcp_gateway/index
- RHCL 1.4 Registering MCP servers and creating policies:
  https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html/registering_mcp_servers_and_creating_policies/index
- RHCL 1.4 Release notes (MCP gateway 0.7.0 features):
  https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html/release_notes/index
- RHCL 1.4 Connectivity Link overview:
  https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html/red_hat_connectivity_link/index
