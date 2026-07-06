# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product baseline | `docs/PLATFORM_BASELINE.md` |
| Document title | Configure user access, storage, and telemetry in OpenShift AI |
| Chapter title | Chapter 5. Managing cluster PVC size |
| Chapter URL | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_resources/managing-cluster-pvc-size |
| Documentation category | Administer / Managing resources |
| Retrieved date | 2026-06-10 |
| Sections used | 5.1 Configuring the default PVC size for your cluster; 5.2 Restoring the default PVC size for your cluster |

## Related Official Sources

| Source | Role |
|--------|------|
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_resources/managing-storage-classes | Broader storage class and persistent storage behavior |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/creating_a_workbench/index | Workbench PVC use from workbench creation |
| https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/storage/index | OpenShift persistent storage background |

## Supporting Project Sources

| Source | Role |
|--------|------|
| `docs/PLATFORM_BASELINE.md` | Active RHOAI/OCP baseline and source hierarchy |
| `AGENTS.md` | OpenShift safety guard and GitOps operating constraints |
| `.agents/skills/rhoai-dashboard-customization/SKILL.md` | Adjacent dashboard configuration context |
| `.agents/skills/rhoai-workbenches-custom-images/SKILL.md` | Workbench PVC mount context |
| `.agents/skills/env-troubleshoot/SKILL.md` | Live storage and workbench diagnostics |

## Source Boundaries

- Product authority: the official Red Hat OpenShift AI 3.4 Managing resources
  chapter above.
- This chapter defines a dashboard workflow for the default PVC size.
- It verifies behavior for new PVCs; it does not define an existing-PVC resize
  workflow.
- It does not define storage class selection, access mode design, object
  storage endpoint configuration, or a GitOps field for the dashboard setting.
- Verification: dashboard setting review and new-PVC size checks.

## Unresolved Or Environment-Specific Items

- GitOps backing field for the dashboard setting.
  Verification: use official docs or installed schema before automating the
  setting.
- Demo default PVC size.
  Verification: choose during active implementation based on workbench data
  footprint and available storage.
- Existing PVC resize policy.
  Verification: use OpenShift storage documentation and the active storage
  class capabilities before resizing any existing PVC.
