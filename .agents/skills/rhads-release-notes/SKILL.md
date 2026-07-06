---
name: rhads-release-notes
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhads"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Trusted Software Supply Chain"
description: >
  Use when checking RHADS-SSC 1.9 release notes, new features, bug fixes, and
  known issues. Covers the compatibility matrix (product versions, OCP versions,
  RHDH plugins), new features (namespace config, GitHub Apps, Helm metadata,
  RHDH-less deploy, TSSC MCP server topology tool), fixed issues, and known
  issues (MSSV/RBAC, unsupported environments, no automated uninstall). Do NOT
  use for installation steps, CLI usage, or architecture overview; use sibling
  rhads-* skills instead.
---

# RHADS-SSC 1.9 Release Notes

Use this skill to answer questions about what changed in RHADS-SSC 1.9,
compatibility requirements, fixed bugs, and known limitations.

## Source Grounding

Read `references/source-capture.md` before citing release-specific information.

## Key Facts

- RHADS-SSC 1.9 is GA. Previously called Red Hat Trusted Application Pipeline.
- The TSSC installer generates the first deployment but does not support
  upgrades; each product must be upgraded separately.
- The installer sizes for proof-of-concept; larger teams need manual
  reconfiguration per product docs.

## Compatibility Matrix

| Product | Version |
|---------|---------|
| Red Hat Developer Hub | 1.9 |
| Red Hat Trusted Artifact Signer | 1.3 |
| Red Hat Trusted Profile Analyzer | 2.2 |
| Conforma | 0.7 |
| OpenShift Container Platform | 4.18, 4.19, 4.20 |
| Red Hat OpenShift Pipelines | 1.21 |
| Red Hat OpenShift GitOps | 1.19 |
| Red Hat Advanced Cluster Security | 4.10 |

## Notable New Features (1.9)

- `--namespace` argument replaces stored namespace in config.yaml
- GitHub App integration no longer requires a PAT
- Helm chart metadata for automatic product disabling
- Deploy without Red Hat Developer Hub
- Tekton tasks use scripts from runner image directly
- TSSC MCP server topology tool for AI-driven visualization
- Standardized CI variables/secrets across all providers
- Non-blocking policy violations in build pipelines
- Conforma policies moved to RHADS-SSC repositories

## Known Issues

- MSSV plugin incompatible with RBAC
- Broken links in MSSV for Artifactory, Nexus, SBOMs
- No support for air-gapped, IBM Power/Z, ARM64, or FIPS
- No automated uninstallation command

## Workflow

1. Read `references/official-doc-extraction.md` for full detail.
2. Check the compatibility matrix before recommending product versions.
3. Review known issues before troubleshooting deployment problems.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
