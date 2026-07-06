---
name: ocp-pipelines-tekton-hub
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "ocp"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when deploying or managing a custom Tekton Hub instance: TektonHub CR
  configuration, catalog management, database setup, API and UI deployment,
  Tekton Hub integration with OpenShift console, and hub resolver
  configuration for OpenShift Pipelines 1.22. Do NOT use for pipeline concepts
  (use ocp-pipelines-about), installing pipelines (use
  ocp-pipelines-install-config), or Artifact Hub migration (use
  ocp-pipelines-install-config).
---

# OCP Pipelines Tekton Hub

Use this skill to ground custom Tekton Hub instance guidance in the
official Red Hat OpenShift Pipelines 1.22 custom Tekton Hub guide for the
active baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority.

## Technology Preview Notice

Tekton Hub is a Technology Preview feature only. Technology Preview features are
not supported with Red Hat production service level agreements (SLAs) and might
not be functionally complete. Red Hat does not recommend using them in
production.

## TektonHub CR Overview

Tekton Hub is an optional component managed via the `TektonHub` CR (not
`TektonConfig`). It helps discover, search, and share reusable tasks and
pipelines for CI/CD workflows.

Key fields: `apiVersion: operator.tekton.dev/v1alpha1`, `kind: TektonHub`,
`metadata.name: hub`.

Two installation modes:
- Without login authorization and ratings (default)
- With login authorization and ratings (requires OAuth application setup)

## Installation Without Login and Rating

Minimal `TektonHub` CR with default configuration:

```yaml
apiVersion: operator.tekton.dev/v1alpha1
kind: TektonHub
metadata:
  name: hub
spec:
  targetNamespace: openshift-pipelines
  api:
    catalogRefreshInterval: 30m
```

Apply and check status:

```bash
oc apply -f <tekton_hub_cr>.yaml
oc get tektonhub.operator.tekton.dev
```

## Installation With Login and Rating

Requires OAuth application with a Git provider (GitHub, GitLab, or Bitbucket)
and a `tekton-hub-api` secret containing client credentials, JWT signing keys,
and auth base URL.

API secret keys: `GH_CLIENT_ID`, `GH_CLIENT_SECRET`, `GL_CLIENT_ID`,
`GL_CLIENT_SECRET`, `BB_CLIENT_ID`, `BB_CLIENT_SECRET`, `JWT_SIGNING_KEY`,
`ACCESS_JWT_EXPIRES_IN`, `REFRESH_JWT_EXPIRES_IN`, `AUTH_BASE_URL`, `GHE_URL`,
`GLE_URL`.

Enterprise note: if using GitHub Enterprise or GitLab Enterprise, deploy Tekton
Hub in the same network as the enterprise server.

## Custom Database

Tekton Hub supports custom PostgreSQL databases instead of the default. Create a
secret named `tekton-hub-db` with keys: `POSTGRES_HOST`, `POSTGRES_DB`,
`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_PORT`.

Crunchy Postgres is explicitly supported. The `pg_hba.conf` must include
`host all all 0.0.0.0/0 md5` for external access.

Data migration from the default database to Crunchy Postgres uses `pg_dump` /
`pg_restore` and `oc cp` for file transfer between pods.

## Catalog and Category Customization

The `TektonHub` CR supports custom `categories`, `catalogs`, `scopes`, and
`default.scopes` fields. Custom values override defaults from the Tekton Hub API
config map.

Catalog fields: `name`, `org`, `type`, `provider`, `url`, `revision`.

## Catalog Refresh Interval

The `catalogRefreshInterval` field controls automatic catalog refresh. Default
is 30 minutes. Supported units: seconds (`s`), minutes (`m`), hours (`h`),
days (`d`), weeks (`w`).

## User Scope Management

Users are added via the `scopes` field in the `TektonHub` CR. Available scopes:
- `agent:create`
- `catalog:refresh`
- `config:refresh`

Default scopes for new users: `rating:read`, `rating:write`.

After adding users, refresh configuration via:

```bash
curl -X POST -H "Authorization: <access_token>" \
    --header "Content-Type: application/json" \
    --data '{"force": true}' \
    <api_route>/system/config/refresh
```

## Disabling Authorization After Upgrade (1.7 to 1.8)

Upgrading from Operator 1.7 to 1.8 does not automatically disable login
authorization. Manual steps required:
1. Delete `tekton-hub-api` secret
2. Delete `TektonInstallerSet` for the API (`oc get tektoninstallerset -o name | grep tekton-hub-api | xargs oc delete`)
3. Wait for Hub to become `READY`
4. Delete `tekton-hub-ui` ConfigMap
5. Delete `TektonInstallerSet` for the UI
6. Wait for Hub to become `READY`

## Workflow

1. Confirm the active OpenShift baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Identify the Tekton Hub task (install, configure database, manage catalogs,
   manage users).
4. For GitOps manifests, verify all API versions and fields against the
   extraction before committing.
5. For live operations, use the repo environment guard.
6. Validate with `references/source-capture.md` boundaries.

## Related Skills

- Use `ocp-pipelines-about` for pipeline concepts and Tekton CRDs.
- Use `ocp-pipelines-install-config` for installing and configuring OpenShift
  Pipelines.
- Use `ocp-cicd-builds` for OpenShift Builds (BuildConfig, Shipwright).

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
