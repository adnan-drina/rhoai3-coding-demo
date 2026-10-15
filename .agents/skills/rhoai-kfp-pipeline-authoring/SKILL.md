---
name: rhoai-kfp-pipeline-authoring
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when writing, changing or reviewing KFP v2 pipeline code in this repo:
  stages/050-model-evaluation/qualification/pipeline.py and compile.py, new
  components or steps, base images and pinned packages, kfp 2.16.1
  Kubernetes-native compilation into
  gitops/stages/050-model-evaluation/model-qualification/pipeline/, new
  PipelineVersion names, Metrics/HTML outputs, or reusing catalog components.
  Do NOT use for the pipeline server, run lifecycle, MLflow tracking or
  server resets (use rhoai-ai-pipelines), or EvalHub collections (use
  rhoai-evaluation).
---

# KFP Pipeline Authoring

Repo-specific skill: how this demo writes and publishes KFP v2 pipelines.
Conventions in `references/kfp-patterns.md`; product behavior in the linked
OpenShift AI 3.5 sections. Pipeline server and runs: `rhoai-ai-pipelines`.

## When to use

- Editing `stages/050-model-evaluation/qualification/pipeline.py` or adding
  a pipeline to another stage.
- Recompiling and publishing a new `PipelineVersion`.
- A step fails at install, compile, registration or in the dashboard view
  because of how the pipeline was written.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Compile to Kubernetes-native `Pipeline`/`PipelineVersion` manifests and commit them; GitOps applies them | `stages/050-model-evaluation/qualification/compile.py`, `gitops/stages/050-model-evaluation/model-qualification/pipeline/` | [Compile Kubernetes-native manifests][k8scompile], [Define a pipeline by using the Kubernetes API][k8sapi] |
| `kfp==2.16.1` with `kfp-kubernetes==2.16.1`, Python 3.11+ | `stages/050-model-evaluation/qualification/compile.py` | [Install the Kubeflow Pipelines SDK][sdk-install] |
| Base image: RHOAI `odh-pipeline-runtime-minimal-cpu-py312-rhel9` pinned by digest; packages pinned; PyPI index for `eval-hub-sdk[cli]==1.0.5` | `stages/050-model-evaluation/qualification/pipeline.py` | not product guidance |
| One named component per step (`step-0-...` to `step-7-...`), no `set_display_name` (dashboard looks steps up by task key) | same | not product guidance; see [View pipeline task executions][executions] |
| Caching off per task (`set_caching_options(False)`) though the server has caching on | same | [Control caching in pipelines][caching] |
| No credential parameters: tasks use the `pipeline-runner-dspa` token and a mounted service CA ConfigMap | same, `gitops/stages/050-model-evaluation/model-qualification/pipeline-server.yaml` | not product guidance |
| Skip switches (`skip_*`) instead of `dsl.If`, so the step chain keeps its order | `stages/050-model-evaluation/qualification/pipeline.py` | not product guidance |

## Procedure

1. Edit `pipeline.py`; keep components hermetic and typed
   (`references/kfp-patterns.md`).
2. Check and compile with a new version name:

   ```bash
   cd stages/050-model-evaluation/qualification
   LC_ALL=C grep -nP '[^\x00-\x7F]' pipeline.py   # must print nothing
   python compile.py v<N>                        # kfp 2.16.1 venv
   ```

3. Review the diff of
   `gitops/stages/050-model-evaluation/model-qualification/pipeline/agentic-coding-model-qualification.yaml`,
   commit, re-pin and deploy Stage 050 (`rhoai-ai-pipelines` procedure).
4. After the OpenShift safety guard in `AGENTS.md`, confirm the version and
   delete the previous one:

   ```bash
   oc get pipelineversion -n evaluated-models
   oc delete pipelineversion agentic-coding-model-qualification-v<N-1> -n evaluated-models
   ```

5. Run once with the long steps skipped, then a full run.

## Pitfalls

- Non-ASCII characters in the source make registration fail (default
  MariaDB `latin1` column).
- `set_display_name` on a reused component breaks the dashboard's Logs and
  Input/Output tabs; task names that start with a digit are rejected by Argo.
- The runtime image's default index has an old `eval-hub-sdk`; without
  `pip_index_urls` the install fails.
- A step cannot depend on a step inside `dsl.If`.
- All with fixes:
  `docs/TROUBLESHOOTING.md#qualification-pipeline-run-shows-no-logs-empty-inputs-or-unopenable-artifacts`.

## Official documentation (OpenShift AI 3.5)

| Topic | Section |
|---|---|
| Defining pipelines | [Options for defining a pipeline][define], [Compile pipeline YAML][compile], [Kubernetes-native manifests][k8scompile], [Kubernetes API][k8sapi] |
| SDK | [Install the SDK][sdk-install], [Authenticate the SDK][sdk-auth], [Pipeline versions with the SDK][sdk-versions] |
| Caching | [Pipeline caching][caching-overview], [Control caching][caching] |
| Run workspaces | [Pipeline run workspaces][workspaces] |
| MLflow from tasks | [Direct SDK access from pipeline tasks][mlflow-sdk] |

## Related skills

`rhoai-ai-pipelines`, `rhoai-evaluation`, `rhoai-model-evaluation`,
`rhoai-mlflow`.

[define]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ai_pipelines/index#defining-a-pipeline_ai-pipelines
[compile]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ai_pipelines/index#compiling-the-pipeline-yaml-with-kfp-sdk_ai-pipelines
[k8scompile]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ai_pipelines/index#compiling-kubernetes-native-manifests-with-kfp-sdk_ai-pipelines
[k8sapi]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ai_pipelines/index#defining-a-pipeline-by-using-the-kubernetes-api_ai-pipelines
[sdk-install]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ai_pipelines/index#installing-kfp-sdk_ai-pipelines
[sdk-auth]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ai_pipelines/index#authenticating-kfp-sdk-with-pipeline-server_ai-pipelines
[sdk-versions]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ai_pipelines/index#working-with-pipeline-versions-sdk_ai-pipelines
[executions]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ai_pipelines/index#viewing-pipeline-task-executions_ai-pipelines
[caching-overview]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ai_pipelines/index#overview-of-pipelines-caching_ai-pipelines
[caching]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ai_pipelines/index#controlling-caching-in-pipelines_ai-pipelines
[workspaces]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ai_pipelines/index#configuring-pipeline-run-workspaces_ai-pipelines
[mlflow-sdk]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ai_pipelines/index#direct-sdk-access-from-pipeline-tasks_ai-pipelines
