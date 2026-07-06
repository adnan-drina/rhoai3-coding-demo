---
name: rhdh-develop
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhdh"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Developer Hub"
description: >
  Use when documenting software development workflows, CI/CD management,
  service monitoring, and code quality tools in Red Hat Developer Hub 1.10.
  Covers Bulk Import (Technology Preview), Software Catalog management,
  and Software Template usage. Do NOT use for TechDocs documentation
  lifecycle (use rhdh-techdocs-manage) or adoption analytics
  (use rhdh-adoption-insights).
---

# RHDH Software Development and Management

Use this skill for Red Hat Developer Hub 1.10 software development and
management workflows grounded in official product documentation.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority. This skill covers Bulk Import,
Software Catalog, and Software Template workflows.

## Key Capabilities

1. **Bulk Import (Technology Preview)** — Import multiple GitHub repositories
   and GitLab projects into the catalog. Requires user OAuth tokens and
   `bulk.import` RBAC permission. Creates pull requests with
   `catalog-info.yaml` files.
2. **Software Catalog** — Centralized view of all software (components, APIs,
   resources). Metadata stored as YAML alongside code. Register manually, via
   templates, or via Bulk Import.
3. **Software Templates** — YAML-defined scaffolding for new components.
   Sequential actions (code scaffolding, repo creation) with conditional steps.
   Import existing templates via `catalog.rules` and `catalog.locations`.

## Bulk Import

- Plugins: `red-hat-developer-hub-backstage-plugin-bulk-import-backend-dynamic`
  and `red-hat-developer-hub-backstage-plugin-bulk-import` (disabled by default)
- RBAC: `bulk.import` permission required for non-admin users
- Audit log events: `BulkImportFindAllOrganizations`,
  `BulkImportCreateImportJobs`, `BulkImportDeleteImportByRepo`, etc.
- Import statuses: `Added`, `Waiting for approval`, `Empty`
- Supports GitHub and GitLab source control tools

## Software Catalog

- Entity kinds: Component, API, Resource, Template
- Registration: manual `catalog-info.yaml`, Software Templates, Bulk Import
- RBAC permissions: `catalog.entity.create`, `catalog.location.create`,
  `catalog.entity.refresh`
- Catalog refresh: up to 45 minutes; manual refresh via entity Overview tab
- Starred entities for quick access

### catalog-info.yaml Shape

```yaml
apiVersion: backstage.io/v1alpha1
kind: Component
metadata:
  name: <component_name>
  description: <description>
  tags: [example, service]
  annotations:
    github.com/project-slug: <org>/<repo>
spec:
  type: service
  owner: group:default/<team>
  lifecycle: production
```

## Software Templates

- Import via `catalog.rules: [allow: [Template]]` and `catalog.locations`
- RBAC: `scaffolder.template.parameter.read`,
  `scaffolder.template.step.read`, `scaffolder.task.create`
- Access: Catalog > Self-service or Global Header Create (+)
- Review step verifies parameters before scaffolding

## Workflow

1. Read `references/official-doc-extraction.md` for exact configuration.
2. Identify the task:
   - Enabling Bulk Import plugins and RBAC
   - Importing GitHub repositories or GitLab projects
   - Registering components manually
   - Creating components from Software Templates
   - Importing existing Software Templates
   - Filtering and searching the Software Catalog
3. Use exact plugin package paths and RBAC permission names from the extraction.
4. Validate using the verification steps per section.

## Related Skills

- `rhdh-techdocs-manage` — TechDocs documentation lifecycle
- `rhdh-adoption-insights` — Adoption analytics and engagement metrics

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
