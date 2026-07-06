# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product family | Red Hat OpenShift Pipelines |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.22/html-single/installing_and_configuring/index |
| Multi-page URL | https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.22/html/installing_and_configuring/index |
| Documentation category | Installing and configuring |
| Official guide | Installing and configuring |
| Capture date | 2026-07-06 |

## Captured Sections

From Installing and configuring:

- Chapter 1: Installing OpenShift Pipelines
  - 1.1 Installing the Red Hat OpenShift Pipelines Operator in web console
  - 1.2 Installing the OpenShift Pipelines Operator by using the CLI
  - 1.3 Red Hat OpenShift Pipelines Operator in a restricted environment
  - 1.4 Additional resources
- Chapter 2: Uninstalling OpenShift Pipelines
  - 2.1 Deleting the OpenShift Pipelines custom resources
  - 2.2 Uninstalling the Red Hat OpenShift Pipelines Operator
  - 2.3 Deleting the custom resource definitions of the operator.tekton.dev group
- Chapter 3: Customizing configurations in the TektonConfig custom resource
  - 3.1 Prerequisites
  - 3.2 Performance tuning using the TektonConfig custom resource
  - 3.3 Configuring the Red Hat OpenShift Pipelines control plane
    - 3.3.1 Modifiable fields with default values
    - 3.3.2 Optional configuration fields
  - 3.4 Changing the default service account for OpenShift Pipelines
  - 3.5 Setting labels and annotations for the OpenShift Pipelines installation
    namespace
  - 3.6 Setting the resync period for the pipelines controller
  - 3.7 Disabling the service monitor
  - 3.8 Configuring pipeline resolvers
  - 3.9 Disabling resolver tasks and pipeline templates
  - 3.10 Disabling the installation of Tekton Triggers
  - 3.11 Disabling the integration of Tekton Hub
  - 3.12 Migrating from Tekton Hub to Artifact Hub
    - 3.12.1 Assess migration impact
    - 3.12.2 Migrating to Artifact Hub
    - 3.12.3 Configuring a private Artifact Hub instance
  - 3.13 Disabling the automatic creation of RBAC resources
  - 3.14 Disabling inline specification of pipelines and tasks
  - 3.15 Configuration of RBAC and Trusted CA flags
  - 3.16 Automatic pruning of task runs and pipeline runs
    - 3.16.1 Configuring the pruner
    - 3.16.2 Annotations for automatically pruning task runs and pipeline runs
  - 3.17 Enabling the event-driven pruner
    - 3.17.1 Configuration of the event-driven pruner
    - 3.17.2 Observability metrics of the event-driven pruner
  - 3.18 Setting additional options for webhooks

## Source Boundaries

This skill captures the Operator installation lifecycle, uninstallation
procedure, and TektonConfig CR customization surface from the official
installing and configuring guide.

It does not capture:

- Pipelines conceptual overview and architecture (separate guide)
- Pipeline, Task, PipelineRun, TaskRun authoring (separate guide)
- Pipelines as Code configuration (separate guide)
- Tekton Chains supply chain security (separate guide)
- Tekton Results observability (separate guide)
- Tekton Hub deep usage (deprecated, migration documented here)
- Performance tuning beyond TektonConfig fields (separate guide)

## Related Official Sources To Add Later

- Red Hat OpenShift Pipelines 1.22 About documentation
- Red Hat OpenShift Pipelines 1.22 Creating CI/CD solutions documentation
- Red Hat OpenShift Pipelines 1.22 Pipelines as Code documentation
- Red Hat OpenShift Pipelines 1.22 Securing pipelines documentation
- Red Hat OpenShift Pipelines 1.22 Performance and resource management
  documentation
