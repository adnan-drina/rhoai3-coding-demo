# Source Capture

## Official Product Sources

| Field | Value |
|-------|-------|
| Product baseline | `docs/PLATFORM_BASELINE.md` |
| Primary chapter title | Enabling accelerators |
| Primary chapter URL | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/installing_and_uninstalling_openshift_ai_self-managed/enabling-accelerators_install |
| NVIDIA chapter title | Enabling NVIDIA GPUs |
| NVIDIA chapter URL | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/working_with_accelerators/enabling-nvidia-gpus_accelerators |
| Hardware profile chapter title | Working with hardware profiles |
| Hardware profile chapter URL | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/working_with_accelerators/working-with-hardware-profiles_accelerators |
| Documentation categories | Install; Administer: Working with accelerators |
| Retrieved date | 2026-06-09 |
| Sections used | Accelerator prerequisites and verification; NVIDIA GPU enablement; hardware profile overview, creation, update, delete, and recommended accelerator sections |

## Supporting Project Sources

| Source | Role |
|--------|------|
| `docs/PLATFORM_BASELINE.md` | Active RHOAI/OCP baseline and source hierarchy |
| `AGENTS.md` | NVIDIA-only demo hardware intent and OpenShift safety guard |
| `.agents/skills/rhoai-self-managed-installation/SKILL.md` | RHOAI installation prerequisite |
| `.agents/skills/rhoai-distributed-workloads/SKILL.md` | Distributed workload dependency when GPU workloads use Kueue, Ray, or Training Operator |
| `.agents/skills/env-manage-resources/SKILL.md` | Live environment GPU node scale-up and scale-down workflows |

## Supporting GitOps Pattern Sources

| Source | Role |
|--------|------|
| https://github.com/redhat-cop/gitops-catalog/tree/main/gpu-operator-certified | Red Hat CoP GPU Operator catalog layout: operator base, channel overlays, instance base, components, overlays |
| https://github.com/redhat-cop/gitops-catalog/tree/main/gpu-operator-certified/instance/components/aws-gpu-machineset | AWS GPU MachineSet component pattern tested on demo.redhat.com |
| https://raw.githubusercontent.com/redhat-cop/gitops-catalog/main/gpu-operator-certified/instance/components/aws-gpu-machineset/job.sh | Transformation logic for cloning an AWS worker MachineSet and adding GPU labels, taints, instance type, and MachineAutoscaler |
| https://raw.githubusercontent.com/redhat-cop/gitops-catalog/main/gpu-operator-certified/instance/base/cluster-policy.yaml | Example NVIDIA ClusterPolicy handoff, including daemonset toleration for GPU-only taint |

## Source Boundaries

- Product authority: official Red Hat documentation above.
- NVIDIA-specific OpenShift operator implementation details that Red Hat docs
  delegate to NVIDIA documentation must be checked against the active Operator
  CSV, installed CRDs, and Red Hat-supported OpenShift baseline before use.
- Hardware profile dashboard behavior is official; exact YAML schema must be
  verified against the active `HardwareProfile` CRD before GitOps promotion.
- Demo hardware profile names, AWS instance types, node selectors, and taints
  are project policy, not Red Hat product requirements.
- Red Hat CoP GitOps Catalog sources are implementation patterns only. Curate
  them locally and verify every channel, CR field, RBAC rule, and MachineSet
  provider field against official docs and the live cluster.
- Legacy backup manifests are implementation references only; they are not
  authoritative unless revalidated against official docs and active CRDs.
