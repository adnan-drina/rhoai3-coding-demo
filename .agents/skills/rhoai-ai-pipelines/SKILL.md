---
name: rhoai-ai-pipelines
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when changing, reviewing or debugging the OpenShift AI pipeline server
  and pipeline lifecycle of this demo: DSC `aipipelines` (enabled by the Stage
  050 MLflow hook), DSPA `dspa` in `evaluated-models` created by the
  `configure-pipeline-server` hook, Kubernetes pipeline storage (`Pipeline`,
  `PipelineVersion` in Git), the MLflow plugin `insecureSkipVerify` copy,
  creating runs with an MLflow experiment, version clean-up and pipeline
  server resets (gitops/stages/050-model-evaluation/model-qualification/). Do
  NOT use for editing pipeline Python or components (use
  rhoai-kfp-pipeline-authoring), the MLflow server (use rhoai-mlflow), EvalHub
  jobs (use rhoai-evaluation), or Tekton (use ocp-pipelines-cicd).
---

# RHOAI AI Pipelines

Thin skill: repo decisions and pitfalls here, product behavior in the linked
OpenShift AI 3.5 sections. Detailed record:
`gitops/stages/050-model-evaluation/model-qualification/README.md` and
`docs/OPERATIONS.md#stage-050-model-qualification-pipeline-2026-10-12`.

## When to use

- The pipeline server in `evaluated-models` is not Ready, or the
  `configure-pipeline-server` hook fails a Stage 050 sync.
- A qualification run shows no logs, empty inputs, unopenable artifacts or
  MLflow errors.
- Publishing a new PipelineVersion, removing an old one, or resetting run history.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| `aipipelines` is `Removed` in Stage 010 and set `Managed` by the Stage 050 MLflow enable hook (delegated field) | `gitops/stages/050-model-evaluation/mlflow/dsc-enablement/enable-job.yaml` | [Manage AI pipelines][manage] |
| One pipeline server, DSPA `dspa` in `evaluated-models`, created by a Sync hook (wave 14) with the dashboard form's values: `dspVersion: v2`, S3 from the Pipelines connection, default database, `pipelineStore: kubernetes`, `cacheEnabled: true`, no sample pipeline. The DSPA is not in Git | `gitops/stages/050-model-evaluation/model-qualification/pipeline-server.yaml` | [Configure a pipeline server][server] |
| Default on-cluster database accepted for the demo (documented for development and test only) | same | [Configure a pipeline server][server] |
| The Pipelines connection carries the external ODF S3 Route so signed artifact links open in a browser | `gitops/stages/050-model-evaluation/model-qualification/storage/` | [Data storage with pipelines][storage] |
| Pipeline definitions stored as Kubernetes `Pipeline` (wave 16) and `PipelineVersion` (wave 17) objects compiled into Git | `gitops/stages/050-model-evaluation/model-qualification/pipeline/` | [Define a pipeline by using the Kubernetes API][k8sapi], [Kubernetes-native manifests][k8scompile] |
| MLflow plugin `insecureSkipVerify: true` in a copied server config (`ds-pipeline-server-config-custom`, `apiServer.customServerConfigMap`); operator decision 2026-10-12 | `gitops/stages/050-model-evaluation/model-qualification/pipeline-server.yaml` | [Enable MLflow integration for pipeline runs][mlflow-enable] |
| Pipeline runs tracked in MLflow experiment `agentic-coding-qualification`, chosen in the run form | `stages/050-model-evaluation/README.md` | [MLflow experiment tracking for pipeline runs][mlflow] |
| `pipeline-runner-dspa` is bound to the EvalHub Role; task containers mount the service CA ConfigMap `pipeline-tasks-service-ca` | `gitops/stages/050-model-evaluation/model-qualification/pipeline-server.yaml` | not product guidance |

## Procedure

1. Change server settings in the hook, not on the live DSPA. Connection
   settings cannot change in place: the hook fails if `dspa` points at another
   bucket or host; delete the DSPA and sync to reconfigure.
2. Deploy and validate all Stage 050 Applications at one SHA:

   ```bash
   ./stages/050-model-evaluation/deploy.sh
   ./stages/050-model-evaluation/validate.sh
   ./stages/050-model-evaluation/validate-ai-services.sh
   ```

3. Inspect read-only after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get dspa dspa -n evaluated-models -o jsonpath='{range .status.conditions[*]}{.type}={.status} {end}{"\n"}'
   oc get pipeline,pipelineversion -n evaluated-models
   ```

4. Start runs from the dashboard **Create run** form with the MLflow
   experiment set. A script must `POST /apis/v2beta1/runs` with
   `plugins_input.mlflow.experiment_name` ([REST API and SDK][rest]).
5. New pipeline version: compile with `rhoai-kfp-pipeline-authoring`, commit,
   re-pin Stage 050, then delete the previous `PipelineVersion` by hand
   (Argo CD does not prune it).
6. Reset (discards run history): stop runs, delete the Argo `workflows` and
   the DSPA in `evaluated-models`, then sync Stage 050
   (`docs/OPERATIONS.md#stage-050-model-qualification-pipeline-2026-10-12`).

## Pitfalls

- KFP SDK `create_run_from_pipeline_*` sends no MLflow experiment; every step
  then fails with `runID is required to update nested MLflow run`.
- Without the `insecureSkipVerify` copy, step drivers fail with
  `x509: certificate signed by unknown authority` against the in-cluster
  MLflow service on 3.5.1.
- The default MariaDB stores the pipeline spec in a `latin1` column: keep
  pipeline source ASCII-only.
- Run metadata (executions, artifacts) has no delete API; only a server reset
  removes it.
- Details for the four items above:
  `docs/TROUBLESHOOTING.md#qualification-pipeline-run-shows-no-logs-empty-inputs-or-unopenable-artifacts`.
- The DSPA is created by a Job, so Argo CD neither prunes nor self-heals it
  (gap recorded in the component README).

## Official documentation (OpenShift AI 3.5)

| Topic | Section |
|---|---|
| Pipeline servers and definitions | [Manage AI pipelines][manage], [Configure a pipeline server][server], [Options for defining a pipeline][define] |
| Kubernetes storage | [Kubernetes API][k8sapi], [Kubernetes-native manifests][k8scompile], [Migrate to Kubernetes API storage][migrate] |
| Versions and caching | [Pipeline versions][versions], [Pipeline caching][caching] |
| Experiments and runs | [Manage pipeline experiments][experiments], [Manage pipeline runs][runs], [Data storage][storage] |
| MLflow | [Track pipeline experiments with MLflow][mlflow-ch], [Enable MLflow][mlflow-enable] |
| Logs, SDK, Elyra | [Pipeline logs][logs], [REST API and SDK][rest], [Pipelines in JupyterLab][jupyter] |
| Troubleshooting | [DSPA component troubleshooting][dspa-ts] |

## Related skills

`rhoai-kfp-pipeline-authoring`, `rhoai-mlflow`, `rhoai-evaluation`,
`rhoai-model-evaluation`, `rhoai-dsci-dsc-configuration`,
`odf-object-bucket-claims`.

[manage]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ai_pipelines/index#managing-ai-pipelines_ai-pipelines
[server]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ai_pipelines/index#configuring-a-pipeline-server_ai-pipelines
[define]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ai_pipelines/index#defining-a-pipeline_ai-pipelines
[k8sapi]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ai_pipelines/index#defining-a-pipeline-by-using-the-kubernetes-api_ai-pipelines
[k8scompile]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ai_pipelines/index#compiling-kubernetes-native-manifests-with-kfp-sdk_ai-pipelines
[migrate]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ai_pipelines/index#migrating-pipelines-from-database-to-kubernetes-api_ai-pipelines
[versions]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ai_pipelines/index#overview-of-pipeline-versions_ai-pipelines
[caching]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ai_pipelines/index#overview-of-pipelines-caching_ai-pipelines
[experiments]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ai_pipelines/index#managing-pipeline-experiments_ai-pipelines
[runs]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ai_pipelines/index#managing-pipeline-runs_ai-pipelines
[storage]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ai_pipelines/index#storing-data-with-pipelines_ai-pipelines
[mlflow-ch]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ai_pipelines/index#tracking-pipeline-experiments-with-mlflow_ai-pipelines
[mlflow]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ai_pipelines/index#mlflow-pipeline-integration-overview_ai-pipelines
[mlflow-enable]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ai_pipelines/index#enabling-mlflow-for-pipeline-runs_ai-pipelines
[logs]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ai_pipelines/index#working-with-pipeline-logs_ai-pipelines
[rest]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ai_pipelines/index#pipelines-sdk-overview_ai-pipelines
[jupyter]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ai_pipelines/index#working-with-pipelines-in-jupyterlab_ai-pipelines
[dspa-ts]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ai_pipelines/index#troubleshooting-dspa-component-errors_ai-pipelines
