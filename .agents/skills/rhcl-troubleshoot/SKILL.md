---
name: rhcl-troubleshoot
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhcl"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when troubleshooting common Connectivity Link issues including MCP
  gateway pods not starting, gateway listener problems, traffic not reaching
  backend MCP servers, requests failing or bypassing the router,
  MCPGatewayExtension not ready, on-premise and external MCP server
  registration issues, external MCP server connectivity and authentication
  failures, MCP gateway authentication issues (OAuth discovery, JWT
  validation, WWW-Authenticate headers), and MCP gateway authorization issues
  (AuthPolicy, CEL evaluation, Authorino). Do NOT use for Connectivity Link
  installation, deployment, API management, or observability configuration;
  use the relevant rhcl-* skill. Do NOT invent diagnostic commands, error
  codes, or recovery steps not documented in the official source.
---

# RHCL Troubleshoot

Use this skill to ground Connectivity Link troubleshooting guidance in the
official Red Hat Connectivity Link 1.4 documentation for the active baseline
in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority. This skill captures diagnostic
procedures for MCP gateway, gateway routing, server registration,
authentication, and authorization issues.

## Key Troubleshooting Areas

### MCP Gateway Pods Not Starting

Common states: `ImagePullBackOff` (check image access), `CrashLoopBackOff`
(check logs), `Pending` (check resources), Init Container Failure (check
RBAC).

### Gateway and Routing

Three diagnostic layers by error type:

- **Connection Refused/Timeout**: check the listener (port, load balancer, TLS)
- **HTTP 404**: check the `HTTPRoute` CR (route rejected or not programmed)
- **503 or bypass**: check API-level and Envoy filters (`EnvoyFilter` presence,
  label matching, controller logs)

### MCPGatewayExtension Not Ready

Common conditions: `InvalidMCPGatewayExtension` (invalid targetRef),
`ReferenceGrantRequired` (cross-namespace), `Conflict` (duplicate extension).

### MCP Server Registration

On-premise: verify `MCPServerRegistration` CR status, `targetRef` pointing to
correct `HTTPRoute`, backend server running, service endpoints, tool prefix
configuration.

External: verify `ServiceEntry` CR, `DestinationRule` CR, DNS resolution,
external connectivity, TLS settings.

### Authentication

OAuth discovery: check `HTTPRoute` path for `/.well-known/`, verify
`AuthPolicy` exclusion for well-known paths. JWT validation: check `AuthPolicy`
configuration, Authorino logs, JWT claims, issuer reachability. Missing
`WWW-Authenticate`: check `AuthPolicy` response configuration.

### Authorization

`AuthPolicy` targeting, `sectionName` matching `Gateway` listener, Kuadrant
Operator pod health, CEL evaluation errors in Authorino logs.

## Workflow

1. Confirm the active RHCL baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Identify the symptom category:
   - pod startup failures
   - gateway listener or routing issues
   - MCPGatewayExtension status problems
   - MCP server registration (on-premise or external)
   - authentication failures (OAuth, JWT, WWW-Authenticate)
   - authorization failures (AuthPolicy, CEL, Authorino)
4. Follow the documented diagnostic commands in order.
5. Do not run cluster-modifying commands without verifying the cluster context.

## Related Skills

- Use `rhcl-develop` for API management, console plugin, RBAC, and API product
  workflows.
- Use `rhcl-observability` for metrics, tracing, dashboards, access logs, and
  MCP gateway observability.
- Use `ocp-ingress-gateway-routes` for Gateway API and HTTPRoute
  infrastructure.
- Use `ocp-security-rbac-scc` for general OCP RBAC and SCC troubleshooting.
- Use `rhoai-troubleshoot` for live demo environment troubleshooting.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
