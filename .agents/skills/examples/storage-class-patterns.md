# Storage Class Patterns

These examples are dashboard runbook and review patterns. They are not active
GitOps manifests because the captured Red Hat chapter describes dashboard
administration and endpoint formatting.

## Dashboard Path

```text
OpenShift AI dashboard -> Settings -> Cluster settings -> Storage classes
```

Use this page to enable or disable storage classes for OpenShift AI users, edit
OpenShift AI display metadata, select visible access modes, and set the
OpenShift AI default storage class.

## Storage Class Acceptance Matrix

| Use case | Preferred access mode | Review notes |
|----------|-----------------------|--------------|
| Individual workbench data | `RWO` | Default and suitable for most single-user workloads |
| Shared read-only reference data | `ROX` | Use when many workbenches need the same data without writes |
| Collaborative shared files | `RWX` | Confirm backend support and document shared-write safety expectations |
| Single-pod restricted storage | `RWOP` | Use only when the single-pod, single-node behavior is intentional |

## Enable Storage Class Runbook

```text
1. Confirm the storage class exists in OpenShift.
2. Log in to OpenShift AI as an administrator.
3. Open Settings -> Cluster settings -> Storage classes.
4. Enable the target storage class.
5. Edit display name and description if user-facing names need clarification.
6. Select access modes that match verified backend capabilities.
7. Save.
8. Verify the class is available when adding cluster storage to a project or
   workbench.
```

Review points:

- Display name and description are OpenShift AI-only metadata.
- `RWO` remains the safe default for individual workloads.
- Do not enable `RWX` for collaboration without data integrity and security
  notes.

## Set OpenShift AI Default Storage Class Runbook

```text
1. Confirm the target storage class is appropriate for common demo workloads.
2. Open Settings -> Cluster settings -> Storage classes.
3. Enable the target storage class if needed.
4. Select Set as default on the target row.
5. Create or inspect a new project or workbench storage request.
6. Confirm the selected default is preselected.
```

Review points:

- This default is for OpenShift AI and can differ from the OpenShift cluster
  default.
- Do not change the default during a demo without checking downstream storage
  creation flows.

## RWX Operations Note Template

```markdown
## Shared Storage

Shared storage access mode: `ReadWriteMany (RWX)`
Storage class: `<storage-class-name>`
Intended users or workbenches: `<trusted users/workbenches>`

Use this shared volume only for workflows designed for simultaneous access.
Avoid concurrent writes to the same file unless the tool handles locking or
transactions. Back up shared data regularly.
```

## Object Storage Endpoint Patterns

```text
# On-cluster MinIO shape
http://minio-cluster.local:9000

# Amazon S3 shape
https://<bucket-name>.s3.<region>.amazonaws.com

# Other S3-compatible stores
https://<provider-specific-endpoint>
```

Review points:

- Match protocol to the provider and TLS setup.
- Replace bucket and region placeholders before use.
- Verify endpoint reachability from the OpenShift AI cluster.
- Store credentials through the component-specific connection or secret
  workflow, not in documentation examples.

## Read-Only Storage Checks

Run only after following the repository OpenShift safety guard:

```bash
oc get storageclass
oc describe storageclass <storage-class-name>
oc get pvc -A
oc describe pvc <pvc-name> -n <project-name>
```

Review points:

- Use these checks to inspect current cluster state.
- Do not use read-only inspection as proof that untested shared write
  workflows are safe.
