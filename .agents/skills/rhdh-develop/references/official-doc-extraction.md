# Official Documentation Extraction

Source: Red Hat Developer Hub 1.10 — Streamline software development and management
Captured: 2026-07-06

---

## 1. Bulk Import (Technology Preview)

Bulk Import automates GitHub repository and GitLab project onboarding into the
catalog.

**Important:** Technology Preview — not supported with Red Hat production SLAs.

### Enable Bulk Import plugins

Plugins are installed but disabled by default:

```yaml
plugins:
  - package: ./dynamic-plugins/dist/red-hat-developer-hub-backstage-plugin-bulk-import-backend-dynamic
    disabled: false
  - package: ./dynamic-plugins/dist/red-hat-developer-hub-backstage-plugin-bulk-import
    disabled: false
```

### RBAC permission for non-admin users

```plaintext
p, role:default/bulk-import, bulk.import, use, allow
g, user:default/<your_user>, role:default/bulk-import
```

Only administrators or users with `bulk.import` permission can use Bulk Import.

### Prerequisites

- User authentication configured with GitHub or GitLab as authentication
  provider (mandatory — user OAuth tokens required for all listing operations)
- For GitHub: GitHub repository discovery enabled

### Import workflow (GitHub)

1. Click Bulk Import in the left sidebar
2. Select source control tool (GitHub) if multiple configured
3. Select repositories and click Add
4. Developer Hub creates a PR in each repo adding `catalog-info.yaml`
5. Import statuses: `Added`, `Waiting for approval`, `Empty`
6. Merge the PR to complete the import

### Audit log events

| Event | Endpoint | Method |
|-------|----------|--------|
| `BulkImportPing` | `/ping` | GET |
| `BulkImportFindAllOrganizations` | `/organizations` | GET |
| `BulkImportFindRepositoriesByOrganization` | `/organizations/:orgName/repositories` | GET |
| `BulkImportFindAllRepositories` | `/repositories` | GET |
| `BulkImportFindAllImports` | `/imports` | GET |
| `BulkImportCreateImportJobs` | `/imports` | POST |
| `BulkImportFindImportStatusByRepo` | `/import/by-repo` | GET |
| `BulkImportDeleteImportByRepo` | `/import/by-repo` | DELETE |

---

## 2. Software Catalog

The Software Catalog is a centralized system for visibility into all software
(services, websites, libraries, data pipelines). Metadata stored as YAML
alongside code in version control.

### Entity kinds

Components, Resources, APIs, Templates, and other related types.

### Add components

Three methods:
- Register manually (GUI or `app-config.yaml`)
- Create from Software Templates
- Bulk Import

### RBAC permissions

| Operation | Required permissions |
|-----------|---------------------|
| Register entity | `catalog.entity.create`, `catalog.location.create` |
| Create via template | `catalog.entity.create`, `scaffolder.template.parameter.read`, `scaffolder.template.step.read`, `scaffolder.task.create` |
| Update entity | `catalog.entity.refresh` |
| Bulk Import | `bulk.import` |

### catalog-info.yaml

```yaml
apiVersion: backstage.io/v1alpha1
kind: Component
metadata:
  name: <your_software_component>
  description: <software_component_brief_description>
  tags:
    - example
    - service
  annotations:
    github.com/project-slug: <repo_link_of_your_component_to_register>
spec:
  type: <your_service>
  owner: <your_team_name>
  lifecycle: <your_lifecycle>
```

### Catalog operations

- **Filter by Kind:** Component, API, Template — available filters change by
  selected Kind
- **Search by text:** Enter component name, description, or keyword
- **View YAML:** Actions > View icon redirects to YAML file in remote repo
- **Star entities:** Actions > star icon for quick access via Your Starred
  Entities card
- **Refresh:** Catalog refresh can take up to 45 minutes; manual refresh via
  entity Overview tab

---

## 3. Software Templates

Templates use YAML definitions for project metadata input and run sequential
scaffolding actions (conditionally based on user input).

### Create component from template

1. Navigate: Catalog > Self-service or Global Header Create (+)
2. Select template and click Choose
3. Follow wizard for project details
4. Review step — verify parameters, click Create
5. Monitor scaffolding in logs; click Cancel to stop

RBAC: `scaffolder.template.parameter.read`, `scaffolder.template.step.read`,
`scaffolder.task.create`

### Import existing template

Add to `app-config.yaml`:

```yaml
catalog:
  rules:
    - allow: [Template]
  locations:
    - type: url
      target: https://<repository_url/template-name>.yaml
```

### Verification

1. Navigate: Catalog
2. Kind list > select Template
3. Verify template appears in list

### Search and filter templates

1. Navigate: Catalog > Self-service
2. Search field for template name
3. Optional: Category list to refine results
