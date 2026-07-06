# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product | Red Hat Advanced Developer Suite - Software Supply Chain |
| Product version | 1.9 |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Chapter or page title | Inspecting SBOMs |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_advanced_developer_suite_-_software_supply_chain/1.9/html-single/inspecting_sboms/index |
| Documentation category | Secure Your Software Supply Chain |
| Capture date | 2026-07-06 |

## Captured Sections

From "Inspecting SBOMs":

- Preface: SBOM purpose and Trusted Profile Analyzer overview
- Chapter 1: Downloading, converting, and analyzing your SBOM
  - Automatic SBOM publishing note (RHADS-SSC 1.9)
  - Prerequisites (cosign, syft, jq)
  - Finding the container image address
  - Downloading the SBOM with cosign
  - Renaming the SBOM component for RHTPA display
  - Retrieving the Bombastic API URL via oc route selector
  - Creating the token_issuer_url from Keycloak route
  - Obtaining TPA OIDC Walker client secret
  - Acquiring a bearer token for the Bombastic API
  - Uploading the SBOM to RHTPA
  - Converting SBOM to CycloneDX 1.4 with syft (fallback)
  - Re-uploading after format conversion
  - Reviewing the Dependency Analytics Report

## Source Boundaries

This skill captures:

- End-to-end SBOM inspection workflow with RHTPA
- cosign SBOM download from container registries
- Bombastic API v2 authentication and upload
- Keycloak OIDC token acquisition for TPA (walker client, chicken realm)
- syft CycloneDX version conversion as upload fallback
- SBOM component name customization for RHTPA UI
- Dependency Analytics Report navigation

This skill does not capture:

- RHADS-SSC installation or initial setup
- Template or pipeline customization (use rhads-customize)
- Conforma policy management (use rhads-compliance)
- Container image signing and attestation (use rhads-compliance)
- RHTPA installation and administration (use tpa-* skills)
- Build pipeline configuration that produces the SBOM

## API Versions and CRDs

No CRDs are directly managed by this workflow.

| Component | Notes |
|-----------|-------|
| Bombastic API | REST API v2 for SBOM upload (`/api/v2/sbom`) |
| Keycloak | OIDC token issuer; realm `chicken`, client `walker` |
| tssc-trustification-integration Secret | Contains `oidc_client_secret` for TPA |
| Route (bombastic-api) | Selector: `app.kubernetes.io/name=bombastic-api` in `tssc` namespace |
| Route (keycloak) | Selector: `app=keycloak` in `tssc-keycloak` namespace |

## Related Official Sources To Add Later

- Red Hat Advanced Developer Suite - SSC 1.9 Installation Guide
- Red Hat Advanced Developer Suite - SSC 1.9 Customizing RHADS-SSC
- Red Hat Advanced Developer Suite - SSC 1.9 Managing Compliance
- Red Hat Trusted Profile Analyzer 2.2 Documentation
