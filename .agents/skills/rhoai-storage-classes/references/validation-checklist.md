# Validation Checklist

Use this checklist before accepting storage class documentation, runbooks, or
operations changes.

## Source Review

- Product links use the active baseline in `docs/PLATFORM_BASELINE.md`.
- The official chapter URL uses the active `/3.4/` baseline path.
- The work is about OpenShift AI storage class visibility, metadata, access
  modes, default selection, or object storage endpoint format.
- Underlying OpenShift storage backend creation is delegated to OpenShift
  storage documentation and platform operations.
- Cluster default PVC size is delegated to `rhoai-cluster-pvc-size`.
- Connection type form design is delegated to `rhoai-connection-types`.

## Storage Class Review

- Operator has OpenShift AI administrator privileges.
- The storage class exists in the underlying OpenShift cluster.
- OpenShift AI display name and description are treated as OpenShift AI-only
  metadata.
- Enablement matches whether users should be able to select the class when
  adding cluster storage.
- Disabling a storage class is not expected to remove or alter existing
  OpenShift `StorageClass` resources.
- The OpenShift AI default storage class is enabled before it is set as
  default.
- User workflows are checked after changing storage class visibility or the
  OpenShift AI default.

## Access Mode Review

- `RWO` remains available because it is always enabled by default.
- `RWX` is enabled only when the backend is expected to support shared
  read-write access.
- `RWX` use cases document data integrity, security, trust, and backup
  expectations.
- `ROX` is considered for shared reference data that should not be modified by
  consumers.
- `RWOP` is used only when the single-pod, single-node restriction is
  intentional.
- Unknown access-mode support warnings are not ignored without recording a
  verification plan.

## Dashboard Procedure Review

Use the official dashboard path:

```text
OpenShift AI dashboard -> Settings -> Cluster settings -> Storage classes
```

For storage class settings:

- enable or disable the class in the Enable column
- use Edit only for OpenShift AI display name, description, and access mode
  settings
- save changes
- verify user selection behavior from a project or workbench storage flow

For OpenShift AI default storage class:

- enable the target storage class if needed
- choose Set as default
- verify new project or workbench storage creation selects that class by
  default

## Object Storage Endpoint Review

- MinIO endpoints use `http://` or `https://`, a cluster-reachable host or IP,
  and a port when required by the MinIO deployment.
- Amazon S3 endpoints use `https://<bucket-name>.s3.<region>.amazonaws.com`.
- S3-compatible endpoints follow the provider's required URL format.
- Placeholder values are replaced with real bucket, region, and provider
  values before use.
- Endpoint reachability is verified from the OpenShift AI cluster.
- Credentials are verified separately from endpoint formatting.

## Optional Read-Only Checks

Run only after following the OpenShift safety guard in `AGENTS.md`:

```bash
oc get storageclass
oc describe storageclass <storage-class-name>
oc get pvc -A
oc describe pvc <pvc-name> -n <project-name>
```

Review points:

- confirm the storage class exists
- inspect provisioner and available parameters without changing the class
- inspect PVC storage class, requested size, access mode, and binding state
- do not infer RWX support from a storage class name alone

## GitOps Review

- Do not add a GitOps representation for OpenShift AI storage class dashboard
  settings until official docs or active schema verification identifies the
  backing resource.
- If future GitOps support is added, preserve unrelated dashboard and storage
  settings.
- Document selected demo defaults, RWX assumptions, and object storage endpoint
  patterns in `docs/OPERATIONS.md` when implemented.

## Fail Conditions

- Documentation implies OpenShift AI dashboard storage class settings modify
  the underlying OpenShift storage class.
- `RWX` is enabled or promoted without a verified backend and shared-write
  safety notes.
- The OpenShift AI default storage class is set to a disabled storage class.
- Object storage endpoints omit protocol, bucket, region, host, or required
  port details.
- A GitOps manifest uses an unverified dashboard storage settings field.
- Live storage changes are made without the repository OpenShift safety guard.
