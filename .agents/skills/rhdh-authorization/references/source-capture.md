# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product | Red Hat Developer Hub |
| Product version | 1.10 |
| Book title | Authorization in Red Hat Developer Hub |
| Book URL | https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/authorization_in_red_hat_developer_hub/index |
| Documentation category | Control access |
| Retrieved date | 2026-07-06 |
| Sections used | Ch 1: Role-based access control in Developer Hub; Ch 2: Enable and give access to the RBAC feature; Ch 3: Determine permission policy and role configuration source; Ch 4: Design your policy rules; Ch 5: Manage RBAC using the Web UI; Ch 6: Manage authorizations by using the REST API (endpoints for roles, policies, conditions, user statistics); Ch 7: Manage authorizations by using external files (Operator and Helm) |

## Supporting Red Hat Sources

| Source | Role |
|--------|------|
| Red Hat Developer Hub 1.10 product documentation | Primary product authority |
| RHDH Permission policies reference (Chapter 8 of the same guide) | Supplemental permission name and action reference |
| RHDH Conditional policies reference (Chapter 9 of the same guide) | Supplemental condition rule schema reference |

## Source Boundaries

- Product configuration truth: official RHDH 1.10 Authorization guide above.
- RBAC plugin behavior, REST API endpoints, CSV format, and conditional policy
  schema: defined by the official guide.
- Demo policy: RBAC policies are managed through GitOps-controlled ConfigMaps;
  no manual Web UI edits in production.
- Verification: REST API responses, RBAC tab in Administration UI, HTTP
  status codes.
- Not authoritative: upstream Backstage community permission framework
  internals unless explicitly referenced by the Red Hat guide.

## Unresolved Or Environment-Specific Items

- Exact policy administrator username for the demo environment.
  Verification: confirm from the RHDH deployment ConfigMap or stage 090
  configuration.
- Which plugins need `pluginsWithPermission` entries beyond catalog,
  scaffolder, and permission.
  Verification: check installed dynamic plugins and their permission
  requirements.
- Whether external CSV files or REST API is the primary policy management
  method for this demo.
  Verification: align with the GitOps pattern decision for the RHDH stage.
