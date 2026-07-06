# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product baseline | `docs/PLATFORM_BASELINE.md` |
| Document title | Administer OpenShift AI platform access, apps, and operations |
| Chapter title | Managing users and groups |
| Chapter URL | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_openshift_ai/managing-users-and-groups |
| Documentation category | Administer |
| Retrieved date | 2026-06-10 |
| Sections used | 1.1 through 1.5.5: user types, viewing users, adding users to groups, selecting user/admin groups, deleting users, stopping workbenches, revoking access, backing up PVC data, cleanup |

## Related Official Sources

| Source | Role |
|--------|------|
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_resources/selecting-admin-and-user-groups_resource-mgmt | Narrow dashboard workflow for selecting existing administrator and user groups |
| https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/authentication_and_authorization/index | OpenShift authentication and authorization |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/working_on_projects/using-project-workbenches_projects | Workbench usage and project context |
| https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/backup_and_restore/index | PVC and cluster backup context |

## Supporting Project Sources

| Source | Role |
|--------|------|
| `docs/PLATFORM_BASELINE.md` | Active RHOAI/OCP baseline and source hierarchy |
| `AGENTS.md` | OpenShift safety guard and GitOps operating constraints |
| `.agents/skills/rhoai-workbenches-custom-images/SKILL.md` | Workbench and PVC context |
| `.agents/skills/rhoai-certificate-management/SKILL.md` | Related user workbench certificate behavior |
| `.agents/skills/env-troubleshoot/SKILL.md` | Live diagnosis when dashboard or access behavior fails |

## Source Boundaries

- Product authority: official Red Hat documentation above.
- User/group membership is managed through OpenShift groups and the OpenShift
  AI dashboard. Do not invent backing CR fields for dashboard settings.
- Identity-provider design, LDAP configuration, and enterprise RBAC policy are
  outside this skill unless official RHOAI docs define the exact integration.
- User deletion cleanup can delete PVC data. Do not run cleanup without backup
  confirmation and explicit user approval.
