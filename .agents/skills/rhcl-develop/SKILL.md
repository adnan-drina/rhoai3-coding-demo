---
name: rhcl-develop
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhcl"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when developing and managing APIs with the OpenShift web console using
  Connectivity Link: enabling the console plugin, publishing API products,
  consuming APIs, managing API key requests, configuring API key and OIDC/JWT
  authentication, setting up RBAC with api-catalog-browser, api-consumer,
  api-owner, and api-admin cluster roles, and verifying role bindings. Do NOT
  use for Connectivity Link installation, deployment, gateway configuration,
  policy creation, or MCP gateway setup; use the relevant rhcl-* skill. Do NOT
  use for observability or troubleshooting; use rhcl-observability or
  rhcl-troubleshoot. Do NOT invent CRD fields, API versions, or RBAC rules
  not documented in the official source.
---

# RHCL Develop — Developing APIs with the Web Console

Use this skill to ground Connectivity Link API development guidance in the
official Red Hat Connectivity Link 1.4 documentation for the active baseline
in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority. This skill captures the Connectivity
Link web console plugin, API product management, API key workflows, OIDC/JWT
authentication, and RBAC configuration.

## Key Concepts

### Console Plugin

- The `kuadrant-console-plugin` must be enabled via Administration > Cluster
  Settings > Configuration > Console plugins.
- OCP 4.20+ provides full API management; OCP 4.19 provides gateway and policy
  visibility only.
- Navigation sections: Connectivity Link (Overview, Policies, API Products,
  Policy Topology) and Connectivity Link API Catalog (API Key Approvals, My
  API Keys).

### API Management (Technology Preview on OCP 4.20+)

API management CRDs:

- `APIProduct`: wraps an `HTTPRoute` with business context (name, docs,
  contact, access policies); set `publishStatus: Published` to make
  discoverable.
- `APIKey`: actual API access credentials in the consumer namespace.
- `APIKeyRequest`: shadow resource in the owner namespace (controller-managed,
  do not modify manually).
- `APIKeyApproval`: approval or rejection action on an `APIKeyRequest`.

### Authentication Methods

- **API key**: Kubernetes secrets store credentials; supports automatic or
  manual approval workflows.
- **OIDC/JWT**: delegates to an external identity provider; no `APIKey`
  resources created; `AuthPolicy` CR validates JWTs.

### RBAC

Four predefined cluster roles:

- `api-catalog-browser`: cluster-wide read access to API catalog resources.
- `api-consumer`: create and manage `APIKey` resources in assigned namespaces
  (requires both `ClusterRoleBinding` for catalog browsing and `RoleBinding`
  for namespace-scoped key management).
- `api-owner`: publish APIs and manage consumer access requests
  (namespace-scoped write, cluster-wide catalog read).
- `api-admin`: cluster-wide management and troubleshooting (no secret read in
  consumer namespaces).

## Workflow

1. Confirm the active RHCL baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Identify whether the task concerns:
   - enabling the console plugin
   - publishing an API product
   - consuming an API from the catalog
   - managing API key approvals
   - configuring authentication methods
   - setting up RBAC roles and bindings
   - verifying role permissions
4. For manifests, verify all API versions, CRDs, fields, namespaces, RBAC, and
   credentials before committing.
5. Validate the output with the official source and cluster schema.

## Related Skills

- Use `rhcl-observability` for Connectivity Link metrics, tracing, dashboards,
  access logs, and MCP gateway observability.
- Use `rhcl-troubleshoot` for diagnosing gateway, routing, policy, DNS, TLS,
  rate limiting, and MCP gateway issues.
- Use `ocp-ingress-gateway-routes` for Gateway API, HTTPRoute, and gateway
  infrastructure.
- Use `ocp-security-rbac-scc` for general OCP RBAC patterns.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
