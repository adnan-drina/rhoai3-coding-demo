---
name: tpa-release-notes
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "tpa"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Trusted Software Supply Chain"
description: >
  Use when checking Red Hat Trusted Profile Analyzer 2.2 release notes, new
  features, bug fixes, known issues, and CVE fixes. Do NOT use for deployment
  (use tpa-deployment), quick start (use tpa-quick-start), or administration
  (use tpa-admin).
---

# TPA Release Notes

Use this skill to ground Trusted Profile Analyzer release information in the
official Red Hat Trusted Profile Analyzer 2.2 release notes for the active
baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority.

## Release Summary

Red Hat Trusted Profile Analyzer (RHTPA) 2.2 is a proactive service for risk
management of Open Source Software packages and dependencies. The latest
sub-release is **2.2.5**.

New for this release:

- Read-only mode for upgrades and data migration
- RHTPA Operator for OpenShift is generally available (GA)
- SBOM document deletion capability
- SBOM generation from Quay container images
- Package recommendations and remediation API endpoint
- Improved SBOM vulnerability retrieval performance
- Automated AIBOM and CBOM labeling for CycloneDX SBOMs
- Enhanced license search and management UI

## Key Topics

- New features: read-only mode, Operator GA, SBOM deletion, Quay SBOM
  generator, recommendations API, AIBOM/CBOM auto-labeling, license search UI,
  upload UI relocation
- Bug fixes: Entra ID OIDC auth, API endpoint consistency, circular SBOM
  references, CVE schema 5.2.0 import, Zstd compression upgrade path,
  Operator reconciliation frequency, importer PVC storage class, Quay image
  tag expiry, orphaned document cleanup, SBOM deletion performance
- Known issues (unresolved): no parallel instances on same cluster, importer
  crash in read-only mode, console read-only false positive, Helm Chart
  validation in OpenShift Console, `authenticator.content` Helm value, ML model
  package details, bulk upload failures, CVSS score selection, SPDX license
  compliance, self-signed Quay certs, ODF `IncompleteBody`, no CPE 2.3 or
  CVSS v4 support, Helm 3.17+ requirement
- Deprecated: delete vulnerability API endpoint removed

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Identify whether the question concerns:
   - new features in RHTPA 2.2
   - Operator GA status and upgrade considerations
   - bug fixes (API, SBOM processing, auth, performance)
   - known issues and workarounds
   - deprecated or removed functionality
4. Use exact feature names, API endpoints, and Helm values from the extraction.
5. When advising on upgrades from 2.1.x, cross-reference the Zstd compression
   fix, `spec.image` CR patch, and known issues.

## Related Skills

- Use `tpa-deployment` for installing RHTPA on OpenShift.
- Use `tpa-quick-start` for getting started with RHTPA.
- Use `tpa-admin` for administering and configuring RHTPA.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
