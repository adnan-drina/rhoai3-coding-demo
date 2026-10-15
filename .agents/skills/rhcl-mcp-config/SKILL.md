---
name: rhcl-mcp-config
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhcl
  docs-version: "1.4"
  skill-group: "Connectivity Link"
description: >
  Use when designing MCP server registration and policies for a Connectivity
  Link MCP gateway in this demo: MCPServerRegistration for in-cluster and
  external servers, credential Secrets, MCPVirtualServer tool curation,
  OAuth/JWT authentication on the mcp listener, tool-level authorization with
  CEL on the mcps listener, revocation, and Vault credentials. Do NOT use for
  installing the MCP gateway (use rhcl-install-mcp), general Connectivity
  Link policies (use rhcl-configure), or the MCP servers Stage 060 runs today
  under the OpenShift AI lifecycle operator.
---

# MCP server registration and policies

Thin skill: no MCP gateway runs in the demo yet (see `rhcl-mcp-gateway`).
These are the facts an adoption must respect and where they are documented.

## When to use

- Designing how Stage 060 MCP servers would move behind a governed gateway.
- Reviewing a proposed `MCPServerRegistration`, `MCPVirtualServer` or MCP
  AuthPolicy.

## Repo constraints

| Constraint | Where | Official section |
|---|---|---|
| Credentials never in Git: MCP credential Secrets are created at runtime | `AGENTS.md` (Security and privacy) | [Register an MCP server][register] |
| Use the existing platform Keycloak (RHBK) as the OIDC issuer rather than a new identity provider | `gitops/stages/070-advanced-app-platform/070-identity/README.md` | [Authentication][authn] |
| Today's per-server controls (caller-token passthrough, Secret denial, local rate limit) are the baseline a gateway must not weaken | `gitops/stages/060-agent-runtime-and-agentops/060-agent-tools/README.md` | — |

## Facts to keep straight (verified against 1.4 on 2026-10-15)

- `MCPServerRegistration` and `MCPVirtualServer` are `mcp.kuadrant.io/v1alpha1`
  ([CR reference][cr], [Virtual servers][virtual]).
- Credential Secrets need the label `mcp.kuadrant.io/secret=true` ([Register][register]).
- Clients select a virtual server with the `X-Mcp-Virtualserver: namespace/name` header ([Virtual servers][virtual]).
- Authentication AuthPolicy targets the `mcp` listener; tool authorization
  targets the `mcps` listener and checks `tool:` roles from
  `x-mcp-toolname`/`x-mcp-servername` with CEL ([Authentication][authn], [Authorization][authz]).
- Revocation takes effect when a new token lacks the role; filtering revoked
  tools from `tools/list` needs extra broker configuration ([Revoke][revoke]).

## Official documentation (Connectivity Link 1.4)

| Topic | Section |
|---|---|
| In-cluster servers | [Register on-premise MCP servers][onprem], [CR reference][cr] |
| External servers | [Register external MCP servers][external] |
| Virtual servers | [Create virtual MCP servers][virtual] |
| Authentication / authorization | [Authentication][authn], [Authorization][authz] |
| Revocation | [Revoke tool access][revoke] |
| Vault credentials | [Vault with the MCP gateway][vault] |

## Related skills

`rhcl-mcp-gateway`, `rhcl-install-mcp`, `rhcl-troubleshoot`, `ocp-authentication-identity-providers`.

[onprem]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/register_mcp_servers_and_create_policies/index#mcp-gateway-register-on-prem-mcp-servers
[register]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/register_mcp_servers_and_create_policies/index#proc-register-mcp-server_mcp-gateway-register-on-prem-servers
[cr]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/register_mcp_servers_and_create_policies/index#ref-mcp-server-registration-cr_mcp-gateway-register-on-prem-servers
[external]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/register_mcp_servers_and_create_policies/index#mcp-gateway-register-ext-mcp-servers
[virtual]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/register_mcp_servers_and_create_policies/index#mcp-gateway-create-virtual-mcp-servers
[authn]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/register_mcp_servers_and_create_policies/index#mcp-gateway-authentication
[authz]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/register_mcp_servers_and_create_policies/index#mcp-gateway-authorization
[revoke]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/register_mcp_servers_and_create_policies/index#mcp-gateway-revoke-mcp-server-tool-access
[vault]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/register_mcp_servers_and_create_policies/index#mcp-gateway-vault
