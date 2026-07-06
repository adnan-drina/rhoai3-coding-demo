# Official Documentation Extraction

This extraction is derived from the official RHOAI 3.4 chapter captured in
`source-capture.md`.

## Purpose

The cluster default PVC size controls the storage size requested for new
OpenShift AI persistent volume claims. Administrators can change this default
so requested storage better matches common OpenShift AI workflows.

PVCs are resource requests in the cluster and act as claims to persistent
storage.

## Configure Default PVC Size

Prerequisite:

- The operator is logged in to OpenShift AI with administrator privileges.

Impact:

- Changing the PVC setting restarts the workbench pod.
- The workbench pod can be unavailable for up to 30 seconds.
- Red Hat recommends performing this action outside the organization's typical
  working day.

Official dashboard path:

```text
OpenShift AI dashboard -> Settings -> Cluster settings
```

Procedure:

1. Open Settings -> Cluster settings.
2. Under PVC size, enter a new size in gibibytes or mebibytes.
3. Save changes.

Verification:

- New PVCs are created with the default storage size that was configured.

## Restore Default PVC Size

Prerequisite:

- The operator is logged in to OpenShift AI with administrator privileges.

Official dashboard path:

```text
OpenShift AI dashboard -> Settings -> Cluster settings
```

Procedure:

1. Open Settings -> Cluster settings.
2. Click Restore Default.
3. Save changes.

Default value:

```text
20GiB
```

Verification:

- New PVCs are created with the default storage size of 20GiB.

## Important Boundaries

- The chapter describes a default for new PVCs.
- Do not claim that changing this setting resizes existing PVCs.
- Do not claim a GitOps API field unless official docs or installed schema
  verifies it.
- Do not confuse this setting with storage class configuration, RWX support,
  object storage endpoints, or project-specific PVC cleanup.

## Out Of Scope For This Chapter

This chapter does not define:

- storage class selection or default storage class configuration
- access mode behavior
- object storage endpoint configuration
- existing PVC expansion
- backup and restore procedures
- workbench-specific PVC mount fields
- dashboard backing CR fields for this setting

Use `rhoai-storage-classes` and OpenShift storage documentation for those
broader storage workflows.
