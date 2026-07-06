# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product | Red Hat Trusted Profile Analyzer |
| Version | 2.2 |
| Documentation category | Reference |
| Official guide | Administration Guide |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_trusted_profile_analyzer/2.2/html-single/administration_guide/index |
| Multi-page URL | https://docs.redhat.com/en/documentation/red_hat_trusted_profile_analyzer/2.2/html/administration_guide/index |
| Capture date | 2026-07-06 |

## Captured Sections

From Administration Guide:

- Chapter 1: Overview of Red Hat Trusted Profile Analyzer (product overview,
  SPOG view, Exhort backend, SBOM/VEX/CVE concepts, CVSS scoring)
- Chapter 2: Data importers (available sources, scheduling, computing resources,
  default state)
- Chapter 3: Creating a software bill of materials manifest file (Syft CLI,
  CycloneDX and SPDX generation from images and filesystems, Technology Preview
  note)
- Chapter 4: Scanning a software bill of materials file (console upload,
  standard SBOM / AIBOM / CBOM support, no data retention)
- Chapter 5: Searching for vulnerability and license information (search
  queries, filtering by date/format/license)
- Chapter 6: Downloading and viewing license information (CSV export, SPDX
  license reference)
- Chapter 7: Editing labels for SBOMs and advisories (add/remove custom labels)
- Chapter 8: Deleting an SBOM document or an advisory (console deletion
  procedure)
- Chapter 9: Configuring Microsoft Entra ID as an OpenID Connect provider
  (API registration, scopes, application roles, frontend registration, Helm
  values, auth.yaml ConfigMap, scopeMappings, token version v2)
- Chapter 10: Frequently asked questions (product overview, benefits, telemetry,
  deployment types, supported formats, CI/CD integration)

## Source Boundaries

This skill covers the Administration Guide only. It provides admin procedures
for managing data importers, SBOM lifecycle, OIDC identity configuration, and
day-to-day RHTPA operations. It does not cover:

- Deployment and installation procedures (separate Deployment Guide)
- Quick start tutorials (separate Quick Start Guide)
- Release notes and known issues (separate Release Notes)
- Red Hat Dependency Analytics IDE plugin configuration
- Detailed API endpoint specifications beyond what the admin guide documents
- Exhort backend internals

## Deployment Platforms Documented

| Platform | Notes |
|----------|-------|
| Red Hat OpenShift Container Platform | 4.16 or later |
| Red Hat Enterprise Linux | Supported but admin guide focuses on OCP |

## Related Official Sources To Add Later

- Deployment Guide (tpa-deployment skill)
- Quick Start Guide (tpa-quick-start skill)
- Release Notes (tpa-release-notes skill)
- Red Hat Dependency Analytics documentation
- Exhort API reference
