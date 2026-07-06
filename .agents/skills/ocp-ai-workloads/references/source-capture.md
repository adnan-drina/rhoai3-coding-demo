# Source Capture

## Official Source

| Field | Value |
|-------|-------|
| Product family | Red Hat OpenShift Container Platform |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Documentation category | AI workloads |
| Official guide | AI workloads |
| Source URL | https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html-single/ai_workloads/index |
| Multi-page URL | https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/ai_workloads/index |
| Capture date | 2026-06-10 |

## Captured Sections

- Overview of AI workloads on OpenShift Container Platform
- Operators for running AI workloads
- Red Hat build of Kueue introduction, release notes, install, disconnected
  install, upgrade, RBAC, quotas, pending workload monitoring, cohorts, fair
  sharing, gang scheduling, running jobs with quota limits, and support data
  collection
- Leader Worker Set Operator overview, install, workload management, and
  uninstall
- JobSet Operator overview, install, workload management, and uninstall

## Source Boundaries

This skill captures OCP platform AI workload operators and APIs. It does not
define Red Hat OpenShift AI `DataScienceCluster` component enablement,
dashboard workflows, workbenches, RHOAI model serving, or RHOAI distributed
workload UX. Use the relevant `rhoai-*` skills for those layers.

This skill does not define GPU node provisioning, NFD hardware discovery,
NVIDIA GPU Operator, or RHOAI hardware profiles. Use `ocp-machine-management`,
`ocp-node-feature-discovery`, `ocp-nodes`, and
`rhoai-nvidia-gpu-accelerators` for those layers.

## Related Official Sources

- OCP Nodes: https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/nodes/index
- OCP Machine management: https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/machine_management/index
- OCP Specialized hardware and driver enablement: https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/specialized_hardware_and_driver_enablement/index
- RHOAI managing distributed workloads: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_openshift_ai/managing-distributed-workloads_managing-rhoai
- RHOAI working with distributed workloads: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/working_with_distributed_workloads
