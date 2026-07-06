# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product baseline | `docs/PLATFORM_BASELINE.md` |
| Document title | Configure user access, storage, and telemetry in OpenShift AI |
| Chapter title | Chapter 1. Selecting OpenShift AI administrator and user groups |
| Chapter URL | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_resources/selecting-admin-and-user-groups_resource-mgmt |
| Documentation category | Administer / Managing resources |
| Retrieved date | 2026-06-10 |
| Sections used | Chapter 1 introduction, prerequisites, procedure, important `system:authenticated` note, verification |

## Related Official Sources

| Source | Role |
|--------|------|
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_openshift_ai/managing-users-and-groups | Broader user and group lifecycle, group membership, user deletion, PVC cleanup |
| https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/authentication_and_authorization/index | OpenShift authentication, groups, and RBAC background |

## Supporting Project Sources

| Source | Role |
|--------|------|
| `docs/PLATFORM_BASELINE.md` | Active RHOAI/OCP baseline and source hierarchy |
| `AGENTS.md` | OpenShift safety guard and repo operating constraints |
| `.agents/skills/rhoai-users-groups-access/SKILL.md` | Broader access lifecycle and cleanup workflows |
| `.agents/skills/rhoai-central-authentication-service/SKILL.md` | Adjacent OIDC provider configuration |

## Source Boundaries

- Product authority: the official Red Hat OpenShift AI 3.4 Managing resources
  chapter above.
- This chapter defines a dashboard workflow, not a GitOps API.
- Group creation, group membership, LDAP synchronization, user cleanup, and PVC
  backup are outside this skill.
- Verification: dashboard login checks plus read-only OpenShift group checks
  listed in this skill.

## Unresolved Or Environment-Specific Items

- Automation path for dashboard user-management selections.
  Verification: use official docs or installed schema before adding automation.
- Final demo group names.
  Verification: record the active environment groups in `docs/OPERATIONS.md`
  when the access model is implemented.
- Whether unrestricted `system:authenticated` access is acceptable for a given
  demo environment.
  Verification: decide per environment and document the tradeoff.
