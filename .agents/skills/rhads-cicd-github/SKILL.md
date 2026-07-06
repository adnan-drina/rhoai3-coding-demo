---
name: rhads-cicd-github
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhads"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Trusted Software Supply Chain"
description: >
  Use when configuring GitHub Actions for secure CI/CD workflows with
  RHADS-SSC 1.9: adding repository secrets and variables for ACS, Cosign,
  Trustification, and image registry integration via the GitHub UI or CLI;
  automating variable setup with ghub-set-vars helper scripts; and verifying
  pipeline execution. Do NOT use for Azure Pipelines (use rhads-cicd-azure),
  GitLab CI (use rhads-cicd-gitlab), Jenkins (use rhads-cicd-jenkins), or
  Tekton pipelines (use rhads-cicd-tekton).
---

# RHADS-SSC GitHub Actions Integration

Use this skill to ground GitHub Actions CI/CD configuration in official
Red Hat Advanced Developer Suite - software supply chain (RHADS-SSC) 1.9
documentation.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority.

## Purpose

GitHub Actions integrate with RHADS-SSC to perform vulnerability scanning,
image signing, and attestation generation. Pipelines require specific secrets
and variables configured as GitHub repository secrets and variables.

## Prerequisites

- RHADS-SSC installed on an OpenShift cluster with `private.env` generated
- GitHub repository for application source and GitOps
- Authentication details for ACS (ROX endpoint, API token)
- Cosign signing key (password, private key, public key)
- Trustification credentials (API URL, issuer URL, client ID, client secret,
  supported CycloneDX version)

## Configuration Methods

GitHub Actions secrets and variables can be configured via:

1. **GitHub UI** — Actions > Secrets and variables page
2. **CLI** — `ghub-set-vars` helper script using `gh` CLI

## Required Secrets

| Variable | Purpose |
|----------|---------|
| `IMAGE_REGISTRY_PASSWORD` | Image registry access |
| `GITOPS_AUTH_PASSWORD` | GitOps repository update token |
| `ROX_API_TOKEN` | ACS API access |
| `COSIGN_SECRET_PASSWORD` | Cosign signing key password |
| `COSIGN_SECRET_KEY` | Cosign private key |
| `TRUSTIFICATION_OIDC_CLIENT_SECRET` | Trustification OIDC auth |

## Required Variables

| Variable | Purpose |
|----------|---------|
| `IMAGE_REGISTRY_USER` | Image registry username |
| `ROX_CENTRAL_ENDPOINT` | ACS central server endpoint |
| `COSIGN_PUBLIC_KEY` | Cosign public key |
| `TRUSTIFICATION_BOMBASTIC_API_URL` | SBOM API URL |
| `TRUSTIFICATION_OIDC_ISSUER_URL` | OIDC issuer URL |
| `TRUSTIFICATION_OIDC_CLIENT_ID` | OIDC client ID |
| `TRUSTIFICATION_SUPPORTED_CYCLONEDX_VERSION` | CycloneDX version |

## Optional Variables

| Variable | Condition |
|----------|-----------|
| `REKOR_HOST` | CI runners not on same cluster as RHADS-SSC |
| `TUF_MIRROR` | CI runners not on same cluster as RHADS-SSC |

## CLI Automation

The `ghub-set-vars` helper script sets all secrets and variables using the
GitHub CLI (`gh`):

```bash
source env_vars.sh
chmod +x ghub-set-vars
./ghub-set-vars your_repository_name
```

The `env_vars.sh` file contains all credential exports. The script uses
`gh variable set` for unmasked variables and `gh secret set` for secrets.

## Verification

Rerun the last pipeline run or commit a minor change to trigger a new run.
If secrets are correctly applied, the pipeline completes successfully.

## Workflow

1. Read `references/official-doc-extraction.md`.
2. Configure secrets and variables (UI or CLI method).
3. Set optional Rekor/TUF variables if runners are off-cluster.
4. Trigger a pipeline run and verify end-to-end execution.

## Related Skills

- `rhads-cicd-azure` for Azure Pipelines integration.
- `rhads-cicd-gitlab` for GitLab CI integration.
- `rhads-cicd-jenkins` for Jenkins integration.
- `rhads-cicd-tekton` for Tekton pipeline and webhook configuration.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
