# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product baseline | `docs/PLATFORM_BASELINE.md` |
| Chapter title | Installing the distributed workloads components |
| Chapter URL | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/installing_and_uninstalling_openshift_ai_self-managed/installing-the-distributed-workloads-components_install |
| Documentation category | Install |
| Retrieved date | 2026-06-09 |
| Sections used | Chapter 5, prerequisites, component state matrix, verification, next step |

## Supporting Project Sources

| Source | Role |
|--------|------|
| `docs/PLATFORM_BASELINE.md` | Active RHOAI/OCP baseline and source hierarchy |
| `.agents/skills/rhoai-self-managed-installation/SKILL.md` | RHOAI install prerequisite and DataScienceCluster context |
| `.agents/skills/rhoai-kfp-pipeline-authoring/SKILL.md` | Pipeline authoring patterns after distributed workload components are installed |
| `AGENTS.md` | OpenShift safety guard and GitOps operating constraints |

## Source Boundaries

- Product installation truth: official Red Hat documentation above.
- Queue, ClusterQueue, LocalQueue, and workload management design: official
  managing distributed workloads documentation, not this install chapter.
- GitOps adaptation: project policy, not a Red Hat product requirement.
- Verification: readonly cluster commands in `validation-checklist.md`.
- Not authoritative: legacy backup manifests unless tied back to official docs.
