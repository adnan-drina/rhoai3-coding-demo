# Source Capture

## Official Source

| Field | Value |
|-------|-------|
| Product family | Red Hat Connectivity Link |
| Product version | 1.4 |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Documentation category | Install |
| Official guide | Installing the MCP gateway |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/installing_the_mcp_gateway/index |
| Capture date | 2026-07-06 |

## Captured Sections

- Chapter 1: Installing and configuring MCP gateway
  - Installing the MCP gateway with OLM
  - Creating a Gateway object for your MCP gateway
  - Configuring MCP gateway listeners (MCP, HTTP, HTTPS)
  - Understanding the MCPGatewayExtension custom resource
  - Applying the MCPGatewayExtension custom resource
  - MCPGatewayExtension CR API reference (all fields)
  - Cross-namespace references with ReferenceGrant
  - Session store configuration
  - Trusted headers key pair

## Source Boundaries

This skill covers MCP gateway operator installation, Gateway listener
configuration, and MCPGatewayExtension deployment. It does not cover MCP server
registration, AuthPolicy for MCP, virtual MCP servers, or Connectivity Link
core policy deployment.

MCP gateway is Technology Preview in RHCL 1.4. Do not recommend for production
workloads without explicit user acknowledgment.
