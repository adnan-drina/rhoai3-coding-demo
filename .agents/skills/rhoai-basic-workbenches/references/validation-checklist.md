# Validation Checklist

Use this checklist before accepting basic workbench documentation, runbooks, or
operations changes.

## Source Review

- Product links use the active baseline in `docs/PLATFORM_BASELINE.md`.
- The official chapter URL uses the active `/3.4/` baseline path.
- The work is about basic workbench administration, idle timeout, tolerations,
  or administrator troubleshooting.
- Project workbench creation and custom image authoring are delegated to
  `rhoai-workbenches-custom-images` and related workbench skills.
- User group changes are delegated to `rhoai-users-groups-access`.
- Storage size and storage class changes are delegated to
  `rhoai-cluster-pvc-size` and `rhoai-storage-classes`.

## Administration Review

- Operator has OpenShift AI administrator privileges.
- The Start basic workbench tile is visible on Applications -> Enabled.
- The Administration tab is reachable from the Start basic workbench
  application.
- Starting another user's workbench uses the Administration tab and a reviewed
  Start a basic workbench form.
- Accessing another user's workbench is justified as troubleshooting or support.
- Stopping another user's workbench is justified by resource reduction,
  troubleshooting, shutdown preparation, or user-resource cleanup.
- Stop all workbenches is used only when broad interruption is acceptable.

## Idle Timeout Review

- The selected timeout is recorded in operations notes when implemented.
- The operator understands that the default is no fixed idle-stop time.
- Any cluster-wide session-disconnect setting is checked because it takes
  precedence over the idle workbench timeout.
- The `notebook-controller-culler-config` ConfigMap is inspected after the
  change.
- `ENABLE_CULLING`, `IDLENESS_CHECK_PERIOD`, and `CULL_IDLE_TIME` match the
  intended behavior.

## Toleration Review

- The toleration key starts with a letter or number.
- The toleration key is no longer than 253 characters.
- The toleration key contains only letters, numbers, hyphens, dots, and
  underscores.
- Matching node taints and target machine pools are documented before the
  setting is used in a demo.
- Existing workbench pods are restarted before expecting the toleration to
  appear.
- Pod details show the expected assigned node and toleration.

## Troubleshooting Review

For Jupyter 404:

- User group membership is checked in OpenShift User Management -> Groups.
- Missing users are added with the user/group access workflow.
- Cases where membership is correct are escalated to Red Hat Support.

For workbench startup failure:

- The workbench namespace is verified as `rhods-notebooks` or the active custom
  workbench namespace.
- A `jupyter-nb-<username>-*` pod search is performed.
- CPU and memory availability are compared with the selected image size.
- Failed `jupyter-nb-*` pod logs are collected before deletion.
- The user can restart the workbench after remediation.

For disk-full errors:

- Pod logs are checked for database or disk full messages.
- Persistent volume expansion uses OpenShift storage guidance.
- User cleanup includes permanent deletion from the JupyterLab trash path when
  files were deleted through the file explorer.

## Optional Read-Only Checks

Run only after following the OpenShift safety guard in `AGENTS.md`:

```bash
oc get configmap notebook-controller-culler-config -n redhat-ods-applications -o yaml
oc get pods -n rhods-notebooks
oc logs <jupyter-nb-pod> -n rhods-notebooks
oc get statefulset -n rhods-notebooks
oc describe pod <jupyter-nb-pod> -n rhods-notebooks
```

If the deployment uses a custom workbench namespace, replace `rhods-notebooks`
with the active namespace.

## GitOps Review

- Do not add GitOps fields for idle timeout or toleration settings until
  official docs or active schema verification identifies the backing resource.
- If future GitOps support is added, preserve unrelated dashboard and
  workbench settings.
- Document chosen timeout, toleration key, and any dedicated workbench node
  pool in `docs/OPERATIONS.md` when implemented.

## Fail Conditions

- Administrator access to another user's workbench is documented as routine
  collaboration rather than support or troubleshooting.
- Stop all workbenches is run during an active demo without an interruption
  note.
- Idle culling is claimed as enabled without checking
  `notebook-controller-culler-config`.
- Tolerations are enabled without matching node taints and restart behavior.
- A failed `jupyter-nb-*` pod is deleted before logs are captured for support.
- Disk cleanup ignores the JupyterLab trash directory.
