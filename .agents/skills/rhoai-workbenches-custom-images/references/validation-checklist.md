# Validation Checklist

Use this checklist before approving workbench or custom image GitOps.

## Source Review

- Product links use the active baseline in `docs/PLATFORM_BASELINE.md`.
- The workbench image and Notebook fields are based on official docs or active
  CRD verification.
- Red Hat support boundaries are explicit: custom image availability in
  OpenShift AI is supported, custom image contents are customer-owned.
- Dashboard-generated timestamps and last-activity annotations are not copied
  into stable GitOps desired state unless intentionally required.
- Image references are pinned or otherwise governed according to project image
  policy.
- Secrets, connection values, and private registry credentials are not committed
  directly.

## Custom Image Build Review

Before publishing custom workbench image guidance:

```bash
oc get imagestream -n redhat-ods-applications
oc get imagestream <base-image> -n redhat-ods-applications -o yaml
```

Check:

- Base image comes from a current default OpenShift AI image or another
  approved compatible base image.
- If Elyra compatibility is required, the base image already contains Elyra.
- OS package installation switches to `USER 0` only for package operations and
  returns to `USER 1001`.
- Python package installation runs as `USER 1001` unless there is a documented
  reason not to.
- The image supports OpenShift random UID execution with GID `0`.
- Persistent data defaults to `/opt/app-root/src`; artifacts are not placed in
  `$HOME` expecting to survive the workbench PVC mount.
- Non-Jupyter IDEs implement `/api` and serve content under `/${NB_PREFIX}`.
- `${NB_PREFIX}/api/kernels` behavior is considered if idle culling is needed.
- `dnf install` and `dnf update` examples mention the required Red Hat
  subscription/package-content boundary.

## Dashboard Import Review

Before relying on dashboard import:

```text
OpenShift AI dashboard -> Settings -> Environment setup -> Workbench images
```

Check:

- Operator has OpenShift AI administrator privileges.
- `dashboardConfig: disableBYONImageStream` is not disabling the Workbench
  images menu when import is required.
- Image registry is reachable from OpenShift AI.
- Image location uses the intended tag or digest.
- Name, description, software metadata, package metadata, and accelerator
  identifier are accurate.
- NVIDIA accelerator metadata is used only after GPU support is enabled and the
  accelerator identifier is known.
- Imported image appears in the Workbench images table and during workbench
  creation.

## ImageStream Review

Before creating or changing custom workbench images:

```bash
oc explain imagestream.spec
oc get imagestream -n redhat-ods-applications
```

Check:

- `ImageStream` lives in `redhat-ods-applications` unless intentionally scoped
  elsewhere.
- `opendatahub.io/dashboard: "true"` is set.
- `opendatahub.io/notebook-image: "true"` is set.
- `opendatahub.io/component: "true"` is set.
- `platform.opendatahub.io/part-of: "workbenches"` is set when using the
  dashboard discovery pattern.
- `app.kubernetes.io/part-of: "workbenches"` is set.
- `app.kubernetes.io/created-by: byon` is set for bring-your-own images.
- `opendatahub.io/notebook-image-name` and
  `opendatahub.io/notebook-image-desc` are user-meaningful.
- Tag annotations accurately describe dependencies, software versions,
  recommended/default status, outdated status, and build provenance.

## Notebook Review

Before creating or changing workbenches:

```bash
oc explain notebook.spec
oc get notebook -n <project>
oc describe notebook <name> -n <project>
```

Check:

- Target project exists.
- `notebooks.opendatahub.io/inject-auth: "true"` is present unless there is an
  explicit, documented exception.
- `notebooks.opendatahub.io/inject-oauth` is not used for RHOAI 3.x
  Gateway API workbenches.
- `notebooks.opendatahub.io/last-image-version-git-commit-selection` matches
  the selected ImageStream tag build commit when the workbench uses a
  RHOAI-managed workbench ImageStream.
- Workbench `metadata.name`, `openshift.io/display-name`, dashboard URL,
  Gateway path, and `NOTEBOOK_ARGS` base URL agree.
- `JUPYTER_IMAGE` and container `image` use the same intended image URL.
- Workbench resource requests and limits are explicit.
- PVC name exists or is created in the same GitOps layer.
- `/dev/shm` `emptyDir` is present when required by workloads.
- Custom CA env vars and mounts align with `rhoai-certificate-management`.
- Kueue queue label is used only when the target project has the referenced
  `LocalQueue`.
- For migrated workbenches, the generated HTTPRoute backend targets
  `<workbench-name>-kube-rbac-proxy:8443`, not the Jupyter container service
  directly.
- For migrated workbenches, the Notebook template, generated StatefulSet, and
  running pod all include the controller-injected `kube-rbac-proxy` sidecar.
- For migrated workbenches, the generated `*-kube-rbac-proxy` Service has a
  ready EndpointSlice endpoint on port `8443`; a Service and HTTPRoute without
  a ready proxy endpoint can still produce `no healthy upstream`.
- Migrating an existing workbench from `inject-oauth` to `inject-auth` can
  require deleting only the generated StatefulSet so the controller recreates
  it from the corrected Notebook spec. Preserve the Notebook and PVC.
- Controller-injected auth-proxy operands are not pinned as static GitOps
  desired state unless Red Hat documentation exposes them as supported user
  configuration.

## GitOps Review

- Long-lived `ImageStream`, `Notebook`, PVC, ConfigMap, Secret reference, and
  RBAC resources are managed through ArgoCD.
- Sync waves ensure dependencies exist before the `Notebook` reconciles.
- `SkipDryRunOnMissingResource=true` is used only where CRD availability
  requires it.
- README or operations notes explain why a workbench is needed and which image
  it uses.

## Fail Conditions

- A custom image is expected in the dashboard without required labels or
  annotations.
- A dashboard import is expected while the Workbench images menu is disabled.
- A custom image is treated as Red Hat-supported beyond the documented support
  boundary.
- A non-Jupyter image lacks the `/api` or `NB_PREFIX` behavior needed by
  OpenShift AI probes and routing.
- A workbench references an image URL that does not exist.
- OAuth logout URL, Jupyter base URL, project, and workbench name are
  inconsistent.
- Kueue queue label references a missing `LocalQueue`.
- Private credentials or connection secrets are committed.
- Dashboard-generated runtime annotations are treated as authoritative desired
  state without a reason.
- A Gateway-backed workbench is marked ready while its auth-proxy Service has
  no ready `8443` endpoint.
