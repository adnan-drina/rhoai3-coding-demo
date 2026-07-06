# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product family | Red Hat OpenShift Pipelines |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Documentation category | Custom Tekton Hub instance |
| Official guide | Custom Tekton Hub instance |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.22/html-single/custom_tekton_hub_instance/index |
| Multi-page URL | https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.22/html/custom_tekton_hub_instance/index |
| Capture date | 2026-07-06 |

## Captured Sections

From Custom Tekton Hub instance:

- Chapter 1: Using Tekton Hub with OpenShift Pipelines
  - Technology Preview notice
  - 1.1 Installing and deploying Tekton Hub on an OpenShift Container Platform cluster
    - 1.1.1 Installing Tekton Hub without login and rating (default TektonHub CR)
    - 1.1.2 Installing Tekton Hub with login and rating (OAuth, tekton-hub-api secret)
  - 1.2 Optional: Using a custom database in Tekton Hub
    - 1.2.1 Optional: Installing Crunchy Postgres database and Tekton Hub
    - 1.2.2 Optional: Migrating Tekton Hub data to an existing Crunchy Postgres database
  - 1.3 Updating Tekton Hub with custom categories and catalogs
  - 1.4 Modifying the catalog refresh interval of Tekton Hub
  - 1.5 Adding new users in Tekton Hub configuration
  - 1.6 Disabling Tekton Hub authorization after upgrading from Operator 1.7 to 1.8

## Source Boundaries

This skill covers the "Custom Tekton Hub instance" guide only. It provides
guidance on deploying, configuring, and managing a custom Tekton Hub instance
on OpenShift. It does not cover:

- Pipeline concepts and Tekton CRDs (separate guide: About OpenShift Pipelines)
- Installing and configuring OpenShift Pipelines Operator (separate guide)
- Creating CI/CD solutions with pipelines (separate guide)
- Pipelines as Code (separate guide)
- Pipeline security (separate guide)
- Pipeline observability (separate guide)
- Artifact Hub migration or hub resolver configuration beyond Tekton Hub

## API Versions Documented

| Resource | API Version |
|----------|-------------|
| TektonHub | `operator.tekton.dev/v1alpha1` |

## Key Secrets Documented

| Secret Name | Purpose |
|-------------|---------|
| `tekton-hub-db` | Custom database connection (POSTGRES_HOST, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_PORT) |
| `tekton-hub-api` | OAuth application credentials and JWT configuration (used with login and rating mode) |

## Related Official Sources To Add Later

- About OpenShift Pipelines (concepts, CRDs)
- Installing and configuring OpenShift Pipelines
- Creating CI/CD solutions for applications using OpenShift Pipelines
- Pipelines as Code documentation
- OpenShift Pipelines security documentation
- OpenShift Pipelines observability documentation
