# Validation Checklist

Use this checklist before accepting connected application documentation,
runbooks, dashboard guidance, or demo examples.

## Source Alignment

- Product links use the active baseline in `docs/PLATFORM_BASELINE.md`.
- The Working with connected applications guide is recorded when connected
  application behavior is introduced.
- Administrator dashboard tile authoring is delegated to
  `rhoai-dashboard-applications`.
- Global OpenShift AI access management is delegated to
  `rhoai-users-groups-access`.
- Project workbench lifecycle is delegated to `rhoai-project-workflows`.
- JupyterLab, code-server, Git, and package workflows are delegated to
  `rhoai-data-science-ide-workflows`.
- Basic workbench administrator controls are delegated to
  `rhoai-basic-workbenches`.

## Discovery And Enablement Review

- Dashboard path is correct: `Applications -> Explore`.
- Enablement examples distinguish SaaS-based applications from on-cluster
  applications that are enabled automatically.
- The Enable button is not expected for applications that require Operator
  installation.
- Operator installation is treated as administrator or platform work, not a
  user dashboard-only operation.
- Software-catalog or third-party Operator support posture is not overstated.
- Required ISV namespaces are checked from the application tile and official
  source material before implementation.
- Service keys and application credentials are never committed.

## Enabled Tile Review

- Successful enablement is verified on `Applications -> Enabled`.
- API endpoints are recorded only when displayed on the Enabled tile.
- Application tiles that do not expose endpoints are documented as resource or
  documentation entry points instead of runtime URLs.
- Endpoint URLs used in notebooks are stored as environment variables or
  project secrets, not hard-coded credentials.
- Resources and documentation links point to official or vendor-provided
  sources.

## Disabled Tile Removal Review

- The application was disabled by an administrator before user tile removal is
  described.
- The tile has a Disabled label before removal.
- Removing a disabled tile is not described as uninstalling the backing
  application or Operator.
- Post-removal verification checks that the tile no longer appears on the
  Enabled page.

## Start Basic Workbench Review

- The demo explains why Start basic workbench is being used instead of a
  project workbench.
- Project workbenches remain the preferred pattern for data, models,
  connections, storage, and pipelines.
- Access permission errors are routed to OpenShift AI group membership review.
- Workbench image, version, container size, accelerator selection, and
  environment variables are intentional.
- Sensitive environment variables use Secret handling.
- Accelerator use is allowed only when accelerators are enabled and the
  selected image supports the accelerator type.
- Events log capture is included for startup troubleshooting.
- "Unable to load workbench configuration options" is routed to administrator
  pod-log review.

## JupyterLab And Package Review

- Notebook, Git, and package workflows are not duplicated when
  `rhoai-data-science-ide-workflows` already covers them.
- `requirements.txt` is used for repeatable packages.
- Exact versions are used where stability matters.
- Git credentials and tokens are not committed.

## Optional Read-Only Checks

Run only after following the OpenShift safety guard in `AGENTS.md`:

```bash
oc get odhapplications.dashboard.opendatahub.io -A
oc get odhdashboardconfig.opendatahub.io -A
oc get notebooks.kubeflow.org -A
oc get pods -A | rg -i 'jupyter|notebook|workbench'
```

Dashboard checks:

```text
Applications -> Explore
Applications -> Enabled
Applications -> Resources
```

## Fail Conditions

Stop and correct the work if any of these are true:

- A tile is treated as proof of installed, configured, supported application
  runtime.
- Service keys, passwords, API tokens, or secret environment-variable values
  appear in committed content.
- Removing a disabled tile is described as uninstalling an application.
- Start basic workbench is used for workflows that require project-scoped
  connections, storage, models, or pipelines without justification.
- Accelerator use is documented without enabled cluster accelerator support and
  supported image selection.
- Administrator manifest fields are guessed from the user-facing connected
  applications guide.
