# Official Documentation Extraction

Source: Red Hat Developer Hub 1.10 — Customizing Red Hat Developer Hub
Captured: 2026-07-06

---

## 1. Title Customization

```yaml
app:
  title: My custom Red Hat Developer Hub title
```

---

## 2. Base URL Customization

```yaml
app:
  baseUrl: https://<my_developer_hub_domain>
backend:
  baseUrl: https://<my_developer_hub_domain>
  cors:
    origin: https://<my_developer_hub_domain>
```

---

## 3. Backend Secret

Generate and configure the BACKEND_SECRET for service-to-service auth:

```bash
echo > <my_product_secrets>.txt "BACKEND_SECRET=$(node -p 'require("crypto").randomBytes(24).toString("base64")')"
```

In `app-config.yaml`:

```yaml
backend:
  auth:
    externalAccess:
      - type: legacy
        options:
          subject: legacy-default-config
          secret: "${BACKEND_SECRET}"
```

---

## 4. Software Templates

### Template versioning plugins

```yaml
global:
  dynamic:
    plugins:
      - package: ./dynamic-plugins/dist/backstage-community-plugin-catalog-backend-module-scaffolder-relation-processor-dynamic
        disabled: false
      - package: ./dynamic-plugins/dist/backstage-plugin-notifications
        disabled: false
      - package: ./dynamic-plugins/dist/backstage-plugin-notifications-backend-dynamic
        disabled: false
```

### Provenance and versioning actions in template steps

```yaml
steps:
  - id: create-provenance-annotation
    name: Append the entityRef of this template to the entityRef
    action: catalog:scaffolded-from
  - id: create-version-annotation
    name: Create Template Version Annotation
    action: catalog:template:version
    input:
      templateVersion: ${{ parameters.version }}
```

### Template version update notifications

```yaml
scaffolder:
  notifications:
    templateUpdate:
      enabled: true
      message:
        title: 'Custom title for $ENTITY_DISPLAY_NAME'
        description: 'Custom description'
```

Supports `$ENTITY_DISPLAY_NAME` variable (title or name of scaffolded entity).

---

## 5. Automated Template Lifecycle Management

### Enable pull request synchronization

```yaml
scaffolder:
  pullRequests:
    templateUpdate:
      enabled: true
```

### Enable notifications for PR creation

```yaml
scaffolder:
  notifications:
    templateUpdate:
      enabled: true
```

### Required plugins

```yaml
plugins:
  - package: './dynamic-plugins/dist/backstage-community-plugin-scaffolder-backend-module-scaffolder-relation-processor'
    disabled: false
  - package: './dynamic-plugins/dist/backstage-plugin-notifications'
    disabled: false
```

### Prerequisites for sync

- GitHub or GitLab integrations configured in `app-config.yaml`
- Entities include `spec.scaffoldedFrom` field
- Entities include `backstage.io/managed-by-location` annotation

### Behavior matrix

| PR Creation | Notifications | Outcome |
|-------------|---------------|---------|
| Disabled | Disabled | No action on template update |
| Disabled | Enabled | Notification with catalog link |
| Enabled | Disabled | PR created, no notification |
| Enabled | Enabled | PR created, notification with PR link |

### Reviewer assignment

- GitHub: requires `github.com/user-login` annotation
- GitLab: requires `gitlab.com/user-login` annotation
- Group owners: PR created without assigned reviewer

---

## 6. Default Environment Parameters and Secrets

```yaml
scaffolder:
  defaultEnvironment:
    parameters:
      githubOrg: my-org
      defaultOwner: platform-team
    secrets:
      GITHUB_TOKEN: ${GITHUB_TOKEN}
```

Access in templates:
- Parameters: `${{ environment.parameters.defaultOwner }}`
- Secrets: `${{ environment.secrets.GITHUB_TOKEN }}`

---

## 7. Register Software Templates

```yaml
catalog:
  locations:
    - type: url
      target: https://<repository_url>/example-template.yaml
      rules:
        - allow: [Template]
```

---

## 8. Basic Template Structure

A Software Template (`template.yaml`) contains:
- `apiVersion: scaffolder.backstage.io/v1beta3`
- `kind: Template`
- `metadata` — name, title, description
- `spec.parameters` — input fields for developers
- `spec.steps` — scaffolding actions (fetch:template, publish:github, etc.)

### Template form playground

Test configuration at `<instance_url>/create/template-form`.

---

## 9. Verification Commands

### Template version annotation
1. Catalog page > locate component > INSPECT ENTITY > YAML Raw view
2. Verify `backstage.io/template-version` annotation present

### Template dependencies
1. Catalog > select Software Template > Dependencies tab
2. View all linked components and resources

### Automated sync
1. Update source template version
2. Check downstream repository for PR named
   `[component-name]/template-upgrade-v[version]`
