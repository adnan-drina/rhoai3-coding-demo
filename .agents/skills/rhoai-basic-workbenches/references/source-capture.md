# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product baseline | `docs/PLATFORM_BASELINE.md` |
| Document title | Configure user access, storage, and telemetry in OpenShift AI |
| Chapter title | Chapter 8. Managing basic workbenches |
| Chapter URL | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_resources/managing-basic-workbenches_notebook-mgmt |
| Documentation category | Administer / Managing resources |
| Retrieved date | 2026-06-10 |
| Sections used | 8.1 Accessing the administration interface for basic workbenches; 8.2 Starting basic workbenches owned by other users; 8.3 Accessing basic workbenches owned by other users; 8.4 Stopping basic workbenches owned by other users; 8.5 Stopping idle workbenches; 8.6 Adding workbench pod tolerations; 8.7 Troubleshooting common problems in workbenches for administrators; 8.7.1 Jupyter 404; 8.7.2 Workbench does not start; 8.7.3 Database or disk full |

## Related Official Sources

| Source | Role |
|--------|------|
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/working_with_connected_applications/using-basic-workbenches_connected-apps | User-facing basic workbench start, notebook, Git, package, and restart workflows |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/creating_a_workbench/index | Preferred project workbench workflow for project-centered data science work |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_resources/selecting-admin-and-user-groups_resource-mgmt | Administrator and user group selection context |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_resources/managing-cluster-pvc-size | Adjacent default PVC size workflow |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_resources/managing-storage-classes | Adjacent storage class and access mode workflow |
| https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/nodes/controlling-pod-placement-onto-nodes-scheduling | OpenShift taints and tolerations background |
| https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/storage/expanding-persistent-volumes | Persistent volume expansion referenced by disk-full troubleshooting |

## Supporting Project Sources

| Source | Role |
|--------|------|
| `docs/PLATFORM_BASELINE.md` | Active RHOAI/OCP baseline and source hierarchy |
| `AGENTS.md` | OpenShift safety guard and GitOps operating constraints |
| `.agents/skills/rhoai-workbenches-custom-images/SKILL.md` | Project workbench and custom image boundary |
| `.agents/skills/rhoai-users-groups-access/SKILL.md` | User and group access boundary |
| `.agents/skills/rhoai-dashboard-customization/SKILL.md` | Start basic workbench tile visibility boundary |
| `.agents/skills/env-troubleshoot/SKILL.md` | Broader live cluster diagnostics |

## Source Boundaries

- Product authority: the official Red Hat OpenShift AI 3.4 Managing resources
  chapter above.
- This chapter defines dashboard administration and troubleshooting workflows
  for basic workbenches.
- It does not define GitOps resources for basic workbench administration
  settings.
- It does not define project workbench creation, custom workbench image
  creation, or workbench image import.
- It references OpenShift taints, tolerations, and persistent volume expansion,
  but those are OpenShift platform operations and must be validated against the
  active OpenShift baseline before implementation.
- Verification: OpenShift AI dashboard behavior, `notebook-controller-culler-config`
  inspection, StatefulSet/pod details, user group membership, pod logs, and
  user ability to open JupyterLab.

## Unresolved Or Environment-Specific Items

- Demo idle workbench timeout.
  Verification: choose during active implementation based on cost controls and
  demo user experience.
- Demo workbench toleration key and tainted node pool.
  Verification: define with the target OpenShift machine pool design before
  enabling the setting.
- GitOps backing fields for idle timeout and toleration settings.
  Verification: use official docs or installed schema before automating these
  dashboard settings.
- Default namespace for basic workbench pods when the deployment uses a custom
  workbench namespace.
  Verification: inspect the target cluster before writing environment-specific
  runbooks.
