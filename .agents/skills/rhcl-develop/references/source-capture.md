# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product family | Red Hat Connectivity Link |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Documentation category | Develop |
| Official guide | Developing APIs with the web console |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/developing_apis_with_the_web_console/index |
| Multi-page URL | https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html/developing_apis_with_the_web_console/index |
| Capture date | 2026-07-06 |

## Captured Sections

- Chapter 1: Using the OpenShift Container Platform web console
  - About using the OpenShift web console (OCP 4.19 vs 4.20+ feature parity)
  - Enabling the Connectivity Link OCP console plugin (`kuadrant-console-plugin`)
- Chapter 2: Create, share, and consume APIs across teams
  - API management pages in the web console (roles and workflows)
  - API management custom resource definitions (`APIProduct`, `APIKey`,
    `APIKeyRequest`, `APIKeyApproval`)
  - API management authentication methods (API key, OIDC/JWT)
  - Publishing an API for other teams to discover and consume
  - Integrate with an API published by another team
  - Control who can access your published API (manual approval workflow)
  - API management role-based-access reference
    - Cluster roles (`api-catalog-browser`, `api-consumer`, `api-owner`,
      `api-admin`)
    - Role binding requirements (consumer, owner, administrator)
    - Verifying API consumer, owner, and administrator access roles

## Source Boundaries

This source covers:

- Web console plugin enablement and navigation
- API product lifecycle (publish, discover, consume, approve/reject)
- API key and OIDC/JWT authentication methods
- RBAC cluster roles and role bindings for API management
- Verification commands for RBAC

This source does NOT cover:

- Connectivity Link installation or operator lifecycle
- Gateway, HTTPRoute, or policy creation outside the API management context
- MCP gateway configuration or MCP server registration
- Observability, metrics, tracing, or dashboards
- Troubleshooting procedures
- DNS, TLS, or rate limiting policy details

## Related Official Sources

- [Installing Connectivity Link](https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html/installing_connectivity_link/index)
- [Deploying Red Hat Connectivity Link](https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html/deploying_red_hat_connectivity_link/index)
- [Observability](https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html/observability/index)
- [Troubleshooting](https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html/troubleshooting/index)
