# Official Doc Extraction

Use this extraction to keep Connectivity Link conceptual content grounded in
official Red Hat sources. When implementation needs exact CR fields, verify the
active cluster schema with `oc explain` or `oc get crd` before authoring GitOps
manifests.

## Product Overview

Red Hat Connectivity Link is a single data plane used to apply policies to
Gateway API resources in OpenShift Container Platform clusters. You can use it
to connect, secure, observe, and protect service endpoints in multicloud and
hybrid cloud environments.

Based on the Kuadrant community project, Connectivity Link provides a control
plane for configuring and deploying ingress gateways with the role-oriented
resources and components of the Kubernetes Gateway API. Policies attach to
Gateway API resources so that networking code is not embedded in applications.

Connectivity Link supports OpenShift Service Mesh 3.2 as the Gateway API
provider.

## Key Features

Multicloud application connectivity:

- DNS provider integrations (Route 53, Azure DNS, Google Cloud DNS, CoreDNS)
- High availability and disaster recovery
- Global load balancing (round-robin, weighted, geo-based)
- Endpoint health and status checks
- Automatic TLS certificate generation
- Universal authentication

Kubernetes ingress policy management:

- Global DNS policy
- TLS policy
- Auth policy
- Rate-limiting policy
- Token rate-limiting policy
- Traffic weighting and distribution
- User-role-based design
- Multicluster administration
- Observability dashboards and alerts
- OpenShift Container Platform web console dynamic plugin

Composable API management:

- API security and governance
- Advanced API metrics collection
- API-level policies for authentication, authorization, and rate limiting
- Flexible integration with open source tools

## TLSPolicy

`TLSPolicy` is a lightweight wrapper API to manage TLS for targeted gateways.
It automatically provisions TLS certificates based on gateway listener hosts
by using integration with `cert-manager` and ACME providers such as Let's
Encrypt. Configures secrets so that the gateway automatically retrieves them.

## AuthPolicy

Use `AuthPolicy` objects to apply authentication and authorization across
selected listeners in a gateway or at the `HTTPRoute` or `HTTPRouteRule` level.
Uses the hierarchical and role-based concept of defaults and overrides to
improve collaboration and ensure compliance.

Supported mechanisms:

- OAuth 2
- JWT authorization policies
- API keys
- Kubernetes tokens
- Role-based access (RBAC)
- Relationship-based access control (ReBAC)
- Open Policy Agent (OPA)
- Dedicated OIDC authentication providers (Red Hat build of Keycloak)
- Fine-grained authorization based on `request` and `metadata` attributes

## RateLimitPolicy

Apply rate-limiting rules across all listeners in a gateway or at the
`HTTPRoute` or `HTTPRouteRule` level. Uses the role-based and hierarchical
concept of defaults and overrides.

Configuration:

- Conditional limits based on metadata and request data
- Share counters via backend store in multicluster environments
- Supported data stores: Redis Enterprise/Cloud, Amazon Elasticache, Dragonfly

Example (official docs):

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

Known issue: when Redis or RedisCached storage is set in a `Limitador` CR and
the pod restarts, the first request to the gateway is never rate-limited. All
subsequent requests are rate-limited. (CONNLINK-856)

## DNSPolicy

`DNSPolicy` is a standard API that is not based on custom annotations. It
automatically populates DNS records based on listener hosts and addresses
expressed by Gateway API resources.

Features:

- Multicluster connectivity and routing (geographic, weighted responses)
- Common cloud DNS providers: Amazon Route 53, Microsoft Azure DNS, Google
  Cloud DNS, CoreDNS (GA in RHCL 1.3)
- Health checks to enable DNS failover

## Policy Attachment Pattern

Connectivity Link uses the policy attachment pattern to add behavior to a
Kubernetes object by using configuration that cannot be described in the object
`spec` field.

With policy attachments comes defaults and overrides. Different roles operate
with policy APIs at different levels of the object hierarchy. Policies are
merged with specific rules and strategies to form an effective policy across
the organization.

## User Workflows

### Platform Engineer

1. Create at least one gateway
2. Connect gateways with DNSPolicy (global load balancing)
3. Secure gateways with TLSPolicy (automatic certificate requests)
4. Set up security defaults with AuthPolicy and RateLimitPolicy
5. Configure observability stack (dashboards, alerts)

### Application Developer

1. Configure routes (HTTPRoute) and API definitions
2. Protect applications with AuthPolicy (OAuth 2, JWT, API keys, RBAC)
3. Observe application and API performance via dashboards

### Business User

1. Monitor application and API status in regional data centers
2. View API metrics: uptime, requests/sec, latency, errors/min
3. Work with customers on specific performance metrics

## Supported Configurations (RHCL 1.3)

### OpenShift Container Platform

| Red Hat Connectivity Link | OCP | OSD | ROSA | ARO |
|--------------------------|-----|-----|------|-----|
| 1.3 | 4.21, 4.20, 4.19 | 4.21, 4.20, 4.19 | 4.21, 4.20, 4.19 | 4.19 |

### Supported Operators

| Red Hat Connectivity Link | OpenShift Service Mesh | cert-manager Operator |
|--------------------------|----------------------|---------------------|
| 1.3 | 3.2 | 1.18 |

### Identity Access Management

| Red Hat Connectivity Link | Red Hat build of Keycloak |
|--------------------------|--------------------------|
| 1.3 | Version 26.4 |

### Cloud DNS Providers

- Amazon Route 53
- Google Cloud Platform DNS
- Microsoft Azure DNS
- CoreDNS (on-premise, GA in 1.3)

### Rate-Limit Data Stores

- Redis Enterprise or Cloud (latest)
- Amazon Elasticache (latest)
- Dragonfly Community or Cloud (latest)

## WebAssembly Plugin

As a WASM plugin developed for the Envoy proxy, Connectivity Link is
lightweight, hardware independent, non-intrusive, and secure. Clusters using
OpenShift Service Mesh, Istio, or Envoy for ingress do not require major
changes to existing ingress objects to begin using Connectivity Link.

## Multicluster Configuration Mirroring

Deploy policies across different cloud service providers consistently.
Development, test, and production environments can be consistent through one
interface. Provides unified experiences, global administration, and security
compliance.
