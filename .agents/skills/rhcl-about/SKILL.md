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
  Use when explaining Connectivity Link concepts, architecture, Kuadrant,
  Istio/Envoy gateway, API management, AuthPolicy, RateLimitPolicy, DNSPolicy,
  TLSPolicy, supported configurations, user workflows, and policy attachment
  patterns from the official Red Hat Connectivity Link 1.3 documentation. Do NOT
  use for MCP gateway (use rhcl-mcp-gateway), installing Connectivity Link or
  MCP gateway (use rhcl-install or rhcl-install-mcp), or release notes (use
  rhcl-release-notes).
---

# RHCL About

Use this skill to ground Red Hat Connectivity Link conceptual guidance in the
official RHCL 1.3 documentation. The demo pins `rhcl-operator.v1.3.4`.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority.

## Connectivity Link Overview

Red Hat Connectivity Link is a control plane for configuring the Gateway API
data plane in OpenShift Container Platform clusters. It applies authentication,
rate limiting, DNS, and TLS policies to gateway resources using a
Kubernetes-native policy attachment pattern.

Based on the Kuadrant community project, Connectivity Link supports OpenShift
Service Mesh 3.2 as the Gateway API provider (Istio-based, Envoy data plane).

## Core Policy APIs

### TLSPolicy

Lightweight wrapper to manage TLS for targeted gateways. Automatically
provisions TLS certificates via `cert-manager` and ACME providers (e.g. Let's
Encrypt) based on gateway listener hosts.

### AuthPolicy

Applies authentication and authorization at the Gateway, HTTPRoute, or
HTTPRouteRule level. Supports hierarchical defaults and overrides. Integrates
with Red Hat build of Keycloak and dedicated OIDC providers. Mechanisms include
OAuth 2, JWT, API keys, Kubernetes tokens, RBAC, ReBAC, and OPA.

### RateLimitPolicy

Applies rate-limiting rules at the Gateway, HTTPRoute, or HTTPRouteRule level.
Uses hierarchical defaults and overrides. Supports conditional limits based on
metadata and request data. Shares counters via Redis-based backend stores in
multicluster environments.

```yaml
apiVersion: kuadrant.io/v1
kind: RateLimitPolicy
metadata:
  name: gw-rlp
spec:
  targetRef:
    group: gateway.networking.k8s.io
    kind: Gateway
    name: external
  defaults:
    limits:
      "global":
        rates:
        - limit: 5
          window: 10s
```

### DNSPolicy

Automatically populates DNS records from listener hosts and addresses.
Configures multicluster connectivity (geographic, weighted responses). Supports
Amazon Route 53, Azure DNS, Google Cloud DNS, and CoreDNS (GA in 1.3). Includes
endpoint health checks for DNS failover.

## Supported Configurations (RHCL 1.3)

| Component | Supported Versions |
|-----------|-------------------|
| OpenShift Container Platform | 4.21, 4.20, 4.19 |
| OpenShift Service Mesh | 3.2 |
| cert-manager Operator | 1.18 |
| Red Hat build of Keycloak | Version 26.4 |
| Cloud DNS Providers | Route 53, Azure DNS, Google Cloud DNS |
| On-premise DNS | CoreDNS |
| Rate-limit data stores | Redis Enterprise/Cloud, Amazon Elasticache, Dragonfly |

## User Workflows

### Platform Engineer

- Create and configure ingress gateways across clusters
- Apply DNS, TLS, auth, and rate-limiting policies uniformly
- Configure observability dashboards and alerts

### Application Developer

- Deploy applications and APIs on pre-configured gateways
- Protect routes with AuthPolicy (OAuth 2, JWT, API keys)
- Monitor workload performance via observability dashboards

### Business User

- View API metrics (uptime, requests/sec, latency, errors/min)
- Monitor regional data center performance via Grafana dashboards

## Key Technologies

- **Policy attachment**: attach behavior to Gateway API objects via CRs
- **Defaults and overrides**: hierarchical role-based policy merging
- **WebAssembly plugin**: lightweight Envoy WASM plugin for rate limiting
- **Multicluster mirroring**: consistent policy deployment across clouds

## Workflow

1. Read `references/official-doc-extraction.md` for detailed product behavior.
2. Identify the relevant policy type or architectural concern.
3. For GitOps manifests, verify API versions (`kuadrant.io/v1`) against the
   extraction before committing.
4. For live operations, use the repo environment guard.

## Related Skills

- Use `rhcl-mcp-gateway` for MCP gateway concepts and architecture.
- Use `rhcl-install-mcp` for installing the MCP gateway.
- Use `rhcl-release-notes` for version history and known issues.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
