# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product baseline | `docs/PLATFORM_BASELINE.md` |
| Document title | Connect your workbench to S3-compatible object storage |
| Guide URL | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_data_in_an_s3-compatible_object_store/index |
| Documentation category | Develop / Working with data in an S3-compatible object store |
| Retrieved date | 2026-06-10 |
| Sections used | Preface; 1 Prerequisites; 2 Creating an S3 client; 3 Listing available buckets; 4 Creating a bucket; 5 Listing files in a bucket; 6 Downloading files; 7 Uploading files; 8 Copying files between buckets; 9 Deleting files; 10 Deleting buckets; 11 Object storage endpoints; 11.1 MinIO; 11.2 Amazon S3; 11.3 Other S3-compatible object stores; 11.4 Verification and troubleshooting; 12 Self-signed certificates |

## Related Official Sources

| Source | Role |
|--------|------|
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/creating_a_workbench/index | Workbench creation and IDE access context |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/working_on_projects | Project and connection context |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_resources/managing-connection-types | Connection type template administration |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/installing_and_uninstalling_openshift_ai_self-managed/working-with-certificates_certs | OpenShift AI trusted CA bundle behavior |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/working_with_ai_pipelines | AI Pipelines use of object storage |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_distributed_workloads/index | Distributed training S3-compatible checkpoint context |

## Supporting Project Sources

| Source | Role |
|--------|------|
| `docs/PLATFORM_BASELINE.md` | Active RHOAI/OCP baseline and source hierarchy |
| `AGENTS.md` | OpenShift safety guard and GitOps operating constraints |
| `.agents/skills/rhoai-connection-types/SKILL.md` | Connection type template boundary |
| `.agents/skills/rhoai-storage-classes/SKILL.md` | Persistent storage class boundary |
| `.agents/skills/rhoai-certificate-management/SKILL.md` | Trusted CA bundle boundary |
| `.agents/skills/rhoai-distributed-workload-workflows/SKILL.md` | S3 checkpointing boundary |
| `.agents/skills/rhoai-kfp-pipeline-authoring/SKILL.md` | AI pipeline object storage boundary |

## Source Boundaries

- Product authority: the official Red Hat OpenShift AI 3.4 S3-compatible
  object storage guide above.
- The guide defines workbench user workflows for Boto3-based S3 access and
  object operations.
- It does not replace connection type administration, credential provisioning,
  OpenShift persistent storage class configuration, AI Pipelines storage
  configuration, model registry storage, model-serving storage, or complete
  production object storage administration.
- Verification: workbench state, connection environment variables, Boto3 client
  connectivity, HTTP status codes, bucket/object listing, uploaded/downloaded
  object presence, endpoint reachability, authentication, endpoint formatting,
  and CA trust for self-signed in-cluster services.

## Unresolved Or Environment-Specific Items

- Active demo object storage provider.
  Verification: choose Amazon S3, MinIO, Ceph RGW, IBM Cloud Object Storage, or
  another S3-compatible provider for the clean-slate implementation.
- Active connection environment variable names.
  Verification: inspect the selected OpenShift AI connection type and
  workbench environment before hard-coding variable names.
- Active bucket naming and retention policy.
  Verification: document project ownership, lifecycle, backup, and cleanup in
  `docs/OPERATIONS.md` when implemented.
- Self-signed CA handling for on-cluster storage.
  Verification: update the RHOAI trusted CA bundle only after confirming the
  target endpoint and certificate chain.
