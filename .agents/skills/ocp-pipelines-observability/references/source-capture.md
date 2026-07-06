# Source Capture

## Official Source

| Field | Value |
|-------|-------|
| Product family | Red Hat OpenShift Pipelines |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Documentation category | Observability |
| Official guide | Observability in OpenShift Pipelines |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.22/html-single/observability_in_openshift_pipelines/index |
| Multi-page URL | https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.22/html/observability_in_openshift_pipelines/index |
| Capture date | 2026-07-06 |

## Captured Sections

- Chapter 1. Using Tekton Results for OpenShift Pipelines observability
  - 1.1. Tekton Results concepts
  - 1.2. Configuring Tekton Results
    - 1.2.1. Configuring LokiStack forwarding for logging information
    - 1.2.2. Configuring an external database server
    - 1.2.3. Configuring the retention policy for Tekton Results
    - 1.2.4. Observability metrics for Tekton Results
  - 1.3. Querying Tekton Results for results and records
    - 1.3.1. Preparing the opc utility environment for querying Tekton Results
    - 1.3.2. Querying for results and records by name
    - 1.3.3. Searching for results
    - 1.3.4. Searching for records
    - 1.3.5. Reference information for searching results
    - 1.3.6. Reference information for searching records
  - 1.4. Querying results and logs by the names of pipeline runs and task runs
    (Technology Preview)
    - 1.4.1. Configuring the opc utility for querying results by pipeline run
      and task run names
    - 1.4.2. Viewing a list of pipeline run names and identifiers
    - 1.4.3. Viewing a list of task run names and identifiers
    - 1.4.4. Viewing result information for a pipeline run
    - 1.4.5. Viewing result information for a task run
    - 1.4.6. Short names for command-line arguments
- Chapter 2. Understanding the Tekton Results retention policy
  - 2.1. Fine-grained retention policies

## Source Boundaries

This skill covers OpenShift Pipelines 1.22 observability features, which are
centered on Tekton Results for archiving, querying, and retaining pipeline run
and task run data, logs, and metrics.

This skill does NOT cover:

- OpenShift Pipelines installation, operator configuration, or TektonConfig
  fields beyond `spec.result`
- Tekton CRD authoring (Pipeline, Task, PipelineRun, TaskRun)
- Pipelines as Code setup, Repository CR configuration, or webhook setup
- General CI/CD pipeline design patterns
- OpenShift Pipelines versions other than 1.22.x
- OCP platform monitoring, logging, or Cluster Observability Operator (use
  `ocp-observability`)
- Tekton Chains, supply chain security, or signing
- OpenShift Builds, OpenShift GitOps, or Jenkins

## Related Official Sources

- OpenShift Pipelines documentation: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.22
- OpenShift Pipelines release notes: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.22/html-single/release_notes/index
- OpenShift Logging documentation: https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/logging/index
- LokiStack documentation: referenced from OpenShift Logging
- Installing tkn: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.22/html/pipelines_cli_tkn_reference/installing-tkn
