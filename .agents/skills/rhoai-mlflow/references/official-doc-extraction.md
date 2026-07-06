# Official Documentation Extraction

This extraction is derived from the official RHOAI 3.4 guide captured in
`source-capture.md`.

## Concept Model

Red Hat OpenShift AI deploys a single shared MLflow instance through the MLflow
Operator. Each OpenShift project maps one-to-one to an MLflow workspace. MLflow
workspaces isolate experiments, runs, registered models, prompts, datasets, and
traces per project.

OpenShift AI manages workspace lifecycle outside MLflow. Project creation,
update, and deletion happen through the OpenShift AI dashboard or OpenShift
CLI, and the corresponding MLflow workspace becomes available automatically.

MLflow API authorization uses Kubernetes RBAC. The MLflow server performs a
`SelfSubjectAccessReview` using the caller bearer token and target project
namespace.

## Installation And Configuration

Prerequisites:

- cluster administrator privileges
- OpenShift Container Platform installed
- permission to patch `DataScienceCluster`
- permission to apply `MLflow` custom resources
- production-oriented deployments have database and S3-compatible storage
  Secrets prepared

Component enablement:

- `DataScienceCluster` component: `spec.components.mlflowoperator`
- desired management state: `Managed`

The `MLflow` resource is cluster-scoped and must be named `mlflow`. The
operator creates or expects it in `redhat-ods-applications` for the documented
deployment pattern.

Development/test deployment pattern:

- SQLite backend store
- PVC-backed file artifact storage
- `serveArtifacts: true`
- file-based artifact storage requires artifact serving to be enabled

Production-oriented deployment pattern:

- PostgreSQL metadata database
- S3-compatible artifact storage
- `backendStoreUriFrom` Secret reference when the database URI contains
  credentials
- more than one replica only when remote storage supports concurrent writers

## MLflow And MLflowConfig Resources

The `MLflow` custom resource defines global deployment state:

- replica count
- backend database URI or Secret reference
- registry store URI
- artifact destination
- default artifact root
- artifact serving behavior
- resources and TLS-related configuration

Important artifact storage rule:

- When `serveArtifacts` is enabled, clients log and retrieve artifacts through
  the MLflow server by using the `mlflow-artifacts:/` proxy URI scheme.
- Do not set `defaultArtifactRoot` to a direct storage URI such as `s3://` when
  artifact serving is enabled, because that causes clients to bypass the proxy.

If no project-specific override exists, artifacts are stored under the default
artifact root by workspace/project name.

The `MLflowConfig` custom resource is namespace-scoped and must be named
`mlflow`. Project owners use it for project-specific artifact storage
overrides.

Key `MLflowConfig` fields:

- `spec.artifactRootSecret`: must reference a Secret named
  `mlflow-artifact-connection`
- `spec.artifactRootPath`: optional relative path appended to the bucket root

## RBAC Model

MLflow access uses aggregate ClusterRoles:

- `mlflow-view`
- `mlflow-edit`
- `mlflow-integration`

Standard OpenShift `view`, `edit`, and `admin` role bindings do not grant
identical access to all MLflow resources because `mlflow` is cluster-scoped and
`mlflowconfig` is namespace-scoped. Effective access depends on binding scope.

`mlflow-integration` is intended for service accounts that need data-plane API
access without broad edit/delete privileges. It can be bound through a
namespace-scoped RoleBinding.

MLflow authorization checks use pseudo-resources in the
`mlflow.kubeflow.org` API group. These pseudo-resources are not Kubernetes
objects and cannot be created, listed, or inspected through the Kubernetes API.

Primary pseudo-resources:

- `experiments`: experiments, runs, traces, artifacts, logged models, scorers,
  and tracking operations
- `registeredmodels`: registered models, model versions, and prompts
- `datasets`: evaluation datasets and related operations

Resource-name granularity can restrict an agent or workload to specific
objects, such as one experiment.

## SDK Installation And Authentication

Install the compatible MLflow SDK:

```bash
pip install "mlflow[kubernetes]>=3.11"
```

The compatible MLflow SDK version is 3.11 or later. The deployed MLflow server
version captured in the guide is 3.10.1.

Preferred authentication:

```bash
export MLFLOW_TRACKING_URI="https://<dashboard-url>/mlflow"
export MLFLOW_TRACKING_AUTH=kubernetes-namespaced
```

The `kubernetes-namespaced` authentication plugin reads credentials from:

- mounted service account token and namespace when running in a pod
- active kubeconfig context when running on a workstation

Manual authentication variables:

```bash
export MLFLOW_TRACKING_URI="https://<dashboard-url>/mlflow"
export MLFLOW_TRACKING_TOKEN="$(oc whoami --show-token)"
export MLFLOW_WORKSPACE="<project-name>"
```

Manual token export is not recommended for production environments.

For demo clusters with self-signed or untrusted TLS certificates:

```bash
export MLFLOW_TRACKING_INSECURE_TLS=true
```

Connectivity verification:

```bash
python -c "import mlflow; print(mlflow.list_workspaces())"
```

## Local Workstation And Pod Configuration

For local workstation use, the authentication plugin uses the active kubeconfig
context. The namespace in the kubeconfig context becomes the workspace unless
the workspace is manually overridden.

For pod use, the authentication plugin uses the mounted service account token
and pod namespace. You do not need to call `mlflow.set_workspace()` when using
the plugin unless the workload intentionally targets another project and has
RBAC for that project.

## Experiment Tracking

The MLflow SDK can log:

- experiments
- runs
- parameters
- metrics
- artifacts

When `kubernetes-namespaced` authentication is configured, the tracking URI
and workspace are resolved from environment and Kubernetes context.

## Storage And Database Compatibility

Supported storage and database options captured in the guide:

- Artifact storage:
  - S3-compatible object storage for production
  - file system for development and testing
- Database:
  - PostgreSQL for production
  - SQLite for development and testing
- Artifact repository plugins:
  - S3
  - file

## Project-Specific S3 Artifact Storage

By default, projects use artifact storage from the cluster-level `MLflow`
resource. A project can override artifact storage by creating:

- a project S3-compatible connection or Secret named
  `mlflow-artifact-connection`
- an `MLflowConfig` resource named `mlflow` in the same project

Required Secret keys for connection API usage:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_S3_BUCKET`
- `AWS_S3_ENDPOINT`

`AWS_DEFAULT_REGION` is optional when the storage provider does not require it.

When using a per-project override, MLflow does not serve artifacts through the
MLflow server. The client accesses S3 directly, so valid S3 credentials must be
available to the client.

`artifactRootPath` rules:

- optional
- relative path only
- no backslashes
- no path traversal such as `..`

## Troubleshooting Signals

Common issues and likely causes:

- `403` or permission denied: missing RBAC in the active project
- workspace not found: wrong project name, namespace filtering, or no selected
  workspace
- artifact override not applied: missing or incorrectly named `MLflowConfig`,
  wrong namespace, or missing Secret
- authentication plugin cannot resolve credentials: missing service account
  token in-cluster or inactive kubeconfig locally
- artifact writes go to default storage: missing project `MLflowConfig` or
  invalid `artifactRootSecret`
- JSON decode error: missing or invalid OpenShift AI authentication token
  causing HTML login response instead of JSON

## Verification Signals

Expected signals:

- `DataScienceCluster` has `mlflowoperator.managementState: Managed`
- `MLflow` CR named `mlflow` exists for the cluster-level deployment
- OpenShift AI Applications menu shows MLflow UI when visible
- MLflow UI can select a workspace and compare runs
- SDK lists accessible workspaces
- SDK can create an experiment and log parameters and metrics
- per-project `MLflowConfig` routes new run artifacts to the intended S3
  bucket/path
