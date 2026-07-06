# Official Doc Extraction

Extract only behavior supported by the official Working with AI pipelines guide
and active-baseline linked Red Hat docs.

## Pipeline Concepts

- AI pipelines standardize and automate portable machine learning workflows
  built from containerized steps.
- Example workflow steps include data extraction, data processing, feature
  extraction, model training, model validation, and model serving.
- The OpenShift AI AI Pipelines feature is based on Kubeflow Pipelines 2.0.
- Use the latest Kubeflow Pipelines 2.0 SDK recommended by the active docs to
  build pipelines in Python and compile them to Intermediate Representation
  YAML.
- The OpenShift AI dashboard manages pipelines, pipeline versions,
  experiments, runs, scheduled runs, archived runs, artifacts, and executions.
- Pipeline artifacts can be stored in S3-compatible object storage.

## Pipeline Server Configuration

- A pipeline server must be configured before an AI pipeline can be created in
  OpenShift AI.
- A project must exist before adding a pipeline server.
- Pipeline server object storage requires S3-compatible endpoint, access key,
  secret key, region, and bucket.
- Incorrect object storage connection settings cannot be updated on the same
  pipeline server. The server must be deleted and recreated.
- The default on-cluster database option deploys a MariaDB database in the
  project and is intended for development and testing.
- For production pipeline workloads, Red Hat recommends an external MySQL or
  MariaDB database.
- External MySQL must be at least version 5.x; Red Hat recommends MySQL 8.x.
- External MariaDB must be version 10.3 or later; Red Hat recommends at least
  MariaDB 10.5.
- The `mysql_native_password` authentication plugin is required for ML Metadata
  connectivity. MySQL 8.4 and later disable this plugin by default.
- Pipeline definitions are stored as Kubernetes resources by default, enabling
  version control and GitOps workflows.
- When a pipeline server uses Kubernetes API storage, GitOps-friendly pipeline
  import can be implemented by creating `Pipeline` and `PipelineVersion`
  custom resources directly. Preserve both compiled KFP IR documents when the
  compiler emits a separate Kubernetes `platformSpec`.
- Caching can be configured at pipeline and task levels by default. Pipeline
  server configuration can disable that flexibility for all pipelines.

## External Amazon RDS And Certificates

- Configuring a pipeline server with external Amazon RDS requires OpenShift AI
  to trust the database certificate authorities.
- The official workflow updates the `DSCInitialization` trusted CA bundle and
  then configures the pipeline server.
- Delegate CA bundle review and implementation to `rhoai-certificate-management`.

## Defining And Compiling Pipelines

- The KFP SDK defines end-to-end AI and machine learning pipelines.
- For FIPS mode clusters, custom pipeline container images must be based on UBI
  9 or RHEL 9.
- Compiling normal pipeline YAML requires:
  - Python 3.11 or later
  - Kubeflow Pipelines SDK package `kfp` version 2.14.3 or later
  - a valid Python pipeline definition file
- The `kfp dsl compile` command produces YAML that contains a `pipelineSpec`.
- The compiled YAML can be imported through the dashboard or stored in Git.
- Compiling Kubernetes-native manifests applies only when the pipeline server
  uses Kubernetes API storage.
- Kubernetes-native output includes `Pipeline` and `PipelineVersion` custom
  resources with `apiVersion: pipelines.kubeflow.org/v2beta1`.
- `PipelineVersion` includes `spec.pipelineSpec` and can include
  `spec.platformSpec` when Kubernetes resource configuration is used.
- Multi-line JSON default values can make compiled YAML headers invalid for
  Kubernetes API storage. Keep large JSON string defaults compact or pass them
  as run parameters from the runner.

## KFP SDK Authentication

- The pipeline server route is protected by OpenShift OAuth.
- KFP SDK clients must provide a valid OpenShift access token.
- The official workflow obtains the current user token with `oc whoami
  --show-token` and passes it to `kfp.client.Client` through
  `existing_token`.
- Do not paste tokens directly into commands or scripts because they can appear
  in shell history or process listings.
- If running outside the cluster or using a custom/self-signed certificate, the
  KFP client can use a trusted certificate bundle path.

## Kubernetes API Storage And Migration

- Pipeline definitions and versions can be stored as Kubernetes custom
  resources instead of the internal database.
- This makes OpenShift GitOps or similar tools easier to use for pipeline and
  version management while preserving dashboard, API, and KFP SDK visibility.
- Database-to-Kubernetes migration changes stored pipeline IDs.
- The original ID is preserved as a label on the migrated pipeline custom
  resource.
- Migration uses a Kubeflow-provided script that is not supported by Red Hat.
  Treat it as a special operation, not a normal demo path.

## Pipeline Lifecycle And Versions

- Pipelines can be imported from a local file or URL after a pipeline server is
  configured.
- Imported pipelines can be deleted from the dashboard.
- Deleting a pipeline server deletes the server and associated metadata state;
  treat it as destructive.
- Pipeline versions preserve iterative changes to pipeline definitions.
- Users can upload, delete, view, and download pipeline versions.

## Caching

- Pipeline caching is enabled by default to improve performance.
- A cached task reuses previous outputs when the component spec, inputs,
  parameters, output names, pipeline name, and workspace path match.
- Cached tasks are marked in the OpenShift AI UI and do not show execution
  logs because they are not re-executed.
- Caching can be controlled at these levels:
  - individual task with `set_caching_options(False)`
  - run submission with `enable_caching=False`
  - compile time through `KFP_DISABLE_EXECUTION_CACHING_BY_DEFAULT=true` or the
    `kfp dsl compile --disable-execution-caching-by-default` flag
  - all pipelines by setting `spec.apiServer.cacheEnabled: false` in the
    `DataSciencePipelinesApplication` custom resource or through dashboard
    pipeline server configuration
- Disabling caching can increase compute time and resource consumption.

## Experiments, Artifacts, And Comparisons

- A pipeline experiment is a workspace for trying different pipeline
  configurations and organizing runs into logical groups.
- Experiments contain pipeline runs, including recurring runs.
- Experiments can be created, archived, restored, and deleted from the archive.
- Archive retains records; delete removes archived records.
- OpenShift AI can compare up to 10 pipeline runs at one time.
- Comparison data can include parameters, scalar metrics, confusion matrices,
  and ROC curve data.
- Pipeline artifacts can be viewed from the dashboard and can include plain
  text, files, models, or interactive visualizations depending on the pipeline.

## Runs And Schedules

- A pipeline run executes a pipeline. By default, a run executes once
  immediately after it is created.
- Runs can be active, scheduled, or archived.
- Users can view, execute, stop, duplicate, archive, restore, delete archived
  runs, and duplicate archived runs.
- Users can create scheduled runs with a cron job or with simplified
  scheduling fields.
- The official scheduling workflow supports concurrency limits up to 10.
- Catch-up behavior is enabled by default for missed schedules. Red Hat
  recommends disabling catch-up if the pipeline can handle backfilling itself.

## Pipeline Run Workspaces

- Pipeline run workspaces provide shared volume storage for tasks in a pipeline
  run.
- Workspace support is configured in the pipeline server
  `DataSciencePipelinesApplication` and enabled per pipeline through
  `dsl.PipelineConfig(workspace=dsl.WorkspaceConfig(...))`.
- Workspace PVC defaults can be configured in `spec.apiServer.workspace` with
  a `volumeClaimTemplateSpec`.
- Workspace storage can specify access modes, storage class, and resource
  requests.
- The KFP workspace placeholder is `dsl.WORKSPACE_PATH_PLACEHOLDER`.
- When using `dsl.importer` with external artifacts such as OCI ModelCar
  images, do not assume the artifact downloads directly into the workspace.
  Copy the artifact into the workspace in a separate pipeline step.

## Logs

- Pipeline task logs show runtime information for a pipeline step.
- The log viewer displays the last 500 lines of pipeline step logs and
  refreshes every three seconds.
- For KFP SDK or Elyra-generated pipelines using Elyra 2024.1 or later, logs
  include the first script executed in the pipeline step.
- Users can download current step logs or all step logs.
- Logs can include main task container logs and artifact transfer logs.

## JupyterLab And Elyra

- Elyra can create and run AI pipelines within JupyterLab.
- The Elyra pipeline editor is available only in specific JupyterLab workbench
  images.
- Elyra is not available in code-server or RStudio IDEs.
- Elyra is not available in Minimal Python or CUDA-based workbenches.
- For project workbenches, a default runtime configuration is created
  automatically when the project has a pipeline server.
- If a user starts a basic workbench from the dashboard tile, they must create
  a runtime configuration before running or exporting an Elyra pipeline.
- Runtime configurations define connectivity information for the pipeline
  instance and S3-compatible storage.

## DSPA Troubleshooting Signals

- `ObjectStorageAvailable=False` can indicate object-store TLS trust problems,
  inaccessible object storage, or wrong credentials.
- Active RHOAI 3.4 DSPA status uses the `ObjectStoreAvailable` condition name
  for object-store connectivity. Check the live CRD/status before hard-coding
  condition names in validation scripts.
- `DatabaseAvailable=False` can indicate database network timeout, certificate
  trust failure, or a blocked database host.
- `APIServerReady=False` can indicate route creation failure caused by a long
  project name. The official solution is to ensure the OpenShift project name
  is less than 40 characters.
- Missing DSPA service accounts can prevent components from creating replicas;
  if the failure persists after startup, recreate the missing service account.
- Component-wide errors include missing deployments, scaled-down deployments,
  progress failures, replica creation failures, pod failures, CrashLoopBackOff,
  and still-deploying components.

## Do Not Infer

- Do not invent DSPA fields beyond the official examples or active CRD schema.
- Do not treat internal database storage as production recommended.
- Do not copy object storage, database, or OpenShift tokens into Git.
- Do not use the unsupported migration script as normal operating guidance.
- Do not claim cached tasks have new logs for skipped execution.
- Do not use code-server or RStudio for Elyra workflows.
- Do not copy mutable example model artifacts into demo manifests without
  validating provenance and versioning.
