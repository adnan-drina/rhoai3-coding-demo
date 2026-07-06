---
name: rhdh-techdocs-manage
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhdh"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Developer Hub"
description: >
  Use when managing documentation lifecycle — adding, searching, viewing, and
  editing content using TechDocs in Red Hat Developer Hub 1.10. Covers
  importing docs from repositories, standalone documentation, enabling docs
  for existing entities, CI/CD builds with GitHub Actions, and video content
  embedding. Do NOT use for Software Catalog or Bulk Import workflows
  (use rhdh-develop) or adoption analytics (use rhdh-adoption-insights).
---

# RHDH TechDocs Management

Use this skill for TechDocs documentation lifecycle management in Red Hat
Developer Hub 1.10 grounded in official product documentation.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority. This skill covers adding, searching,
viewing, editing, and building documentation using TechDocs.

## Key Capabilities

1. **Import docs from repository** — Import documentation from a remote
   repository containing `mkdocs.yaml` and `catalog-info.yaml`.
2. **Standalone documentation** — Create docs not tied to a codebase
   (onboarding guides, architecture overviews, runbooks).
3. **Enable docs for existing entity** — Add `backstage.io/techdocs-ref`
   annotation to an existing catalog entity.
4. **Search and filter** — Search by keywords, filter by owner, tags, starred,
   or owned docs.
5. **Edit documentation** — Edit directly from the document book page; opens
   the file in the remote repository.
6. **Video content** — Embed videos via `<iframe>` elements with DOMPurify
   sanitization configuration.
7. **CI/CD builds** — Automate TechDocs generation and publishing to AWS S3
   using GitHub Actions (`rhdh-techdocs-pipeline`).

## TechDocs Entity Configuration

### backstage.io/techdocs-ref annotation

```yaml
apiVersion: backstage.io/v1alpha1
kind: Component
metadata:
  name: my-component
  annotations:
    backstage.io/techdocs-ref: dir:.
spec:
  type: service
  lifecycle: production
  owner: group:default/my-team
```

### Standalone documentation entity

```yaml
apiVersion: backstage.io/v1alpha1
kind: Component
metadata:
  name: my-documentation
  description: Onboarding guide for new team members
  annotations:
    backstage.io/techdocs-ref: dir:.
spec:
  type: documentation
  lifecycle: production
  owner: group:default/my-team
```

### mkdocs.yml

```yaml
site_name: My Documentation
nav:
  - Home: index.md
plugins:
  - techdocs-core
```

Developer Hub automatically adds `techdocs-core` plugin if missing.

## Required Directory Structure

```
my-documentation/
  catalog-info.yaml
  mkdocs.yml
  docs/
    index.md
```

## RBAC Permissions

| Operation | Required permissions |
|-----------|---------------------|
| Import documentation | `catalog.entity.create`, `catalog.location.create` |

## CI/CD Build Configuration (GitHub Actions)

For production, build externally and publish to AWS S3:

```yaml
techdocs:
  builder: external
  publisher:
    type: awsS3
    awsS3:
      bucketName: ${AWS_S3_BUCKET_NAME}
      accountId: ${AWS_ACCOUNT_ID}
      region: ${AWS_REGION}
```

Required GitHub repository secrets: `TECHDOCS_S3_BUCKET_NAME`,
`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`.

## Video Embedding

Requires `techdocs.sanitizer.allowedIframeHosts` and `backend.csp.frame-src`:

```yaml
backend:
  csp:
    frame-src: ['https://www.youtube.com/']
techdocs:
  sanitizer:
    allowedIframeHosts:
      - www.youtube.com
```

## Workflow

1. Read `references/official-doc-extraction.md` for exact configuration.
2. Identify the task:
   - Importing docs from a remote repository
   - Creating standalone documentation
   - Enabling docs for an existing catalog entity
   - Searching and filtering documentation
   - Editing documentation
   - Embedding video content
   - Setting up CI/CD TechDocs builds
3. Use exact annotation names, plugin settings, and directory structures.
4. Catalog refresh can take up to 45 minutes; use entity refresh button.

## Related Skills

- `rhdh-develop` — Software Catalog and template workflows
- `rhdh-adoption-insights` — Adoption analytics and engagement metrics

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
