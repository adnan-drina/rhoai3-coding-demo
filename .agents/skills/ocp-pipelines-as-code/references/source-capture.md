# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product family | Red Hat OpenShift Pipelines |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Documentation category | Pipelines as Code |
| Official guide | Pipelines as Code |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.22/html-single/pipelines_as_code/index |
| Multi-page URL | https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.22/html/pipelines_as_code/index |
| Capture date | 2026-07-06 |

## Captured Sections

From Pipelines as Code guide:

- Chapter 1: About Pipelines as Code
  - Key features (GitHub Checks API, ACL, tkn pac CLI, multi-provider support)
  - Pipelines as Code concepts (Repository CR, .tekton directory, resolver)
- Chapter 2: Installing and configuring Pipelines as Code
  - Installing PAC on OpenShift (TektonConfig enable/disable)
  - Installing PAC CLI (tkn pac and opc)
  - Customizing PAC configuration (TektonConfig settings)
  - Configuring additional PAC controllers for multiple GitHub Apps
- Chapter 3: Using PAC with Git repository hosting service providers
  - GitHub App integration (CLI, web console, manual setup)
  - Scoping GitHub token to additional repositories
  - GitHub Webhook integration
  - GitLab integration
  - Bitbucket Cloud integration
  - Bitbucket Data Center integration
  - Custom certificates for PAC
  - Private repository support
- Chapter 4: Using the Repository custom resource
  - Creating Repository CR
  - Global Repository CR (Tech Preview)
  - Setting concurrency limits
  - Changing source branch for pipeline definition (pipelinerun_provenance)
  - Custom parameter expansion (params, secret_ref, CEL filter)
- Chapter 5: Creating pipeline runs in Pipelines as Code
  - Creating pipeline runs (.tekton directory, annotations)
  - Dynamic variables (commit/URL info, GitHub App token)
  - Resolver annotations (remote tasks, remote pipelines, overriding tasks)
  - Annotations for matching events (pull_request, push, comment, CEL)
  - Annotations for filtering events (path-changed, path-changed-ignore, label)
  - Annotations for cancel-in-progress
- Chapter 6: Managing pipeline runs
  - Verifying pipeline runs (tkn pac resolve)
  - Running pipeline runs (execution, ACL, /ok-to-test)
  - Triggering PipelineRun on Git tags
  - Restarting or canceling (/test, /retest, /cancel)
  - Monitoring pipeline run status (Checks tab, log snippets, annotations)
  - Cleaning up pipeline runs (max-keep-runs)
  - Using incoming webhooks
- Chapter 7: Pipelines as Code command reference
  - tkn pac CLI commands (bootstrap, repository, generate, resolve, cel)
  - Configuring PAC logging (pac-config-logging configmap)
  - Splitting PAC logs by namespace

## Source Boundaries

This skill covers the "Pipelines as Code" guide only. It provides configuration,
usage, and administration of the Pipelines as Code subsystem. It does not cover:

- Core Tekton concepts and CRDs (use ocp-pipelines-about)
- Installation and configuration of OpenShift Pipelines operator (use ocp-pipelines-install-config)
- Creating CI/CD pipelines without PAC (use ocp-pipelines-cicd)
- Pipeline security (use ocp-pipelines-security)
- Pipeline observability beyond PAC-specific logging (use ocp-pipelines-observability)

## API Versions Documented

| Resource | API Version |
|----------|-------------|
| Repository | `pipelinesascode.tekton.dev/v1alpha1` |
| TektonConfig | `operator.tekton.dev/v1alpha1` |
| PipelineRun (in .tekton) | `tekton.dev/v1` |

## Technology Preview Features

The following features are marked as Technology Preview in this guide:

- Global Repository CR (pipelines-as-code in openshift-pipelines namespace)
- Matching comment events to pipeline runs (`on-comment` annotation)
- Matching pull request labels (`on-label` annotation)
- Automatic cancellation-in-progress (`cancel-in-progress` annotation)
- Using header/body payload fields in CEL expressions
- Starting pipeline runs via comment that don't match an event
- Error detection annotations from container logs
- `tkn pac cel` command

## Related Official Sources To Add Later

- Installing and configuring OpenShift Pipelines
- Creating CI/CD solutions for applications using OpenShift Pipelines
- OpenShift Pipelines security documentation
- OpenShift Pipelines observability documentation
