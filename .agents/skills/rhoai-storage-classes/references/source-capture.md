# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product baseline | `docs/PLATFORM_BASELINE.md` |
| Document title | Configure user access, storage, and telemetry in OpenShift AI |
| Chapter title | Chapter 7. Managing storage classes |
| Chapter URL | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_resources/managing-storage-classes |
| Documentation category | Administer / Managing resources |
| Retrieved date | 2026-06-10 |
| Sections used | 7.1 About persistent storage; 7.1.1 Storage classes in OpenShift AI; 7.1.2 Access modes; 7.1.2.1 Using shared storage (RWX); 7.2 Configuring storage class settings; 7.3 Configuring the default storage class for your cluster; 7.4 Overview of object storage endpoints; 7.4.1 MinIO (On-Cluster); 7.4.2 Amazon S3; 7.4.3 Other S3-Compatible Object Stores; 7.4.4 Verification and Troubleshooting |

## Related Official Sources

| Source | Role |
|--------|------|
| https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/storage/understanding-persistent-storage | OpenShift persistent storage, PVC, PV, and dynamic provisioning background |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_resources/managing-cluster-pvc-size | Adjacent OpenShift AI default PVC size dashboard workflow |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_resources/customizing-the-dashboard | Dashboard visibility for Settings -> Cluster settings -> Storage classes |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_resources/managing-connection-types | Connection type templates that can represent object storage connection forms |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/creating_a_workbench/index | Workbench workflows that consume project storage |

## Supporting Project Sources

| Source | Role |
|--------|------|
| `docs/PLATFORM_BASELINE.md` | Active RHOAI/OCP baseline and source hierarchy |
| `AGENTS.md` | OpenShift safety guard and GitOps operating constraints |
| `.agents/skills/rhoai-cluster-pvc-size/SKILL.md` | Adjacent PVC-size setting boundary |
| `.agents/skills/rhoai-dashboard-customization/SKILL.md` | Dashboard menu visibility for storage classes |
| `.agents/skills/rhoai-connection-types/SKILL.md` | Connection type template boundary for object storage credentials |
| `.agents/skills/env-troubleshoot/SKILL.md` | Live storage and Pending pod diagnostics |

## Source Boundaries

- Product authority: the official Red Hat OpenShift AI 3.4 Managing resources
  chapter above.
- This chapter defines dashboard management of storage class visibility,
  OpenShift AI-only metadata, access mode selection, and OpenShift AI default
  storage class selection.
- It does not define how to create, install, or tune the underlying OpenShift
  `StorageClass` resources.
- It does not define a GitOps schema for dashboard storage class settings.
- It gives endpoint-format guidance for object stores; it does not provision
  MinIO, Amazon S3, or another object storage provider.
- Verification: dashboard behavior, user selection checks, read-only
  OpenShift storage class and PVC inspection, and endpoint reachability tests.

## Unresolved Or Environment-Specific Items

- Demo default OpenShift AI storage class.
  Verification: inspect the target AWS/OpenShift environment storage classes
  and access modes before documenting a default.
- GitOps backing field for OpenShift AI storage class settings.
  Verification: use official docs or installed schema before automating the
  dashboard setting.
- Demo RWX provider.
  Verification: confirm a target storage class supports `ReadWriteMany` before
  presenting shared storage as implemented.
- Object storage endpoint provider and bucket naming.
  Verification: define with the active demo object storage implementation and
  validate reachability from the cluster.
