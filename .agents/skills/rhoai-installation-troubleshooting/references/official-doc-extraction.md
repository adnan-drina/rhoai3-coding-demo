# Official Doc Extraction

This extraction is derived from the official RHOAI 3.4 chapter captured in
`source-capture.md`.

## General Guidance

If an installation problem is not covered by the troubleshooting chapter or the
release notes, contact Red Hat Support. When opening a support case, include
cluster debugging information collected with the Red Hat OpenShift AI
must-gather workflow.

Operator log verbosity can be adjusted when more or less diagnostic detail is
needed. Use `rhoai-logs-and-audit-records` for logger configuration details.

## Symptom Matrix

| Symptom | Official signal | Diagnosis | Official resolution |
|---------|-----------------|-----------|---------------------|
| Operator cannot be retrieved from image registry | `Failure to pull from quay` | Check OpenShift Events for the image pull error. Causes can include registry availability, network connection, or cluster health. | Contact Red Hat Support. |
| Unsupported infrastructure | Operator pod logs contain `ERROR: Deploying on $infrastructure, which is not supported. Failing Installation` | Inspect the failing `rhods-operator` pod logs in `redhat-ods-operator` or all projects. | Confirm the environment is fully supported before a new install. Use the supported configurations source. |
| OpenShift AI custom resource creation fails | Operator pod logs contain `ERROR: Attempt to create the ODH CR failed.` | Inspect the failing `rhods-operator` pod logs. | Contact Red Hat Support. |
| OpenShift AI Notebooks custom resource creation fails | Operator pod logs contain `ERROR: Attempt to create the RHODS Notebooks CR failed.` | Inspect the failing `rhods-operator` pod logs. | Contact Red Hat Support. |
| Dashboard is not accessible after install | Required namespaces are `Active`, but dashboard access fails due to an errored pod | In the OpenShift console, show all projects, filter pods to statuses other than Running and Completed, then inspect the failing pod status/logs. | Use the pod status link or pod Logs tab for more detail and targeted troubleshooting. |
| Reinstall fails after CLI uninstall | Operator logs include `unable to find DSCInitialization` while reconciling `Auth` | A leftover `Auth` custom resource from the previous installation can cause this after uninstall and before reinstall. | Uninstall OpenShift AI Operator, delete the `Auth` custom resource from `services.platform.opendatahub.io`, then install again. |
| dedicated-admins RBAC policy cannot be created | Operator pod logs contain `ERROR: Attempt to create the RBAC policy for dedicated admins group in $target_project failed.` | Inspect the failing `rhods-operator` pod logs. | Contact Red Hat Support. |
| ODH parameter secret does not get created | Operator pod logs contain `ERROR: Addon managed odh parameter secret does not exist.` | Inspect the failing `rhods-operator` pod logs. | Contact Red Hat Support. |

## Operator Log Inspection Pattern

The official diagnosis path repeatedly uses the failing `rhods-operator` pod:

1. Open the Administrator perspective in the OpenShift web console.
2. Go to Workloads, then Pods.
3. Set Project to All Projects or `redhat-ods-operator`.
4. Open the `rhods-operator-<random string>` pod with an error status.
5. Open Logs and select the `rhods-operator` container.
6. Search for the official error signal.

CLI equivalent patterns are in
`examples/install-troubleshooting-symptom-map.md`.

## Reinstall Cleanup Boundary

The official local remediation in this chapter is specific: if reinstall fails
because a previous `Auth` custom resource was not deleted, uninstall the
OpenShift AI Operator, delete the `Auth` custom resource, and install again.

Do not generalize this into broad cleanup of OpenShift AI CRDs or namespaces.
Use the official uninstall process and confirm user intent before deleting live
resources.

## Unresolved Items

This chapter does not define:

- registry/network remediation for `Failure to pull from quay`
- local remediation for failed ODH CR creation
- local remediation for failed Notebooks CR creation
- local remediation for dedicated-admins RBAC creation failure
- local remediation for missing ODH parameter secret
- detailed dashboard pod-specific fixes
- full must-gather commands

Use Red Hat Support, the must-gather article, release notes, and relevant
component documentation before proposing changes in those areas.
