---
name: rhcl-configure
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhcl"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when deploying and configuring Connectivity Link to secure, protect, and
  connect APIs on OpenShift, including AuthPolicy, RateLimitPolicy,
  TokenRateLimitPolicy, DNSPolicy, TLSPolicy, HTTPRoute, GRPCRoute, Gateway
  object setup, and application-level policy overrides. Do NOT use for
  Connectivity Link operator installation; use rhcl-install. Do NOT use for MCP
  gateway registration or MCP auth policies; use rhcl-mcp-config.
---

# RHCL Configure

Use this skill to ground Connectivity Link policy deployment decisions in
official RHCL 1.4 documentation for the active baseline in
`docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority.

## Key Concepts

- All policies use `apiVersion: kuadrant.io/v1` except TokenRateLimitPolicy
  (`kuadrant.io/v1alpha1`).
- Policies target Gateway or HTTPRoute/GRPCRoute via `spec.targetRef`.
- Gateway-level policies provide defaults; route-level policies override.
- Zero-trust pattern: apply `deny-all` AuthPolicy at Gateway level; each app
  developer creates route-level AuthPolicy overrides.
- Rate limiting uses Limitador; shared Redis required for multicluster.
- TokenRateLimitPolicy counts LLM tokens from OpenAI-compatible
  `usage.total_tokens` response field.
- GRPCRoute support is Technology Preview in 1.4.
- CoreDNS can provide on-premise DNS as an alternative to cloud providers.

## Workflow

1. Confirm the active RHCL baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Identify whether the task concerns:
   - Gateway object creation and listener configuration
   - TLSPolicy and certificate issuer setup
   - DNSPolicy for DNS automation and load balancing
   - AuthPolicy (deny-all default or route-level override)
   - RateLimitPolicy (gateway default or user-specific override)
   - TokenRateLimitPolicy for LLM token budgets
   - HTTPRoute or GRPCRoute for application traffic
   - Rate-limit response headers
   - On-premise DNS with CoreDNS
4. For manifests, verify API versions against official docs.
5. Validate with verification commands from the extraction.

## Validation Signals

```bash
oc get authpolicy <name> -n <ns> -o=jsonpath='{.status.conditions}'
oc get ratelimitpolicy <name> -n <ns> -o=jsonpath='{.status.conditions}'
oc get tlspolicy <name> -n <ns> -o=jsonpath='{.status.conditions}'
oc get dnspolicy <name> -n <ns> -o=jsonpath='{.status.conditions}'
oc get gateway <name> -n <ns> -o=jsonpath='{.status.conditions}'
```

All policies report `Accepted` and `Enforced` conditions when healthy.

## Related Skills

- `rhcl-install` for Connectivity Link operator installation.
- `rhcl-install-mcp` for MCP gateway installation.
- `rhcl-mcp-config` for MCP server registration and auth.
- `rhoai-maas-governance` for RHOAI MaaS governance integration.
- `ocp-ingress-gateway-routes` for OCP Gateway API primitives.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
