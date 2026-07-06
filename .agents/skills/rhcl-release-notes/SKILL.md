---
name: rhcl-release-notes
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhcl"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when checking RHCL 1.3 release notes, new features, bug fixes, known
  issues, async releases (1.3.1 through 1.3.5), MCP gateway Technology Preview
  introduction, wasm-shim fixes, Limitador storage fixes, DNS operator fixes,
  and Authorino operator fixes. Note: RHCL 1.4.0 is deprecated; the demo stays
  on 1.3.4. Do NOT use for general Connectivity Link concepts (use rhcl-about),
  MCP gateway architecture (use rhcl-mcp-gateway), or installation (use
  rhcl-install or rhcl-install-mcp).
---

# RHCL Release Notes

Use this skill to check Red Hat Connectivity Link 1.3 release notes, including
new features, bug fixes, known issues, and async patch releases. The demo pins
`rhcl-operator.v1.3.4`.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority.

## RHCL 1.3 GA Features

- CoreDNS integration for on-premise DNS (Generally Available)
- Enhanced observability documentation (access logs, tracing, request
  correlation)
- OpenShift Service Mesh 3.2 as the Gateway API provider
- OCP 4.19, 4.20, 4.21 support
- cert-manager Operator 1.18 support
- Red Hat build of Keycloak Version 26.4 support

## Async Releases

### 1.3.5 (1 July 2026)

Advisory: RHBA-2026:34242

Bug fix:

- `AuthConfig` CRD v1beta2 schema validation blocked upgrades when CEL
  predicates were used. Now v1beta3 is the standard served version and v1beta2
  is deprecated and removed. Upgrades proceed without OLM blocking.
  (CONNLINK-1131)

### 1.3.4 (2 June 2026) — Demo pinned version

Advisory: RHBA-2026:22741

Bug fixes:

- Limitador deployment stuck on Multi-Attach PVC error when disk storage
  enabled. Fix: `DeploymentStrategy` is `Recreate` by default for all storage
  options. (CONNLINK-855)
- DNS Operator silently discarded wildcard replacement due to `strings.Replace`
  return value not being captured. Fixed. (Kuadrant-750)
- DNS Operator rejected valid hostnames under private registry suffixes
  (`httpbin.org`, `github.io`, `s3.amazonaws.com`). Now only rejects true
  ICANN-managed TLDs. (Kuadrant-765)
- Authorino Operator TLS preflight check missed empty-string certificate secret
  names. Now validates against both empty values and empty strings.
  (Kuadrant-309)

### 1.3.3 (30 April 2026)

Advisory: RHEA-2026:10743

New features:

- MCP gateway available as Technology Preview on the `preview` update channel
- MCP gateway aggregates in-cluster and remote MCP servers behind a single
  endpoint
- Elicitation support for interactive workflows (requires client support)

Known issue:

- `MCPGatewayExtension` with `httpRouteManagement: Enabled` only creates
  `/mcp` rule, missing `/.well-known/oauth-protected-resource`. Workaround:
  set `httpRouteManagement: Disabled` and use manual HTTPRoute.

### 1.3.2 (8 April 2026)

Advisory: RHBA-2026:7016

Bug fix:

- `wasm-shim` processed protection policies out of sequence with data
  forwarding, creating a race condition where upstream received denied requests
  before connection was cut. Fixed: policy check is now blocking before data
  dispatch. (CONNLINK-912)

### 1.3.1 (18 March 2026)

Advisory: RHBA-2026:4903

Bug fix:

- `wasm-shim` incorrectly appended values to existing request headers instead
  of replacing them during external authorization flow. Fixed: headers in
  `CheckResponse` now correctly replace existing values. (CONNLINK-867)

## Known Issues (1.3 GA)

- When Redis or RedisCached storage is set in a `Limitador` CR and the pod
  restarts, the first request to the gateway is never rate-limited. Subsequent
  requests are rate-limited. (CONNLINK-856)

## Version Deprecation Notice

RHCL 1.4.0 is deprecated. The demo stays on RHCL 1.3.4. All guidance in this
skill is grounded in RHCL 1.3 release notes only.

## Update Channel

Red Hat Connectivity Link uses the `stable` update channel to track and receive
updates for the Operator. Manage updates through the OLM subscription resource.

## Workflow

1. Read `references/official-doc-extraction.md` for full release details.
2. Check the specific async release for the version in question.
3. For known issues, verify current cluster state against documented
   workarounds.
4. For bug fixes, confirm the fix applies to the pinned version (1.3.4).

## Related Skills

- Use `rhcl-about` for general Connectivity Link concepts.
- Use `rhcl-mcp-gateway` for MCP gateway architecture.
- Use `rhcl-install-mcp` for MCP gateway installation.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
