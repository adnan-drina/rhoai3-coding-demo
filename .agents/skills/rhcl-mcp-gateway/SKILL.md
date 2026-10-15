---
name: rhcl-mcp-gateway
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhcl
  docs-version: "1.4"
  skill-group: "Connectivity Link"
description: >
  Use when evaluating the Connectivity Link MCP gateway for this demo: what it
  is (router, broker, discovery controller), its Technology Preview status,
  how it would close the Stage 060 gap of no central MCP governance, and where
  it differs from the OpenShift AI MCP lifecycle operator the demo uses. Do NOT
  use for installing it (use rhcl-install-mcp), registering servers or
  policies (use rhcl-mcp-config), or general Connectivity Link concepts (use
  rhcl-about).
---

# Connectivity Link MCP gateway

Thin skill: the repo's position and links to the Connectivity Link 1.4 MCP
gateway book. Product architecture is in the [introduction][intro].

## When to use

- Designing central MCP authentication, authorization or rate limiting.
- Comparing the MCP gateway with the per-server controls in Stage 060.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| The MCP gateway is not installed; MCP servers run under the OpenShift AI MCP lifecycle operator with per-server access control | `gitops/stages/060-agent-runtime-and-agentops/060-mcp-platform/README.md`, `.../agent-tools/README.md` (Gap rows) | [About the MCP gateway][about] |
| Central MCP governance is recorded as a blocked gap, not planned work in this stage | same READMEs, "Alignment with official guidance" | — |

## Facts to check before proposing it

- Technology Preview in Connectivity Link 1.4 (no production SLA)
  ([About the MCP gateway][about]); the operator ships on the `preview` channel
  ([install book][install]).
- Components: an Envoy `ext_proc` router, a broker that aggregates servers
  behind `/mcp`, and a discovery controller that watches
  `MCPServerRegistration` and `HTTPRoute` ([Architecture][arch]).
- OpenShift AI 3.5 documents the MCP gateway Operator as a prerequisite for
  MCP management in its MCP catalog guide (cited in the 060 READMEs).

## Official documentation (Connectivity Link 1.4)

| Topic | Section |
|---|---|
| What it is | [About the MCP gateway][about] |
| Architecture | [MCP gateway architecture][arch] |
| Install, isolated instances | [Install the MCP gateway][install] |
| Registration and policies | [Register MCP servers and create policies][register] |

## Related skills

`rhcl-install-mcp`, `rhcl-mcp-config`, `rhcl-troubleshoot`.

[intro]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/mcp_gateway/index
[about]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/mcp_gateway/index#con-about-mcp-gateway_mcp-gateway-introduction
[arch]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/mcp_gateway/index#mcp-gateway-architecture_mcp-gateway-introduction
[install]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/install_the_mcp_gateway/index
[register]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/register_mcp_servers_and_create_policies/index
