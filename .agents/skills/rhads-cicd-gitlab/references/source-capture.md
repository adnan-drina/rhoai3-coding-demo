# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product family | Red Hat Advanced Developer Suite - software supply chain |
| Product version | 1.9 |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Documentation category | CI/CD |
| Official guide | Integrating GitLab CI |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_advanced_developer_suite_-_software_supply_chain/1.9/html-single/integrating_gitlab_ci/index |
| Multi-page URL | https://docs.redhat.com/en/documentation/red_hat_advanced_developer_suite_-_software_supply_chain/1.9/html/integrating_gitlab_ci/index |
| Capture date | 2026-07-06 |

## Captured Sections

From Integrating GitLab CI:

- Preface: pipeline secret requirements overview
- Chapter 1: Configuring GitLab CI for external integration by using the UI
  - Prerequisites (ACS, Cosign, Trustification credentials)
  - Adding masked secrets (QUAY_IO_CREDS_PSW, ARTIFACTORY_IO_CREDS_PSW,
    NEXUS_IO_CREDS_PSW, GITOPS_AUTH_PASSWORD, ROX_API_TOKEN,
    COSIGN_SECRET_PASSWORD, COSIGN_SECRET_KEY,
    TRUSTIFICATION_OIDC_CLIENT_SECRET)
  - Adding unmasked variables (QUAY_IO_CREDS_USR,
    ARTIFACTORY_IO_CREDS_USR, NEXUS_IO_CREDS_USR, GITOPS_AUTH_USERNAME,
    ROX_CENTRAL_ENDPOINT, COSIGN_PUBLIC_KEY,
    TRUSTIFICATION_BOMBASTIC_API_URL, TRUSTIFICATION_OIDC_ISSUER_URL,
    TRUSTIFICATION_OIDC_CLIENT_ID,
    TRUSTIFICATION_SUPPORTED_CYCLONEDX_VERSION)
  - Optional Rekor and TUF variables (REKOR_HOST, TUF_MIRROR)
- Chapter 2: Configuring GitLab CI for external integration by using the CLI
  - env_vars.sh environment variable file format
  - glab-set-vars helper script (GitLab API, setVars function, masked flag)
  - Image registry credential options (Quay, JFrog Artifactory, Sonatype Nexus)
  - Script execution procedure
- Chapter 3: Configuring self-hosted GitLab runner requirements
  - Security Context Constraint (SCC) for OpenShift runners
  - SCC manifest (gitlab-ci-sa-scc) with capabilities and runAsUser
  - Maximum artifact size for self-hosted instances

## Source Boundaries

This skill covers the "Integrating GitLab CI" guide only. It provides GitLab CI
variable and secret configuration for RHADS-SSC integration and self-hosted
runner setup. It does not cover:

- Azure Pipelines integration (separate guide)
- GitHub Actions integration (separate guide)
- Jenkins integration (separate guide)
- Tekton pipeline definition (separate guide)
- RHADS-SSC installation or software template creation
- ACS, Cosign, or Trustification product configuration
