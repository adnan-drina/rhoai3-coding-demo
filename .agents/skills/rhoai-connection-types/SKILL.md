---
name: rhoai-connection-types
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when an administrator views, creates, duplicates, edits, enables or
  deletes OpenShift AI connection types (Settings, Environment setup,
  Connection types), including a Python package index type, or reviews which
  type the repo's S3 connection Secrets use (connection-type-protocol s3 in
  demo-sandbox and evaluated-models, the deprecated connection-type-ref on the
  Stage 050 ones). Do NOT use for creating or attaching project connections
  (use rhoai-project-workflows), S3 data access from a notebook (use
  rhoai-s3-object-storage-data) or storage classes (use rhoai-storage-classes).
---

# RHOAI Connection Types

Thin skill: repo decisions and pitfalls here, product behavior in the linked
OpenShift AI 3.5 sections. Detailed record:
`gitops/stages/010-openshift-ai-platform-foundation/sandbox-storage/README.md`.

## When to use

- Someone proposes a custom connection type, or a type must be hidden from users.
- Reviewing the type annotations on the repo's connection Secrets.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| No custom connection type; all repo connections use the pre-installed S3-compatible type | `gitops/stages/010-openshift-ai-platform-foundation/sandbox-storage/connection-*.yaml`, `gitops/stages/050-model-evaluation/model-qualification/storage/connection-*.yaml` | [Manage connection types][types], [View][view] |
| Connection Secrets name the type with `opendatahub.io/connection-type-protocol: s3`, label `opendatahub.io/dashboard: "true"`, display name annotation; no credential data in Git | same paths | [Connections API][api] |
| Stage 050 Secrets also carry `opendatahub.io/connection-type-ref: s3`, which 3.5 marks deprecated (protocol takes precedence) | `gitops/stages/050-model-evaluation/model-qualification/storage/connection-*.yaml` | [S3 connection via the API][api-s3] |
| `connectionTest: true` (Technology Preview) lets users test S3 connections in the dashboard | `gitops/stages/010-openshift-ai-platform-foundation/rhoai-platform/odhdashboardconfig.yaml` | see `rhoai-dashboard-customization` |

## Procedure

1. Manage types in the dashboard (Settings, Environment setup, Connection
   types). To tailor a pre-installed type, [duplicate][dup] it rather than
   edit it; preview the user form before saving.
2. Changing or disabling a type does not change existing connections; check
   the connections that use it first.
3. Read-only checks after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get secret -A -l opendatahub.io/dashboard=true \
     -o custom-columns=NS:.metadata.namespace,NAME:.metadata.name,PROTOCOL:.metadata.annotations.opendatahub\\.io/connection-type-protocol
   ./stages/010-openshift-ai-platform-foundation/validate.sh
   ```

   Unresolved: where 3.5 stores connection type definitions. Verify on the
   live cluster before declaring a type in Git.

## Pitfalls

- A type holds form fields and optional defaults, never secret values.
- Category labels are for filtering only; they grant nothing.
- When Stage 050 storage is next changed, drop the deprecated
  `connection-type-ref` annotation and rerun
  `./stages/050-model-evaluation/validate.sh`.

## Official documentation (OpenShift AI 3.5)

| Topic | Section |
|---|---|
| Types | [Manage connection types][types], [View][view], [Create][create], [Python package index][pypi] |
| Change | [Duplicate][dup], [Edit][edit], [Enable][enable], [Delete][delete] |
| Connection Secret format | [Connections API][api], [S3 connection via the API][api-s3] |

## Related skills

`rhoai-project-workflows`, `rhoai-s3-object-storage-data`,
`rhoai-dashboard-customization`, `odf-object-bucket-claims`, `rhoai-storage-classes`.

[types]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#managing-connection-types
[view]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#viewing-connection-types_resource-mgmt
[create]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#creating-a-connection-type_resource-mgmt
[pypi]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#creating-a-connection-type-for-a-python-package-index_resource-mgmt
[dup]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#duplicating-a-connection-type_resource-mgmt
[edit]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#editing-a-connection-type_resource-mgmt
[enable]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#enabling-a-connection-type_resource-mgmt
[delete]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#deleting-a-connection-type_resource-mgmt
[api]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_on_projects/index#using-connections-api_projects
[api-s3]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_on_projects/index#creating-s3-compatible-connection-type-api_projects
