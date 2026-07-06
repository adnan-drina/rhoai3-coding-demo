# Official Doc Extraction

This extraction is derived from the official RHADS-SSC 1.9 "Getting Started"
guide captured in `source-capture.md`.

## Development Workflow

The official workflow steps:

1. Install RHADS-SSC
2. Create an application from a software template
3. Update application source code (triggers pipeline)
4. View security insights (RHACS reports, SBOM, Conforma)
5. Promote build (dev -> stage -> prod)
6. (Optional) Customize templates and pipelines

## Software Templates

Templates integrate with ACS, Quay (or JFrog/Artifactory), OpenShift Pipelines,
and OpenShift GitOps. Supported languages: Java, Python, JavaScript, Go.

## Creating an Application

### Application Information (Step 1/4)

- **Name**: lowercase a-z, 0-9, dashes; 1-63 chars; must start/end alphanumeric
- **Owner**: RHDH component owner; default `user:guest`

### Repository Information (Step 2/4)

- **Host Type**: GitHub, GitLab, or Bitbucket
- **Repository Server**: pre-populated per host type; can use on-premise URL
- **CI Provider** (per host):
  - GitHub: Tekton (SLSA 3), GitHub Actions (SLSA 2), Jenkins (SLSA 2), Azure Pipelines (SLSA 2, TP)
  - GitLab: Tekton (SLSA 3), GitLab CI (SLSA 2), Jenkins (SLSA 2)
  - Bitbucket: Tekton (SLSA 3), Jenkins (SLSA 2), Azure Pipelines (SLSA 2, TP)

Webhooks required for: Bitbucket+Tekton, GitLab+Tekton. Secrets required for:
GitHub Actions, GitLab CI, Azure Pipelines, Jenkins.

### Deployment Information (Step 3/4)

- **Image Name**: lowercase, digits, separators (`.`, `__`, `-`)
- **Image Registry**: Quay, JFrog Artifactory, Sonatype Nexus (no HTTP protocol)
- **Image Organization**: registry org name
- **Deployment Namespace**: prefix (default `tssc-app`); creates `-development`,
  `-stage`, `-prod`

### Automated Setup (Step 4)

On Create, RHADS-SSC performs:
- Repository creation (source + GitOps)
- Namespace creation (dev, stage, prod)
- GitOps integration (Argo CD resources)
- Pipeline definition (Pipelines as Code)

## Unregistering an Application

Removes from catalog view only; application remains functional. To fully
remove from cluster:

```bash
oc delete application <app-name>-app-of-apps -n tssc-gitops
```

## Updating Source Code

Modify code, commit, and push. For GitLab/Bitbucket: webhooks and secrets must
be configured to trigger pipeline runs automatically.

## Pipeline Security Tasks

### RHACS Tasks (when configured)

- `roxctl image scan`: identifies components and vulnerabilities (JSON output)
- `roxctl image check`: verifies build-time security violations
- `roxctl deployment check`: checks YAML deployment files

### SBOM Task

`show-sbom` generates SBOM listing:
- Source/author/publisher
- Library name and version
- License type

Format: CycloneDX 1.4.

Download SBOM:
```bash
cosign download sbom <sbom_url>
cosign download sbom <sbom_url> > sbom.txt
```

## Build Promotion

### Workflow

1. Copy image URL from `development/deployment-patch.yaml`
2. Paste into `stage/deployment-patch.yaml` (dev->stage)
3. Copy from `stage/deployment-patch.yaml` to `prod/deployment-patch.yaml`
   (stage->prod)
4. Create PR to trigger promotion pipeline
5. Merge PR to trigger Argo CD deployment

### Promotion Pipeline Tasks

- `git-clone`: clones repository
- `gather-deploy-images`: extracts images from deployment YAML
- `verify-enterprise-contract`: validates images with Conforma + cosign
- `deploy-images`: deploys to target environment
- `download-sbom-from-url-in-attestations`: retrieves SBOMs from attestations
- `upload-sbom-to-trustification`: uploads SBOMs via BOMbastic API

### Conforma Compliance

Evaluates builds against defined policies using signed in-toto attestations.
Reports detail:
- Successful checks (passed policies)
- Warnings and failures (with explanations)
- Rule compliance (source code refs, attestation validations)

View reports in RHDH CI tab (Tekton) or build logs
(`Step: verify-enterprise-contract` for other providers).

## Unresolved Items

This chapter does not define:

- RHADS-SSC installation procedure (separate guide)
- Conforma policy authoring syntax
- Template customization steps (referenced but not detailed here)
- Webhook configuration details for each provider
