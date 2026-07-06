# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product family | Red Hat Advanced Developer Suite - software supply chain |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_advanced_developer_suite_-_software_supply_chain/1.9/html-single/installing_red_hat_advanced_developer_suite_-_software_supply_chain/index |
| Multi-page URL | https://docs.redhat.com/en/documentation/red_hat_advanced_developer_suite_-_software_supply_chain/1.9/html/installing_red_hat_advanced_developer_suite_-_software_supply_chain/index |
| Documentation category | Installing |
| Official guide | Installing Red Hat Advanced Developer Suite - software supply chain |
| Capture date | 2026-07-06 |

## Captured Sections

From Installing Red Hat Advanced Developer Suite - software supply chain:

- Preface: RHADS-SSC overview, high-level install steps
- Chapter 1: Standard deployment workflow
- Chapter 2: Minimum hardware requirements
  - 2.1 RHACS hardware requirements
  - 2.2 RHDH hardware requirements
  - 2.3 OpenShift GitOps hardware requirements
  - 2.4 OpenShift Pipelines hardware requirements
  - 2.5 RHTPA hardware requirements
  - 2.6 RHTAS hardware requirements
  - 2.7 Red Hat build of Keycloak minimum hardware requirements
- Chapter 3: Upgrading RHADS-SSC
- Chapter 4: Downloading the installation program image
- Chapter 5: Creating the config.yaml file
- Chapter 6: Customizing the config.yaml file
  - 6.1 Customizing the tssc.products section
- Chapter 7: Integrating products and external services
  - 7.1 Integrating GitHub (PAT + GitHub App)
  - 7.2 Integrating GitLab
  - 7.3 Integrating RHACS
  - 7.4 Integrating RHTAS
  - 7.5 Integrating RHTPA
  - 7.6 Integrating Bitbucket
  - 7.7 Integrating GitHub Actions
  - 7.8 Integrating Jenkins
  - 7.9 Integrating Azure Pipelines
  - 7.10 Integrating Quay
  - 7.11 Integrating JFrog Artifactory
  - 7.12 Integrating Sonatype Nexus Repository
- Chapter 8: Deploying RHADS-SSC
- Chapter 9: RHADS-SSC credentials reference
- Chapter 10: RHADS-SSC component list

## Source Boundaries

This skill captures the full RHADS-SSC 1.9 installation guide: hardware
requirements, installer image download, config.yaml creation and
customization, service integrations (Git, CI, registry, pre-existing
products), deployment, upgrade posture, credentials reference, and the
component list.

It does not capture:

- CI/CD pipeline authoring or Tekton task/pipeline configuration (separate
  guides per CI provider)
- Post-install component customization beyond config.yaml
- Conforma policy authoring and compliance workflows
- Individual product administration (RHACS, RHDH, RHTAS, RHTPA) beyond
  integration
- Release notes and compatibility matrix (separate guide)
- Software template usage and Developer Hub workflows (separate guide)

## Related Official Sources To Add Later

- RHADS-SSC 1.9 Release notes (compatibility matrix, plugin support)
- RHADS-SSC 1.9 Getting started with Red Hat Trusted Application Pipeline
- RHADS-SSC 1.9 Configuring Red Hat Trusted Application Pipeline
- Individual component documentation (RHACS 4.10, RHDH 1.9, RHTAS 2.2,
  RHTPA 2.2, OpenShift Pipelines 1.21, OpenShift GitOps)
