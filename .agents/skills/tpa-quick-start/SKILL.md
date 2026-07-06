---
name: tpa-quick-start
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "tpa"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Trusted Software Supply Chain"
description: >
  Use when getting started with Red Hat Trusted Profile Analyzer 2.2 managed
  service on Red Hat Hybrid Cloud Console, including SBOM upload, CVE scanning,
  and vulnerability analysis. Do NOT use for self-hosted deployment (use
  tpa-deployment), release notes (use tpa-release-notes), or administration
  (use tpa-admin).
---

# TPA Quick Start

Use this skill when helping users get started with the Red Hat Trusted Profile
Analyzer (RHTPA) 2.2 managed service on the Red Hat Hybrid Cloud Console.

## Source Grounding

Read `references/source-capture.md` before using product configuration details.
Official Red Hat docs are product authority. Red Hat articles and rh-brain are
supporting narrative and examples only.

## Key Quick-Start Workflows

### Searching for Vulnerability Information

Use the RHTPA managed service to search for existing SBOM documents, VEX
documents, license information, CVE details, and advisory information for Red
Hat products and software packages.

Scope limitation: the managed service currently provides information only for:

- Red Hat Enterprise Linux Universal Base Image (UBI) versions 8 and 9
- The Java Quarkus library

Access path: Hybrid Cloud Console -> Application Services -> Trusted Profile
Analyzer -> Search.

### Scanning an SBOM File

Upload and scan SBOM documents for vulnerability analysis. Supported formats:

- CycloneDX 1.3, 1.4, 1.5, 1.6
- SPDX 2.2, 2.3

Supports standard SBOMs, AI Bill of Materials (AIBOM) containing language
models, and Cryptographic Bill of Materials (CBOM) containing keys,
certificates, and libraries.

Red Hat does not retain a copy of scanned SBOM documents.

Access path: Hybrid Cloud Console -> Application Services -> Trusted Profile
Analyzer -> SBOMs -> Generate vulnerability report.

### IDE Integration: VS Code Dependency Analytics

The Dependency Analytics extension for VS Code provides access to RHTPA
vulnerability information directly in the IDE.

Supported ecosystems: Maven (`pom.xml`), NPM (`package.json`), Go (`go.mod`),
Python (`requirements.txt`), Gradle (`build.gradle`/`build.gradle.kts`),
Yarn (Berry/Classic), Dockerfiles.

Prerequisites: relevant package manager binaries in system `PATH`; for
Dockerfiles, `syft` binary required.

Exclude packages from analysis with the `exhortignore` comment tag in the
respective manifest file format.

### IDE Integration: IntelliJ Dependency Analytics

The Dependency Analytics plugin for IntelliJ IDEA provides the same
vulnerability scanning capabilities with identical ecosystem support.

Access: open a manifest file and hover over flagged dependencies, or right-click
the manifest in the Project window and select "Dependency Analytics Report".

## Workflow

1. Confirm user has a Red Hat account for Hybrid Cloud Console access.
2. Identify the task: search existing vulnerability data, scan an SBOM, or
   configure IDE integration.
3. Read `references/official-doc-extraction.md` for detailed procedures.
4. For SBOM scanning, confirm the document format is CycloneDX 1.3-1.6 or
   SPDX 2.2-2.3.
5. For IDE integration, confirm the target package manager is supported and
   the required binary is in `PATH`.
6. Validate results: check vulnerability report output, advisory counts, and
   remediation suggestions.

## Validation

- Hybrid Cloud Console accessible and TPA service visible in navigation
- SBOM scan produces a vulnerability summary with package-level CVE detail
- VS Code/IntelliJ Dependency Analytics extension shows inline component
  analysis markers on manifest dependencies
- `exhortignore` comment correctly suppresses flagged dependencies

## Related Skills

- `tpa-deployment` — self-hosted RHTPA deployment on OpenShift
- `tpa-release-notes` — RHTPA 2.2 release notes and known issues
- `tpa-admin` — RHTPA administration, configuration, and user management
- `tpa-quick-start` — this skill (managed service quick start)

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
