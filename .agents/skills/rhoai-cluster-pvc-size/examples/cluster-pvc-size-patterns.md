# Cluster PVC Size Patterns

These examples are runbook and review patterns. They are not active GitOps
manifests because the captured Red Hat chapter describes a dashboard workflow.

## Configure Default PVC Size

```text
1. Log in to OpenShift AI as an administrator.
2. Open Settings -> Cluster settings.
3. Under PVC size, enter the desired size.
4. Save changes.
5. Verify that new PVCs use the configured default size.
```

Example values:

```text
20Gi
40Gi
51200Mi
```

Review points:

- Use a unit in GiB or MiB.
- Schedule the change outside a critical demo window.
- Warn users that the workbench pod can restart and be unavailable briefly.

## Restore Default PVC Size

```text
1. Log in to OpenShift AI as an administrator.
2. Open Settings -> Cluster settings.
3. Click Restore Default.
4. Save changes.
5. Verify that new PVCs use 20GiB.
```

Review points:

- The documented default is 20GiB.
- The verification target is new PVCs.
- Existing PVC resize is a different storage workflow.

## Operations Note Template

```markdown
## Cluster Default PVC Size

OpenShift AI default PVC size: `<size>`

Dashboard path:

`OpenShift AI dashboard -> Settings -> Cluster settings`

Changing this setting can restart a workbench pod and make it unavailable for
up to 30 seconds, so changes should be scheduled outside demo windows when
possible.

This setting applies to new PVCs. Existing PVC resizing is not handled by this
runbook.
```

## Read-Only PVC Check

Run only after following the repository OpenShift safety guard:

```bash
oc get pvc -A
oc describe pvc <pvc-name> -n <project-name>
```

Review points:

- Inspect a PVC created after the setting was changed.
- Do not use this check to infer that existing PVCs were resized.
