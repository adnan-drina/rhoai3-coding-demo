---
name: rhoai-mlflow
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when changing, reviewing or debugging the shared OpenShift AI MLflow
  tracking server of Stage 050: the cluster-scoped MLflow CR `mlflow`, its
  PostgreSQL StatefulSet `mlflow-postgresql`, the ODF artifact bucket
  `rhoai-mlflow-artifacts`, the `mlflowoperator`/`trustyai`/`aipipelines`
  enable hook, the `ai-curated-prompts` global prompt workspace, MLflow SDK
  authentication, or EvalHub and pipeline runs that fail to log to MLflow
  (gitops/stages/050-model-evaluation/050-mlflow/). Do NOT use for EvalHub jobs,
  providers and collections (use rhoai-evaluation), AI pipeline servers (use
  rhoai-ai-pipelines), or registry records (use rhoai-model-registry-workflows).
---

# RHOAI MLflow

Thin skill: repo decisions and pitfalls here, product behavior in the linked
OpenShift AI 3.5 sections. Detailed record:
`gitops/stages/050-model-evaluation/050-mlflow/README.md`.

## When to use

- The MLflow CR is not `Available`, or EvalHub, the qualification pipeline or
  GenAI Studio tracing cannot write runs.
- Changing the MLflow database, artifact storage, CA trust or sizing.
- Adding a global prompt workspace or reviewing who may read MLflow data.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| `mlflowoperator`, `trustyai` and `aipipelines` set `Managed` by a Sync hook into fields Stage 010 delegates (one shared DSC) | `gitops/stages/050-model-evaluation/050-mlflow/dsc-enablement/` | [Enable the MLflow Operator component][enable] |
| One cluster-scoped `MLflow` named `mlflow`; Secret and ConfigMap references resolve in `redhat-ods-applications` | `gitops/stages/050-model-evaluation/050-mlflow/mlflow.yaml` | [MLflow configuration parameters][params] |
| PostgreSQL 16 metadata store via `backendStoreUriFrom` (Secret `mlflow-db-credentials`, created by `setup-ai-services.sh`); no SQLite | `gitops/stages/050-model-evaluation/050-mlflow/postgresql-statefulset.yaml` | [Install and configure MLflow][install], [Storage and database compatibility][storage] |
| Artifacts in ODF bucket `rhoai-mlflow-artifacts` with `serveArtifacts: true`, so clients never hold S3 keys | `gitops/stages/050-model-evaluation/050-mlflow/objectbucketclaim.yaml` | [MLflow configuration parameters][params] |
| `ai-curated-prompts` is a global prompt workspace (label `opendatahub.io/global-mlflow-workspace: mlflow`) listed in dashboard `globalMLflowNamespaces` | `gitops/stages/050-model-evaluation/050-mlflow/prompts/namespace.yaml` | [Cluster roles for global prompt registry namespaces][globalroles] |
| One replica and one worker, automatic schema migration: demo sizing | `gitops/stages/050-model-evaluation/050-mlflow/mlflow.yaml` | [MLflow configuration parameters][params] |
| All data objects (PVC, StatefulSet, bucket, CR) carry `Prune=false,Delete=false`, so MLflow is its own Argo CD Application `050-mlflow` | `gitops/applications/050-mlflow.yaml` | not product guidance |

## Procedure

1. Change manifests under `gitops/stages/050-model-evaluation/050-mlflow/`, commit,
   publish, then deploy all Stage 050 Applications at one SHA:

   ```bash
   ./stages/050-model-evaluation/deploy.sh      # runs setup-ai-services.sh
   ./stages/050-model-evaluation/validate.sh
   ./stages/050-model-evaluation/validate-ai-services.sh
   ```

2. Inspect read-only, after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get mlflows.mlflow.opendatahub.io mlflow -o jsonpath='{range .status.conditions[*]}{.type}={.status} {end}{"\n"}'
   oc get statefulset,pvc,obc -n redhat-ods-applications | grep -i mlflow
   ```

3. SDK clients authenticate with `MLFLOW_TRACKING_AUTH=kubernetes-namespaced`
   and use their OpenShift project as the MLflow workspace ([SDK][sdk]).
   Grant access with the aggregate `mlflow-view` / `mlflow-edit` roles
   ([aggregate roles][roles]).

## Pitfalls

- `setup-ai-services.sh` refuses to regenerate `mlflow-db-credentials` while
  the database PVC or StatefulSet exists; a lost Secret means restoring it,
  not re-running the helper.
- `caBundleConfigMap` (trust for the ODF S3 service) is in the repo CR but was
  not found in the 3.5 parameter text; verify with
  `oc explain mlflows.spec.caBundleConfigMap` before relying on it elsewhere.
- Pipeline step MLflow calls ignore the service CA on 3.5.1; the qualification
  project uses `insecureSkipVerify` in a copied server config. See
  `docs/TROUBLESHOOTING.md#qualification-pipeline-run-shows-no-logs-empty-inputs-or-unopenable-artifacts`.
- A deleted MLflow experiment keeps its name reserved; delete runs, not the
  experiment, when it will be reused
  (`docs/OPERATIONS.md#stage-050-model-qualification-pipeline-2026-10-12`).
- The database URI uses `sslmode=disable`; the NetworkPolicy still lets every
  pod in `redhat-ods-applications` reach port 5432.

## Official documentation (RHOAI 3.5)

| Topic | Section |
|---|---|
| Concepts, projects as workspaces | [MLflow for experiment tracking][about] |
| Install, CR and MLflowConfig fields | [Install and configure MLflow][install], [Parameters][params] |
| Roles and API authorization | [Aggregate cluster roles][roles], [RBAC model][rbac] |
| SDK setup and errors | [Install and authenticate the SDK][sdk], [Pods][sdkpods], [Troubleshooting][sdktrouble], [Version compatibility][versions] |
| Per-project artifact storage | [Project-specific S3 artifact storage][s3project] |
| Workbench integration | [Track experiments in workbenches][workbench] |
| Trace archival | [Trace archival][archival] |

## Related skills

`rhoai-evaluation`, `rhoai-ai-pipelines`, `rhoai-gen-ai-playground`,
`rhoai-dsci-dsc-configuration`, `odf-object-bucket-claims`.

[about]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_mlflow/index#about-mlflow_mlflow
[install]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_mlflow/index#installing-mlflow_mlflow
[params]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_mlflow/index#mlflow-configuration-parameters_mlflow
[roles]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_mlflow/index#reference-aggregate-cluster-roles_mlflow
[globalroles]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_mlflow/index#cluster_roles_for_global_prompt_registry_namespaces
[rbac]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_mlflow/index#rbac-model-api-usage_mlflow
[sdk]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_mlflow/index#installing-and-authenticating-mlflow-sdk_mlflow
[sdkpods]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_mlflow/index#configuring-mlflow-sdk-environment-variables-for-pods_mlflow
[sdktrouble]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_mlflow/index#troubleshooting-mlflow-sdk_mlflow
[versions]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_mlflow/index#mlflow-version-compatibility_mlflow
[storage]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_mlflow/index#mlflow-storage-database-compatibility_mlflow
[s3project]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_mlflow/index#configuring-project-specific-s3-artifact-storage_mlflow
[enable]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_mlflow/index#enabling-mlflow-component_mlflow
[workbench]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_mlflow/index#tracking-experiments-with-mlflow-in-workbenches
[archival]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_mlflow/index#mlflow-trace-archival-overview_mlflow
