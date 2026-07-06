---
name: rhads-cicd-jenkins
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhads"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Trusted Software Supply Chain"
description: >
  Use when configuring Jenkins for secure CI/CD workflows with RHADS-SSC 1.9:
  adding credentials and environment variables for ACS, Cosign, Trustification,
  and image registry integration; automating credential setup with
  ci-set-org-vars.sh; adding applications to Jenkins; and viewing pipeline
  results in Red Hat Developer Hub. Do NOT use for Azure Pipelines
  (use rhads-cicd-azure), GitHub Actions (use rhads-cicd-github), GitLab CI
  (use rhads-cicd-gitlab), or Tekton pipelines (use rhads-cicd-tekton).
---

# RHADS-SSC Jenkins Integration

Use this skill to ground Jenkins CI/CD configuration in official Red Hat
Advanced Developer Suite - software supply chain (RHADS-SSC) 1.9
documentation.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority.

## Purpose

Jenkins integrates with RHADS-SSC to perform vulnerability scanning, image
signing, and attestation generation. Jenkins requires credentials (secrets) and
environment variables configured through its management interface.

## Prerequisites

- RHADS-SSC installed on an OpenShift cluster with `private.env` generated
- Jenkins installed and configured in your environment
- Permissions to create and manage Jenkins jobs
- Authentication details for ACS (ROX endpoint, API token)
- Cosign signing key (password, private key, public key)
- Trustification credentials (API URL, issuer URL, client ID, client secret,
  supported CycloneDX version)

## Setup Sequence

| Action | When |
|--------|------|
| Add secrets to Jenkins | Before creating an application with secure templates |
| Add application to Jenkins | After creating application and source repositories |

## Automated Credential Setup

The `ci-set-org-vars.sh` script from the `tssc-cli` image creates required
Jenkins credentials and environment variables:

```bash
bash-5.1$ ./scripts/ci-set-org-vars.sh -b jenkins
```

## Required Credentials (Secrets)

### Image Registry and GitOps

| Credential | Description |
|------------|-------------|
| `QUAY_IO_CREDS` | Username and password for Quay (default, uncommented) |
| `ARTIFACTORY_IO_CREDS` | Username and password for JFrog Artifactory |
| `NEXUS_IO_CREDS` | Username and password for Sonatype Nexus |
| `GITOPS_AUTH_PASSWORD` | GitOps repository update token |

### ACS and SBOM

| Credential | Description |
|------------|-------------|
| `ROX_API_TOKEN` | ACS API access token |
| `COSIGN_SECRET_PASSWORD` | Cosign signing key password |
| `COSIGN_SECRET_KEY` | Cosign private key |
| `TRUSTIFICATION_OIDC_CLIENT_SECRET` | Trustification OIDC client secret |

To use Artifactory or Nexus instead of Quay, uncomment the corresponding lines
in both Jenkinsfiles (gitops-template and source-repo folders in
tssc-sample-templates).

## Required Environment Variables

| Variable | Purpose |
|----------|---------|
| `GITOPS_AUTH_USERNAME` | (Optional) Required for GitLab integration |
| `ROX_CENTRAL_ENDPOINT` | ACS central server endpoint |
| `COSIGN_PUBLIC_KEY` | Cosign public key |
| `TRUSTIFICATION_BOMBASTIC_API_URL` | SBOM API URL |
| `TRUSTIFICATION_OIDC_ISSUER_URL` | OIDC issuer URL |
| `TRUSTIFICATION_OIDC_CLIENT_ID` | OIDC client ID |
| `TRUSTIFICATION_SUPPORTED_CYCLONEDX_VERSION` | CycloneDX version |

## Optional Variables

| Variable | Condition |
|----------|-----------|
| `REKOR_HOST` | Jenkins not on local OpenShift; uncomment in Jenkinsfile |
| `TUF_MIRROR` | Jenkins not on local OpenShift; uncomment in Jenkinsfile |

Environment variables are set via Manage Jenkins > System > Global properties >
Environment variables.

## Adding Applications to Jenkins

1. Create a Pipeline project; the job name must match the application name.
2. If using a different pipeline name, update `jenkins.io/job-full-name` in
   `catalog-info.yaml` in the application source repository.
3. Set the Repository URL to the application source repository.
4. Select Build Now and wait for completion.

## RHDH Integration Verification

After integration, verify in Red Hat Developer Hub:

- **CI tab**: view Jenkins project, rerun jobs, view job history
- **CD tab**: view ArgoCD/GitOps deployment details
- **Catalog > Resource**: view Jenkins GitOps jobs
- **Topology tab**: visualize application deployment

## Workflow

1. Read `references/official-doc-extraction.md`.
2. Add credentials (automated or manual).
3. Add environment variables via Global properties.
4. Set optional Rekor/TUF variables if Jenkins is off-cluster.
5. Create a Pipeline project and add the application.
6. Verify pipeline execution and RHDH integration.

## Related Skills

- `rhads-cicd-azure` for Azure Pipelines integration.
- `rhads-cicd-github` for GitHub Actions integration.
- `rhads-cicd-gitlab` for GitLab CI integration.
- `rhads-cicd-tekton` for Tekton pipeline and webhook configuration.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
