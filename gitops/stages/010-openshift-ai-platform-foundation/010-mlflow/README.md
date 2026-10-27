# MLflow tracking service (`010-mlflow`)

This Application runs the shared OpenShift AI MLflow tracking server with a project-owned PostgreSQL database and an
OpenShift Data Foundation bucket for artifacts. Its hook Job turns on the MLflow operator and the dashboard's global
prompt settings. It is a platform service: GenAI Studio tracing and the Ops Assistant prompt (Stage 040), EvalHub and
the qualification pipeline (Stage 050), agent traces (Stage 060) and the curated prompt workspace all write to it; each
project is its own MLflow workspace [1]. Until 2026-10-27 it was the Stage 050 Application `050-mlflow`;
`docs/OPERATIONS.md` records the move.

| | |
|---|---|
| Argo CD Application | `010-mlflow` ([manifest](../../../applications/010-mlflow.yaml)) |
| Deployed by | [`stages/010-openshift-ai-platform-foundation/deploy.sh`](../../../../stages/010-openshift-ai-platform-foundation/deploy.sh) (script-deployed component, last in the stage; alone with `--component 010-mlflow`). Between the sync and the wait it creates or reuses the database Secret and waits for the bound bucket and the injected CA |
| Validated by | [`validate.sh --component 010-mlflow`](../../../../stages/010-openshift-ai-platform-foundation/validate.sh) (Application Synced/Healthy, dashboard settings, PostgreSQL, bucket, CA bundle, MLflow `Available`, workload Secret and TLS wiring); part of the full Stage 010 validation |
| Sync | Automated, `prune` and `selfHeal`. Server-Side Diff by annotation; `RespectIgnoreDifferences=true`. `ignoreDifferences` on `ConfigMap/mlflow-service-ca` `/data/service-ca.crt` (injected by the service CA operator). |
| Depends on | `010-rhoai-platform` (delegated DSC and dashboard fields); `010-odf` (Multicloud Object Gateway `openshift-storage.noobaa.io`); the MLflow health gate in `gitops/bootstrap`; `gp3-csi`. |
| Used by | `040-genai-studio` (playground tracing, Ops Assistant prompt), `050-evalhub` (tracking URI), `050-model-qualification` (pipeline-run tracking), Stage 060 agent traces (`ai-agents` workspace). |

## Why

OpenShift AI 3.5 ships MLflow as an operator-managed component: enable `mlflowoperator` in the `DataScienceCluster`, then
create one cluster-scoped `MLflow` resource named `mlflow` [1][2]. For production the guide uses PostgreSQL for metadata
(`backendStoreUriFrom`) and S3-compatible object storage for artifacts (`artifactsDestination`, `serveArtifacts`); SQLite on
a PVC is for development and testing [1]. The product does not ship a PostgreSQL operator, so this component runs one
pinned Red Hat PostgreSQL 16 StatefulSet. Artifacts go to an ODF bucket requested with an ObjectBucketClaim [5].

The data (database, PVC, bucket, MLflow CR) is retained independently of the stages that use it, so it is its own
Application with `Prune=false,Delete=false` on every data object. It belongs to the foundation stage because Stages
040, 050 and 060 all use it.

## What

### Tracking service and data (component root)

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| PersistentVolumeClaim | `mlflow-postgresql` | `redhat-ods-applications` | 10 Gi `gp3-csi` database volume. Wave 12, `Prune=false,Delete=false`. |
| Service | `mlflow-postgresql` | `redhat-ods-applications` | Port 5432. Wave 12, retained. |
| StatefulSet | `mlflow-postgresql` | `redhat-ods-applications` | One replica, `rhel9/postgresql-16` pinned by digest (the image RHOAI 3.5.1 names as `RELATED_IMAGE_POSTGRESQL_16_IMAGE`), no service-account token, `RuntimeDefault` seccomp, all capabilities dropped. Wave 12, retained. |
| NetworkPolicy | `mlflow-postgresql` | `redhat-ods-applications` | Ingress to 5432 only from pods in the same namespace. Wave 12, retained. |
| ObjectBucketClaim | `rhoai-mlflow-artifacts` | `redhat-ods-applications` | Fixed bucket name so the MLflow CR can reference it. Wave 12, retained. |
| ConfigMap | `mlflow-service-ca` | `redhat-ods-applications` | Service CA bundle injection target (`inject-cabundle`), used to trust the ODF S3 service. Wave 12, retained. |
| MLflow | `mlflow` | cluster | Wave 20, retained. PostgreSQL backend from a Secret, proxied S3 artifacts, CA bundle, one replica and worker, automatic schema migration. |

### `enablement/`

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| ServiceAccount | `enable-mlflow` | `redhat-ods-applications` | Hook identity. Wave 1. |
| ClusterRole / ClusterRoleBinding | `enable-mlflow` | cluster | `get`/`patch` on `default-dsc`; `get` on the `mlflows.mlflow.opendatahub.io` CRD. Wave 1. |
| Role / RoleBinding | `enable-mlflow-dashboard` | `redhat-ods-applications` | `get`/`patch` on `odh-dashboard-config` only. Wave 1. |
| Job | `enable-mlflow` | `redhat-ods-applications` | `Sync` hook, wave 2, `BeforeHookCreation,HookSucceeded`, 900 s deadline. Patches the DSC and dashboard (below) with a resourceVersion test and waits for the MLflow CRD. |

The evaluation settings this Job used to set as well (TrustyAI, AI Pipelines, `disableLMEval`) moved to
`050-model-qualification` (`evaluation-enablement/`).

### `prompts/`

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| Namespace | `ai-curated-prompts` | cluster | Wave 25, `Prune=false,Delete=false`. Dashboard project labelled `opendatahub.io/global-mlflow-workspace: mlflow`. |

### Objects not in Git

| Object | Created by |
|---|---|
| Secret `mlflow-db-credentials` (`database-user`, `database-password`, `database-name`, `backend-store-uri`) | `stages/010-openshift-ai-platform-foundation/deploy.sh`, once, with a random password; it refuses to regenerate it when a database PVC or StatefulSet already exists |
| Secret and ConfigMap `rhoai-mlflow-artifacts` (S3 keys, `BUCKET_HOST`, `BUCKET_PORT`) | ODF from the ObjectBucketClaim [5] |
| ServiceAccount `mlflow-sa`, the MLflow Deployment, Service and dashboard integration | MLflow operator, owned by the `MLflow` CR |
| Experiments, runs, traces, artifacts | MLflow clients (EvalHub, pipelines, GenAI Studio, agents, helpers) |

## How

**Ordering.** RBAC (wave 1) and the hook Job (wave 2) run first, so the MLflow CRD exists before the `MLflow` CR syncs.
Data objects follow at wave 12 and the `MLflow` CR at wave 20 [6]. `stages/010-openshift-ai-platform-foundation/deploy.sh`
applies and syncs the Application, creates the database Secret (the server cannot become healthy without it), waits
for the bound bucket and the injected CA, then waits for the Application to be Healthy, which the MLflow health gate
ties to `Available`, `MLflowOperatorReady` and `Migration` at the current generation. Stage 050 publishes the MLflow
HTTPS address for EvalHub.

**Delegated fields.** `010-rhoai-platform` owns `default-dsc` and `odh-dashboard-config` and delegates these fields through
`ignoreDifferences` with `RespectIgnoreDifferences=true` [7] (`scripts/stage-apps.sh delegated 010 ...`):

| Object | Field | Value set by the hook | Consumer | Default |
|---|---|---|---|---|
| `DataScienceCluster/default-dsc` | `/spec/components/mlflowoperator` | `managementState: Managed` | this component | `Removed` [1] |
| `OdhDashboardConfig/odh-dashboard-config` | `/spec/dashboardConfig/globalProjectPrompts` | `true` | curated prompts | `false`, Technology Preview [3] |
| same | `/spec/globalMLflowNamespaces` | `["ai-curated-prompts"]` | `prompts/` namespace (this component) | unset |

The dashboard patch refuses to merge with a foreign `globalMLflowNamespaces` value.

**MLflow CR choices.**

- `backendStoreUriFrom: mlflow-db-credentials/backend-store-uri`: the documented Secret reference for a URI with
  credentials [1]. References resolve in `redhat-ods-applications` (the CR is cluster-scoped; see the manifest comment).
- `artifactsDestination: s3://rhoai-mlflow-artifacts/artifacts` with `serveArtifacts: true`: clients upload and download
  through the tracking server and never receive S3 keys [1].
- `MLFLOW_S3_ENDPOINT_URL` is built from the bucket ConfigMap's internal HTTPS service host and port; `caBundleConfigMap:
  mlflow-service-ca` lets the server verify that service certificate, and the validator checks `MLFLOW_S3_IGNORE_TLS` is
  `false`.
- `migration.mode: Automatic` upgrades the database schema when the image changes.
- One replica and one worker: demo sizing.

**Database transport.** The URI uses `sslmode=disable` (written by `stages/010-openshift-ai-platform-foundation/deploy.sh`). The NetworkPolicy keeps the
port inside `redhat-ods-applications`, but every pod in that namespace may connect.

**Secrets.** No value is in Git. The database Secret is generated by `stages/010-openshift-ai-platform-foundation/deploy.sh`; the S3 credentials are
generated by ODF.

## Validation

`stages/010-openshift-ai-platform-foundation/validate.sh --component 010-mlflow` (also part of the full Stage 010 run)
checks: the Application `Synced` and `Healthy`; `mlflowoperator` `Managed`; `globalProjectPrompts: true`,
`globalMLflowNamespaces: [ai-curated-prompts]`; the curated workspace label; the PostgreSQL StatefulSet current and ready
with a Bound `gp3-csi` PVC; the database Secret keys; the bucket Bound to `rhoai-mlflow-artifacts` with S3 keys and an
internal HTTPS endpoint on 443; the injected CA; MLflow `Available` with `MLflowOperatorReady` and `Migration` at the
current generation; one current operator-owned Deployment that reads the backend Secret, mounts a CA bundle and verifies
S3 TLS.

By hand:

```bash
oc get mlflows.mlflow.opendatahub.io mlflow -o jsonpath='{range .status.conditions[*]}{.type}={.status} {end}{"\n"}'
oc get statefulset,pvc,obc -n redhat-ods-applications -l app.kubernetes.io/part-of=rhoai-platform | grep -i mlflow
```

## Alignment with official guidance

| Topic | Official guidance (link) | This repository | Status |
|---|---|---|---|
| Enable the component | `mlflowoperator` `Managed` in the DSC [1][2] | Hook Job into a field delegated by `010-rhoai-platform` | Deviation (justified: the shared DSC has one owner Application) |
| MLflow resource | One cluster-scoped `MLflow` named `mlflow` [1] | Same | Aligned |
| Metadata store | PostgreSQL for production, SQLite for development and testing [1] | PostgreSQL 16, single instance, no TLS, no backup | Deviation (justified: demo; not an HA or backup design) |
| Artifact store | S3-compatible storage with `artifactsDestination` and `serveArtifacts` [1] | ODF bucket, proxied artifacts, TLS verified with the service CA | Aligned |
| Credentials | Secret references, not literal URIs [1] | `backendStoreUriFrom` and `envFrom` the OBC Secret | Aligned |
| Bucket provisioning | ObjectBucketClaim on `openshift-storage.noobaa.io`; documented example uses `generateBucketName` [5] | Fixed `bucketName` | Deviation (justified: the MLflow CR needs a known bucket name; field is accepted by the provisioner but not shown in the ODF guide) |
| Global prompts | `globalProjectPrompts` is Technology Preview [3]; global workspace label `opendatahub.io/global-mlflow-workspace` [1] | Enabled for `ai-curated-prompts` | Aligned (Technology Preview) |
| Component boundary | One owner per lifecycle | The hook enables only MLflow and its prompt settings; evaluation settings are Stage 050's | Aligned |
| Argo CD | Server-Side Diff by annotation [8]; retained data with `Prune=false,Delete=false` [7] | Both | Aligned |

## References

1. Working with MLflow, Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_mlflow/index
2. Installing and deploying OpenShift AI (DSC component management states), Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/installing_and_uninstalling_openshift_ai_self-managed/installing-and-deploying-openshift-ai_install
3. Customizing the dashboard (dashboard feature configuration options), Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/managing_resources/customizing-the-dashboard
4. Evaluating AI systems (2.20 Configure MLflow experiment tracking for evaluation jobs), Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/evaluating_ai_systems/index
5. Object Bucket Claim, Red Hat OpenShift Data Foundation 4.22. https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.22/html/managing_hybrid_and_multicloud_resources/object-bucket-claim
6. Sync phases and waves, Argo CD (upstream). https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/
7. Sync options, Argo CD (upstream). https://argo-cd.readthedocs.io/en/stable/user-guide/sync-options/
8. Diff strategies (Server-Side Diff), Argo CD (upstream). https://argo-cd.readthedocs.io/en/stable/user-guide/diff-strategies/
