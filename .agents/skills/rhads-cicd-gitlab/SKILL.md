---
name: rhads-cicd-gitlab
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhads"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Trusted Software Supply Chain"
description: >
  Use when configuring GitLab CI for secure CI/CD workflows with RHADS-SSC 1.9:
  adding masked secrets and variables for ACS, Cosign, Trustification, and
  image registry integration via the GitLab UI or CLI; automating variable
  setup with glab-set-vars helper scripts; and configuring self-hosted GitLab
  runner requirements including SCC and artifact size. Do NOT use for Azure
  Pipelines (use rhads-cicd-azure), GitHub Actions (use rhads-cicd-github),
  Jenkins (use rhads-cicd-jenkins), or Tekton pipelines (use rhads-cicd-tekton).
---

# RHADS-SSC GitLab CI Integration

Use this skill to ground GitLab CI configuration in official Red Hat Advanced
Developer Suite - software supply chain (RHADS-SSC) 1.9 documentation.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority.

## Purpose

GitLab CI integrates with RHADS-SSC to perform vulnerability scanning, image
signing, and attestation generation. Pipelines require specific secrets and
variables configured as GitLab CI/CD variables.

## Prerequisites

- RHADS-SSC installed on an OpenShift cluster with `private.env` generated
- GitLab repository for application source and GitOps
- Authentication details for ACS (ROX endpoint, API token)
- Cosign signing key (password, private key, public key)
- Trustification credentials (API URL, issuer URL, client ID, client secret,
  supported CycloneDX version)

## Configuration Methods

GitLab CI variables can be configured via:

1. **GitLab UI** — Settings > CI/CD > Variables
2. **CLI** — `glab-set-vars` helper script using the GitLab API

## Required Secrets (Masked)

| Variable | Purpose |
|----------|---------|
| `QUAY_IO_CREDS_PSW` | Quay repository password |
| `ARTIFACTORY_IO_CREDS_PSW` | JFrog Artifactory password |
| `NEXUS_IO_CREDS_PSW` | Sonatype Nexus password |
| `GITOPS_AUTH_PASSWORD` | GitOps repository update token |
| `ROX_API_TOKEN` | ACS API access |
| `COSIGN_SECRET_PASSWORD` | Cosign signing key password |
| `COSIGN_SECRET_KEY` | Cosign private key |
| `TRUSTIFICATION_OIDC_CLIENT_SECRET` | Trustification OIDC auth |

## Required Variables (Unmasked)

| Variable | Purpose |
|----------|---------|
| `QUAY_IO_CREDS_USR` | Quay repository username |
| `ARTIFACTORY_IO_CREDS_USR` | JFrog Artifactory username |
| `NEXUS_IO_CREDS_USR` | Sonatype Nexus username |
| `GITOPS_AUTH_USERNAME` | OpenShift GitOps username |
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

The `glab-set-vars` helper script sets all variables using the GitLab API:

```bash
source env_vars.sh
chmod +x glab-set-vars
./glab-set-vars your_repository_name
```

The script uses `MY_GITLAB_TOKEN` and `MY_GITLAB_USER` environment variables.
By default, `setVars` creates masked variables; pass `false` as the third
argument for unmasked variables.

## Self-Hosted Runner Requirements

### Security Context Constraint (SCC)

Required when using self-hosted GitLab runners on OpenShift. Apply a custom SCC
(`gitlab-ci-sa-scc`) to the runner service account. The SCC allows privilege
escalation and `SETFCAP`/`MKNOD` capabilities with `runAsUser: 0`.

```bash
oc apply -f gitlab-ci-scc.yml
oc get scc gitlab-ci-sa-scc
```

### Maximum Artifact Size

Required when using a self-hosted GitLab instance. Adjust the maximum artifact
size in GitLab admin settings.

## Verification

Rerun the last pipeline run or commit a minor change to trigger a new run.
If secrets are correctly applied, the pipeline completes successfully.

## Workflow

1. Read `references/official-doc-extraction.md`.
2. Configure secrets and variables (UI or CLI method).
3. Set optional Rekor/TUF variables if runners are off-cluster.
4. Configure SCC if using self-hosted runners on OpenShift.
5. Trigger a pipeline run and verify end-to-end execution.

## Related Skills

- `rhads-cicd-azure` for Azure Pipelines integration.
- `rhads-cicd-github` for GitHub Actions integration.
- `rhads-cicd-jenkins` for Jenkins integration.
- `rhads-cicd-tekton` for Tekton pipeline and webhook configuration.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
