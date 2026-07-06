---
name: rhoai-model-registry
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when documenting, reviewing, or provisioning Red Hat OpenShift AI model
  registries: enabling the modelregistry DataScienceCluster component,
  setting registriesNamespace, creating and editing model registries, choosing
  default non-production or external PostgreSQL/MySQL databases, configuring
  database CA certificates, managing registry permissions for users, groups,
  and project service accounts, understanding generated registry RBAC, and
  deleting registries without removing connected databases. Do NOT use for
  model catalog source governance, user model registration/version/deployment
  workflows, model serving runtime configuration, or live cluster changes
  without the OpenShift safety guard.
---

# RHOAI Model Registry

Use this skill to provision and secure access to OpenShift AI model registries
for the active product baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product configuration details.
Official Red Hat documentation is product authority. This skill adapts the
official Managing model registries guide to this repo's GitOps and governance
review model.

## Scope

This skill covers:

- the difference between the model catalog and model registry
- enabling the `modelregistry` component on the `DataScienceCluster`
- setting `registriesNamespace: rhoai-model-registries`
- verifying the registry namespace and operator controller deployment
- creating model registries from the dashboard
- model registry resource naming constraints
- default non-production database versus external PostgreSQL or MySQL database
  selection
- external database host, port, username, password, database name, and CA
  certificate options
- editing model registry name, description, and database details
- granting registry access to OpenShift users, groups, and project service
  accounts
- generated registry RBAC resources and `<model-registry-name>-users` groups
- deleting model registries and preserving connected databases

Use other skills for adjacent work:

- `rhoai-model-catalog-sources` for AI hub catalog source governance
- `rhoai-model-catalog-workflows` for catalog discovery, performance
  evaluation, and starting catalog registration or deployment flows
- `rhoai-model-registry-workflows` for registering models, versions, ModelCar
  images, transfer jobs, metadata edits, deployments, archive, and restore
- `rhoai-model-serving-platform` for serving models from registries
- `rhoai-dashboard-customization` for dashboard visibility flags such as
  `disableModelRegistry`
- `rhoai-users-groups-access` for broader OpenShift AI user and group access
- `rhoai-certificate-management` for shared CA bundle behavior
- `rhoai-api-tiers` for `modelregistry.opendatahub.io/v1beta1` support posture

## Demo Policy

For this repo:

- Treat model registry as the governed metadata and lifecycle store between
  experimentation and serving.
- Use the default database only for demo, evaluation, development, or testing
  flows, and label it as non-production.
- For production-oriented European enterprise narratives, describe external
  PostgreSQL or MySQL as the production path.
- Do not store database passwords or uploaded certificate material directly in
  committed manifests.
- Prefer group-based access for repeatable demo roles; use individual users
  only for narrow exceptions.
- Do not grant `system:authenticated` access unless the README or operations
  note explicitly explains why all cluster users should access the registry.
- Treat registry deletion as a destructive action requiring explicit approval;
  connected databases are not removed by deleting the registry.
- Do not author a direct `ModelRegistry` custom resource manifest unless the
  exact API, fields, and support posture are verified against active Red Hat
  docs or live schema.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/source-capture.md` and
   `references/official-doc-extraction.md`.
3. Confirm the `modelregistry` component should be managed by OpenShift AI.
4. Enable or review the `DataScienceCluster` component configuration.
5. Decide whether the registry uses the default non-production database or an
   external PostgreSQL/MySQL database.
6. For external databases, document hostname format, port, credentials source,
   database name, and CA certificate handling.
7. Create or edit the registry through the documented dashboard workflow unless
   a schema-verified GitOps path exists.
8. Grant access through users, groups, or projects and review generated RBAC.
9. Verify the registry in Model registry settings or AI registry settings.
10. Validate with `references/validation-checklist.md`.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/model-registry-patterns.md`
