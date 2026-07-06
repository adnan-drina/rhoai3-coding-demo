# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product baseline | `docs/PLATFORM_BASELINE.md` |
| Chapter title | Chapter 13. Viewing logs and audit records |
| Chapter URL | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_openshift_ai/viewing-logs-and-audit-records_managing-rhoai |
| Documentation category | Administer |
| Retrieved date | 2026-06-10 |
| Sections used | 13.1 Configuring the OpenShift AI Operator logger; 13.1.1 Viewing the OpenShift AI Operator logs; 13.2 Viewing audit records |

## Supporting Project Sources

| Source | Role |
|--------|------|
| `docs/PLATFORM_BASELINE.md` | Active RHOAI/OCP baseline and source hierarchy |
| `AGENTS.md` | OpenShift safety guard and GitOps operating constraints |
| `.agents/skills/rhoai-self-managed-installation/SKILL.md` | DSCI and DSC installation context |
| `.agents/skills/env-troubleshoot/SKILL.md` | Live diagnostic workflow when a specific environment issue is reported |
| OpenShift documentation linked from the official chapter | Supplemental source for audit log policy, audit log viewing, log retention, and ROSA logging behavior |

## Source Boundaries

- Product authority: official Red Hat OpenShift AI 3.4 Administer chapter
  above.
- GitOps adaptation and temporary-debug policy: project policy, not a Red Hat
  product requirement.
- General OpenShift audit policy, log forwarding, and retention are governed by
  OpenShift documentation and environment policy.
- Do not commit raw audit logs unless sanitized and intentionally approved.
