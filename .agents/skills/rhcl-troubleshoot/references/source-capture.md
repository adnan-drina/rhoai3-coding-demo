# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product family | Red Hat Connectivity Link |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Documentation category | Troubleshoot |
| Official guide | Troubleshooting |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/troubleshooting/index |
| Multi-page URL | https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html/troubleshooting/index |
| Capture date | 2026-07-06 |

## Captured Sections

- Chapter 1: Troubleshooting and support for MCP gateway
  - MCP gateway pods not starting (ImagePullBackOff, CrashLoopBackOff,
    Pending, Init Container Failure)
  - Gateway and routing troubleshooting
    - Troubleshooting the gateway listener
    - Troubleshooting traffic not reaching the backend MCP server
    - Troubleshooting requests failing or bypassing the router
      (MCPGatewayExtension, EnvoyFilter, controller logs)
  - Troubleshooting an MCPGatewayExtension status of not ready
    (InvalidMCPGatewayExtension, ReferenceGrantRequired, Conflict)
  - Troubleshooting on-premise MCP server registration issues
    (MCPServerRegistration CR, targetRef, HTTPRoute, backend health, prefix)
  - Troubleshooting external MCP server connectivity issues
    (ServiceEntry, DestinationRule, DNS, TLS, egress)
  - Troubleshooting external MCP server authentication issues
    (Secret CR, credentialRef, broker logs)
  - Troubleshooting MCP gateway authentication issues
    (OAuth discovery, JWT validation, WWW-Authenticate, AuthPolicy,
    Authorino logs, issuer reachability)
  - Troubleshooting MCP gateway authorization issues
    (AuthPolicy rules, CEL evaluation, targetRef, sectionName,
    Kuadrant Operator health, Authorino CEL logs)

## Source Boundaries

This source covers:

- MCP gateway pod startup diagnostics
- Gateway listener, HTTPRoute, and EnvoyFilter troubleshooting
- MCPGatewayExtension status diagnostics
- On-premise and external MCP server registration issues
- External MCP server connectivity and authentication
- MCP gateway authentication (OAuth, JWT, WWW-Authenticate)
- MCP gateway authorization (AuthPolicy, CEL, Authorino)
- Diagnostic `oc` commands for each troubleshooting scenario

This source does NOT cover:

- Connectivity Link installation or operator lifecycle
- API management, console plugin, or RBAC configuration
- Observability, metrics, tracing, or dashboard configuration
- Gateway or policy creation procedures
- DNS, TLS, or rate limiting policy authoring (only troubleshooting)
- General OCP troubleshooting outside the Connectivity Link context

## Related Official Sources

- [Observability](https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html/observability/index)
- [Deploying Red Hat Connectivity Link](https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html/deploying_red_hat_connectivity_link/index)
- [Registering MCP servers and creating policies](https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html/registering_mcp_servers_and_creating_policies/index)
- [Installing the MCP gateway](https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html/installing_the_mcp_gateway/index)
