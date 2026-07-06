# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product family | Red Hat OpenShift Pipelines |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Documentation category | About |
| Official guide | About OpenShift Pipelines |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.22/html-single/about_openshift_pipelines/index |
| Multi-page URL | https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.22/html/about_openshift_pipelines/index |
| Capture date | 2026-07-06 |

## Captured Sections

From About OpenShift Pipelines:

- Chapter 1: About Red Hat OpenShift Pipelines (product overview, release cadence note)
- Chapter 2: Understanding OpenShift Pipelines
  - Key features
  - Tasks (steps, pods, containers)
  - When expressions (input, operator, values)
  - Finally tasks (parallel execution after pipeline tasks)
  - TaskRun (instantiation, automatic creation by PipelineRun)
  - Pipelines (task ordering, runAfter, workspaces, params)
  - PipelineRun (binding, status tracking, volumeClaimTemplate)
  - Pod templates (PipelineRun and TaskRun, securityContext)
  - Workspaces (declaration, backing storage, sharing)
  - StepActions (reusable step definitions, resolvers, env-based params)
  - Triggers (TriggerBinding, TriggerTemplate, Trigger, EventListener, interceptors)

## Source Boundaries

This skill covers the "About OpenShift Pipelines" guide only. It provides
conceptual understanding of Tekton CRDs, pipeline architecture, and trigger
components. It does not cover:

- Installation and configuration (separate guide)
- Creating CI/CD solutions with pipelines (separate guide)
- Pipelines as Code (separate guide)
- Security (separate guide)
- Observability (separate guide)
- Resolver configuration details beyond basic references

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

## Related Official Sources To Add Later

- Installing and configuring OpenShift Pipelines
- Creating CI/CD solutions for applications using OpenShift Pipelines
- Pipelines as Code documentation
- OpenShift Pipelines security documentation
- OpenShift Pipelines observability documentation
