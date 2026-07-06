---
name: rhcl-about
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhcl"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when explaining Connectivity Link concepts, architecture, multicloud API
  connectivity, Kuadrant, Istio/Envoy gateway, and API management capabilities.
  Do NOT use for MCP gateway (use rhcl-mcp-gateway), installing (use
  rhcl-install), or configuring (use rhcl-configure).
---

# RHCL About

Use this skill to ground Red Hat Connectivity Link conceptual and architectural
guidance in the official RHCL 1.4 product documentation.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is the product authority. This skill captures the RHCL
product definition, architecture, features, user workflows, policy APIs, and
supported configurations.

## Product Definition

Red Hat Connectivity Link is a control plane for configuring the Gateway API
data plane in OpenShift Container Platform clusters. It applies authentication,
rate limiting, and DNS policies to gateway resources.

Connectivity Link consists of four Operators bundled in a single combined
catalog:

- Connectivity Link Operator (policy attachment, Gateway API integration)
- Authorino Operator (authentication and authorization engine)
- Limitador Operator (rate limiting engine)
- DNS Operator (multi-cluster DNS management)

Connectivity Link is based on the Kuadrant community project and supports
OpenShift Service Mesh 3.2 as the Gateway API provider.

## Core Capabilities

- Multicloud application connectivity (DNS, HA/DR, global load balancing)
- Kubernetes ingress policy management (TLSPolicy, AuthPolicy,
  RateLimitPolicy, DNSPolicy)
- Composable API management (security, governance, advanced metrics)
- Policy attachment to Gateway API resources (defaults and overrides)
- Observability dashboards and alerts (Grafana, Prometheus, Alertmanager)

## Policy APIs

| Policy | Purpose |
|--------|---------|
| `TLSPolicy` | Automatic TLS certificate provisioning via cert-manager/ACME |
| `AuthPolicy` | Authentication and authorization at Gateway or HTTPRoute level |
| `RateLimitPolicy` | Rate limiting with defaults/overrides and conditional limits |
| `DNSPolicy` | DNS record reconciliation with cloud DNS providers |

All policies use the Gateway API policy attachment pattern with hierarchical
defaults and overrides for role-oriented collaboration.

## Supported Configurations (1.4)

- OCP: 4.21, 4.20, 4.19, 4.18
- OpenShift Service Mesh: 3.2
- cert-manager Operator: 1.18
- Cloud providers: AWS, GCP, Azure
- DNS providers: Route 53, Google Cloud DNS, Azure DNS, CoreDNS
- Rate-limiting stores: Redis Enterprise/Cloud, Amazon Elasticache, Dragonfly
- Identity: Red Hat build of Keycloak 26.4, API keys

## User Workflows

- **Platform engineer**: Create gateways, configure DNS/TLS/Auth/RateLimit
  policies, observe connectivity metrics.
- **Application developer**: Deploy apps and APIs, protect with AuthPolicy,
  observe performance.
- **Business user**: Monitor API metrics (uptime, latency, errors) via Grafana.

## Demo Posture

For this demo, RHCL provides the MaaS Gateway for governed external model
access. The repo pins `rhcl-operator.v1.3.4` per `docs/PLATFORM_BASELINE.md`
(compatibility hold). RHCL 1.4 documentation is used for skill content because
it is the target upgrade path once RHCL 1.4.1+ is validated.

## Workflow

1. Confirm the active RHCL baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Identify whether the task concerns:
   - RHCL product concepts, architecture, or features (this skill)
   - MCP gateway concepts (use `rhcl-mcp-gateway`)
   - Installation (use `rhcl-install` when available)
   - Configuration and deployment (use `rhcl-configure` when available)
   - Release notes and known issues (use `rhcl-release-notes`)
4. Do not invent CR fields, policy schemas, or operator configurations
   beyond what is documented in the official source.
5. For live operations, verify against cluster schema with `oc explain` and
   `oc get crd`.

## Related Skills

- Use `rhcl-mcp-gateway` for MCP gateway architecture and concepts.
- Use `rhcl-release-notes` for RHCL 1.4 release notes and known issues.
- Use `rhoai-maas-governance` for RHOAI MaaS integration that consumes RHCL.
- Use `ocp-ingress-gateway-routes` for OCP-level Gateway API and routing.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
