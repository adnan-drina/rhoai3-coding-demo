# Official Doc Extraction

This extraction is derived from the official RHADS-SSC 1.9 release notes
captured in `source-capture.md`.

## About This Release

RHADS-SSC 1.9 is generally available. Previously called Red Hat Trusted
Application Pipeline; starting with version 1.6 it became part of RHADS-SSC.

The TSSC installation program generates the first deployment but does not
support upgrades. Each product must be upgraded separately. The installer sizes
for proof-of-concept or very small teams.

## Compatibility Matrix

### RHADS-SSC Products

| Product | Version |
|---------|---------|
| Red Hat Developer Hub | 1.9 |
| Red Hat Trusted Artifact Signer | 1.3 |
| Red Hat Trusted Profile Analyzer | 2.2 |
| Conforma | 0.7 |

### OCP Subscription Products

| Product | Version | Subscription |
|---------|---------|-------------|
| OpenShift Container Platform | 4.18, 4.19, 4.20 | OCP |
| Red Hat OpenShift Pipelines | 1.21 | OCP |
| Red Hat OpenShift GitOps | 1.19 | OCP |
| Red Hat Advanced Cluster Security | 4.10 | OpenShift Platform Plus |

### RHDH Plugins (Supported)

Argo CD, GitHub, GitHub Org, GitLab Org, Keycloak, Kubernetes (backend), MSSV
(+ backend), RBAC, Tech Docs (+ backend), Tekton, Topology.

### RHDH Plugins (Technology Preview)

Argo CD (scaffolder), Azure DevOps (+ backend), Bitbucket Cloud, GitHub
Actions, GitLab (+ backend), Jenkins (+ backend), JFrog Artifactory, Kubernetes
(frontend), Nexus Repository Manager, Quay.

## New Features and Enhancements

| Feature | Summary |
|---------|---------|
| `--namespace` argument | Replaces stored namespace in config.yaml; default is `tssc` |
| GitHub App without PAT | GitHub App integration no longer requires a personal access token |
| Helm chart metadata | Automatic product disabling using Helm chart metadata |
| Deploy without RHDH | RHADS-SSC deployable without Red Hat Developer Hub |
| Runner image scripts | Tekton tasks use scripts from runner image directly |
| Azure cleanup | Sample Azure pipelines include resource cleanup step |
| Single org repos | All sample repos moved to `tssc-dev-multi-ci` organization |
| In-cluster GitLab | Templates compatible with in-cluster GitLab instances |
| Conforma policy repos | Policy configs moved to RHADS-SSC repositories |
| Standardized CI vars | Consistent variable/secret lifecycle across all CI providers |
| Non-blocking violations | Build pipeline policy violations non-blocking by default |
| No SBOM deprecation warnings | Updated to SBOM attestations, resolving Cosign warnings |
| Cleaner CI output | Unnecessary warnings removed from CI scripts |
| TSSC MCP topology tool | AI agents can query and visualize deployed topology |
| MCP server reliability | Improved tool reliability, error handling, and documentation |

## Fixed Issues

| Issue | Description |
|-------|-------------|
| CI tab GitLab | Correctly displays only selected CI provider |
| Argo CD commit names | Now appear in Deployment Lifecycle cards |
| CD tab with RBAC | Functions correctly when RBAC enabled |
| Tekton FETCH_HEAD | No longer fails intermittently in step-get-images-per-env |
| RHTPA/RHTAS integration | No longer disabled without user interaction |
| Deploy without Pipelines | No longer fails when OpenShift Pipelines disabled |
| Custom config path | `tssc config create /path/to/config.yaml` accepted |
| External RHTAS promotion | Variables propagated correctly for external RHTAS |

## Known Issues

| Issue | Impact | Workaround |
|-------|--------|------------|
| MSSV incompatible with RBAC | Plugin non-functional with RBAC | Disable RBAC or use unrestricted user |
| MSSV broken links | Artifactory, Nexus, SBOM links incorrect | None; fix planned |
| Unsupported environments | No air-gap, IBM Power/Z, ARM64, FIPS | None |
| No automated uninstall | No `tssc uninstall` command | Manually remove `tssc` namespaces |

## Unresolved Items

This document does not define:

- Upgrade procedures for individual products
- Detailed Conforma policy syntax
- RHDH plugin configuration parameters
- Cluster sizing for production use
