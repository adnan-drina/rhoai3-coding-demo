# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product family | Red Hat Advanced Developer Suite - software supply chain |
| Product version | 1.9 |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Documentation category | CI/CD |
| Official guide | Integrating Jenkins |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_advanced_developer_suite_-_software_supply_chain/1.9/html-single/integrating_jenkins/index |
| Multi-page URL | https://docs.redhat.com/en/documentation/red_hat_advanced_developer_suite_-_software_supply_chain/1.9/html/integrating_jenkins/index |
| Capture date | 2026-07-06 |

## Captured Sections

From Integrating Jenkins:

- Preface: setup sequence overview (secrets first, then add application)
- Chapter 1: Adding secrets to Jenkins for integration with external tools
  - Prerequisites (ACS, Cosign, Trustification credentials)
  - Automated setup with `ci-set-org-vars.sh -b jenkins`
  - Image registry credentials (QUAY_IO_CREDS, ARTIFACTORY_IO_CREDS,
    NEXUS_IO_CREDS, GITOPS_AUTH_PASSWORD)
  - ACS and SBOM secrets (ROX_API_TOKEN, COSIGN_SECRET_PASSWORD,
    COSIGN_SECRET_KEY, TRUSTIFICATION_OIDC_CLIENT_SECRET)
  - Uncommenting Artifactory/Nexus lines in Jenkinsfiles
- Chapter 2: Adding environment variables to Jenkins for integration with
  external tools
  - Global properties > Environment variables procedure
  - GitOps variable (GITOPS_AUTH_USERNAME for GitLab)
  - ACS and SBOM variables (ROX_CENTRAL_ENDPOINT, COSIGN_PUBLIC_KEY,
    TRUSTIFICATION_BOMBASTIC_API_URL, TRUSTIFICATION_OIDC_ISSUER_URL,
    TRUSTIFICATION_OIDC_CLIENT_ID,
    TRUSTIFICATION_SUPPORTED_CYCLONEDX_VERSION)
  - Optional Rekor and TUF variables (REKOR_HOST, TUF_MIRROR)
- Chapter 3: Adding your application to Jenkins
  - Pipeline project creation (name must match application name)
  - catalog-info.yaml jenkins.io/job-full-name field
  - Repository URL configuration
  - Build Now and pipeline verification
  - RHDH integration (CI tab, CD tab, Catalog Resource, Topology)

## Source Boundaries

This skill covers the "Integrating Jenkins" guide only. It provides Jenkins
credential, environment variable, and application configuration for RHADS-SSC
integration. It does not cover:

- Azure Pipelines integration (separate guide)
- GitHub Actions integration (separate guide)
- GitLab CI integration (separate guide)
- Tekton pipeline definition (separate guide)
- RHADS-SSC installation or software template creation
- ACS, Cosign, or Trustification product configuration
- Jenkins installation or general Jenkins administration
