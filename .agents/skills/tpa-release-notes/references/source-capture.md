# Source Capture

## Official Source

| Field | Value |
|-------|-------|
| Product family | Red Hat Trusted Profile Analyzer |
| Product version | 2.2 (latest sub-release: 2.2.5) |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Documentation category | Discover |
| Official guide | Release notes |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_trusted_profile_analyzer/2.2/html-single/release_notes/index |
| Multi-page URL | https://docs.redhat.com/en/documentation/red_hat_trusted_profile_analyzer/2.2/html/release_notes/index |
| Capture date | 2026-07-06 |

## Captured Sections

- Chapter 1. Introduction
  - New for this release summary
- Chapter 2. New features and enhancements
  - Read-only mode
  - Optimized data model for large-scale SBOM deletions
  - Automated labeling of AIBOMs and CBOMs
  - Improved license search capabilities
  - Upload functionality relocation
  - New API endpoint for recommendations
  - Trusted Profile Analyzer Operator GA
  - SBOM document generator for Quay container images
- Chapter 3. Bug fixes
  - Replica logic, Entra ID OIDC, API endpoint consistency, dashboard SBOM
    deletion handling, `latest` API ancestors, missing API results, metrics
    endpoint ordering, circular SBOM references, CVE schema 5.2.0, Zstd
    compression upgrade, vulnerability retrieval performance, `spec.image`
    default, SBOM deletion performance, Operator reconciliation loop, importer
    PVC pending, Quay image tag expiry, orphaned document cleanup
- Chapter 4. Known issues
  - Resolved: CVE schema 5.2.0, Operator reconciliation loop, importer PVC
  - Unresolved: parallel instances, read-only importer crash, console
    read-only false positive, Helm validation, `authenticator.content`, ML
    model packages, cryptographic methods as packages, bulk uploads, CVSS
    score selection, SPDX license compliance, self-signed Quay certs, ODF
    `IncompleteBody`, large vulnerability loads, SBOM version search, load
    balancer idle drops, CPE 2.3, Helm 3.17 requirement, CVSS v4, advisory
    env/temporal score upload
- Chapter 5. Deprecated functionality
  - Delete vulnerability API endpoint removed

## Source Boundaries

This skill covers only the RHTPA 2.2 release notes (through sub-release
2.2.5). It documents what changed, what is new, what is fixed, what is known
to be broken, and what is deprecated.

This skill does NOT cover:

- RHTPA installation, deployment, or Operator setup procedures
- RHTPA quick start or getting started workflows
- RHTPA administration, Helm Chart configuration, or OIDC provider setup
- SBOM authoring, ingestion workflows, or API usage guides
- RHTPA versions other than 2.2.x
- Red Hat Trusted Artifact Signer or other TSSC components

## Related Official Sources

- RHTPA 2.2 documentation: https://docs.redhat.com/en/documentation/red_hat_trusted_profile_analyzer/2.2
- RHTPA deployment guide: https://docs.redhat.com/en/documentation/red_hat_trusted_profile_analyzer/2.2/html-single/deploying_red_hat_trusted_profile_analyzer/index
- RHTPA administration guide: https://docs.redhat.com/en/documentation/red_hat_trusted_profile_analyzer/2.2/html-single/administration_guide/index
- RHTPA quick start guide: https://docs.redhat.com/en/documentation/red_hat_trusted_profile_analyzer/2.2/html-single/quick_start_guide/index
