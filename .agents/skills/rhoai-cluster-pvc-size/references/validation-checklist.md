# Validation Checklist

Use this checklist before accepting cluster PVC size documentation, runbooks, or
operations changes.

## Source Review

- Product links use the active baseline in `docs/PLATFORM_BASELINE.md`.
- The official chapter URL uses the active `/3.4/` baseline path.
- The work is about the OpenShift AI cluster default PVC size.
- The runbook does not claim existing PVCs are resized by this setting.
- Storage classes, RWX storage, and object storage endpoint formatting are
  delegated to `rhoai-storage-classes`; PVC expansion is delegated to broader
  OpenShift storage guidance.

## Change Planning Review

- Operator has OpenShift AI administrator privileges.
- The new size is recorded with a unit in GiB or MiB.
- The selected size matches expected demo workbench data needs.
- Available cluster storage capacity is considered before increasing the
  default.
- The change is scheduled outside normal working hours when possible.
- Users are warned that a workbench pod restart can cause up to 30 seconds of
  unavailability.

## Dashboard Procedure Review

Use the official dashboard path:

```text
OpenShift AI dashboard -> Settings -> Cluster settings
```

For custom size:

- enter the new value under PVC size
- save changes

For restore:

- click Restore Default
- save changes
- expect the default value to be 20GiB

## Verification Review

After setting a custom size:

- create or inspect a new OpenShift AI PVC through a controlled test workflow
- verify the new PVC uses the configured storage size
- confirm any affected workbench recovered from the restart

After restoring the default:

- create or inspect a new OpenShift AI PVC through a controlled test workflow
- verify the new PVC uses 20GiB
- confirm any affected workbench recovered from the restart

Optional read-only checks after following the safety guard:

```bash
oc get pvc -A
oc describe pvc <pvc-name> -n <project-name>
```

## GitOps Review

- Do not add a GitOps field for this setting until official docs or active
  schema verification identifies the backing field.
- If a future implementation automates this setting, preserve unrelated
  dashboard or platform settings.
- Document the chosen default PVC size in `docs/OPERATIONS.md`.

## Fail Conditions

- A runbook changes PVC size during a critical demo window without noting the
  workbench restart impact.
- The selected size lacks a storage unit.
- Documentation claims existing PVCs are resized automatically.
- The restore workflow uses a value other than the documented 20GiB default.
- A GitOps manifest uses an unverified field for the dashboard setting.
