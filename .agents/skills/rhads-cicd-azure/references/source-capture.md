# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product family | Red Hat Advanced Developer Suite - software supply chain |
| Product version | 1.9 |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Documentation category | CI/CD |
| Official guide | Integrating Azure Pipelines |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_advanced_developer_suite_-_software_supply_chain/1.9/html-single/integrating_azure_pipelines/index |
| Multi-page URL | https://docs.redhat.com/en/documentation/red_hat_advanced_developer_suite_-_software_supply_chain/1.9/html/integrating_azure_pipelines/index |
| Capture date | 2026-07-06 |

## Captured Sections

From Integrating Azure Pipelines:

- Preface: pipeline secret requirements overview
- Chapter 1: Adding secrets and variables to Azure Pipelines for integration
  with external tools
  - Prerequisites (ACS, Cosign, Trustification credentials)
  - Automated setup with `ci-set-org-vars.sh -b azure`
  - Image registry and GitOps secrets (IMAGE_REGISTRY_PASSWORD,
    GITOPS_AUTH_PASSWORD)
  - ACS and SBOM secrets (ROX_API_TOKEN, COSIGN_SECRET_PASSWORD,
    COSIGN_SECRET_KEY, TRUSTIFICATION_OIDC_CLIENT_SECRET)
  - Image registry and GitOps variables (IMAGE_REGISTRY_USER,
    GITOPS_AUTH_USERNAME)
  - ACS and SBOM variables (ROX_CENTRAL_ENDPOINT, COSIGN_PUBLIC_KEY,
    TRUSTIFICATION_BOMBASTIC_API_URL, TRUSTIFICATION_OIDC_ISSUER_URL,
    TRUSTIFICATION_OIDC_CLIENT_ID,
    TRUSTIFICATION_SUPPORTED_CYCLONEDX_VERSION)
  - Optional Rekor and TUF variables (REKOR_HOST, TUF_MIRROR)
  - Pipeline permissions and variable group authorization
  - Custom variable group name in azure-pipelines.yml
- Chapter 2: Creating pipelines for integration with application and GitOps
  repositories
  - Prerequisites (variable group, agent pool, repositories)
  - Pipeline creation procedure for source and GitOps repos

## Source Boundaries

This skill covers the "Integrating Azure Pipelines" guide only. It provides
Azure Pipelines variable and secret configuration for RHADS-SSC integration.
It does not cover:

- GitHub Actions integration (separate guide)
- GitLab CI integration (separate guide)
- Jenkins integration (separate guide)
- Tekton pipeline definition (separate guide)
- RHADS-SSC installation or software template creation
- ACS, Cosign, or Trustification product configuration
