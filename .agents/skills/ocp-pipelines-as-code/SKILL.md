---
name: ocp-pipelines-as-code
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: ocp_pipelines
  docs-version: "1.24"
  skill-group: "OpenShift Platform"
description: >
  Use when someone asks about Pipelines as Code (Repository CR, .tekton
  directory, GitHub App or GitLab webhook integration, tkn pac, PAC
  annotations) for OpenShift Pipelines 1.24. Pipelines as Code is not used in
  this repo; this stub records that and links the official sections. Do NOT
  use for the repo's Triggers-based delivery path (use ocp-pipelines-cicd) or
  operator settings (use ocp-pipelines-install-config).
---

# Pipelines as Code (not used in this repo)

Link-only stub. Product guidance lives in the linked OpenShift Pipelines 1.24
sections.

## When to use

- Evaluating Pipelines as Code as a replacement for the repo's per-project
  Triggers, or answering a PAC question.

## Not used in this repo

No `Repository` CR, `.tekton/` directory or PAC configuration exists in Git.
Builds start from plain Tekton Triggers: the enrollment reconciler
(`gitops/stages/070-advanced-app-platform/pipelines/gitlab/reconcile.py`)
renders a GitLab `EventListener` per enrolled project; the platform, not the
project repository, owns the pipeline definition. Adopting PAC would move the
pipeline into project repositories and needs a design change to that
boundary (see `gitops/stages/070-advanced-app-platform/pipelines/README.md`, "Why").

## Official documentation (OpenShift Pipelines 1.24)

| Topic | Section |
|---|---|
| Overview | [About Pipelines as Code][about] |
| Install and configure | [Install and configure][install], [Customize configuration][custom] |
| GitLab | [Use with GitLab][gitlab] |
| Repository CR | [Repository custom resource][repo] |
| PipelineRuns and annotations | [Creating pipeline runs][runs], [Resolver annotations][resolver] |
| CLI | [Command reference][cli] |

## Related skills

`ocp-pipelines-cicd`, `ocp-pipelines-install-config`, `ocp-pipelines-tekton-hub`.

[about]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/pipelines_as_code/index#about-pipelines-as-code
[install]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/pipelines_as_code/index#install-config-pipelines-as-code
[custom]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/pipelines_as_code/index#customizing-pipelines-as-code-configuration_install-config-pipelines-as-code
[gitlab]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/pipelines_as_code/index#using-pipelines-as-code-with-gitlab_using-pipelines-as-code-repos
[repo]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/pipelines_as_code/index#using-repository-crd
[runs]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/pipelines_as_code/index#creating-pipeline-runs-pac
[resolver]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/pipelines_as_code/index#pipelines-as-code-resolver-annotations_creating-pipeline-runs-pac
[cli]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/pipelines_as_code/index#pipelines-as-code-command-reference_pac-command-reference
