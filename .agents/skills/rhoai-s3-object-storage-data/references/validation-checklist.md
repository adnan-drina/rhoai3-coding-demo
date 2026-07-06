# Validation Checklist

Use this checklist before accepting S3-compatible object storage documentation,
notebooks, demo scripts, or GitOps-adjacent configuration.

## Source Alignment

- Product links use the active baseline in `docs/PLATFORM_BASELINE.md`.
- The official S3-compatible object storage guide is recorded when the workflow
  is introduced.
- Connection type template administration is delegated to
  `rhoai-connection-types`.
- Storage class administration is delegated to `rhoai-storage-classes`.
- Trusted CA bundle changes are delegated to `rhoai-certificate-management`.
- AI Pipelines object-store configuration is delegated to
  `rhoai-kfp-pipeline-authoring`.

## Credential Review

- S3 credentials are scoped to the specific project bucket or resource set.
- Shared cross-project credentials are not used.
- Access keys, secret keys, session tokens, and provider API keys are not
  committed to Git or saved in notebooks.
- IAM or bucket policies grant only the minimum permissions required.
- Workbench connection environment variables are verified before use.

## Workbench And Client Review

- The workbench exists and is running before the workflow starts.
- The workbench has a configured connection for the S3-compatible object store.
- Boto3 and required Python libraries are available in the workbench session.
- Client setup reads credentials and endpoint from environment variables rather
  than hard-coded values.
- S3 signature version and endpoint URL are configured consistently with the
  provider.
- Initial `list_buckets()` connectivity check succeeds before object
  operations are attempted.

## Bucket And Object Review

- Bucket names and object keys are placeholders or project-owned values, not
  unrelated examples.
- Bucket creation is allowed by the scoped credentials before documenting it.
- Object listing handles empty buckets without assuming `Contents` exists.
- Download target paths are workbench-local and intentional.
- Upload source paths exist in the workbench.
- Copy operations identify both source and destination buckets and keys.
- Object deletion is verified with a post-delete listing.
- Bucket deletion is attempted only after the bucket is empty.

## Endpoint Review

- MinIO endpoints include protocol, hostname or cluster IP, and port when
  required.
- Amazon S3 endpoints use HTTPS and the expected region-specific format.
- Other S3-compatible endpoints follow provider documentation.
- Endpoint reachability is verified from the OpenShift AI environment.
- Authentication failures are separated from endpoint-format failures.

## Self-Signed Certificate Review

- In-cluster object storage or database endpoints using private/self-signed CAs
  have a reviewed trust path.
- `DSCInitialization` trusted CA bundle changes are reviewed with
  `rhoai-certificate-management`.
- CA bundle changes are treated as cluster/platform configuration, not
  notebook-only behavior.
- Verification confirms the consuming component starts successfully after CA
  trust changes.

## Optional Read-Only Checks

Run only after following the OpenShift safety guard in `AGENTS.md`:

```bash
oc get notebook -n <namespace>
oc get secret -n <namespace>
oc get configmap -n <namespace>
oc get dscinitialization default-dsci -o yaml
```

Workbench-local Python checks:

```python
s3_client.list_buckets()
s3_client.list_objects_v2(Bucket="<bucket-name>")
```

## Fail Conditions

Stop and correct the work if any of these are true:

- S3 credentials are shared across projects.
- Secret values are committed or saved in notebooks.
- Endpoint examples omit required provider-specific format checks.
- Destructive delete operations are included without pre-delete and post-delete
  verification.
- Bucket deletion is attempted without confirming the bucket is empty.
- In-cluster self-signed certificate trust is handled only by disabling TLS
  verification instead of reviewing CA trust.
