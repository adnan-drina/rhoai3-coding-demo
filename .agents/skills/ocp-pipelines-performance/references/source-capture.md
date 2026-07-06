# Source Capture

## Official Source

| Field | Value |
|-------|-------|
| Product family | Red Hat OpenShift Pipelines |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Documentation category | Installing and configuring |
| Official guide | Managing performance and resource use |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.22/html-single/managing_performance_and_resource_use/index |
| Multi-page URL | https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.22/html/managing_performance_and_resource_use/index |
| Capture date | 2026-07-06 |

## Captured Sections

- Chapter 1. Managing OpenShift Pipelines performance
  - 1.1. Improving OpenShift Pipelines performance
  - 1.2. Additional resources
- Chapter 2. Reducing resource consumption of OpenShift Pipelines
  - 2.1. Understanding resource consumption in pipelines
  - 2.2. Mitigating extra resource consumption in pipelines
  - 2.3. Override step level compute resources in a PipelineRun
    - 2.3.1. Setting compute resources for a task step
  - 2.4. Additional resources
- Chapter 3. Setting compute resource quota for OpenShift Pipelines
  - 3.1. Alternative approaches for limiting compute resource consumption in OpenShift Pipelines
  - 3.2. Specifying pipelines resource quota using priority class
  - 3.3. Additional resources
- Chapter 4. Protecting Tekton workload pods from eviction during node drains
  - 4.1. Eviction protection for TaskRun pods
  - 4.2. Preventing eviction of TaskRun pods during node maintenance
- Chapter 5. Multicluster support for OpenShift Pipelines
  - 5.1. About multicluster support in OpenShift Pipelines
  - 5.2. Multicluster architecture
    - 5.2.1. Hub cluster
    - 5.2.2. Spoke clusters
    - 5.2.3. Kueue and MultiKueue
  - 5.3. Configuring the hub cluster for multicluster
  - 5.4. Configuring spoke clusters for multicluster
  - 5.5. Verifying multicluster setup
  - 5.6. Creating pipeline runs in a multicluster environment
  - 5.7. Known limitations for multicluster pipeline runs
  - 5.8. Kueue resources for multicluster configuration
  - 5.9. Additional resources

## Source Boundaries

This skill covers the OpenShift Pipelines 1.22 managing performance and
resource use guide. It documents performance tuning, resource consumption
models, resource quotas, pod eviction protection, and multicluster pipeline
support (Technology Preview).

This skill does NOT cover:

- OpenShift Pipelines installation, configuration, or operator management
- Tekton CRD authoring (Pipeline, Task, PipelineRun, TaskRun)
- Pipelines as Code setup, Repository CR configuration, or webhook setup
- General CI/CD pipeline design patterns
- OpenShift Pipelines release notes or version compatibility
- OpenShift Pipelines versions other than 1.22.x
- OpenShift Builds, OpenShift GitOps, or Jenkins

## Related Official Sources

- OpenShift Pipelines documentation: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.22
- Release notes: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.22/html/release_notes/index
- Performance tuning using the TektonConfig CR: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.22/html/installing_and_configuring/customizing-configurations-in-the-tektonconfig-cr
- Resource quotas per project (OCP): https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/building_applications/quotas-setting-per-project
- Restricting resource consumption using limit ranges (OCP): https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/building_applications/quotas-setting-across-multiple-projects
- Installing Red Hat build of Kueue: https://docs.redhat.com/en/documentation/red_hat_build_of_kueue/1.3
- Kueue MultiKueue upstream: https://kueue.sigs.k8s.io/docs/concepts/multikueue/
