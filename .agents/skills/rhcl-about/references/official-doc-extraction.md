# Official Doc Extraction

Use this extraction to ground RHCL conceptual and architectural content in the
official documentation. When implementation needs exact Operator, CR, policy,
or gateway field definitions, verify against the separate RHCL installation,
deployment, and configuration documentation and active cluster schema.

## Product Definition

Red Hat Connectivity Link is a control plane for configuring the Gateway API
data plane in OpenShift Container Platform clusters. You can use it to apply
authentication, rate limiting, and DNS policies to gateway resources.

Connectivity Link is a modular and flexible solution for application
connectivity, policy management, and API management in multicloud and hybrid
cloud environments.

## Operator Composition

Connectivity Link consists of four Operators bundled in a single combined
catalog:

1. **Connectivity Link Operator** — policy attachment and Gateway API
   integration; includes wasm-shim and console-plugin runtime images.
2. **Authorino Operator** — authentication and authorization engine; includes
   the `authorino` runtime image.
3. **Limitador Operator** — rate limiting engine; includes the `limitador`
   runtime image.
4. **DNS Operator** — multi-cluster DNS management.

The Connectivity Link Operator declares the other three as OLM dependencies.

## Architectural Foundation

- Based on the Kuadrant community project.
- Provides a control plane to configure and deploy ingress gateways and
  policies based on the Kubernetes Gateway API standard.
- Supports OpenShift Service Mesh 3.2 as the Gateway API provider (Istio-based).
- Uses a policy attachment pattern: add behavior to Kubernetes objects via
  configuration that cannot be described in the object `spec` field.
- Supports defaults and overrides for role-oriented policy collaboration.
- Uses WebAssembly (WASM) plugin for Envoy proxy — lightweight, hardware
  independent, non-intrusive, and secure.

## Gateway API Integration

Gateway API is structured to meet different organizational team needs:

- Platform engineers create and secure gateways.
- Application developers deploy apps and attach route-level policies.
- Business users consume observability metrics.

Connectivity Link attaches policies to Gateway API resources, enabling a
code-as-infrastructure approach without embedding networking code in
applications.

## Policy APIs

### TLSPolicy

- Lightweight wrapper API to manage TLS for targeted gateways.
- Automatically provisions TLS certificates based on gateway listener hosts
  via cert-manager and ACME providers (e.g., Let's Encrypt).
- Configures secrets for automatic gateway retrieval.

### AuthPolicy

- Applies authentication and authorization at Gateway listener or
  HTTPRoute/HTTPRouteRule level.
- Supports hierarchical defaults and overrides for compliance.
- Integrates with dedicated OIDC providers (Red Hat build of Keycloak).
- Applies fine-grained authorization based on request and metadata attributes.

### RateLimitPolicy

- Applies rate-limiting rules at Gateway listener or HTTPRoute/HTTPRouteRule
  level.
- Supports hierarchical defaults and overrides.
- Configures limits conditionally based on metadata and request data.
- Shares counters via backend store in multicluster environments.
- API version: `kuadrant.io/v1`

Example shape:

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

- Standard API (not custom-annotation based).
- Automatically populates DNS records based on listener hosts and addresses.
- Configures multicluster connectivity (geographic, weighted responses).
- Supports: Amazon Route 53, Azure DNS, Google Cloud DNS, CoreDNS.
- Configures health checks for DNS failover.

## Supported Configurations (RHCL 1.4)

### OpenShift Container Platform

RHCL 1.4 supports: OCP 4.21, 4.20, 4.19, 4.18

Also supported: OpenShift Dedicated, ROSA, Azure Red Hat OpenShift on the same
OCP versions.

### Required Operators

- Red Hat OpenShift Service Mesh: 3.2
- cert-manager Operator for Red Hat OpenShift: 1.18

### Cloud Providers

AWS, Google Cloud Platform, Microsoft Azure

### DNS Providers

Amazon Route 53, Google Cloud Platform DNS, Microsoft Azure DNS, CoreDNS
(on-premise)

### Rate-Limiting Data Stores

Redis Enterprise or Cloud (latest), Amazon Elasticache (latest), Dragonfly
Community or Cloud (latest)

### Identity Access Management

Red Hat build of Keycloak version 26.4, plus API keys.

## User Workflow Summary

### Platform Engineer

1. Create gateways.
2. Configure DNS policies for geographic routing and load balancing.
3. Configure TLS policies for automatic certificate generation.
4. Configure Auth and RateLimit policies for security and performance.
5. Observe connectivity and runtime metrics via dashboards and alerts.

### Application Developer

1. Deploy applications and API routes on platform-provided gateways.
2. Protect applications with AuthPolicy (OAuth 2, JWT, API keys, RBAC, ReBAC,
   OPA, Kubernetes tokens).
3. Observe API performance metrics (uptime, RPS, latency, errors).

### Business User

1. Monitor application and API status via Grafana-based dashboards.
2. View regional API metrics for customer SLA compliance.

## Technologies and Patterns

- **Policy-based configuration** — defaults and overrides across object
  hierarchy for multi-role collaboration.
- **WebAssembly plugin** — lightweight Envoy extension; no major changes to
  existing ingress objects.
- **Multicluster configuration mirroring** — consistent policy deployment
  across cloud providers.
- **API connectivity and management** — scalable multi-gateway connectivity
  with observability, auth, and rate limiting.

## Verification Before Implementation

Before implementing RHCL resources, verify:

- Installed Connectivity Link Operator subscription and CSV
- Authorino, Limitador, and DNS Operator CRDs and health
- Available Gateway API CRDs (Gateway, HTTPRoute, GRPCRoute)
- OpenShift Service Mesh 3.2 deployment and health
- cert-manager Operator installation and ClusterIssuer
- Kuadrant CR status

Discovery commands belong in validation checklists; do not run without
confirming the target cluster via the OpenShift safety guard.
