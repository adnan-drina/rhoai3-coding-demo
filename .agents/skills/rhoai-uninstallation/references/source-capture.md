# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product baseline | `docs/PLATFORM_BASELINE.md` |
| Chapter title | Uninstalling Red Hat OpenShift AI Self-Managed |
| Chapter URL | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/installing_and_uninstalling_openshift_ai_self-managed/uninstalling-openshift-ai-self-managed_uninstalling-openshift-ai-self-managed |
| Documentation category | Install |
| Retrieved date | 2026-06-09 |
| Sections used | 11.1 Understanding the uninstallation process; 11.2 Uninstalling OpenShift AI Self-Managed by using the CLI |

## Related Official Sources

| Source | Role |
|--------|------|
| https://olm.operatorframework.io/docs/tasks/uninstall-operator/ | OLM uninstall behavior referenced by Red Hat |

## Supporting Project Sources

| Source | Role |
|--------|------|
| `docs/PLATFORM_BASELINE.md` | Active RHOAI/OCP baseline and source hierarchy |
| `AGENTS.md` | OpenShift safety guard and GitOps operating constraints |
| `.agents/skills/env-manage-resources/SKILL.md` | Non-destructive shutdown and GPU cost-management path |
| `.agents/skills/env-troubleshoot/SKILL.md` | Live cluster diagnosis when uninstall stalls or leaves resources |
| `.agents/skills/rhoai-installation-troubleshooting/SKILL.md` | Reinstall failure context after incomplete uninstall |

## Source Boundaries

- Product authority: official Red Hat documentation above.
- GitOps sequencing is project policy, not a Red Hat product requirement.
- Backup strategy for PVC data must follow environment and organization policy.
- Do not treat uninstall as automatic cleanup of user-created projects, CRs, or
  CRDs. Red Hat explicitly retains user-created resources.
- Do not commit raw backups, kubeconfigs, tokens, or sensitive uninstall logs.
