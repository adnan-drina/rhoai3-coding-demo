# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product family | Red Hat Advanced Developer Suite - software supply chain |
| Product version | 1.9 |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Documentation category | CI/CD |
| Official guide | Integrating GitHub Actions |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_advanced_developer_suite_-_software_supply_chain/1.9/html-single/integrating_github_actions/index |
| Multi-page URL | https://docs.redhat.com/en/documentation/red_hat_advanced_developer_suite_-_software_supply_chain/1.9/html/integrating_github_actions/index |
| Capture date | 2026-07-06 |

## Captured Sections

From Integrating GitHub Actions:

- Preface: pipeline secret requirements overview
- Chapter 1: Configuring GitHub Actions for external integration by using
  the UI
  - Prerequisites (ACS, Cosign, Trustification credentials)
  - Adding repository secrets (IMAGE_REGISTRY_PASSWORD,
    GITOPS_AUTH_PASSWORD, ROX_API_TOKEN, COSIGN_SECRET_PASSWORD,
    COSIGN_SECRET_KEY, TRUSTIFICATION_OIDC_CLIENT_SECRET)
  - Adding repository variables (IMAGE_REGISTRY_USER, ROX_CENTRAL_ENDPOINT,
    COSIGN_PUBLIC_KEY, TRUSTIFICATION_BOMBASTIC_API_URL,
    TRUSTIFICATION_OIDC_ISSUER_URL, TRUSTIFICATION_OIDC_CLIENT_ID,
    TRUSTIFICATION_SUPPORTED_CYCLONEDX_VERSION)
  - Optional Rekor and TUF variables (REKOR_HOST, TUF_MIRROR)
- Chapter 2: Configuring GitHub Actions for external integration by using
  the CLI
  - env_vars.sh environment variable file format
  - ghub-set-vars helper script (gh variable set, gh secret set)
  - Image registry credential options (Quay, JFrog Artifactory, Sonatype Nexus)
  - Script execution procedure

## Source Boundaries

This skill covers the "Integrating GitHub Actions" guide only. It provides
GitHub Actions secret and variable configuration for RHADS-SSC integration.
It does not cover:

- Azure Pipelines integration (separate guide)
- GitLab CI integration (separate guide)
- Jenkins integration (separate guide)
- Tekton pipeline definition (separate guide)
- RHADS-SSC installation or software template creation
- ACS, Cosign, or Trustification product configuration
