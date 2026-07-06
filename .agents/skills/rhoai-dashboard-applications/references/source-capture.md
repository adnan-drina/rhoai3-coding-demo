# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product baseline | `docs/PLATFORM_BASELINE.md` |
| Document title | Administer OpenShift AI platform access, apps, and operations |
| Chapter title | Managing applications that show in the dashboard |
| Chapter URL | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_openshift_ai/managing-applications-that-show-in-the-dashboard |
| Documentation category | Administer |
| Retrieved date | 2026-06-10 |
| Sections used | 3.1 through 3.5: adding applications, preventing application additions, disabling connected applications, showing/hiding application information, hiding default basic workbench |

## Related Official Sources

| Source | Role |
|--------|------|
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_openshift_ai/managing-users-and-groups | OpenShift AI administrator access context |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_openshift_ai/creating-custom-workbench-images | Related dashboard configuration pattern for Workbench images visibility |
| https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/operators/index | Operator lifecycle and uninstall background |

## Supporting Project Sources

| Source | Role |
|--------|------|
| `docs/PLATFORM_BASELINE.md` | Active RHOAI/OCP baseline and source hierarchy |
| `AGENTS.md` | OpenShift safety guard and GitOps operating constraints |
| `.agents/skills/rhoai-users-groups-access/SKILL.md` | OpenShift AI administrator/user access context |
| `.agents/skills/rhoai-workbenches-custom-images/SKILL.md` | Custom workbench image dashboard import boundary |
| `.agents/skills/project-gitops-authoring/SKILL.md` | GitOps authoring patterns for ArgoCD-managed resources |

## Source Boundaries

- Product authority: official Red Hat documentation above.
- GitOps adaptation: project policy, not a Red Hat product requirement.
- `OdhApplication` and `OdhDashboardConfig` fields must come from official docs
  or active CRD schema inspection.
- Operator uninstall removes the Operator deployment but does not remove all
  CRDs, managed resources, applications, or off-cluster resources. Treat it as
  destructive and incomplete without a reviewed cleanup plan.
- Do not use this skill for OpenShift Console dynamic plugins or Model Catalog
  content unless official RHOAI docs explicitly tie those resources to
  dashboard applications.
