# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product baseline | `docs/PLATFORM_BASELINE.md` |
| Chapter title | Installing and deploying OpenShift AI |
| Chapter URL | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/installing_and_uninstalling_openshift_ai_self-managed/installing-and-deploying-openshift-ai_install |
| Documentation category | Install |
| Retrieved date | 2026-06-09 |
| Sections used | Chapter 3, including requirements, custom namespaces, CLI Operator installation, CLI component installation, component status, and viewing installed components |

## Supporting Project Sources

| Source | Role |
|--------|------|
| `docs/PLATFORM_BASELINE.md` | Active RHOAI/OCP baseline and source hierarchy |
| `.agents/skills/rhoai-update-channels/SKILL.md` | Channel selection and latest-version policy |
| `.agents/skills/rhoai-architecture-overview/SKILL.md` | Default namespace roles and product/application boundary |
| `AGENTS.md` | OpenShift safety guard and GitOps operating constraints |

## Source Boundaries

- Product installation truth: official Red Hat documentation above.
- Channel policy: official update-channel docs plus `rhoai-update-channels`.
- GitOps adaptation: project policy, not Red Hat product requirement.
- Verification: readonly cluster commands in `validation-checklist.md`.
- Not authoritative: legacy backup manifests unless tied back to official docs.
