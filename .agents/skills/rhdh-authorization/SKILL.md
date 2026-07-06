---
name: rhdh-authorization
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhdh"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Developer Hub"
description: >
  Use when configuring authorization, RBAC, permission policies, and role
  management in Red Hat Developer Hub: enabling the RBAC plugin; declaring
  policy administrators; creating roles and assigning users/groups; defining
  permission policies via Web UI, REST API, or external CSV/YAML files;
  designing policy rules and conditional policies; using condition rule
  operators (anyOf, allOf, not); and managing user statistics. Do NOT use for
  authentication provider setup, user provisioning, or sign-in configuration;
  use rhdh-authentication. Do NOT use for RHDH installation or plugin
  management.
---

# RHDH Authorization

Use this skill to configure role-based access control (RBAC) and permission
policies in Red Hat Developer Hub 1.10.

## Source Grounding

Read `references/source-capture.md` before using product configuration details.
Official Red Hat documentation is product authority. This skill adapts the
official Authorization guide to this repo's GitOps and secret-handling model.

## Key Concepts

- RBAC is built on top of the Permissions framework.
- Default policy is **deny** — all access must be explicitly allowed.
- Policies can be defined via three sources: Configuration file, REST API/Web
  UI, or external CSV file. Each resource is associated with one source.
- Conditional policies override basic policies; deny conditional overrides
  allow conditional.

## Policy Evaluation Order

1. Default policy: `deny`
2. A conditional rule overrides a basic rule.
3. A `deny` basic rule overrides an `allow` basic rule.
4. An `allow` conditional rule overrides a `deny` basic rule.
5. A `deny` conditional rule overrides an `allow` conditional rule.

## Workflow

1. **Enable RBAC plugin** in `dynamic-plugins.yaml` (Chapter 2).
2. **Declare policy administrators** in `app-config.yaml` under
   `permission.rbac.admin.users` (Chapter 2).
3. **Choose policy source**: Web UI, REST API, or external CSV/YAML files.
4. **Define roles** and assign users/groups to them.
5. **Define permission policies** for each role.
6. **Add conditional policies** when fine-grained resource filtering is needed.
7. **Verify** via the RBAC tab in Administration or REST API GET endpoints.

## Demo Policy

For this repo:

- Use external CSV/YAML files managed through GitOps for reproducible RBAC
  configuration.
- Declare the demo admin user as the policy administrator.
- Keep RBAC policies in ConfigMaps referenced by the Backstage CR.
- Default deny ensures new plugins/resources require explicit access grants.

## Enabling RBAC

In `dynamic-plugins.yaml`:
```yaml
plugins:
  - package: ./dynamic-plugins/dist/backstage-community-plugin-rbac
    disabled: false
```

In `app-config.yaml`:
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

## Policy Sources

| Source | Managed via | Mutability |
|--------|------------|-----------|
| Configuration file | `app-config.yaml` | Read-only at runtime |
| REST API | Web UI or curl | Mutable at runtime |
| CSV file | External `rbac-policies.csv` | Mutable via file only |
| Legacy | Pre-2.1.3 policies | Should be migrated |

## CSV Policy Format

Role permission:
```
p, <role_entity_reference>, <permission>, <action>, <allow_or_deny>
```

Role assignment:
```
g, <group_or_user>, <role_entity_reference>
```

Example:
```
p, role:default/guests, catalog-entity, read, allow
p, role:default/guests, catalog.entity.create, create, allow
g, user:default/my-user, role:default/guests
g, group:default/my-group, role:default/guests
```

## Conditional Policies (YAML)

```yaml
result: CONDITIONAL
roleEntityRef: role:default/test
pluginId: catalog
resourceType: catalog-entity
permissionMapping:
  - read
conditions:
  rule: IS_ENTITY_OWNER
  resourceType: catalog-entity
  params:
    claims:
      - group:default/team-a
```

Condition operators: `anyOf`, `allOf`, `not` (nestable).

## RBAC REST API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/permission/roles` | List all roles |
| POST | `/api/permission/roles` | Create a role |
| PUT | `/api/permission/roles/<kind>/<ns>/<name>` | Update a role |
| DELETE | `/api/permission/roles/<kind>/<ns>/<name>` | Delete a role |
| GET | `/api/permission/policies` | List all policies |
| POST | `/api/permission/policies` | Create a policy |
| PUT | `/api/permission/policies/<kind>/<ns>/<name>` | Update a policy |
| DELETE | `/api/permission/policies/<kind>/<ns>/<name>` | Delete a policy |
| GET | `/api/permission/roles/conditions` | List conditions |
| POST | `/api/permission/roles/conditions` | Create a condition |
| GET | `/api/permission/plugins/condition-rules` | List available rules |
| GET | `/api/permission/plugins/policies` | List plugin permissions |

## Available Condition Rules (Catalog Plugin)

| Rule | Description | Params |
|------|-------------|--------|
| `HAS_ANNOTATION` | Match entities with annotation | `annotation`, `value` |
| `HAS_LABEL` | Match entities with label | `label` |
| `HAS_METADATA` | Match entities with metadata field | `key`, `value` |
| `HAS_SPEC` | Match entities with spec field | `key`, `value` |
| `IS_ENTITY_KIND` | Match entities of specified kinds | `kinds[]` |
| `IS_ENTITY_OWNER` | Match entities owned by claims | `claims[]` |

## Validation

- With RBAC enabled, most features are disabled by default (deny-all).
- The Create button disappears from Catalog; Register button from API page.
- REST API returns standard HTTP codes: 200, 201, 204, 400, 401, 403, 404, 409.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
