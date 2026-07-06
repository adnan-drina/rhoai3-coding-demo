---
name: rhads-cicd-tekton
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhads"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Trusted Software Supply Chain"
description: >
  Use when defining Tekton pipelines and configuring webhooks for secure CI/CD
  workflows with RHADS-SSC 1.9: setting up GitLab webhooks with push and merge
  request events; setting up Bitbucket webhooks with push and merged events;
  and verifying automated pipeline triggers in Red Hat Developer Hub. Do NOT use
  for Azure Pipelines (use rhads-cicd-azure), GitHub Actions
  (use rhads-cicd-github), GitLab CI (use rhads-cicd-gitlab), or Jenkins
  (use rhads-cicd-jenkins).
---

# RHADS-SSC Tekton Pipeline Integration

Use this skill to ground Tekton pipeline webhook configuration in official Red
Hat Advanced Developer Suite - software supply chain (RHADS-SSC) 1.9
documentation.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority.

## Purpose

When using Tekton as the CI provider with RHADS-SSC, webhooks must be
configured in the git provider (GitLab or Bitbucket) to ensure code updates
automatically trigger pipeline runs in Red Hat Developer Hub (RHDH).

## Prerequisites

- RHADS-SSC installed with Tekton selected as CI provider
- `private.env` file containing Webhook URL and Secret Token
- Application repository created from RHDH software templates

## GitLab Webhook Configuration

### Prerequisites

- GitLab integrated during RHADS-SSC install
- GitLab repository selected in the RHDH platform catalog

### Procedure

1. Navigate to the GitLab source repository via RHDH Catalog > Overview >
   View Source.
2. In the Trigger section, select:
   - Push events
   - Merge request events
3. Click Add Webhook.

### Verification

1. Commit a change to the source repository in GitLab.
2. Navigate to the CI tab in RHDH.
3. Verify that a pipeline run is triggered for the code push.

## Bitbucket Webhook Configuration

### Prerequisites

- Bitbucket integrated during RHADS-SSC install
- Bitbucket repository selected in the RHDH platform catalog
- Webhook URL from `private.env`

### Procedure

1. In the Trigger section, select:
   - Push
   - Merged
2. Select Save.

### Verification

1. Make a code change in the Bitbucket repository and push.
2. Navigate to the CI tab in RHDH.
3. Verify that a pipeline run is triggered after the code update.

## Workflow

1. Read `references/official-doc-extraction.md`.
2. Identify the git provider (GitLab or Bitbucket).
3. Locate Webhook URL and Secret Token in `private.env`.
4. Configure the webhook in the git provider repository settings.
5. Trigger a pipeline run and verify in RHDH CI tab.

## Related Skills

- `rhads-cicd-azure` for Azure Pipelines integration.
- `rhads-cicd-github` for GitHub Actions integration.
- `rhads-cicd-gitlab` for GitLab CI integration.
- `rhads-cicd-jenkins` for Jenkins integration.
- `ocp-pipelines-about` for Tekton CRD concepts.
- `ocp-pipelines-cicd` for creating CI/CD solutions with pipelines.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
