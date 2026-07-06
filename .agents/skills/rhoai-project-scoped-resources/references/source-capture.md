# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product baseline | `docs/PLATFORM_BASELINE.md` |
| Document title | Administer OpenShift AI platform access, apps, and operations |
| Chapter title | Creating project-scoped resources |
| Chapter URL | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_openshift_ai/creating-project-scoped-resources_managing-rhoai |
| Documentation category | Administer |
| Retrieved date | 2026-06-10 |
| Sections used | Chapter 4: project-scoped resource types, prerequisites, trusted YAML sources, namespace/name/display-name edits, verification |

## Related Official Sources

| Source | Role |
|--------|------|
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_openshift_ai/creating-custom-workbench-images | Workbench image details |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/working_with_accelerators/working-with-hardware-profiles_accelerators | Hardware profile details |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/deploying_models | Serving runtime and model deployment details |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/working_on_projects/using-project-workbenches_projects | User-facing workbench verification context |

## Supporting Project Sources

| Source | Role |
|--------|------|
| `docs/PLATFORM_BASELINE.md` | Active RHOAI/OCP baseline and source hierarchy |
| `AGENTS.md` | OpenShift safety guard and GitOps operating constraints |
| `.agents/skills/rhoai-workbenches-custom-images/SKILL.md` | Workbench image source and dashboard visibility |
| `.agents/skills/rhoai-nvidia-gpu-accelerators/SKILL.md` | Hardware profile and NVIDIA accelerator context |
| `.agents/skills/project-gitops-authoring/SKILL.md` | GitOps placement and ArgoCD review |

## Source Boundaries

- Product authority: official Red Hat documentation above.
- GitOps adaptation: project policy, not a Red Hat product requirement.
- This chapter identifies resource types and project-scoping workflow; it does
  not define complete schemas for `ImageStream`, `HardwareProfile`, `Template`,
  or embedded `ServingRuntime` objects.
- For fields beyond `metadata.namespace`, `metadata.name`, and documented
  display-name fields, use component-specific docs or active CRD/schema
  verification.
- Do not assume project-scoped resources are visible until the user has access
  to the target project and the dashboard configuration allows project-scoped
  resources.
