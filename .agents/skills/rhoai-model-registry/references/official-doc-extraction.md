# Official Documentation Extraction

## Concept Model

The model catalog is a curated discovery surface where data scientists and AI
engineers find and evaluate available generative AI models.

The model registry is a central metadata repository for registering,
versioning, sharing, deploying, and tracking models across the AI/ML lifecycle.
It bridges experimentation and serving and is a key governance component.

Administrators create model registries and grant access to data scientists and
AI engineers. Users with access can use registries to store, share, version,
deploy, and track models.

## Enabling The Component

Before users can work with the model registry and catalog, the
`modelregistry` component must be enabled in OpenShift AI.

The official guide notes that `modelregistry` is enabled by default in a new
OpenShift AI 3.4 installation. If it was not enabled in a previous OpenShift AI
version, enable it after upgrading.

Prerequisites:

- cluster administrator privileges
- access to the data science cluster
- Red Hat OpenShift AI Operator installed
- sufficient resources for OpenShift AI

DataScienceCluster component shape:

```yaml
spec:
  components:
    modelregistry:
      managementState: Managed
      registriesNamespace: rhoai-model-registries
```

Verification:

- `rhoai-model-registries` namespace exists
- `model-registry-operator-controller-manager` deployment in
  `redhat-ods-applications` has a running pod

## Creating A Registry

Dashboard path:

```text
Settings -> Model resources and operations -> Model registry settings
```

Creation inputs:

- name
- optional resource name
- optional description
- database choice
- optional external database connection and CA certificate details

Resource name rules:

- maximum 253 characters
- lowercase alphanumeric characters or `-`
- starts and ends with an alphanumeric character
- unique among model registry resources in the cluster
- cannot be edited after creation

Database choices:

- Default database: PostgreSQL database enabled by default on the OpenShift
  cluster; non-production only.
- External database: MySQL or PostgreSQL database intended for production use
  cases.

Production external database prerequisites:

- PostgreSQL 16.x, or
- MySQL 5.x or later, with MySQL 9.x preferred by the official guide

External database fields:

- database type: MySQL or PostgreSQL
- host
- port: default MySQL `3306`, default PostgreSQL `5432`
- username
- password
- database name

Host format:

- if the database is in `rhoai-model-registries`, use only the hostname
- if the database is in another namespace, use
  `<hostname>.<namespace>.svc.cluster.local`

CA certificate options:

- use cluster-wide CA bundle from `ca-bundle.crt` in
  `odh-trusted-ca-bundle`
- use Red Hat OpenShift AI CA bundle from `odh-ca-bundle.crt` in
  `odh-trusted-ca-bundle`
- choose an existing ConfigMap or secret key in `rhoai-model-registries`
- upload a new certificate as a ConfigMap

If an external database enforces TLS, a CA certificate must be added. Uploading
a certificate creates the `db-credential` ConfigMap with key `ca.crt`. To use a
secret instead, create the secret in `rhoai-model-registries` and select it as
an existing certificate.

## Editing A Registry

Dashboard path:

```text
Settings -> Model resources and operations -> Model registry settings
```

Editable details include:

- name
- description
- database selection and external database connection details
- database CA certificate option

The resource name is not editable after creation.

## Permissions And RBAC

Dashboard path:

```text
Settings -> Model resources and operations -> AI registry settings
```

Administrators can grant registry access to:

- OpenShift groups
- OpenShift users
- all service accounts in a project

Adding `system:authenticated` grants access to all cluster users.

OpenShift AI creates a `<model-registry-name>-users` group for model registry
use. The model registry operator uses OpenShift RBAC and creates resources in
`rhoai-model-registries`.

For each model registry instance, the operator creates:

- a `registry-users-<model registry instance name>` role
- an OpenShift group named `<model registry instance name>-users`
- a role binding from the group to the registry-users role

Cluster administrators can add users to the generated group to grant access
without creating a role binding per user. To grant an individual user, service
account, or group directly, create a role binding to the
`registry-users-<model registry instance name>` role.

Verification:

- users, groups, and project service accounts with access can register, view,
  edit, version, deploy, delete, archive, and restore models
- Users and Groups sections show granted users and groups
- Projects tab shows projects granted access

## Deleting A Registry

Dashboard path:

```text
Settings -> Model resources and operations -> AI registry settings
```

Deleting a model registry removes the registry from AI registry settings but
does not remove databases connected to the model registry. Remaining database
cleanup requires cluster-administrator action.

Treat registry deletion as destructive and require explicit approval before
performing it in a live environment.

## API Tier Handoff

The API tier skill records `modelregistry.opendatahub.io/v1beta1` as Tier 2
and `modelregistries.components.platform.opendatahub.io/v1alpha1` as Tier 4.
Use `rhoai-api-tiers` before relying on direct manifests or client code.
