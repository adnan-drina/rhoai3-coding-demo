---
name: tpa-deployment
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "tpa"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Trusted Software Supply Chain"
description: >
  Use when deploying Red Hat Trusted Profile Analyzer 2.2 on Red Hat Enterprise
  Linux or Red Hat OpenShift, including prerequisites, operator installation,
  and self-hosted configuration. Do NOT use for the managed service quick start
  (use tpa-quick-start), release notes (use tpa-release-notes), or
  administration (use tpa-admin).
---

# TPA Deployment

Use this skill for deploying Red Hat Trusted Profile Analyzer (RHTPA) 2.2 on
the active platform baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product configuration details.
Official Red Hat docs are product authority. This skill covers installation
platform selection, Ansible-based RHEL deployment, OLM Operator deployment, and
Helm-based OpenShift deployment with AWS or Red Hat service backends.

## Installation Platforms

RHTPA supports two target platforms:

- **Red Hat Enterprise Linux** — installed via Ansible playbook from Automation
  Hub (`rhtpa` collection, `tpa_single_node` role).
- **Red Hat OpenShift Container Platform 4.17+** — installed via OLM Operator
  or Helm chart.

OpenShift deployments support two infrastructure backends:

- **AWS**: Cognito (OIDC), S3 (storage), RDS (PostgreSQL).
- **Red Hat services**: Red Hat SSO (OIDC), ODF (S3-compatible storage),
  self-managed PostgreSQL.

## Prerequisites

### RHEL (Ansible)

- RHEL 9.3 or later.
- Red Hat Hybrid Cloud Console account.
- Configured OIDC provider (Red Hat SSO or AWS Cognito).
- Storage provider (ODF or AWS S3).
- Available PostgreSQL or Amazon RDS instance.

### OpenShift (OLM or Helm)

- OpenShift Container Platform 4.17 or later.
- `cluster-admin` role on the web console (OLM) or `oc` CLI access.
- Configured OIDC provider (Red Hat SSO or AWS Cognito).
- Storage provider (ODF or AWS S3) with a bucket named `trustify-UNIQUE_ID`.
- Available PostgreSQL or Amazon RDS instance.
- Ingress with publicly trusted HTTPS certificates (Helm path).

### Resource Recommendations (OpenShift)

| Resource | Baseline |
|----------|----------|
| CPU | 4 cores |
| Memory | 8 GB RAM |
| DB storage | 45 GB |
| Object storage | 45 GB (scale by SBOM volume) |

## Workflow

1. Read `references/source-capture.md` and confirm the product baseline.
2. Select an installation platform (RHEL Ansible, OLM Operator, or Helm).
3. Read `references/official-doc-extraction.md` for the chosen path.
4. Provision prerequisites (OIDC, storage, database).
5. Create required Kubernetes Secrets (storage, OIDC, PostgreSQL credentials).
6. Deploy using the selected method.
7. Validate deployment.

### OLM Operator Path

1. Install the RHTPA Operator from OperatorHub.
2. Create a `TrustedProfileAnalyzer` CR instance (YAML view).
3. Paste OIDC, storage, and importer config under `spec`.
4. Click Create.

### Helm Path

1. Create project: `oc new-project trusted-profile-analyzer`.
2. Create Secrets: `storage-credentials`, `oidc-cli`,
   `postgresql-credentials`, `postgresql-admin-credentials`.
3. Prepare `values-rhtpa.yaml` and `values-importers.yaml`.
4. Add Helm repo: `helm repo add openshift-helm-charts https://charts.openshift.io/`.
5. Install: `helm upgrade --install redhat-trusted-profile-analyzer ...`.

### Validation

```shell
# Verify pods are running
oc -n trusted-profile-analyzer get pods

# Get console URL
oc -n $NAMESPACE get route --selector app.kubernetes.io/name=server \
  -o jsonpath='https://{.items[0].status.ingress[0].host}'
```

## Required Secrets (OpenShift)

All deployment paths require these Secrets in the target namespace:

| Secret | Keys | Purpose |
|--------|------|---------|
| `storage-credentials` | `aws_access_key_id`, `aws_secret_access_key` (AWS) or `user`, `password` (RH) | S3 storage access |
| `oidc-cli` | `client-secret` | OIDC CLI client secret |
| `postgresql-credentials` | `db.host`, `db.name`, `db.user`, `db.password`, `db.port` | Standard DB access |
| `postgresql-admin-credentials` | `db.host`, `db.name`, `db.user`, `db.password`, `db.port` | Admin DB access (migrations) |

## CRDs

| Kind | API Group | Installation method |
|------|-----------|---------------------|
| `TrustedProfileAnalyzer` | (OLM Operator) | OLM |

## Related Skills

- `tpa-quick-start` — managed service quick start on Red Hat Hybrid Cloud Console.
- `tpa-release-notes` — RHTPA 2.2 release notes, known issues, fixes.
- `tpa-admin` — post-deployment administration, user management, configuration.
- `tpa-integration` — SBOM/VEX ingestion, importer configuration, API usage.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
