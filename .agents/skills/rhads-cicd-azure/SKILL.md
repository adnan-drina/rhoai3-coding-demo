---
name: rhads-cicd-azure
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhads"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Trusted Software Supply Chain"
description: >
  Use when configuring Azure Pipelines for secure CI/CD workflows with
  RHADS-SSC 1.9: adding secrets and variables for ACS, Cosign, Trustification,
  and image registry integration; automating variable group setup with
  ci-set-org-vars.sh; creating pipelines for application and GitOps
  repositories; and authorizing pipeline access to variable groups. Do NOT use
  for GitHub Actions (use rhads-cicd-github), GitLab CI (use rhads-cicd-gitlab),
  Jenkins (use rhads-cicd-jenkins), or Tekton pipelines (use rhads-cicd-tekton).
---

# RHADS-SSC Azure Pipelines Integration

Use this skill to ground Azure Pipelines CI/CD configuration in official
Red Hat Advanced Developer Suite - software supply chain (RHADS-SSC) 1.9
documentation.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority.

## Purpose

Azure Pipelines integrate with RHADS-SSC to perform vulnerability scanning,
image signing, and attestation generation. Pipelines require specific secrets
and variables to connect with external tools such as Quay, JFrog Artifactory,
Red Hat Advanced Cluster Security (RHACS), Cosign, and Trustification.

## Prerequisites

- RHADS-SSC installed on an OpenShift cluster with `private.env` generated
- Azure DevOps project with an active agent pool
- Authentication details for ACS (ROX endpoint, API token)
- Cosign signing key (password, private key, public key)
- Trustification credentials (API URL, issuer URL, client ID, client secret,
  supported CycloneDX version)

## Automated Variable Group Setup

The `ci-set-org-vars.sh` script from the `tssc-cli` image creates a variable
group named `tssc` with all required variables and secrets:

```bash
bash-5.1$ ./scripts/ci-set-org-vars.sh -b azure -p <devops_project>
```

Override the variable group name with `-g`:

```bash
bash-5.1$ ./scripts/ci-set-org-vars.sh -b azure -p <devops_project> -g <custom-name>
```

## Required Secrets (Masked)

| Variable | Purpose |
|----------|---------|
| `IMAGE_REGISTRY_PASSWORD` | Image registry access |
| `GITOPS_AUTH_PASSWORD` | GitOps repository update token |
| `ROX_API_TOKEN` | ACS API access |
| `COSIGN_SECRET_PASSWORD` | Cosign signing key password |
| `COSIGN_SECRET_KEY` | Cosign private key |
| `TRUSTIFICATION_OIDC_CLIENT_SECRET` | Trustification OIDC auth |

## Required Variables (Unmasked)

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
| `GITOPS_AUTH_USERNAME` | Required for Bitbucket integration |
| `REKOR_HOST` | CI runners not on same cluster as RHADS-SSC |
| `TUF_MIRROR` | CI runners not on same cluster as RHADS-SSC |

## Pipeline Configuration

If the variable group uses a name other than `tssc`, update `azure-pipelines.yml`:

```yaml
variables:
    - group: <my-variable-group>
```

After configuring variables, authorize pipelines to access the variable group
via Pipeline permissions in the variable group settings.

## Creating Pipelines

Pipelines are created for both the application source repository and the GitOps
repository. Each pipeline requires:

- Azure Pipelines variable group with all required secrets and variables
- Active agent pool with pipeline permissions
- Source and GitOps repositories from RHDH software templates
- Corresponding pool name and variable group in `azure-pipelines.yml`

## Verification

Rerun the latest pipeline. If secrets are correctly applied, the pipeline
completes successfully. Verify that ACS scanning, SBOM generation, and image
signing tasks show expected output.

## Workflow

1. Read `references/official-doc-extraction.md`.
2. Configure secrets and variables (automated or manual).
3. Create pipelines for application source and GitOps repositories.
4. Authorize pipeline access to the variable group.
5. Verify pipeline execution end-to-end.

## Related Skills

- `rhads-cicd-github` for GitHub Actions integration.
- `rhads-cicd-gitlab` for GitLab CI integration.
- `rhads-cicd-jenkins` for Jenkins integration.
- `rhads-cicd-tekton` for Tekton pipeline and webhook configuration.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
