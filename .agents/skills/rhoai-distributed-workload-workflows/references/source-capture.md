# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product baseline | `docs/PLATFORM_BASELINE.md` |
| Document title | Accelerate data processing and training with distributed workloads |
| Guide URL | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_distributed_workloads/index |
| Documentation category | Develop / Working with distributed workloads |
| Retrieved date | 2026-06-10 |
| Sections used | Preface; 1 Overview of distributed workloads; 1.1 Distributed workloads infrastructure; 1.2 Types of distributed workloads; 2 Preparing the distributed training environment; 2.1 Creating a workbench; 2.2 Using cluster server and token; 2.3 Managing custom training images; 3 RoCE networking for distributed LLM deployments; 4 Running Ray-based distributed workloads; 4.1 Jupyter notebooks; 4.2 AI pipelines; 4.3 disconnected environments; 5 Training Operator workloads; 5.1 PyTorchJob; 5.2 Training Operator SDK; 5.3 fine-tuning; 5.4 RDMA; 6 Kubeflow Trainer v2 workloads; 6.1 training runtimes; 6.2 TrainJob; 6.3 SDK; 6.4 fine-tuning; 6.5 examples; 7 checkpointing with PVC or S3; 8 monitoring distributed workloads; 9 user troubleshooting |

## Related Official Sources

| Source | Role |
|--------|------|
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/installing_and_uninstalling_openshift_ai_self-managed/installing-the-distributed-workloads-components_install | Distributed workload component installation |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_openshift_ai/managing-workloads-with-kueue | Kueue integration and queue enforcement |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_openshift_ai/managing-distributed-workloads_managing-rhoai | Administrator queue resources, quotas, RDMA, and troubleshooting |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/working_with_accelerators | Accelerator prerequisites and supported accelerator context |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/working_on_projects | Projects, workbenches, and project access context |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/working_with_ai_pipelines | AI pipeline launch-surface context |
| https://access.redhat.com/articles/rhoai-supported-configs-3.x | Supported configurations, images, packages, and accelerator context |

## Supporting Project Sources

| Source | Role |
|--------|------|
| `docs/PLATFORM_BASELINE.md` | Active RHOAI/OCP baseline and source hierarchy |
| `AGENTS.md` | OpenShift safety guard and GitOps operating constraints |
| `.agents/skills/rhoai-distributed-workloads/SKILL.md` | Distributed workload component installation boundary |
| `.agents/skills/rhoai-kueue-workload-management/SKILL.md` | Kueue integration and queue enforcement boundary |
| `.agents/skills/rhoai-distributed-workload-operations/SKILL.md` | Administrator quota/RDMA/troubleshooting boundary |
| `.agents/skills/rhoai-nvidia-gpu-accelerators/SKILL.md` | NVIDIA GPU prerequisite boundary |
| `.agents/skills/rhoai-kfp-pipeline-authoring/SKILL.md` | AI pipeline implementation boundary |

## Source Boundaries

- Product authority: the official Red Hat OpenShift AI 3.4 Working with
  distributed workloads guide above.
- The guide defines user workflows for running Ray, Training Operator, and
  Kubeflow Trainer v2 workloads from notebooks, CLI patterns, SDKs, pipelines,
  and dashboard monitoring surfaces.
- It does not replace distributed workload component installation, Kueue queue
  policy, quota resource management, GPU Operator installation, or complete
  pipeline implementation.
- Verification: workbench state, authentication source, selected training
  image, RayCluster/Workload status, PyTorchJob status, TrainJob status,
  checkpoint storage behavior, workload metrics, Kueue alerts, pod events, and
  pod logs.

## Unresolved Or Environment-Specific Items

- Active demo training/fine-tuning workload shape.
  Verification: choose whether the clean-slate implementation demonstrates Ray,
  Training Operator, Trainer v2, or a narrower subset.
- Active demo local queue names and quota limits.
  Verification: define in GitOps with `rhoai-distributed-workload-operations`.
- Active training image tags.
  Verification: confirm against the supported configurations article and the
  deployed OpenShift AI image streams before using them.
- Active checkpoint storage backend.
  Verification: choose PVC or S3-compatible storage and document capacity,
  cleanup, and ownership in `docs/OPERATIONS.md`.
- RoCE/RDMA support in the live AWS environment.
  Verification: use only after supported hardware, networking, and
  administrator configuration are explicitly implemented.
