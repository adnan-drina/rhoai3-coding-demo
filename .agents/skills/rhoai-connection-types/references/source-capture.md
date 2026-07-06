# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product baseline | `docs/PLATFORM_BASELINE.md` |
| Document title | Configure user access, storage, and telemetry in OpenShift AI |
| Chapter title | Chapter 6. Managing connection types |
| Chapter URL | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_resources/managing-connection-types |
| Documentation category | Administer / Managing resources |
| Retrieved date | 2026-06-10 |
| Sections used | 6.1 Viewing connection types; 6.2 Creating a connection type; 6.3 Duplicating a connection type; 6.4 Editing a connection type; 6.5 Enabling a connection type; 6.6 Deleting a connection type |

## Related Official Sources

| Source | Role |
|--------|------|
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_resources/customizing-the-dashboard | Dashboard visibility for the Connection types menu |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_resources/managing-storage-classes | Broader storage and object-storage endpoint context |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/creating_a_workbench/index | Workbench resources that can consume connections |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/deploying_models | Model server resources that can consume connections |

## Supporting Project Sources

| Source | Role |
|--------|------|
| `docs/PLATFORM_BASELINE.md` | Active RHOAI/OCP baseline and source hierarchy |
| `AGENTS.md` | OpenShift safety guard and GitOps operating constraints |
| `.agents/skills/rhoai-dashboard-customization/SKILL.md` | Dashboard menu visibility for connection types |
| `.agents/skills/rhoai-workbenches-custom-images/SKILL.md` | Workbench context for connection consumption |

## Source Boundaries

- Product authority: the official Red Hat OpenShift AI 3.4 Managing resources
  chapter above.
- This chapter defines dashboard management of connection type templates.
- It does not define the storage format, CRD schema, or GitOps representation
  for connection types.
- It does not define how real connection secrets are created, stored, mounted,
  or consumed by each component.
- Verification: dashboard table, form preview, enabled-state behavior, and
  user selection checks.

## Unresolved Or Environment-Specific Items

- GitOps representation for connection type templates.
  Verification: use official docs or installed schema before automating the
  setting.
- Demo standard connection types.
  Verification: define when active GitOps and step workflows identify required
  object storage, model registry, URI repository, or external provider
  patterns.
- Secret creation and lifecycle for user connections.
  Verification: handle in the component skill that consumes the connection.
