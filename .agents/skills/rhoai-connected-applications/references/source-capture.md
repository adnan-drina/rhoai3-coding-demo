# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product baseline | `docs/PLATFORM_BASELINE.md` |
| Document title | Working with connected applications |
| Guide title | Enable and manage connected applications from the OpenShift AI dashboard |
| Guide URL | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_connected_applications/index |
| Documentation category | Develop / Working with connected applications |
| Retrieved date | 2026-06-10 |
| Sections used | Preface; 1 Viewing applications that are connected to OpenShift AI; 2 Enabling applications that are connected to OpenShift AI; 3 Removing disabled applications from the dashboard; 4 Using basic workbenches; 4.1 Starting a basic workbench; 4.2 Creating and importing Jupyter notebooks; 4.3 Collaborating on Jupyter notebooks by using Git; 4.4 Managing Python packages; 4.5 Updating workbench settings by restarting your workbench |

## Related Official Sources

| Source | Role |
|--------|------|
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_openshift_ai/managing-applications-that-show-in-the-dashboard | Administrator dashboard application tile management and disablement |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_on_projects/index | Preferred project workbench lifecycle and project-scoped work |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_in_your_data_science_ide/index | JupyterLab, code-server, Git, and Python package workflows |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/working_with_accelerators | Accelerator enablement and support boundaries |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_openshift_ai/managing-users-and-groups | OpenShift AI user/admin access group management |

## Supporting Project Sources

| Source | Role |
|--------|------|
| `docs/PLATFORM_BASELINE.md` | Active RHOAI/OCP baseline and source hierarchy |
| `AGENTS.md` | OpenShift safety guard and GitOps operating constraints |
| `.agents/skills/rhoai-dashboard-applications/SKILL.md` | Administrator-side dashboard application tile boundary |
| `.agents/skills/rhoai-users-groups-access/SKILL.md` | User/group access boundary |
| `.agents/skills/rhoai-project-workflows/SKILL.md` | Preferred project workbench boundary |
| `.agents/skills/rhoai-data-science-ide-workflows/SKILL.md` | JupyterLab and code-server IDE workflow boundary |
| `.agents/skills/rhoai-basic-workbenches/SKILL.md` | Administrator-side basic workbench boundary |

## Source Boundaries

- Product authority: the official Red Hat OpenShift AI 3.4 Working with
  connected applications guide above.
- The guide defines user-facing dashboard workflows: discovering connected
  applications, enabling SaaS-based applications, removing already-disabled
  tiles, and using the Start basic workbench enabled application.
- It does not replace administrator tile manifest authoring, Operator
  installation, global access management, project workbench lifecycle,
  broad IDE usage, or accelerator platform enablement.
- Verification: Applications -> Explore tile visibility, Enabled page tile
  visibility, API endpoint display where applicable, disabled tile removal,
  basic workbench IDE access, and captured access or workbench startup errors.

## Unresolved Or Environment-Specific Items

- Active connected applications for the demo.
  Verification: record which applications are actually installed, enabled, and
  used in `docs/OPERATIONS.md` or the relevant step README when implemented.
- SaaS service key handling.
  Verification: define credential source and secret storage before enabling a
  SaaS connected application in demo content.
- ISV namespace requirements.
  Verification: inspect the application tile and official ISV docs before
  creating namespaces or GitOps resources.
- Start basic workbench role in the demo.
  Verification: document whether the demo uses Start basic workbench at all or
  keeps all user work in project workbenches.
