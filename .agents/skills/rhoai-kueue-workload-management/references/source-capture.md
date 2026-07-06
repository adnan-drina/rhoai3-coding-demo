# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product baseline | `docs/PLATFORM_BASELINE.md` |
| Document title | Administer OpenShift AI platform access, apps, and operations |
| Chapter title | Managing workloads with Kueue |
| Chapter URL | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_openshift_ai/managing-workloads-with-kueue |
| Documentation category | Administer |
| Retrieved date | 2026-06-10 |
| Sections used | 8.1 through 8.4: overview, management states, queue enforcement, restrictions, workflow, configuration, dashboard enablement, troubleshooting, migration |

## Related Official Sources

| Source | Role |
|--------|------|
| https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/ai_workloads/red-hat-build-of-kueue | Red Hat build of Kueue Operator, quotas, queues, and workload objects |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/installing_and_uninstalling_openshift_ai_self-managed/installing-the-distributed-workloads-components_install | Distributed workload component installation prerequisites |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/working_with_accelerators/working-with-hardware-profiles_accelerators | Hardware profile and local queue integration |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/managing_openshift_ai/index | Same Red Hat guide, Chapter 9 distributed workload quota examples and troubleshooting context |

## Supporting Project Sources

| Source | Role |
|--------|------|
| `docs/PLATFORM_BASELINE.md` | Active RHOAI/OCP baseline and source hierarchy |
| `AGENTS.md` | OpenShift safety guard and GitOps operating constraints |
| `.agents/skills/rhoai-distributed-workloads/SKILL.md` | Distributed workloads installation prerequisites |
| `.agents/skills/rhoai-nvidia-gpu-accelerators/SKILL.md` | NVIDIA GPU readiness context |
| `.agents/skills/rhoai-hardware-profiles/SKILL.md` | Hardware profile lifecycle and Kueue local queue handoff |
| `.agents/skills/project-gitops-authoring/SKILL.md` | GitOps authoring and ArgoCD review |
| `.agents/skills/env-troubleshoot/SKILL.md` | Live troubleshooting boundary |

## Source Boundaries

- Product authority: official Red Hat documentation above.
- GitOps adaptation: project policy, not a Red Hat product requirement.
- This skill covers RHOAI integration with Kueue and documented troubleshooting
  signals. Full quota design for `ResourceFlavor`, `ClusterQueue`, and
  `LocalQueue` belongs to the Red Hat build of Kueue documentation and future
  demo-specific GitOps design.
- Upstream Kueue documentation can be used only where the official RHOAI chapter
  points to it, such as `waitForPodsReady`; label it as supplemental and verify
  the active Red Hat build of Kueue schema.
- Do not run migration, namespace labeling, or Deployment changes without the
  OpenShift safety guard in `AGENTS.md`.
