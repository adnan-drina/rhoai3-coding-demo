# Official Documentation Extraction

This extraction is derived from the official RHOAI 3.4 chapter captured in
`source-capture.md`.

## Concept Model

OpenShift cluster administrators create storage classes to describe storage
available in the cluster. These storage classes can represent different
quality-of-service levels, backup policies, or custom policies.

OpenShift AI uses persistent storage for workbenches, project data, and model
training. Persistent storage is provisioned through OpenShift storage classes
and persistent volumes. Access modes control how the resulting volumes can be
mounted and used.

Storage classes available in OpenShift AI come from the underlying OpenShift
cluster. Cluster administrators create and configure those OpenShift storage
classes. OpenShift AI administrators enable selected storage classes and access
modes for use in OpenShift AI.

## Access Modes

Storage classes can support different access modes depending on the backend.
When more than one access mode is available, users can select the mode that
fits the requested storage use case.

| Access mode | Official behavior summary |
|-------------|---------------------------|
| `ReadWriteOnce (RWO)` | Default mode. Storage can be attached to a single workbench or pod at a time. Suitable for most individual workloads. Always enabled by default and cannot be disabled by the administrator. |
| `ReadWriteMany (RWX)` | Storage can be attached to many workbenches at the same time. Enables shared data access and introduces data risks. |
| `ReadOnlyMany (ROX)` | Storage can be attached to many workbenches as read-only. Useful for shared reference data. |
| `ReadWriteOncePod (RWOP)` | Storage can be attached to a single pod on a single node with read-write permissions. Similar to `RWO` with additional node-level restrictions. |

If an access mode has unknown support, the dashboard can warn the operator, but
the operator can continue and save the selection. Only access modes enabled by
cluster and OpenShift AI administrators are visible to users.

## Shared Storage With RWX

`ReadWriteMany (RWX)` allows multiple workbenches to access and write to the
same storage volume at the same time. Use RWX only for collaborative work where
multiple users need shared datasets or project files.

Risks to document before using RWX:

- simultaneous writes can corrupt or lose data when tools are not designed for
  shared write access
- a compromised workbench with access to shared storage can put all data on the
  shared volume at risk
- deleting or editing files affects all users sharing the volume

Safe-use expectations:

- use tools and workflows that handle simultaneous writes safely, such as
  databases or distributed processing frameworks
- limit RWX access to trusted users and secure workbenches
- back up shared data regularly
- prefer `ReadWriteOnce (RWO)` for individual tasks

## Configuring Storage Class Settings

Prerequisite:

- The operator is logged in to OpenShift AI with administrator privileges.

Official dashboard path:

```text
OpenShift AI dashboard -> Settings -> Cluster settings -> Storage classes
```

The Storage classes page shows the storage classes defined in the underlying
OpenShift cluster.

OpenShift AI administrators can manage these OpenShift AI settings:

- display name
- description
- access modes
- whether users can use the storage class when creating or editing cluster
  storage

These settings do not affect the storage class within OpenShift.

Workflow:

1. Open Settings -> Cluster settings -> Storage classes.
2. Use the Enable column toggle to enable or disable the storage class for
   users.
3. Use the row action menu and choose Edit to change OpenShift AI details.
4. Optionally update the display name.
5. Optionally update the description.
6. For storage classes that support multiple access modes, select the access
   mode that should be available.
7. Save.

Verification:

- An enabled storage class is available when a user adds cluster storage to a
  project or workbench.
- A disabled storage class is not available when a user adds cluster storage to
  a project or workbench.
- Edited display names appear when a user adds cluster storage to a project or
  workbench.

## Configuring The OpenShift AI Default Storage Class

OpenShift AI administrators can configure the default storage class for
OpenShift AI separately from the default storage class in OpenShift.

Prerequisite:

- The operator is logged in to OpenShift AI with administrator privileges.

Workflow:

1. Open Settings -> Cluster settings -> Storage classes.
2. If the desired storage class is not enabled, enable it.
3. On the target row, select Set as default.

Verification:

- When a user adds cluster storage to a project or workbench, the OpenShift AI
  default storage class is automatically selected.

## Object Storage Endpoint Formatting

The chapter provides endpoint-format guidance for Amazon S3, MinIO, and other
S3-compatible stores. Correct endpoint format reduces connection errors and
avoids accidental storage access failures.

### MinIO On-Cluster

For on-cluster MinIO, use a local endpoint URL format:

- prefix the endpoint with `http://` or `https://` according to the MinIO TLS
  setup
- include the cluster IP or hostname
- include the port when the MinIO instance requires one

Example shape:

```text
http://minio-cluster.local:9000
```

Verify that the MinIO instance is reachable inside the cluster by checking DNS
and network configuration.

### Amazon S3

For Amazon S3, use region-specific HTTPS endpoints in this shape:

```text
https://<bucket-name>.s3.<region>.amazonaws.com
```

Replace `<bucket-name>` and `<region>` with the real bucket and region.
Confirm the bucket is in the correct region for security and compliance.

### Other S3-Compatible Stores

For other S3-compatible providers:

- use the provider's documented base URL
- prefer `https://`
- include bucket and region parameters in the format required by the provider
- verify provider-specific endpoint requirements before use

Incorrectly formatted endpoints can cause access-denied or connectivity errors.

## Verification And Troubleshooting

After configuring an endpoint, verify connectivity with a test upload or by
accessing object storage through the OpenShift AI dashboard.

Troubleshooting checks:

- endpoint is reachable from the OpenShift AI cluster
- credentials are correct
- endpoint URL has no typos or missing components

## Out Of Scope For This Chapter

This chapter does not define:

- how to create OpenShift `StorageClass` resources
- how to install an RWX-capable storage backend
- how to resize PVCs
- how to set the cluster default PVC size
- how to configure AI pipelines, model registry, Feature Store, or model
  serving persistence
- a GitOps schema for OpenShift AI storage class dashboard settings
- object storage bucket creation, IAM policy, or credential rotation
