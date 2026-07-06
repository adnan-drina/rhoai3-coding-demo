# Official Doc Extraction

Extract only behavior supported by the official Working with connected
applications guide and active-baseline linked Red Hat docs.

## Connected Application Purpose

- Connected applications extend OpenShift AI capabilities by connecting to
  open source and third-party applications.
- The official guide gives examples such as Starburst and IBM watsonx.ai.
- Users can remove unused applications from the dashboard after an
  administrator disables them.

## Viewing Connected Applications

- Users view available open source and third-party connected applications from
  `Applications -> Explore` in the OpenShift AI dashboard.
- The Explore page displays applications that are available for use with
  OpenShift AI.
- Users can click a tile for more information or to access the Enable button.
- The Enable button is visible only when an application does not require an
  OpenShift Operator installation.

## Enabling Connected Applications

- SaaS-based applications must be enabled before they can be used with
  OpenShift AI.
- On-cluster applications are enabled automatically.
- Connected applications can be installed or enabled through:
  - the Explore page on the OpenShift AI dashboard
  - Operator installation from the software catalog through OLM
  - installing the application as an Operator to the cluster
- Deployments containing Operators installed from the software catalog might
  not be fully supported by Red Hat.
- Some application tiles expose an API endpoint on the Enabled page.
- Some applications cannot be accessed directly from their tile. For example,
  OpenVINO provides notebook images for use in Jupyter and does not provide an
  endpoint link from its tile.
- Endpoint URLs can be useful as environment variables in notebook
  environments.
- Some independent software vendor applications must be installed in specific
  namespaces; the tile specifies the required namespace.
- Learning resources and documentation are available from the Resources page or
  from links on the Enabled tile.
- Enabling a connected application requires the application to have already
  been installed or configured by an administrator.
- If prompted, users enter the application's service key and then confirm
  enablement.
- Successful enablement displays the application on the Enabled page and shows
  the API endpoint on the tile when the application exposes one.

## Removing Disabled Application Tiles

- Users can manually remove an unused application tile from the Enabled page
  only after an administrator has disabled the application.
- Disabled application tiles on the Enabled page are marked with a Disabled
  label.
- Removing a disabled tile removes it from the user's Enabled page.
- The guide does not make tile removal equivalent to uninstalling the backing
  application or Operator.

## Start Basic Workbench

- OpenShift AI provides Start basic workbench as an enabled application.
- Basic workbench is intended for situations where users do not need their own
  projects, or where users want to open a Jupyter notebook developed outside
  OpenShift AI with no dependencies on other environments.
- The preferred way to access workbenches is through a project.
- Project workbenches organize data science work and add functionality such as
  connections for data access and saving models and pipelines.
- Basic workbench uses a server-client architecture: the workbench runs in a
  container on the OpenShift cluster and the IDE opens in the user's browser.
- Processing occurs on the cluster, and data being processed stays on the
  cluster.

## Starting Basic Workbench

- Users start basic workbench from `Applications -> Enabled`.
- If the user sees an Access permission needed message, the user is not in the
  default OpenShift AI user group or administrator group when groups are
  configured. Route this to `rhoai-users-groups-access`.
- Users select:
  - workbench image
  - image version when multiple versions exist
  - container size
  - optional accelerator
  - accelerator count when accelerators are selected
  - optional environment variables
  - whether to start the workbench in the current tab
- When a new workbench image version is released, the previous version remains
  available and supported on the cluster to give users time to migrate.
- Accelerator support is limited to specific workbench images. For GPUs, the
  official guide identifies AMD ROCm, PyTorch, TensorFlow, and CUDA workbench
  images.
- Accelerator selection is available only when accelerators are enabled on the
  cluster.
- Environment variables are stored so users enter them only once.
- Sensitive environment variable values must use the Secret checkbox.
- Workbench startup can take several minutes. Users can view the Events log tab
  for additional startup information.
- Users should cancel startup only if they intend to cancel workbench creation.
- Verification: the IDE interface opens.
- If "Unable to load workbench configuration options" appears, users should
  contact an administrator to review logs associated with the workbench pod.

## Basic Workbench JupyterLab Handoff

- The guide repeats JupyterLab notebook creation, local upload, Git clone,
  Git pull, Git push, package listing, and `requirements.txt` installation
  workflows.
- Use `rhoai-data-science-ide-workflows` for detailed JupyterLab and package
  workflow guidance.
- Use `rhoai-basic-workbenches` for administrator-side basic workbench
  troubleshooting and management.

## Updating Basic Workbench Settings

- Users can update basic workbench settings by stopping and relaunching the
  workbench.
- Example reason: a server runs out of memory and needs a larger container
  size.
- Users open the Hub Control Panel from JupyterLab, stop the workbench, update
  settings, and start the workbench again.
- Verification: the workbench starts and contains updated settings.

## Do Not Infer

- Do not assume an application tile means the backing application is installed,
  configured, reachable, or supported.
- Do not assume every connected application exposes an endpoint from its tile.
- Do not use this user guide to author `OdhApplication` or dashboard
  configuration manifests.
- Do not treat removing a disabled tile as uninstalling an application or
  Operator.
- Do not place service keys, endpoint credentials, or environment-variable
  secret values in Git.
- Do not use Start basic workbench as the default architecture for demo steps
  that need project connections, storage, models, or pipelines.
