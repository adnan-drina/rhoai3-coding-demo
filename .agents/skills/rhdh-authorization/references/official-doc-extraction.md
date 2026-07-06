# Official Doc Extraction

Use this reference when authoring or reviewing RHDH authorization and RBAC
content.

## Component Purpose

Authorization in Red Hat Developer Hub uses role-based access control (RBAC) to
define what authenticated users can do. Administrators define roles with
specific permissions and assign roles to users and groups. The RBAC feature is
built on the Backstage Permissions framework but uses declarative CSV/YAML
policies instead of code.

## RBAC Architecture

- The RBAC backend plugin (`backstage-community-plugin-rbac`) manages all
  policy evaluation.
- Default policy is **deny** — nothing is allowed unless explicitly permitted.
- Three management interfaces: Web UI, REST API, and external files.
- Each policy/role is associated with exactly one source to maintain
  consistency.

## Prerequisites

- A custom RHDH application configuration is deployed.
- An authentication provider is enabled (see `rhdh-authentication` skill).
- Users/groups are provisioned to the software catalog.

## Enabling RBAC (Chapter 2)

### Step 1: Enable the plugin

`dynamic-plugins.yaml`:
```yaml
plugins:
  - package: ./dynamic-plugins/dist/backstage-community-plugin-rbac
    disabled: false
```

### Step 2: Declare policy administrators

`app-config.yaml`:
```yaml
permission:
  enabled: true
  rbac:
    admin:
      users:
        - name: user:default/<admin_username>
    pluginsWithPermission:
      - catalog
      - scaffolder
      - permission
```

The default `role:default/rbac_admin` role has permissions to create, read,
update, delete permission policies or roles, and to read catalog entities.

### Verification

With RBAC enabled:
- The Create button is not visible on the Catalog page.
- The Register button is not visible on the API page.

## Policy Sources (Chapter 3)

| Source | Description |
|--------|-------------|
| Configuration file | `role:default/rbac_admin` defined in `app-config.yaml` |
| REST API | Roles/policies managed via Web UI or REST API |
| CSV file | External `rbac-policies.csv` and `rbac-conditional-policies.yaml` |
| Legacy | Pre-2.1.3 policies (should be migrated) |

A resource's source determines how it can be modified. You cannot change a
CSV-sourced policy via the REST API.

## Policy Rule Design (Chapter 4)

Evaluation precedence (most specific wins):
1. Default: `deny`
2. Conditional rule overrides basic rule
3. `deny` basic overrides `allow` basic
4. `allow` conditional overrides `deny` basic
5. `deny` conditional overrides `allow` conditional

Best practices:
- Use `allow` rules to explicitly grant access.
- Avoid `deny` rules unless you understand their interaction with existing
  conditional rules.

## Managing RBAC via Web UI (Chapter 5)

Available operations for policy administrators:
- **Create role**: Administration → RBAC → CREATE
- **Edit role**: Edit icon on role row or OVERVIEW page
- **Delete role**: Delete icon from Actions column

Required permissions for Web UI management:
- Create: `policy.entity.create`, `policy.entity.read`, `catalog.entity.read`
- Edit: `policy.entity.update`, `policy.entity.read`, `catalog.entity.read`
- Delete: `policy.entity.delete`, `policy.entity.read`, `catalog.entity.read`

Policies from CSV/ConfigMap cannot be edited or deleted via the Web UI.

## Managing RBAC via REST API (Chapter 6)

### Authentication

All REST API calls require a Bearer token obtained from the browser Network
tab (`query?term=` response).

### Roles API

Create a role:
```bash
curl -v -H "Content-Type: application/json" \
  -H "Authorization: Bearer $token" \
  -X POST "https://<rhdh_domain>/api/permission/roles" \
  -d '{
    "memberReferences": ["group:default/example"],
    "name": "role:default/test",
    "metadata": { "description": "This is a test role" }
  }'
```

### Permission Policies API

Create a permission policy:
```bash
curl -v -H "Content-Type: application/json" \
  -H "Authorization: Bearer $token" \
  -X POST "https://<rhdh_domain>/api/permission/policies" \
  -d '[{
    "entityReference": "role:default/test",
    "permission": "catalog-entity",
    "policy": "read",
    "effect": "allow"
  }]'
```

### Conditional Policies API

Create a conditional policy:
```bash
curl -v -H "Content-Type: application/json" \
  -H "Authorization: Bearer $token" \
  -X POST "https://<rhdh_domain>/api/permission/roles/conditions" \
  -d '{
    "result": "CONDITIONAL",
    "roleEntityRef": "role:default/test",
    "pluginId": "catalog",
    "resourceType": "catalog-entity",
    "permissionMapping": ["read"],
    "conditions": {
      "rule": "IS_ENTITY_OWNER",
      "resourceType": "catalog-entity",
      "params": {"claims": ["group:default/team-a"]}
    }
  }'
```

### HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | OK |
| 201 | Created |
| 204 | No Content (successful delete) |
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not Found |
| 409 | Conflict |

## Managing RBAC via External Files (Chapter 7)

### CSV Format for Policies

`rbac-policies.csv`:
```
p, role:default/guests, catalog-entity, read, allow
p, role:default/guests, catalog.entity.create, create, allow
g, user:default/my-user, role:default/guests
g, group:default/my-group, role:default/guests
```

Format:
- `p, <role>, <permission>, <action>, <effect>` — permission policy
- `g, <user_or_group>, <role>` — role assignment

### YAML Format for Conditional Policies

`rbac-conditional-policies.yaml`:
```yaml
result: CONDITIONAL
roleEntityRef: role:default/test
pluginId: catalog
resourceType: catalog-entity
permissionMapping:
  - read
  - update
  - delete
conditions:
  rule: IS_ENTITY_OWNER
  resourceType: catalog-entity
  params:
    claims:
      - group:default/team-a
```

### Deploying via Operator

Upload files to a ConfigMap:
```bash
oc create configmap rbac-policies \
  --from-file=rbac-policies.csv \
  --from-file=rbac-conditional-policies.yaml
```

Reference in `app-config.yaml`:
```yaml
permission:
  enabled: true
  rbac:
    policies-csv-file: /opt/app-root/src/rbac-policies.csv
    policyFileReload: true
    conditionalPoliciesFile: /opt/app-root/src/rbac-conditional-policies.yaml
```

## Available Condition Rules

### Catalog Plugin Rules

| Rule | Description | Required params |
|------|-------------|-----------------|
| `HAS_ANNOTATION` | Match entities with specific annotation | `annotation` (+ optional `value`) |
| `HAS_LABEL` | Match entities with specific label | `label` |
| `HAS_METADATA` | Match entities with metadata subfield | `key` (+ optional `value`) |
| `HAS_SPEC` | Match entities with spec subfield | `key` (+ optional `value`) |
| `IS_ENTITY_KIND` | Match entities of specified kinds | `kinds[]` |
| `IS_ENTITY_OWNER` | Match entities owned by claims | `claims[]` |

### Condition Operators

Conditions support nested logical operators:
- `anyOf: [...]` — logical OR
- `allOf: [...]` — logical AND
- `not: {...}` — logical NOT

Example with nested operators:
```json
{
  "anyOf": [
    {
      "rule": "IS_ENTITY_OWNER",
      "resourceType": "catalog-entity",
      "params": { "claims": ["group:default/team-a"] }
    },
    {
      "rule": "IS_ENTITY_KIND",
      "resourceType": "catalog-entity",
      "params": { "kinds": ["Group"] }
    }
  ]
}
```

## User Statistics API (Chapter 6.4.4)

The `licensed-users-info-backend` plugin provides:
- `GET /api/licensed-users-info/users/quantity` — total logged-in user count
- `GET /api/licensed-users-info/users` — user list (JSON or CSV)

Protected by `policy.entity.read` permission when RBAC is enabled.

## Security Considerations

- Policy administrators have full control over all RBAC configuration.
- The default `role:default/rbac_admin` has limited permissions; create a
  custom admin role if more permissions are needed.
- External services can query the RBAC API with service-to-service tokens
  (GET only).
- CSV/ConfigMap policies cannot be edited at runtime through the Web UI or
  REST API, providing immutability for GitOps-managed configurations.
