# Official Doc Extraction — rhdh-git-integration

Source: Red Hat Developer Hub 1.10 — Integrating Red Hat Developer Hub with
your Git provider

## Purpose

Connect Red Hat Developer Hub to GitHub or GitLab to discover repositories
automatically and import multiple projects efficiently using bulk import
capabilities.

## GitHub Repository Discovery

### Prerequisites

- Custom Developer Hub application configuration added
- Sufficient GitHub permissions to create and manage a GitHub App
- GitHub configured as authentication provider (auxiliary or main)

### GitHub App Configuration

Register a GitHub App with:

- **Homepage URL**: `https://<my_developer_hub_domain>`
- **Authorization callback URL**: `https://<my_developer_hub_domain>/api/auth/github/handler/frame`
- **Webhook**: Disabled (not needed for auth/catalog)
- **Permissions** (reading software components):
  - Contents: Read-only
  - Commit statuses: Read-only
  - Members (org): Read-only
- **Permissions** (publishing templates):
  - Administration: Read & write
  - Contents: Read & write
  - Pull requests: Read & write
  - Issues: Read & write
  - Workflows: Read & write (if templates include GitHub workflows)
- **Install scope**: Only on this account

### Required Secrets

| Secret Key | Value |
|-----------|-------|
| `GITHUB_APP_APP_ID` | GitHub App ID |
| `GITHUB_APP_CLIENT_ID_INTEGRATION` | Client ID |
| `GITHUB_APP_CLIENT_SECRET_INTEGRATION` | Client Secret |
| `GITHUB_APP_PRIVATE_KEY` | Private Key (PEM) |
| `GITHUB_URL` | GitHub host (e.g., https://github.com) |
| `GITHUB_ORG` | Organization name |

### Dynamic Plugin

```yaml
plugins:
  - package: './dynamic-plugins/dist/backstage-plugin-catalog-backend-module-github'
    disabled: false
```

### app-config.yaml

```yaml
catalog:
  providers:
    github:
      providerId:
        organization: "${GITHUB_ORG}"
        schedule:
          frequency:
            minutes: 30
          initialDelay:
            seconds: 15
          timeout:
            minutes: 15
integrations:
  github:
    - host: ${GITHUB_URL}
      apps:
        - appId: ${GITHUB_APP_APP_ID}
          clientId: ${GITHUB_APP_CLIENT_ID_INTEGRATION}
          clientSecret: ${GITHUB_APP_CLIENT_SECRET_INTEGRATION}
          privateKey: |
            ${GITHUB_APP_PRIVATE_KEY}
```

## GitLab Integration

### app-config.yaml

```yaml
integrations:
  gitlab:
    - host: ${GITLAB_HOST}
      token: ${GITLAB_TOKEN}
```

### GitLab Catalog Provider Plugin

```yaml
plugins:
  - package: './dynamic-plugins/dist/backstage-plugin-catalog-backend-module-gitlab-org-dynamic'
    disabled: false
```

## Bulk Import (Technology Preview)

### Key Constraints

- Requires user OAuth tokens for all repository/organization listing
- No fallback to server-wide integration credentials (GitHub App, PAT, GitLab token)
- HTTP 401 Unauthorized returned without valid user OAuth tokens
- User-scoped access matches personal Git provider permissions

### Enable Bulk Import Plugins

```yaml
plugins:
  - package: ./dynamic-plugins/dist/red-hat-developer-hub-backstage-plugin-bulk-import-backend-dynamic
    disabled: false
  - package: ./dynamic-plugins/dist/red-hat-developer-hub-backstage-plugin-bulk-import
    disabled: false
```

### RBAC Configuration

```plaintext
p, role:default/bulk-import, bulk.import, use, allow
g, user:default/<your_user>, role:default/bulk-import
```

### Import API Modes

| Mode | Description |
|------|-------------|
| `open-pull-requests` | Default — creates PRs/MRs for `catalog-info.yaml` |
| `scaffolder` | Uses custom Scaffolder template for import logic |
| `orchestrator` | Runs Orchestrator workflow for advanced bulk operations |

### Custom Scaffolder Template Configuration

```yaml
bulkImport:
  importTemplate: <your_template_entity_reference>
  importAPI: scaffolder
```

### Orchestrator Workflow Configuration

```yaml
bulkImport:
  orchestratorWorkflow: your_workflow_id
  importAPI: 'orchestrator'
```

### Scaffolder Template Input Parameters

| Parameter | Description |
|-----------|-------------|
| `repoUrl` | Normalized repository URL |
| `name` | Repository name |
| `organization` | Repository owner |
| `branchName` | Proposed branch (default: `bulk-import-catalog-entity`) |
| `targetBranchName` | Default branch of Git repository |
| `gitProviderHost` | Git provider host parsed from URL |

## Troubleshooting Repository Visibility

If repositories are not visible in Bulk Import:

1. Verify user has access to repositories in GitHub/GitLab
2. Confirm repositories are not already in the catalog
3. Check OAuth session validity
4. Verify authentication provider configuration
5. Confirm `ScmAuthApi` registration for SCM hosts

## Audit Log Events

Bulk Import generates the following audit events:

- `BulkImportFindAllOrganizations`
- `BulkImportFindRepositoriesByOrganization`
- `BulkImportFindAllRepositories`
- `BulkImportFindAllImports`
- `BulkImportCreateImportJobs`
- `BulkImportFindImportStatusByRepo`
- `BulkImportDeleteImportByRepo`
