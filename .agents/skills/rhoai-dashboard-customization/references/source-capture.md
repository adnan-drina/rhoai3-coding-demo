# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product baseline | `docs/PLATFORM_BASELINE.md` |
| Document title | Configure user access, storage, and telemetry in OpenShift AI |
| Chapter title | Chapter 2. Customizing the dashboard |
| Chapter URL | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_resources/customizing-the-dashboard |
| Documentation category | Administer / Managing resources |
| Retrieved date | 2026-06-10 |
| Sections used | 2.1 Editing the dashboard configuration; 2.2 Dashboard configuration options |

## Related Official Sources

| Source | Role |
|--------|------|
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_openshift_ai/managing-applications-that-show-in-the-dashboard | OdhApplication tiles, application enablement, and related dashboard application visibility |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_resources/selecting-admin-and-user-groups_resource-mgmt | Dashboard user-management access selection workflow |
| https://access.redhat.com/support/offerings/techpreview | Technology Preview support scope |

## Supporting Project Sources

| Source | Role |
|--------|------|
| `docs/PLATFORM_BASELINE.md` | Active RHOAI/OCP baseline and source hierarchy |
| `AGENTS.md` | OpenShift safety guard and GitOps operating constraints |
| `.agents/skills/rhoai-dashboard-applications/SKILL.md` | Adjacent dashboard application tile workflow |
| `.agents/skills/project-gitops-authoring/SKILL.md` | GitOps authoring patterns for ArgoCD-managed resources |

## Source Boundaries

- Product authority: the official Red Hat OpenShift AI 3.4 Managing resources
  chapter above.
- This skill controls dashboard visibility and feature flags, not underlying
  component installation.
- Dashboard configuration does not replace component-specific configuration for
  KServe, Kueue, Feature Store, Model Registry, observability, MaaS, MLflow,
  or Gen AI Studio.
- Verification: dashboard behavior plus read-only schema and resource checks.

## Unresolved Or Environment-Specific Items

- Exact GitOps ownership path for `odh-dashboard-config`.
  Verification: define it when active GitOps implementation is recreated.
- Whether each Technology Preview or Developer Preview item belongs in the demo.
  Verification: decide per step and record support posture in the README or
  operations notes.
- Final model server size and notebook size profiles.
  Verification: align with GPU and workload sizing during implementation.
