---
name: ocp-pipelines-about
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: ocp_pipelines
  docs-version: "1.24"
  skill-group: "OpenShift Platform"
description: >
  Use when explaining OpenShift Pipelines concepts (Task, TaskRun, Pipeline,
  PipelineRun, Workspace, pod template, StepAction, Triggers) and mapping them
  to this demo's objects, or when collecting must-gather data for Pipelines
  support. Do NOT use for installation (use ocp-pipelines-install-config),
  pipeline authoring (use ocp-pipelines-cicd), Pipelines as Code (use
  ocp-pipelines-as-code), security (use ocp-pipelines-security), or
  observability (use ocp-pipelines-observability).
---

# OpenShift Pipelines concepts

Thin skill: where each Tekton concept appears in this repo; definitions in
the linked OpenShift Pipelines 1.24 sections.

## When to use

- Explaining the Stage 070 delivery path to a reader new to Tekton.
- Gathering diagnostic data for a Red Hat support case.

## Repo decisions (concept → repo object)

| Concept | Repo object | Official section |
|---|---|---|
| Task | `gitlab-clone`, `maven-build`, `sonar-scan`, `build-internal-image`, `promote-gitlab-runtime`, `resolve-image-registry` in `gitops/stages/070-advanced-app-platform/070-pipelines/project-pipeline/` | [Tasks][tasks] |
| Pipeline / PipelineRun | `app-push` per `<project>-dev`; runs named `gitlab-<project-id>-<sha>` by `070-pipelines/gitlab/reconcile.py` | [Pipelines][pipelines], [Pipeline run][pipelinerun] |
| Workspace | `source` (per-run claim), `maven-cache` (PVC), `basic-auth` (Secret) | [Workspaces][workspaces] |
| Pod template | per-task `podTemplate` (`hostUsers: false`) for the image build | [Pod templates][podtemplate] |
| Triggers | per-project `EventListener` `gitlab` + `TriggerTemplate` `gitlab-push` | [Triggers][triggers] |
| When expressions, finally, StepActions | not used | [When][when], [Finally][finally], [Step actions][stepactions] |

## Procedure

Read-only, after the OpenShift safety guard in `AGENTS.md`:

```bash
oc api-resources --api-group=tekton.dev
oc api-resources --api-group=triggers.tekton.dev
oc get pipeline,task -n coolstore-dev
```

For a support case use the documented must-gather ([must-gather][mustgather]).

## Pitfalls

- RHOAI "AI pipelines" are Kubeflow Pipelines, a different product; use
  the `rhoai-ai-pipelines` skill for them.
- ClusterTask is gone; the repo uses namespaced Tasks only.

## Official documentation (OpenShift Pipelines 1.24)

| Topic | Section |
|---|---|
| Overview | [About OpenShift Pipelines][about], [Key features][features], [Concepts][concepts] |
| Diagnostics | [Must-gather][mustgather], [Collecting debugging data][debug] |

## Related skills

`ocp-pipelines-cicd`, `ocp-pipelines-install-config`, `rhoai-ai-pipelines`.

[about]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/about_openshift_pipelines/index#about-pipelines
[features]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/about_openshift_pipelines/index#op-key-features_understanding-openshift-pipelines
[concepts]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/about_openshift_pipelines/index#op-pipelines-concepts_understanding-openshift-pipelines
[tasks]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/about_openshift_pipelines/index#about-tasks_understanding-openshift-pipelines
[when]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/about_openshift_pipelines/index#about-whenexpression_understanding-openshift-pipelines
[finally]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/about_openshift_pipelines/index#about-finally_tasks_understanding-openshift-pipelines
[pipelines]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/about_openshift_pipelines/index#about-pipelines_understanding-openshift-pipelines
[pipelinerun]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/about_openshift_pipelines/index#about-pipelinerun_understanding-openshift-pipelines
[podtemplate]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/about_openshift_pipelines/index#about-podtemplate_understanding-openshift-pipelines
[workspaces]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/about_openshift_pipelines/index#about-workspaces_understanding-openshift-pipelines
[stepactions]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/about_openshift_pipelines/index#about-stepactions_understanding-openshift-pipelines
[triggers]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/about_openshift_pipelines/index#about-triggers_understanding-openshift-pipelines
[mustgather]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/about_openshift_pipelines/index#op-about-must-gather_op-proc-gathering-diagnostic-information
[debug]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/about_openshift_pipelines/index#op-collecting-pipelines-debugging-data_op-proc-gathering-diagnostic-information
