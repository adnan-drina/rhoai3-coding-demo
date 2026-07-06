# Validation Checklist

Use this checklist when reviewing model registry documentation, GitOps
manifests, runbooks, or live operations plans.

## Source Alignment

- The RHOAI documentation version matches `docs/PLATFORM_BASELINE.md`.
- The official Managing model registries source is recorded in the README,
  runbook, or skill reference that introduces registry behavior.
- The task is administrator registry provisioning or access management, not
  model catalog source governance or end-user model version workflows.
- API support posture is checked with `rhoai-api-tiers` before direct manifests
  or API clients are treated as durable.

## Component Enablement

- `DataScienceCluster.spec.components.modelregistry.managementState` is
  `Managed`.
- `registriesNamespace` is `rhoai-model-registries`.
- The `rhoai-model-registries` namespace exists after enablement.
- The `model-registry-operator-controller-manager` deployment in
  `redhat-ods-applications` has a running pod.

## Registry Creation

- Registry name and optional resource name are intentional.
- Resource name follows the official constraints and is unique.
- The default database is labeled non-production when used.
- Production-oriented content uses an external PostgreSQL or MySQL database.
- When the default database is used on AWS EBS storage, the generated
  PostgreSQL Deployment rollout is checked for an RWO PVC rolling-update stall
  before declaring the registry operational.
- External database hostname format matches the namespace location.
- Database password handling avoids committed secrets.
- TLS-enforcing external databases include a CA certificate option.

## Database And CA Certificate Review

- PostgreSQL production examples use PostgreSQL 16.x.
- MySQL production examples use MySQL 5.x or later, with MySQL 9.x preferred.
- Default ports are correct unless the database configuration says otherwise:
  MySQL `3306`, PostgreSQL `5432`.
- CA bundle selection is one of the documented options.
- Uploaded certificate behavior is documented as creating `db-credential` with
  the `ca.crt` key.
- Secret-backed certificates are created in `rhoai-model-registries` before
  selection.

## Permissions

- Access grants use existing OpenShift users or groups.
- Group-based access is preferred for repeatable demo roles.
- `system:authenticated` is not used unless intentionally documented.
- Project access is described as granting access to all service accounts in the
  project.
- Generated RBAC resources are understood before writing manual role bindings.

## Deletion

- Deletion is explicitly approved before live use.
- The runbook states that connected databases are not removed.
- Any remaining database cleanup is assigned to a cluster administrator.

## Fail Conditions

Stop and correct the work if any of these are true:

- The default database is described as production-supported.
- Database credentials or CA material are committed in plain text.
- A registry resource name is changed after creation.
- `system:authenticated` access is added without an explicit reason.
- Registry deletion is described as deleting the connected database.
- Direct `ModelRegistry` manifests are introduced without schema and tier
  verification.
