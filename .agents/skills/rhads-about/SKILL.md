---
name: rhads-about
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhads"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Trusted Software Supply Chain"
description: >
  Use when explaining RHADS-SSC concepts, architecture, Trusted Application
  Pipeline, and software supply chain security capabilities. Covers the
  DevSecOps framework, key features (customizable templates, secure CI/CD,
  SBOM management, tamper-proof signing, compliance/policy enforcement),
  integrated technologies (RHDH, RHTAS, RHTPA, RHACS, OpenShift GitOps,
  OpenShift Pipelines), configuration options (CI/CD providers, source repos,
  artifact registries), and the development workflow. Do NOT use for
  installation steps, CLI usage, or release-specific changes; use
  rhads-getting-started, rhads-standalone-clis, or rhads-release-notes instead.
---

# RHADS-SSC Overview

Use this skill to ground explanations of Red Hat Advanced Developer Suite -
software supply chain (RHADS-SSC) 1.9 concepts, architecture, and capabilities
in official product documentation.

## Source Grounding

Read `references/source-capture.md` before citing product capabilities.
Official Red Hat documentation is product authority. This skill covers the
"Understanding" guide — high-level features, integrated technologies,
configuration options, and workflow.

## Product Identity

RHADS-SSC is a DevSecOps framework that integrates security from project
inception to production. It reduces security risks in CI/CD pipelines by
embedding security checks, ensuring artifact integrity, and enabling compliance
with standards such as SLSA.

Previously known as Red Hat Trusted Application Pipeline. Starting with version
1.6, it became part of Red Hat Advanced Developer Suite - software supply chain.

## Key Features

- Customizable templates with established security practices
- Secure CI/CD pipelines (build, test, deploy container images)
- Integrated security checks for vulnerability detection
- SBOM management (automatic generation, signed attestations, traceability)
- Tamper-proof artifact signing (cryptographic signatures, immutable logs)
- Compliance and policy enforcement (SLSA Level 3, approval gates, policy scans)

## Integrated Technologies

| Component | Role |
|-----------|------|
| Red Hat Developer Hub (RHDH) | Self-service portal with security best practices |
| Red Hat Trusted Artifact Signer (RHTAS) | Signature and attestation for artifact integrity |
| Red Hat Trusted Profile Analyzer (RHTPA) | SBOM creation and management |
| Red Hat Advanced Cluster Security (RHACS) | Vulnerability scanning of artifacts |
| OpenShift GitOps | Deployment automation and lifecycle management |
| OpenShift Pipelines | CI/CD process automation |

## Configuration Options

- **CI/CD**: Tekton (default, SLSA L3), Jenkins, GitHub Actions, GitLab CI, Azure CI (Tech Preview)
- **Source repos**: GitHub (default), GitLab, Bitbucket Cloud
- **Artifact registries**: Quay, JFrog Artifactory, Sonatype Nexus Repository

## Development Workflow

1. Start with secure templates from RHDH
2. Develop and modify code (triggers pipeline with security checks, signing, SBOM)
3. OpenShift GitOps-driven deployment with Conforma policy enforcement

## Workflow

1. Read `references/official-doc-extraction.md` for full detail.
2. When describing RHADS-SSC, map capabilities to the official features list.
3. When diagramming architecture, use the integrated technologies table.
4. For implementation specifics, switch to the relevant component skill.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
