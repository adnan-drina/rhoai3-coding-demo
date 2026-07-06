# Official Doc Extraction

Use this extraction to keep Tekton pipeline webhook configuration content
grounded in official RHADS-SSC 1.9 sources.

## Product Overview

When using Tekton as the CI provider with Red Hat Advanced Developer Suite -
software supply chain (RHADS-SSC), webhooks must be configured in the git
provider (GitLab or Bitbucket). This ensures that code updates automatically
trigger pipeline runs in Red Hat Developer Hub (RHDH).

## GitLab Webhooks

### Prerequisites

- GitLab integrated during RHADS-SSC install
- Application selected in the RHDH platform catalog
- Webhook URL and Secret Token from `private.env`

### Procedure

1. Navigate to the GitLab source repository:
   - In RHDH, go to Catalog and select the application where GitLab is the
     repository host.
   - Go to Overview tab and select View Source to open the source repository.
2. In the webhook configuration Trigger section, select:
   - **Push events**
   - **Merge request events**
3. Click Add Webhook.

### Verification

1. Commit any change to the source repository in GitLab.
2. Navigate to the CI tab in RHDH.
3. Verify that a pipeline run is triggered for the code push.

## Bitbucket Webhooks

### Prerequisites

- Bitbucket integrated during RHADS-SSC install
- Application selected in the RHDH platform catalog
- Webhook URL from `private.env`

### Procedure

1. In the webhook configuration Trigger section, select:
   - **Push**
   - **Merged**
2. Select Save.

### Verification

1. Make a code change in the Bitbucket repository and push the changes.
2. Navigate to the CI tab in RHDH.
3. Verify that a pipeline run is triggered after the code update.

## Key Details

- Webhook URL and Secret Token are found in the `private.env` file generated
  during RHADS-SSC installation.
- GitLab requires both Push events and Merge request events for full coverage.
- Bitbucket requires both Push and Merged events.
- Pipeline runs are visible in the RHDH CI tab after webhook triggers fire.
- GitHub webhooks are not covered in this guide; GitHub Actions has its own
  integration path.
