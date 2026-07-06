---
name: rhcl-mcp-config
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhcl"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when registering MCP servers and configuring auth policies for the MCP
  gateway, including MCPServerRegistration CRs for on-prem and external servers,
  MCPVirtualServer CRs for curated tool collections, AuthPolicy for MCP
  sessions with OAuth/JWT, and credential secrets. Do NOT use for MCP gateway
  operator installation; use rhcl-install-mcp. Do NOT use for general
  Connectivity Link policies; use rhcl-configure.
---

# RHCL MCP Config

Use this skill to ground MCP server registration and MCP gateway authentication
decisions in official RHCL 1.4 documentation for the active baseline in
`docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority.

## Technology Preview Notice

MCP gateway is a Technology Preview feature in RHCL 1.4. It is not supported
with Red Hat production SLAs and might not be functionally complete.

## Key Concepts

- `MCPServerRegistration` CR (apiVersion `mcp.kuadrant.io/v1alpha1`) registers
  each backend MCP server with the gateway.
- `prefix` field namespaces tool/prompt names to avoid collisions (lowercase
  a-z, 0-9, underscore only; must start with letter or digit).
- `targetRef` points to an HTTPRoute that routes to the backend MCP server.
- `credentialRef` references a Secret for backend authentication.
- Secrets must have label `mcp.kuadrant.io/secret: "true"`.
- `MCPVirtualServer` CR creates curated subsets of tools/prompts from
  aggregated servers, accessed via `X-Mcp-Virtualserver` header.
- External MCP servers require ServiceEntry, DestinationRule, HTTPRoute, and
  optionally an AuthPolicy for OAuth pass-through.
- MCP gateway auth uses Kuadrant AuthPolicy with JWT validation and
  OAuth 2.0 Protected Resource Metadata discovery.

## Workflow

1. Confirm the active RHCL baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Identify whether the task concerns:
   - on-prem MCP server registration
   - external MCP server registration (ServiceEntry + DestinationRule)
   - credential secrets for backend auth
   - MCPVirtualServer for tool curation
   - AuthPolicy for MCP gateway (JWT/OAuth)
   - OAuth discovery configuration
   - verifying server registration and tool discovery
4. For manifests, verify API versions against official docs.
5. Validate with verification commands from the extraction.

## Validation Signals

- `oc get mcpsr -A` shows all registered servers with READY=True
- `oc get mcpsr <name> -n <ns> -o yaml` shows `status.discoveredTools`
- `oc get mcpvirtualserver -A` lists virtual servers
- MCP session test: POST `/mcp` with `initialize` then `tools/list`

## Related Skills

- `rhcl-install-mcp` for MCP gateway operator installation.
- `rhcl-install` for Connectivity Link core operator installation.
- `rhcl-configure` for general gateway policy deployment.
- `rhoai-maas-governance` for RHOAI MaaS governance integration.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
