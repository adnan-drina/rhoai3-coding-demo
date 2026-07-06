# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product family | Red Hat Advanced Developer Suite - software supply chain |
| Product version | 1.9 |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Documentation category | CI/CD |
| Official guide | Defining pipelines with Tekton |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_advanced_developer_suite_-_software_supply_chain/1.9/html-single/defining_pipelines_with_tekton/index |
| Multi-page URL | https://docs.redhat.com/en/documentation/red_hat_advanced_developer_suite_-_software_supply_chain/1.9/html/defining_pipelines_with_tekton/index |
| Capture date | 2026-07-06 |

## Captured Sections

From Defining pipelines with Tekton:

- Preface: webhook requirement for Tekton CI provider
- Chapter 1: Configuring GitLab Webhooks to enable automated pipeline triggers
  - Prerequisites (GitLab integration, RHDH catalog, Webhook URL, Secret Token)
  - Procedure (navigate via RHDH, push events, merge request events)
  - Verification (commit change, CI tab, pipeline run trigger)
- Chapter 2: Configuring Bitbucket webhooks to enable automated pipeline
  triggers
  - Prerequisites (Bitbucket integration, RHDH catalog, Webhook URL)
  - Procedure (push event, merged event)
  - Verification (code change, CI tab, pipeline run trigger)

## Source Boundaries

This skill covers the "Defining pipelines with Tekton" guide only. It provides
webhook configuration for GitLab and Bitbucket to trigger Tekton pipeline runs
via RHDH. It does not cover:

- Azure Pipelines integration (separate guide)
- GitHub Actions integration (separate guide)
- GitLab CI integration (separate guide)
- Jenkins integration (separate guide)
- Tekton CRD concepts (use ocp-pipelines-about)
- Tekton pipeline authoring (use ocp-pipelines-cicd)
- RHADS-SSC installation or software template creation
