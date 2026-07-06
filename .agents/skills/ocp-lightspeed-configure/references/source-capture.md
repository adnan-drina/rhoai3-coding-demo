# Source Capture

## Official Source

| Field | Value |
|-------|-------|
| Product family | Red Hat OpenShift Lightspeed |
| Product version | 1.0 |
| Documentation category | Configuring |
| Official guide | Configure |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/configure/index |
| Single-page URL | https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/configure/index |
| Capture date | 2026-07-06 |

## Captured Sections

- Chapter 1: Configuring and deploying OpenShift Lightspeed
  - 1.1 Creating credentials secret (web console)
  - 1.2 Creating OLSConfig CR (web console)
    - 1.2.1 Configuring custom TLS certificates
    - 1.2.2 Configuring trusted CA certificate for LLM
  - 1.3 Creating credentials secret (CLI)
  - 1.4 Creating OLSConfig CR (CLI)
    - 1.4.1 Configure trusted-ca certificates and LLM providers
    - 1.4.2 Configuring trusted CA certificate for LLM
  - 1.5 Verifying the deployment
  - 1.6 About RBAC
  - 1.7 Expose the service by using a route
    - 1.7.1 Granting user access (CLI)
    - 1.7.2 Granting user access (YAML)
    - 1.7.3 Granting user group access (CLI)
    - 1.7.4 Granting user group access (YAML)
    - 1.7.5 Obtain authentication token
  - 1.8 Filtering and redacting information
  - 1.9 About the BYO Knowledge tool
    - 1.9.1 About document title and URL
    - 1.9.2 Providing custom knowledge to the LLM
    - 1.9.3 Disabling the OCP documentation RAG database
  - 1.10 About cluster interaction
    - 1.10.1 Disabling cluster interaction
    - 1.10.2 Enabling a custom MCP server
    - 1.10.3 Authentication flow for cluster introspection
  - 1.11 Tokens and token quota limits
    - 1.11.1 Activating token quota limits
  - 1.12 About PostgreSQL persistence
    - 1.12.1 Enabling PostgreSQL persistence
    - 1.12.2 Overriding default PVC specifications
  - 1.13 About query-based tool filtering
    - 1.13.1 Enabling query-based tool filtering
    - 1.13.2 About operation approvals
    - 1.13.3 Tools approval configuration
- Chapter 2: OLSConfig API reference
  - 2.1 OLSConfig API specifications (full field reference)
- Chapter 3: REST API authentication configurations
  - 3.1 Authentication modules (k8s, noop, noop-with-token)
- Chapter 4: Integrating Google Vertex AI
  - 4.1 Google Vertex AI provider types
  - 4.2 Configuring Google Vertex AI
  - 4.3 OLSConfig field reference for Google Vertex AI

## Source Boundaries

This source is authoritative for configuring and deploying the OpenShift
Lightspeed Service via the OLSConfig CR. It covers LLM provider setup,
credential secrets, TLS configuration, RBAC user/group access, query filtering,
BYO Knowledge RAG, cluster interaction via MCP, token quotas, PostgreSQL
persistence, tool filtering, operation approvals, REST API authentication, and
Google Vertex AI integration.

It does **not** cover:
- Operator installation procedures (separate "Install" guide)
- Conceptual architecture or feature overview (separate "About" guide)
- Day-2 operations, scaling, or maintenance (separate "Operate" guide)
- Troubleshooting and diagnostics (separate "Troubleshoot" guide)
- Upgrade or removal procedures

## API Versions Documented

| Resource | apiVersion | Kind |
|----------|-----------|------|
| OLSConfig | `ols.openshift.io/v1alpha1` | `OLSConfig` |
| Credential Secret | `v1` | `Secret` |
| ConfigMap (trusted CA) | `v1` | `ConfigMap` |
| ClusterRoleBinding | `rbac.authorization.k8s.io/v1` | `ClusterRoleBinding` |
| Route | `route.openshift.io/v1` | `Route` |

## Related Official Sources to Add Later

- Red Hat OpenShift Lightspeed 1.0 "About" guide — concepts and architecture
- Red Hat OpenShift Lightspeed 1.0 "Install" guide — Operator installation
- Red Hat OpenShift Lightspeed 1.0 "Operate" guide — day-2 operations
- Red Hat OpenShift Lightspeed 1.0 "Troubleshoot" guide — diagnostics
- Red Hat OpenShift Lightspeed 1.0 "Upgrade" guide — upgrade procedures
- Red Hat OpenShift Lightspeed 1.0 "Uninstall" guide — removal procedures
