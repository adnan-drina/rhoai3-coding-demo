# Official Doc Extraction

Use this extraction to keep RHCL 1.3 release note content grounded in official
Red Hat sources. When referencing bug fixes or known issues, verify the current
cluster operator version with `oc get csv -n <namespace>` before assuming a fix
is present.

## Product Overview (from Release Notes)

Red Hat Connectivity Link is a modular and flexible solution for application
connectivity, policy management, and API management in multicloud and hybrid
cloud environments. Use Connectivity Link to secure, protect, connect, and
observe APIs, applications, and infrastructure.

Based on the Kuadrant community project. Provides a control plane for
configuring and deploying ingress gateways and policies based on the Kubernetes
Gateway API standard. Supports OpenShift Service Mesh 3.2 as the Gateway API
provider (based on the Istio community project).

Update channel: `stable` (for GA features). MCP gateway uses `preview` channel.

## GA New Features (1.3.0)

### CoreDNS Integration (GA)

CoreDNS integration for on-premise DNS is Generally Available in RHCL 1.3.
Allows configuring an on-cluster DNS zone without external cloud DNS providers.

### Updated Observability Documentation

Enhanced documentation covering:

- Configuring access logs
- Tracing
- Request correlation

## GA Known Issues

### Limitador First-Request Skip (CONNLINK-856)

When either the `Redis` or `RedisCached` storage option is set in a `Limitador`
CR and the `limitador` pod gets restarted for any reason, the first request to
the gateway is never rate-limited. All HTTP requests after this are
rate-limited.

Status: known issue, not fixed as of 1.3.5.

## Async Release: 1.3.5 (1 July 2026)

Advisory: RHBA-2026:34242

### AuthConfig CRD Upgrade Fix (CONNLINK-1131)

**Problem:** During upgrades, OLM validates existing `AuthConfig` CRs against
all active CRD versions. The `v1beta2` version lacked a schema validation patch
for CEL predicate fields. The API server evaluated `v1beta3` resources
containing CEL predicates against the stricter `v1beta2` schema, causing OLM to
block upgrades.

**Fix:** The `v1beta3` version of the `AuthConfig` API is now the standard for
served CRD versions. The `v1beta2` version is deprecated and removed. Existing
`AuthConfig` resources with CEL predicate conditions no longer trigger schema
validation failures.

## Async Release: 1.3.4 (2 June 2026) — Demo Pinned

Advisory: RHBA-2026:22741

### Limitador PVC Multi-Attach Fix (CONNLINK-855)

**Problem:** When disk storage option was enabled in the `Limitador` CR, both
initial deployment and Operator update got stuck on a `Multi-Attach` error
because of the PVC volume.

**Fix:** `DeploymentStrategy` is `Recreate` by default in all storage options.
Reconciliation process works as expected. Switching between in-memory and disk
storage types no longer causes deployment failures.

### DNS Wildcard Replacement Fix (Kuadrant-750)

**Problem:** The DNS Operator silently discarded wildcard replacement. The
`strings.Replace` function handled wildcard DNS record replacements but its
returned result was never assigned back to the target variable.

**Fix:** The return value is properly captured and assigned. DNS records are
now accurately processed.

### DNS Zone-Matching Fix (Kuadrant-765)

**Problem:** The DNS Operator zone-matching validation was too restrictive,
causing all public suffixes to be rejected. Hostnames under valid private
registry suffixes (`httpbin.org`, `github.io`, `s3.amazonaws.com`) were
incorrectly rejected.

**Fix:** The DNS Operator uses a strict check that differentiates between
standard ICANN-managed TLDs and private registry suffixes. Only true
ICANN-managed TLDs trigger rejection.

### Authorino TLS Preflight Fix (Kuadrant-309)

**Problem:** The Authorino Operator TLS preflight validation only checked if
`CertSecret.Name` field was empty. Cases where the field was initialized but
contained an empty string were not validated, causing confusing errors later.

**Fix:** Preflight check validates against both empty values and empty strings
for the certificate secret name. Invalid names are caught immediately with
clear error feedback.

## Async Release: 1.3.3 (30 April 2026)

Advisory: RHEA-2026:10743

### MCP Gateway Technology Preview

The Model Context Protocol (MCP) gateway is now available as a Technology
Preview feature on the `preview` update channel. Not intended for production
use.

Capabilities:

- Aggregates in-cluster and remote MCP servers behind a single endpoint
- Discovers tools from registered MCP servers
- Focus on agentic AI applications without building networking into code
- Standardize access and security governance of MCP servers
- Add and remove MCP servers without restarting systems
- Curate MCP server tools by creating virtual MCP servers

### Elicitation Support

Elicitation support is available with the MCP gateway if the client supports
it. MCP servers can implement interactive workflows by enabling user input
requests.

### Known Issue: MCPGatewayExtension HTTPRoute

When `httpRouteManagement: Enabled` (default) is set on an
`MCPGatewayExtension` CR, the MCP controller `buildGatewayHTTPRoute()` only
creates a single rule for `/mcp` endpoints. The
`/.well-known/oauth-protected-resource` rule is missing.

**Workaround:** Set `httpRouteManagement: Disabled` in the
`MCPGatewayExtension` CR with a manually managed `HTTPRoute` CR.

## Async Release: 1.3.2 (8 April 2026)

Advisory: RHBA-2026:7016

### Wasm-Shim Race Condition Fix (CONNLINK-912)

**Problem:** The `wasm-shim` component processed protection policies (auth,
rate-limiting) out of sequence with data forwarding. This created a race
condition where the Gateway started sending the request to the upstream server
while simultaneously asking the policy if the request was allowed. The upstream
server received and potentially acted upon denied requests.

**Fix:** The policy check is now a blocking operation that must complete before
any data is dispatched to the upstream backend. Denied requests are strictly
terminated at the Gateway.

## Async Release: 1.3.1 (18 March 2026)

Advisory: RHBA-2026:4903

### Wasm-Shim Header Fix (CONNLINK-867)

**Problem:** The `wasm-shim` networking protocol incorrectly appended values to
existing request headers instead of replacing them during the external
authorization flow. This caused comma-separated header values that could disrupt
upstream processing.

**Fix:** Headers provided in the `CheckResponse` object now correctly replace
existing values, restoring predictable header management.

## Verification Commands

```bash
oc get csv -n connectivity-link-system | grep rhcl-operator
oc get subscription -n connectivity-link-system -o yaml | grep currentCSV
oc get installplan -n connectivity-link-system
```
