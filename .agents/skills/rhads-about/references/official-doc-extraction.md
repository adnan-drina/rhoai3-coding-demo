# Official Doc Extraction

This extraction is derived from the official RHADS-SSC 1.9 "Understanding"
chapter captured in `source-capture.md`.

## Product Overview

Red Hat Advanced Developer Suite - software supply chain (RHADS-SSC) is a
DevSecOps framework that integrates security from project inception to
production. It reduces security risks in CI/CD pipelines by embedding security
checks, ensuring artifact integrity, and enabling compliance with standards
such as Supply chain Levels for Software Artifacts (SLSA).

RHADS-SSC was previously known as Red Hat Trusted Application Pipeline.
Starting with version 1.6, it became part of Red Hat Advanced Developer Suite -
software supply chain.

## Key Features

| Feature | Description |
|---------|-------------|
| Customizable templates | Start projects with templates that include established security practices |
| Secure CI/CD pipelines | Build, test, and deploy container images securely with pre-configured pipelines integrated with Git |
| Integrated security checks | Detect and address vulnerabilities with detailed insights |
| SBOM management | Auto-generate SBOM for each pipeline; sign attestations for traceability and compliance |
| Tamper-proof artifact signing | Cryptographic signatures on code and artifacts; immutable log of build/deploy activities |
| Compliance and policy enforcement | SLSA Level 3, approval gates, vulnerability scans, policy-verified artifacts |

## Integrated Technologies

| Component | Role |
|-----------|------|
| Red Hat Developer Hub (RHDH) | Self-service portal integrating security best practices |
| Red Hat Trusted Artifact Signer (RHTAS) | Software integrity through signature and attestation |
| Red Hat Trusted Profile Analyzer (RHTPA) | SBOM creation and management for transparency and compliance |
| Red Hat Advanced Cluster Security (RHACS) | Vulnerability scanning of artifacts |
| OpenShift GitOps | Application deployment and lifecycle management automation |
| OpenShift Pipelines | CI/CD process automation with visibility and control |

## Configuration Options

### CI/CD Pipelines

| Provider | SLSA Level | Notes |
|----------|-----------|-------|
| Tekton | Build L3 | Default |
| Jenkins | Build L2 | |
| GitHub Actions | Build L2 | |
| GitLab CI | Build L2 | |
| Azure CI | Build L2 | Technology Preview |

### Source Repositories

- GitHub (Default)
- GitLab
- Bitbucket Cloud

### Artifact Registries

- Quay
- JFrog Artifactory
- Sonatype Nexus Repository

## Development Workflow

The official workflow is three steps:

1. **Start with secure templates**: Use pre-built templates from RHDH for a
   secure foundation including code repositories, documentation, and
   pre-configured CI/CD pipelines.
2. **Develop and modify code**: Each code change triggers a pipeline that
   automatically performs security checks including artifact signing,
   vulnerability scanning, and SBOM generation.
3. **OpenShift GitOps driven deployment**: RHADS-SSC enforces security policies
   throughout the development lifecycle using Conforma, ensuring only compliant
   builds are deployed.

## Unresolved Items

This chapter does not define:

- Specific operator names, channels, or Subscription resources
- Installation prerequisites or cluster sizing
- Conforma policy configuration details
- RBAC or namespace setup
- CLI tool usage

Use the relevant component skills or installation documentation for those items.
