# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product baseline | `docs/PLATFORM_BASELINE.md` |
| Document title | Administer OpenShift AI platform access, apps, and operations |
| Chapter title | Customizing component deployment resources |
| Chapter URL | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_openshift_ai/customizing-component-deployment-resources_resource-mgmt |
| Documentation category | Administer |
| Retrieved date | 2026-06-10 |
| Sections used | 6.1 through 6.4: overview, customizing component resources, disabling customization, re-enabling customization |

## Related Official Sources

| Source | Role |
|--------|------|
| https://access.redhat.com/support/offerings/techpreview | Technology Preview support scope |
| https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/workloads_apis/deployment-apps-v1 | OpenShift Deployment API background |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_openshift_ai/managing-applications-that-show-in-the-dashboard | Related dashboard Deployment context |

## Supporting Project Sources

| Source | Role |
|--------|------|
| `docs/PLATFORM_BASELINE.md` | Active RHOAI/OCP baseline and source hierarchy |
| `AGENTS.md` | OpenShift safety guard and GitOps operating constraints |
| `.agents/skills/project-gitops-authoring/SKILL.md` | GitOps authoring boundaries |
| `.agents/skills/env-manage-resources/SKILL.md` | Demo shutdown/resource scaling boundary |
| `.agents/skills/rhoai-distributed-workloads/SKILL.md` | Kueue/Ray/Training Operator component context |

## Source Boundaries

- Product authority: official Red Hat documentation above.
- GitOps adaptation: project policy, not a Red Hat product requirement.
- This chapter covers component Deployment resources such as CPU and memory
  requests/limits. It does not define quotas, autoscaling policy, hardware
  profiles, model runtime sizing, or user workload resource governance.
- The official chapter uses console edits. If this repo automates the workflow,
  use scoped patches and verify active Deployment/container names before
  applying them.
- Do not remove or set `opendatahub.io/managed` to `false` after adding it.
  Use the official delete-and-reconcile workflow to re-enable customization.
