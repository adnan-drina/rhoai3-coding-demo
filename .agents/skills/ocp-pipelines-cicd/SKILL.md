---
name: ocp-pipelines-cicd
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: ocp_pipelines
  docs-version: "1.24"
  skill-group: "OpenShift Platform"
description: >
  Use when changing or debugging this demo's Tekton delivery path: the
  per-project app-push Pipeline and its Tasks (gitlab-clone, maven-build,
  sonar-scan, build-internal-image, promote-gitlab-runtime), the per-project
  GitLab EventListener, TriggerTemplate and webhook Route created by the
  enrollment reconciler, the provision-migration-run Pipeline in
  app-platform-build, and PipelineRun failures. Do NOT use for operator and
  TektonConfig settings (use ocp-pipelines-install-config), build SCCs and
  webhook security (use ocp-pipelines-security), Pipelines as Code (not used;
  see ocp-pipelines-as-code), or RHOAI data science pipelines (use
  rhoai-ai-pipelines).
---

# OpenShift Pipelines CI/CD in this repo

Thin skill: repo decisions and pitfalls here, product behavior in the linked
OpenShift Pipelines 1.24 sections. Detailed record:
`gitops/stages/070-advanced-app-platform/070-pipelines/README.md` ("project-pipeline/
and project-enrollment/" and "How").

## When to use

- A change touches `gitops/stages/070-advanced-app-platform/070-pipelines/project-pipeline/`,
  `.../project-enrollment/`, `.../gitlab/reconcile.py` or `.../build/*provision-migration-run*`.
- A pushed commit does not start a PipelineRun, or a PipelineRun fails.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Plain Triggers per project, not Pipelines as Code: reconciler renders `TriggerTemplate` `gitlab-push`, `EventListener` `gitlab` and Route `gitlab-webhook` (edge TLS to `el-gitlab`) | `070-pipelines/gitlab/reconcile.py` (`trigger_resources`) | [Adding triggers][triggers], [Creating webhooks][webhooks] |
| Event filter: `gitlab` interceptor (secret `gitlab-webhook`, `Push Hook`) then `cel` (project id, repo URL, `refs/heads/main`, 40-hex `checkout_sha`) | same | [Adding triggers][triggers]; CEL filtering example in [GitHub interceptor][gh-filter] |
| Deterministic PipelineRun name `gitlab-<project-id>-<sha>`: duplicate deliveries end in AlreadyExists | same (`pipeline_run`) | [Running a pipeline][run] |
| Tasks are local, namespaced Tasks rendered with the project; no ClusterTask, no hub/bundles/git resolvers | `070-pipelines/project-pipeline/task-*.yaml`, `pipeline.yaml` | [Resolvers][resolvers], [ClusterTask migration][clustertask] |
| Pipeline `app-push`: resolve registry → clone → Maven build → Sonar gate → internal-registry image → digest promotion into delivery Git | `070-pipelines/project-pipeline/pipeline.yaml` | [Assembling a pipeline][assemble] |
| Workspaces: per-run `volumeClaimTemplate` (`gp3-csi`, 2Gi), persistent `maven-cache` PVC, `basic-auth` Secret workspace | `070-pipelines/gitlab/reconcile.py`, `070-pipelines/project-pipeline/pvc-maven-cache.yaml` | [Workspaces][workspaces] |
| Stage 130 runs are created and retired by Pipeline `provision-migration-run` in `app-platform-build`, never by hand | `070-pipelines/build/pipeline-provision-migration-run.yaml`, `task-provision-migration-run.yaml` | [Pipelines concepts][concepts] |

## Procedure

1. Edit the templates in Git; the coordinator renders them per project from
   the pinned revision. Never edit a project namespace's Tasks live.
2. Static tests and live checks:

   ```bash
   ./stages/070-advanced-app-platform/validate.sh --static   # delivery-integration, internal-registry, provisioning tests
   ./stages/070-advanced-app-platform/validate.sh            # Coolstore pipeline installed, Webhook listener ready, ...
   ```

3. Read-only, after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get eventlistener,triggertemplate,route -n <project>-dev
   oc get pipelinerun -n <project>-dev --sort-by=.metadata.creationTimestamp
   oc get taskrun -n <project>-dev -l tekton.dev/pipelineRun=<run> \
     -o custom-columns=TASK:.metadata.labels.tekton\\.dev/pipelineTask,STATUS:.status.conditions[0].reason
   ```

4. Coolstore end-to-end order (namespace, enrollment, digest, delivery Git):
   `docs/OPERATIONS.md#stage-070--coolstore-dev-environment`.

## Pitfalls

- Repository creation by a template does not prove the webhook fired; check
  the EventListener and PipelineRun
  (`docs/TROUBLESHOOTING.md#pipelines-1226-template-publishes-but-provisioning-never-starts`).
- Enrollment stays pending until the coordinator validates the issue:
  `docs/TROUBLESHOOTING.md#stage-070-gitlab-project-enrollment-is-pending`.
- The image task refuses without the registered ImageStream or internal mode:
  `docs/TROUBLESHOOTING.md#stage-070-internal-registry-build-refuses`.
- Two PVC workspaces in one run need `coschedule: pipelineruns`
  (`ocp-pipelines-install-config`).
- TaskRun evictions on modelcar nodes are node disk pressure:
  `docs/TROUBLESHOOTING.md#pipeline-or-workspace-pods-evicted-for-ephemeral-storage`.
- Image signing is not in `app-push` (Gap); see `ocp-pipelines-security`.

## Official documentation (OpenShift Pipelines 1.24)

| Topic | Section |
|---|---|
| Concepts (Task, Pipeline, Workspace, Triggers) | [Concepts][concepts], [Workspaces][workspaces], [Triggers][about-triggers] |
| Build a CI/CD pipeline | [Creating tasks][tasks], [Assembling][assemble], [Running][run] |
| Triggers and webhooks | [Adding triggers][triggers], [Multi-namespace listeners][el-multi], [Creating webhooks][webhooks], [GitLab ClusterTriggerBindings][gitlab-ctb] |
| Remote tasks | [Resolvers][resolvers], [ClusterTask migration][clustertask] |
| Web console | [Pipelines in the web console][console] |

## Related skills

`ocp-pipelines-install-config`, `ocp-pipelines-security`,
`ocp-pipelines-performance`, `ocp-pipelines-about`,
`rhdh-dynamic-plugins-configure` (Tekton plugin), `ocp-gitops-operator`.

[concepts]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/about_openshift_pipelines/index#op-pipelines-concepts_understanding-openshift-pipelines
[workspaces]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/about_openshift_pipelines/index#about-workspaces_understanding-openshift-pipelines
[about-triggers]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/about_openshift_pipelines/index#about-triggers_understanding-openshift-pipelines
[tasks]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/creating_cicd_pipelines/index#creating-pipeline-tasks_creating-applications-with-cicd-pipelines
[assemble]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/creating_cicd_pipelines/index#assembling-a-pipeline_creating-applications-with-cicd-pipelines
[run]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/creating_cicd_pipelines/index#running-a-pipeline_creating-applications-with-cicd-pipelines
[triggers]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/creating_cicd_pipelines/index#adding-triggers_creating-applications-with-cicd-pipelines
[el-multi]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/creating_cicd_pipelines/index#configuring-eventlisteners-to-serve-multiple-namespaces_creating-applications-with-cicd-pipelines
[webhooks]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/creating_cicd_pipelines/index#creating-webhooks_creating-applications-with-cicd-pipelines
[gh-filter]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/creating_cicd_pipelines/index#op-filtering-pull-requests-using-GitHub-interceptor_creating-applications-with-cicd-pipelines
[gitlab-ctb]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/creating_cicd_pipelines/index#gitlab-cluster-trigger-bindings_using-clustertriggerbindings
[resolvers]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/creating_cicd_pipelines/index#remote-pipelines-tasks-resolvers
[clustertask]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/creating_cicd_pipelines/index#migrate-from-clustertask-to-cluster-resolver
[console]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/creating_cicd_pipelines/index#working-with-pipelines-web-console
