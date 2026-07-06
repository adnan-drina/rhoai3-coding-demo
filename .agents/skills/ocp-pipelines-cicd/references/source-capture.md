# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product family | Red Hat OpenShift Pipelines |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Documentation category | Creating CI/CD pipelines |
| Official guide | Creating CI/CD pipelines |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.22/html-single/creating_cicd_pipelines/index |
| Multi-page URL | https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.22/html/creating_cicd_pipelines/index |
| Capture date | 2026-07-06 |

## Captured Sections

From Creating CI/CD pipelines:

- Chapter 1: Creating CI/CD solutions for applications using OpenShift Pipelines
  - 1.1 Prerequisites
  - 1.2 Creating a project and checking your pipeline service account
  - 1.3 Creating pipeline tasks
  - 1.4 Assembling a pipeline
  - 1.5 Mirroring images to run pipelines in a restricted environment
  - 1.6 Running a pipeline
  - 1.7 Adding triggers to a pipeline
  - 1.8 Configuring event listeners to serve many namespaces
  - 1.9 Creating webhooks
  - 1.10 Triggering a pipeline run
  - 1.11 Enabling monitoring of event listeners for Triggers for user-defined projects
  - 1.12 Configuring pull request capabilities in GitHub Interceptor
    - 1.12.1 Filtering pull requests using GitHub Interceptor
    - 1.12.2 Validating pull requests using GitHub Interceptors
  - 1.13 Additional resources
- Chapter 2: Working with Red Hat OpenShift Pipelines in the web console
  - 2.1 Working with Red Hat OpenShift Pipelines in the Developer perspective
    - 2.1.1 Constructing pipelines using the Pipeline builder
    - 2.1.2 Creating OpenShift Pipelines along with applications
    - 2.1.3 Adding a GitHub repository containing pipelines
    - 2.1.4 Interacting with pipelines using the Developer perspective
    - 2.1.5 Starting pipelines from Pipelines view
    - 2.1.6 Starting pipelines from Topology view
    - 2.1.7 Interacting with pipelines from Topology view
    - 2.1.8 Editing pipelines
    - 2.1.9 Deleting pipelines
  - 2.2 Additional resources
  - 2.3 Creating pipeline templates in the Administrator perspective
  - 2.4 Pipeline execution statistics in the web console
    - 2.4.1 Enabling the OpenShift Pipelines console plugin
    - 2.4.2 Viewing the statistics for all pipelines together
    - 2.4.3 Viewing the statistics for a specific pipeline
- Chapter 3: Specifying remote pipelines, tasks, and step actions using resolvers
  - 3.1 Specifying a remote pipeline, task, or step action from a Tekton catalog
    - 3.1.1 Configuring the hub resolver
    - 3.1.2 Specifying a remote pipeline, task, or step action using the hub resolver
  - 3.2 Specifying a remote pipeline, task, or step action from a Tekton bundle
    - 3.2.1 Configuring the bundles resolver
    - 3.2.2 Specifying a remote pipeline, task, or step action using the bundles resolver
  - 3.3 Specifying a remote pipeline, task, or step action with anonymous Git cloning
    - 3.3.1 Configuring the Git resolver for anonymous Git cloning
    - 3.3.2 Specifying a remote pipeline, task, or step action by using the Git resolver for anonymous cloning
  - 3.4 Specifying a remote pipeline, task, or step action with an authenticated Git API
    - 3.4.1 Configuring the Git resolver for an authenticated API
    - 3.4.2 Configuring many Git providers
    - 3.4.3 Specifying a remote pipeline, task, or step action using the Git resolver with the authenticated SCM API
    - 3.4.4 Specifying many Git providers
    - 3.4.5 Overriding the Git resolver configuration
  - 3.5 Specifying a remote pipeline, task, or step action by using the HTTP resolver
    - 3.5.1 Configuring the HTTP resolver
    - 3.5.2 Specifying a remote pipeline, task, or step action with the HTTP Resolver
  - 3.6 Specifying a remote pipeline, task, or step action from the same cluster
    - 3.6.1 Configuring the cluster resolver
    - 3.6.2 Specifying a remote pipeline, task, or step action using the cluster resolver

## Source Boundaries

This skill covers the "Creating CI/CD pipelines" guide only. It provides
practical guidance for building and deploying applications with pipelines,
using resolvers, creating pipeline templates, and working with pipelines
in the web console.

It does not cover:

- Pipeline concepts and architecture (use `ocp-pipelines-about`)
- Installation and configuration (use `ocp-pipelines-install-config`)
- Pipelines as Code (separate guide, use `ocp-pipelines-as-code`)
- Pipeline security (separate guide, use `ocp-pipelines-security`)
- Observability and Tekton Results (separate guide)
- Performance tuning beyond basic configuration

## API Versions Documented

| Resource | API Version |
|----------|-------------|
| Task | `tekton.dev/v1` |
| TaskRun | `tekton.dev/v1` |
| Pipeline | `tekton.dev/v1` |
| PipelineRun | `tekton.dev/v1` |
| StepAction | `tekton.dev/v1` |
| TriggerBinding | `triggers.tekton.dev/v1` |
| TriggerTemplate | `triggers.tekton.dev/v1` |
| Trigger | `triggers.tekton.dev/v1` |
| EventListener | `triggers.tekton.dev/v1` |
| ServiceMonitor | `monitoring.coreos.com/v1` |
| TektonConfig | `operator.tekton.dev/v1alpha1` |

## Related Official Sources To Add Later

- Red Hat OpenShift Pipelines 1.22 Pipelines as Code documentation
- Red Hat OpenShift Pipelines 1.22 Security documentation
- Red Hat OpenShift Pipelines 1.22 Observability documentation
- Red Hat OpenShift Pipelines 1.22 Performance and resource management
