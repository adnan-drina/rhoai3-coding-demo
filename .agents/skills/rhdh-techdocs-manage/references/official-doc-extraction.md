# Official Documentation Extraction

Source: Red Hat Developer Hub 1.10 — Manage and consume technical documentation
Captured: 2026-07-06

---

## 1. Import Documentation from a Remote Repository

Teams store documentation files alongside code. Import into TechDocs from a
repository containing `mkdocs.yaml` and `catalog-info.yaml`.

### Prerequisites

- Documentation files in a remote repository
- `mkdocs.yaml` file in the root directory
- `catalog.entity.create` and `catalog.location.create` permissions

### Procedure

1. Navigate: Catalog > Self-service > Register Existing Component
2. Enter URL to `catalog-info.yaml`:
   `https://github.com/<project_name>/<repo_name>/blob/<branch_name>/<file_directory>/catalog-info.yaml`
3. Click Analyze
4. Click Finish

### Verification

1. Navigate: Docs
2. Verify documentation appears in the Documentation page table

---

## 2. Create Standalone Documentation

For content not tied to a specific codebase (onboarding guides, architecture
overviews, team runbooks).

### Required directory structure

```
my-documentation/
  catalog-info.yaml
  mkdocs.yml
  docs/
    index.md
```

### catalog-info.yaml

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

### Registration

1. Navigate: Catalog > Self-service > Register Existing Component
2. Enter URL to `catalog-info.yaml`
3. Click Analyze, then Finish

### Verification

- Check Docs page for the documentation entry
- Refresh can take up to 45 minutes; use entity Overview refresh button

---

## 3. Enable Documentation for an Existing Entity

Add TechDocs to a component already registered in the Software Catalog.

### Add annotation to catalog-info.yaml

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

### Create mkdocs.yml

```yaml
site_name: My Component Documentation
nav:
  - Home: index.md
```

Developer Hub automatically adds `techdocs-core` plugin if missing.

### Procedure

1. Commit, push, and merge changes
2. Navigate to the component in the Software Catalog
3. Verify Docs tab appears (may take up to 45 minutes)

---

## 4. Search and Filter Documentation

### Available filters on the Documentation page

- **Search:** Keywords within documents
- **Filter by Owner:** Documents owned by specific users or groups
- **Filter by Tags:** Narrow by labels or categories
- **Filter by Owned:** Documents belonging to you or your group
- **Filter by Starred:** Bookmarked favorites

Results update automatically.

---

## 5. Navigate Documentation

On-screen navigation tools:
- Search bar: keywords within current document
- Table of contents: jump to sections
- Navigation menu: switch between documents in a book
- Next: sequential navigation
- Add-ons: configured plugins (e.g., text size)

---

## 6. Edit Documentation

Any authorized user can edit regardless of document ownership.

1. Navigate: Docs
2. Click document name in Documentation table
3. Click "Edit this page" icon to open in remote repository
4. Edit in repository provider UI
5. Commit and merge using team processes

---

## 7. Video Content Embedding

### iframe syntax

```html
<iframe
  width="<video_width>"
  height="<video_height>"
  src="<video_url>"
  title="<video_title>"
  frameborder="0"
  allow="picture-in-picture"
  allowfullscreen>
</iframe>
```

### DOMPurify and CSP configuration

TechDocs uses DOMPurify for HTML sanitization. Every permitted video host must
be listed:

```yaml
backend:
  csp:
    connect-src: ['https:']
    frame-src: ['https://www.youtube.com/']
techdocs:
  builder: external
  sanitizer:
    allowedIframeHosts:
      - www.youtube.com
      - <additional_video_host_url>
  publisher:
    type: awsS3
    awsS3:
      bucketName: ${AWS_S3_BUCKET_NAME}
      accountId: ${AWS_ACCOUNT_ID}
      region: ${AWS_REGION}
```

---

## 8. CI/CD Builds with GitHub Actions

For production: build externally, publish to AWS S3, configure read-only mode.

### Prerequisites

- TechDocs plugin enabled and configured
- Documentation files in remote repository with `mkdocs.yaml`
- `catalog.entity.create` and `catalog.location.create` permissions
- AWS S3 bucket with Write and Read IAM policies
- IAM User with access key

### Setup

1. Fork the `rhdh-techdocs-pipeline` repository
2. Add repository secrets: `TECHDOCS_S3_BUCKET_NAME`, `AWS_ACCESS_KEY_ID`,
   `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`
3. Enable workflow permissions via GitHub GUI
4. Optional: Customize `rhdh-techdocs-pipeline` structure
5. Optional: Add mkdocs plugins to `mkdocs.yaml` and workflow YAML

### app-config.yaml for S3

```yaml
techdocs:
  builder: external
  publisher:
    type: awsS3
    awsS3:
      bucketName: ${AWS_S3_BUCKET_NAME}
      accountId: ${AWS_ACCOUNT_ID}
      region: ${AWS_REGION}

aws:
  accounts:
    - accountId: ${AWS_ACCOUNT_ID}
      accessKeyId: ${AWS_ACCESS_KEY_ID}
      secretAccessKey: ${AWS_SECRET_ACCESS_KEY}

catalog:
  locations:
    - type: url
      target: https://github.com/<your_org>/rhdh-techdocs-pipeline/blob/main/catalog-info.yaml
```

### Trigger

Changes to `docs/` folder or `mkdocs.yaml` trigger the workflow. After
successful run, generated TechDocs are uploaded to S3.

### Verification

- Navigate to RHDH > Docs to see TechDocs served from S3
- Restart the pod via Topology in OpenShift console after `app-config.yaml`
  changes
