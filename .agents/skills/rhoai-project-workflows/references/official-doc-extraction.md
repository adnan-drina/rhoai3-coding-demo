# Official Doc Extraction

Extract only behavior supported by the official Working on projects guide and
active-baseline linked Red Hat docs.

## Project Lifecycle

- An OpenShift AI project organizes data science work in one place and supports
  collaboration across developers and data scientists.
- In OpenShift, a project is a Kubernetes namespace with additional
  annotations and is the main way to manage user access to resources.
- A project can include connections, workbenches, deployed models, pipelines,
  cluster storage, model servers, and bias metrics.
- Project resource names:
  - use lowercase letters, numbers, and hyphens
  - are no longer than 30 characters
  - start with a letter
  - end with a letter or number
  - cannot be changed after project creation
- Project display name and description can be edited after creation.
- Deleting a project deletes associated workbenches, AI pipelines, cluster
  storage, and connections. Treat this as permanent data loss.

## Workbench Lifecycle

- A workbench is an isolated area for examining models, working with data, and
  running code such as data preparation or training.
- A workbench is not required only for narrow cases such as serving an existing
  model, but it is needed for most data science workflow tasks.
- Supported IDE choices include JupyterLab, code-server, and RStudio
  (Technology Preview).
- Workbench IDEs use a server-client architecture: the server runs in a
  container on OpenShift and the UI is displayed in the user's browser.
- Workbenches can use connections and cluster storage.
- Workbenches in the same project can share models and data through object
  storage with AI Pipelines and model servers.
- Multiple workbenches can exist in one project when tasks need different
  CPU/RAM/IDE settings or task separation.

## Workbench Images

- Workbench images include tools and libraries for model development.
- Users can select provided images; administrators can create custom images.
- The official guide lists default images including CUDA, Standard Data
  Science, TensorFlow, PyTorch, Minimal Python, TrustyAI, code-server, RStudio
  Server (Technology Preview), CUDA - RStudio Server (Technology Preview),
  ROCm, ROCm-PyTorch, and ROCm-TensorFlow.
- Technology Preview workbench images are not production supported.
- Red Hat supports managing workbenches in OpenShift AI but does not provide
  support for RStudio software itself.
- The code-server workbench image does not support Elyra-based pipelines.
- If extra packages are needed, either install them after launch for ad hoc
  work or use a custom image for repeatability.

## Workbench Creation

- A project must exist before creating a project workbench.
- Choose the workbench name and resource name carefully; workbench resource
  names follow the same format and immutability constraints as project
  resource names.
- Select the image and image version. Prefer the most recently added image when
  the goal is to use the latest packages from a supported image stream.
- If hardware profiles are enabled, select a hardware profile. If not, select
  a container size.
- Hardware profiles are Technology Preview in the RHOAI 3.4 baseline.
- Environment variables can be configured directly or stored as secrets.
- For S3-compatible object storage, the official workflow identifies
  `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` as recommended variable names
  for access credentials.
- Scope object storage credentials to the specific project bucket and minimum
  IAM permissions.
- Cluster storage can be created or existing storage can be attached while
  creating a workbench.
- A storage class cannot be changed after storage is added to a workbench.
- Access mode choices appear only when enabled by the cluster and OpenShift AI
  administrators.

## Connections

- Connections let project resources access data and external services without
  hard-coding endpoints or credentials.
- A project connection can be added, updated, or deleted from the project
  details page.
- Deleting a connection removes it from the project; review dependent
  workbenches, models, and pipelines before removal.
- The connection API is namespace-isolated. Consumers must use connections from
  the same namespace as the workload.
- RBAC must allow the workload or operator to read the referenced connection
  secret.
- Connection validation scope is tied to the expected workload and connection
  type.
- Workload annotations distinguish how connections are consumed by
  `InferenceService` and `LLMInferenceService` resources.
- The official guide includes connection API examples for Amazon
  S3-compatible, URI, and OCI connection types with both `InferenceService` and
  `LLMInferenceService`.

## Cluster Storage

- Persistent storage lets project data survive workbench restarts.
- OpenShift AI cluster storage creates project PVC-backed storage.
- `ReadWriteOnce` is the safer default for individual workbench use.
- `ReadWriteMany` can support collaborative shared storage, but simultaneous
  writes can corrupt or lose data and a compromised workbench can expose shared
  contents.
- Use RWX only when collaboration requires it, with trusted users,
  write-conflict controls, and backups.
- Adding cluster storage can also attach it to an existing workbench.
- When updating cluster storage, display metadata can be changed and size can
  be increased. Size increases can restart the attached workbench.
- To change storage class, create new cluster storage with the target storage
  class, copy data, detach old storage, attach new storage, and verify the new
  storage class and mount path.
- Deleting cluster storage deletes the associated persistent volume claim and
  persistent volume data. Treat this as permanent data loss.

## Project Access

- Project access is managed from the project Permissions tab.
- The documented project permission levels are:
  - Admin: edit project details and manage project access
  - Contributor: view and edit project components such as workbenches,
    connections, and cluster storage
- OpenShift AI administrators and project owners can update project access.
- If the current user is not a cluster administrator, the group Name list might
  not be visible and a manual input field is used instead.
- Removing project access prevents the affected users or groups from performing
  the actions allowed by their previous permission level.

## Project-Scoped Resource Handoff

- Users can access global resources in all OpenShift AI projects and
  project-scoped resources only in the specified project.
- Project-scoped resource types in this guide are workbench images,
  model-serving runtimes for KServe, and hardware profiles.
- All project-scoped resource names must be unique within a project.
- The dashboard configuration option `disableProjectScoped` must be `false` for
  project-scoped resources to be used from the dashboard.
- YAML for project-scoped resources must come from a trusted source such as
  existing verified resources, Git, documentation, or a cluster administrator.
- The project-scoped resource workflow updates `metadata.namespace`,
  `metadata.name`, and documented display-name fields only.

## Do Not Infer

- Do not infer undocumented connection annotation keys, CR fields, or model
  storage schema from this guide alone.
- Do not assume project creation creates workbenches, storage, connections,
  pipelines, or model servers.
- Do not assume RWX is safe for all team use.
- Do not treat Technology Preview image or hardware-profile choices as
  production-supported.
- Do not use a project-level access workflow as a substitute for global
  OpenShift AI user/admin group configuration.
