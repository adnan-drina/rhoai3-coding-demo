# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product | Red Hat Advanced Developer Suite - Software Supply Chain |
| Product version | 1.9 |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Chapter or page title | Customizing Red Hat Advanced Developer Suite - software supply chain |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_advanced_developer_suite_-_software_supply_chain/1.9/html-single/customizing_red_hat_advanced_developer_suite_-_software_supply_chain/index |
| Documentation category | Secure Your Software Supply Chain |
| Capture date | 2026-07-06 |

## Captured Sections

From "Customizing Red Hat Advanced Developer Suite - software supply chain":

- Chapter 1: Customizing sample software templates
  - Prerequisites (forked tssc-sample-templates)
  - Properties file key-value configuration
  - Running generate.sh to apply customizations
  - Jenkins external cluster configuration (REKOR_HOST, TUF_MIRROR)
  - Manual template import (Option B)
- Chapter 2: About sample pipelines
  - gitops-repo, pipelines, source-repo, tasks directory layout
- Chapter 3: Customizing sample pipelines
  - Updating pac URLs with update-tekton-definition script
  - Review, commit, push workflow
- Chapter 4: Customizing GitLab pipelines and rebuilding container images
  - Extracting pipeline files with podman
  - Dockerfile customization with quay.io/redhat-tssc/task-runner:1.9
  - Rebuilding and pushing container images
  - Platform engineer vs developer image update paths
- Chapter 5: Image registry detection in RHDH
  - 5.1 Enabling the Image Registry tab for an existing component
  - 5.2 Enabling the Image Registry tab for all future components

## Source Boundaries

This skill captures:

- Software template properties file customization for on-premise environments
- Default host, org, namespace, pipeline, ArgoCD, and secret configuration
- generate.sh template generation workflow
- Sample pipelines repository structure and purpose
- Pipeline as Code URL customization via update-tekton-definition script
- GitLab runner image customization and rebuild workflow
- Jenkins external cluster REKOR_HOST and TUF_MIRROR configuration
- RHDH Image Registry tab annotation and detection logic customization

This skill does not capture:

- RHADS-SSC installation and initial setup
- SBOM inspection workflows (use rhads-sbom)
- Conforma policy management (use rhads-compliance)
- Container image signing and attestation (use rhads-compliance)
- RHDH configuration beyond image registry detection

## API Versions and CRDs

No CRDs are directly managed by this customization workflow.

| Component | Notes |
|-----------|-------|
| tssc-sample-templates | Git repository; Backstage software templates |
| tssc-sample-pipelines | Git repository; Tekton PipelineRun definitions |
| RHDH catalog-info.yaml | Backstage component metadata with registry annotations |

## Related Official Sources To Add Later

- Red Hat Advanced Developer Suite - SSC 1.9 Installation Guide
- Red Hat Advanced Developer Suite - SSC 1.9 Inspecting SBOMs
- Red Hat Advanced Developer Suite - SSC 1.9 Managing Compliance
