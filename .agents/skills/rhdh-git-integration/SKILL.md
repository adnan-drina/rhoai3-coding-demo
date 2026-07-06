---
name: rhdh-git-integration
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhdh"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Developer Hub"
description: >
  Use when configuring Git provider integration (GitHub, GitLab, Bitbucket) in
  Red Hat Developer Hub. Covers GitHub App setup, repository discovery,
  GitLab integration, and Bulk Import capabilities for automated catalog
  onboarding. Do NOT use for RHDH installation or operator configuration;
  use rhdh-install-* skills. Do NOT use for authentication provider setup
  beyond Git integration specifics.
---

# RHDH Git Integration

Configure Red Hat Developer Hub 1.10 to integrate with GitHub and GitLab
Git providers for repository discovery, catalog entity ingestion, and bulk
import workflows.

## When to Use

- Setting up GitHub App for RHDH integration
- Configuring automatic repository discovery via `catalog.providers.github`
- Enabling Bulk Import plugins for GitHub or GitLab
- Configuring GitLab integration via `integrations.gitlab`
- Setting up RBAC for `bulk.import` permission
- Troubleshooting repository visibility or OAuth token issues
- Configuring custom Scaffolder templates for Bulk Import
- Setting up Orchestrator workflows for bulk operations

## Key Concepts

### GitHub Integration

- Uses a **GitHub App** (not OAuth app) for fine-grained permissions and
  short-lived tokens
- Discovery via `plugin-catalog-backend-module-github` dynamic plugin
- Configuration in `catalog.providers.github` and `integrations.github`
- Required secrets: `GITHUB_APP_APP_ID`, `GITHUB_APP_CLIENT_ID_INTEGRATION`,
  `GITHUB_APP_CLIENT_SECRET_INTEGRATION`, `GITHUB_APP_PRIVATE_KEY`

### GitLab Integration

- Configuration via `integrations.gitlab` with host and token
- Catalog provider plugin: `backstage-plugin-catalog-backend-module-gitlab-org-dynamic`
- Bulk Import creates merge requests (MRs) instead of pull requests

### Bulk Import (Technology Preview)

- Requires **user OAuth tokens** for repository listing (no fallback to
  integration credentials)
- Plugins (disabled by default):
  - `red-hat-developer-hub-backstage-plugin-bulk-import-backend-dynamic`
  - `red-hat-developer-hub-backstage-plugin-bulk-import`
- RBAC: `bulk.import` permission required for non-admin users
- Supports three import modes: `open-pull-requests` (default), `scaffolder`,
  `orchestrator`
- User-scoped access ensures audit trails tied to individual accounts

## Prerequisites

- RHDH 1.10 instance deployed (Operator or Helm)
- Sufficient GitHub/GitLab permissions to create and manage apps
- GitHub or GitLab configured as authentication provider (required for
  Bulk Import)

## Validation

```bash
# Verify GitHub discovery plugin loaded
oc logs deployment/<rhdh-deployment> -c backstage-backend | grep "github"

# Verify Bulk Import plugins
oc logs -c install-dynamic-plugins deployment/<rhdh-deployment> | grep "bulk-import"

# Verify catalog entities discovered
curl -H "Authorization: Bearer $TOKEN" \
  https://<rhdh-url>/api/catalog/entities?filter=kind=Component | jq length
```

## Boundaries

- Git integration configuration only; authentication provider setup is a
  separate concern
- Bulk Import is Technology Preview — not for production SLA workloads
- Orchestrator workflow mode requires separate Orchestrator plugin installation

## References

- `references/source-capture.md` — source ledger
- `references/official-doc-extraction.md` — extracted procedures and config
