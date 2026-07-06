# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product baseline | `docs/PLATFORM_BASELINE.md` |
| Chapter title | Troubleshooting common installation problems |
| Chapter URL | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/installing_and_uninstalling_openshift_ai_self-managed/troubleshooting-common-installation-problems_install |
| Documentation category | Install |
| Retrieved date | 2026-06-09 |
| Sections used | 10.1 through 10.8: Operator image retrieval, unsupported infrastructure, CR creation failures, dashboard access, reinstall failure, RBAC failure, and ODH parameter secret failure |

## Related Official Sources

| Source | Role |
|--------|------|
| https://access.redhat.com/solutions/7061604 | Red Hat OpenShift AI must-gather support evidence |
| https://access.redhat.com/articles/rhoai-supported-configs-3.x | Supported configurations check for unsupported infrastructure failures |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/installing_and_uninstalling_openshift_ai_self-managed/viewing-logs-and-audit-records_install | Operator logger and audit-record workflow |

## Supporting Project Sources

| Source | Role |
|--------|------|
| `docs/PLATFORM_BASELINE.md` | Active RHOAI/OCP baseline and source hierarchy |
| `AGENTS.md` | OpenShift safety guard and GitOps operating constraints |
| `.agents/skills/env-troubleshoot/SKILL.md` | Live cluster troubleshooting workflow |
| `.agents/skills/rhoai-self-managed-installation/SKILL.md` | Install resource and DSC/DSCI context |
| `.agents/skills/rhoai-logs-and-audit-records/SKILL.md` | Operator log verbosity, log streaming, and audit records |

## Source Boundaries

- Product authority: official Red Hat documentation above.
- Support escalation: follow Red Hat support guidance when the official chapter
  does not provide a local fix.
- GitOps adaptation: project policy, not a Red Hat product requirement.
- Do not treat old backup manifests as authoritative troubleshooting evidence.
- Do not commit raw must-gather archives, kubeconfigs, tokens, or unsanitized
  logs.
