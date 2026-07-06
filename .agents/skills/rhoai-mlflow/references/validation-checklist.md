# Validation Checklist

Use this checklist before accepting MLflow README content, GitOps manifests,
SDK examples, notebooks, runbooks, or demo scripts.

## Source Alignment

- Product links use the active baseline in `docs/PLATFORM_BASELINE.md`.
- The official Working with MLflow source is recorded when MLflow behavior is
  introduced.
- `rhoai-api-tiers` is used when API tier posture matters for `MLflow`, MLflow
  REST API, or `MLflowConfig` dependencies.
- Project and workspace lifecycle claims are checked with
  `rhoai-project-workflows`.
- S3 connection and credential handling are checked with
  `rhoai-s3-object-storage-data` and `rhoai-connection-types`.
- OpenShift AI model registry behavior is not confused with MLflow model
  registry APIs.
- Custom evaluation evidence behavior is checked with `rhoai-model-evaluation`
  when the task is outside the product MLflow guide.

## Platform Configuration Review

- `DataScienceCluster` MLflow Operator component is set to `Managed` only when
  MLflow is intentionally enabled.
- `MLflow` resource is named `mlflow`.
- Cluster-level MLflow deployment is reviewed against `oc explain mlflow.spec`
  before authoring or applying fields.
- Development/test storage uses SQLite and PVC/file artifacts only when the
  demo explicitly accepts non-production storage.
- Production-shaped storage uses PostgreSQL for metadata and S3-compatible
  object storage for artifacts.
- Database URIs containing credentials use `backendStoreUriFrom`.
- Database and S3 credentials are not committed.
- Replica count greater than one uses remote storage that supports concurrent
  access.
- `serveArtifacts` and `defaultArtifactRoot` are configured consistently.

## RBAC Review

- Human users rely on appropriate OpenShift project roles.
- Service accounts use the narrowest role that satisfies the workflow.
- `mlflow-integration` is considered for automated tracking or model registry
  tasks.
- RBAC scope is explicit: cluster-scoped `mlflow` access versus namespace
  `mlflowconfig` access.
- Pseudo-resources are treated as authorization targets only, not Kubernetes
  objects.
- Resource-name granularity is used when a workload should only access a
  specific experiment or registry object.

## SDK Review

- SDK install uses `mlflow[kubernetes]>=3.11`.
- `MLFLOW_TRACKING_URI` points to the OpenShift AI dashboard MLflow endpoint.
- Preferred authentication uses `MLFLOW_TRACKING_AUTH=kubernetes-namespaced`.
- Local workstation examples rely on active kubeconfig context.
- Pod examples rely on mounted service account token and namespace.
- Manual `MLFLOW_TRACKING_TOKEN` examples are labeled non-production or
  troubleshooting only.
- `MLFLOW_TRACKING_INSECURE_TLS=true` is used only for accepted self-signed
  demo certificate posture.
- Connectivity is verified with `mlflow.list_workspaces()`.

## Experiment And Artifact Review

- Experiments and runs are scoped to the intended workspace/project.
- Logged parameters, metrics, and artifacts do not expose secrets.
- Project-specific artifact overrides use:
  - Secret name `mlflow-artifact-connection`
  - `MLflowConfig` name `mlflow`
  - required S3 keys
  - optional relative `artifactRootPath`
- Per-project artifact override notes explain that clients access S3 directly.
- Workbench or pod workloads have credentials required for direct S3 artifact
  access when overrides are used.

## Optional Read-Only Checks

Run only after following the OpenShift safety guard in `AGENTS.md`:

```bash
oc get datasciencecluster default-dsc -o yaml
oc get mlflow -A -o yaml
oc get mlflowconfig -A -o yaml
oc get clusterrole | rg '^mlflow-'
oc get rolebinding -A | rg 'mlflow'
```

Schema checks:

```bash
oc explain datasciencecluster.spec.components.mlflowoperator
oc explain mlflow.spec
oc explain mlflowconfig.spec
```

SDK connectivity:

```bash
python -c "import mlflow; print(mlflow.list_workspaces())"
```

## Fail Conditions

Stop and correct the work if any of these are true:

- MLflow workspace lifecycle is described as MLflow API-managed instead of
  OpenShift project-managed.
- Database or S3 credentials are committed.
- `defaultArtifactRoot` is set to a direct `s3://` URI while
  `serveArtifacts` is enabled.
- Production-shaped deployments use SQLite or PVC-backed file artifacts
  without a clear non-production label.
- A per-project artifact override uses a Secret name other than
  `mlflow-artifact-connection`.
- `artifactRootPath` is absolute, includes backslashes, or includes `..`.
- Service account examples use broad roles without a reason.
- Manual token export is presented as production guidance.
- Troubleshooting treats MLflow pseudo-resources as Kubernetes objects.
