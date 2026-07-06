---
name: rhcl-install-mcp
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhcl"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when installing the MCP gateway on single or multiple clusters, including
  the mcp-gateway operator, MCPGatewayExtension CR, Gateway object listeners,
  ReferenceGrant for cross-namespace, and session store configuration. Do NOT
  use for registering MCP servers or creating auth policies for MCP; use
  rhcl-mcp-config. Do NOT use for Connectivity Link core operator installation;
  use rhcl-install.
---

# RHCL Install MCP

Use this skill to ground MCP gateway installation decisions in official RHCL
1.4 documentation for the active baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority.

## Technology Preview Notice

MCP gateway is a Technology Preview feature in RHCL 1.4. It is not supported
with Red Hat production SLAs and might not be functionally complete.

## Key Concepts

- Separate operator: `mcp-gateway` from `redhat-operators` on the `preview`
  channel.
- Uses `OperatorGroup` with `targetNamespaces` (namespaced install).
- `MCPGatewayExtension` CR (apiVersion `mcp.kuadrant.io/v1alpha1`) deploys the
  MCP broker-router and links to a Gateway listener.
- Each namespace can have only one `MCPGatewayExtension`. Each Gateway can have
  only one targeting it.
- Automatic HTTPRoute creation (`mcp-gateway-route`) routes `/mcp` traffic.
- `httpRouteManagement: Disabled` for custom route control.
- `sessionStore` references a Redis secret for persistent sessions.
- `trustedHeadersKey` enables JWT-based tool filtering.
- `backendPingIntervalSeconds` controls upstream MCP server health (10–7200s,
  default 60).

## Workflow

1. Confirm the active RHCL baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Identify whether the task is:
   - initial MCP gateway operator install
   - Gateway object with MCP listener creation
   - MCPGatewayExtension CR deployment
   - cross-namespace ReferenceGrant setup
   - session store or trusted-headers configuration
4. For manifests, verify API versions against official docs and cluster schema.
5. Validate with verification commands from the extraction.

## Validation Signals

- `oc wait csv -n <ns> -l operators.coreos.com/mcp-gateway.<ns>="" --for=jsonpath='{.status.phase}'=Succeeded --timeout=5m`
- `oc wait --for=condition=Ready mcpgatewayextension/<name> -n <ns>`
- Automatic HTTPRoute exists: `oc get httproute mcp-gateway-route -n <ns>`
- EnvoyFilter present: `oc get envoyfilter -n <gw-ns> -l app.kubernetes.io/managed-by=mcp-gateway-controller`

## Related Skills

- `rhcl-install` for Connectivity Link core operator installation.
- `rhcl-mcp-config` for registering MCP servers and creating policies.
- `rhcl-configure` for general gateway policy deployment.
- `ocp-ingress-gateway-routes` for OCP Gateway API primitives.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
