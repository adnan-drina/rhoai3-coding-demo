# Official Doc Extraction

Use this extraction to keep custom Tekton Hub guidance grounded in official Red
Hat sources. When implementation needs exact CR fields, verify the active
cluster schema with `oc explain` or `oc get crd` before authoring GitOps
manifests.

## Technology Preview Status

Tekton Hub is a Technology Preview feature. Technology Preview features are not
supported with Red Hat production service level agreements (SLAs) and might not
be functionally complete. Red Hat does not recommend using them in production.

## TektonHub CR (Without Login and Rating)

```yaml
apiVersion: operator.tekton.dev/v1alpha1
kind: TektonHub
metadata:
  name: hub
spec:
  targetNamespace: openshift-pipelines
  db:
    secret: tekton-hub-db

  categories:
    - Automation
    - Build Tools
    - CLI
    - Cloud
    - Code Quality

  catalogs:
    - name: tekton
      org: tektoncd
      type: community
      provider: github
      url: https://github.com/tektoncd/catalog
      revision: main

  scopes:
    - name: agent:create
      users: [abc, qwe, pqr]
    - name: catalog:refresh
      users: [abc, qwe, pqr]
    - name: config:refresh
      users: [abc, qwe, pqr]

  default:
    scopes:
      - rating:read
      - rating:write

  api:
    catalogRefreshInterval: 30m
```

Field reference:
- `spec.targetNamespace`: namespace where Tekton Hub is installed; default
  `openshift-pipelines`
- `spec.db.secret`: name of database secret; must be `tekton-hub-db`
- `spec.categories`: custom categories for tasks and pipelines (overrides
  defaults from API config map)
- `spec.catalogs`: custom catalogs with `name`, `org`, `type`, `provider`,
  `url`, `revision`
- `spec.scopes`: additional users with named scopes (`agent:create`,
  `catalog:refresh`, `config:refresh`)
- `spec.default.scopes`: default scopes for new users
- `spec.api.catalogRefreshInterval`: auto-refresh interval; supports `s`, `m`,
  `h`, `d`, `w` units; default 30m

## TektonHub API Secret (Login and Rating Mode)

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: tekton-hub-api
  namespace: openshift-pipelines
type: Opaque
stringData:
  GH_CLIENT_ID: <GitHub OAuth Client ID>
  GH_CLIENT_SECRET: <GitHub OAuth Client Secret>
  GL_CLIENT_ID: <GitLab OAuth Client ID>
  GL_CLIENT_SECRET: <GitLab OAuth Client Secret>
  BB_CLIENT_ID: <Bitbucket OAuth Client ID>
  BB_CLIENT_SECRET: <Bitbucket OAuth Client Secret>
  JWT_SIGNING_KEY: <long random string for JWT signing>
  ACCESS_JWT_EXPIRES_IN: <expiry time, e.g. 15m>
  REFRESH_JWT_EXPIRES_IN: <expiry time, e.g. 1h>
  AUTH_BASE_URL: <route URL for OAuth application>
  GHE_URL: <GitHub Enterprise URL, if applicable>
  GLE_URL: <GitLab Enterprise URL, if applicable>
```

Field reference:
- `GH_CLIENT_ID` / `GH_CLIENT_SECRET`: GitHub OAuth credentials
- `GL_CLIENT_ID` / `GL_CLIENT_SECRET`: GitLab OAuth credentials
- `BB_CLIENT_ID` / `BB_CLIENT_SECRET`: Bitbucket OAuth credentials
- `JWT_SIGNING_KEY`: random string for signing JWTs
- `ACCESS_JWT_EXPIRES_IN`: access token expiry (must be shorter than refresh)
- `REFRESH_JWT_EXPIRES_IN`: refresh token expiry (must be longer than access)
- `AUTH_BASE_URL`: OAuth application route URL
- `GHE_URL`: GitHub Enterprise URL (not the catalog URL)
- `GLE_URL`: GitLab Enterprise URL (not the catalog URL)

Unused provider fields may be deleted.

OAuth callback URLs:
- GitHub: set Homepage URL and Authorization callback URL to `<auth_route>`
- GitLab: set `REDIRECT_URI` to `<auth_route>/auth/gitlab/callback`
- Bitbucket: set `Callback URL` to `<auth_route>`

Enterprise networking: deploy Tekton Hub in the same network as GitHub
Enterprise or GitLab Enterprise servers (e.g. same VPN).

## Custom Database Secret

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: tekton-hub-db
  labels:
    app: tekton-hub-db
type: Opaque
stringData:
  POSTGRES_HOST: <database host>
  POSTGRES_DB: <database name>
  POSTGRES_USER: <username>
  POSTGRES_PASSWORD: <password>
  POSTGRES_PORT: "<port>"
```

The secret name must be `tekton-hub-db`. Default target namespace is
`openshift-pipelines`.

## TektonHub CR with Custom Database

```yaml
apiVersion: operator.tekton.dev/v1alpha1
kind: TektonHub
metadata:
  name: hub
spec:
  targetNamespace: openshift-pipelines
  db:
    secret: tekton-hub-db
  api:
    hubConfigUrl: https://raw.githubusercontent.com/tektoncd/hub/main/config.yaml
    catalogRefreshInterval: 30m
```

For initial install: `oc apply -f <tekton_hub_cr>.yaml`
For post-install change: `oc replace -f <tekton_hub_cr>.yaml`

## Crunchy Postgres Integration

Prerequisites:
- Install Crunchy Postgres Operator from OperatorHub
- Create a Postgres instance

Required `pg_hba.conf` entry for external access:

```
host  all  all 0.0.0.0/0 md5
```

After editing `pg_hba.conf`, reload with:

```sql
SELECT pg_reload_conf();
```

Decode Crunchy Postgres host secret:

```bash
echo '<base64_encoded_host>' | base64 --decode
```

## Data Migration to Crunchy Postgres

1. Dump data from default database:

```bash
pg_dump -Ft -h localhost -U postgres hub -f /tmp/hub.dump
```

2. Copy dump to local system:

```bash
oc cp -n <namespace> <podName>:/tmp/hub.dump <local_path>
```

3. Copy dump to Crunchy Postgres pod:

```bash
oc cp -n <namespace> <local_path> <crunchy_pod>:/tmp/hub.dump
```

4. Restore in Crunchy Postgres:

```bash
pg_restore -d <database_name> -h localhost -U postgres /tmp/hub.dump
```

5. Verify `pg_hba.conf`, create `tekton-hub-db` secret, update `TektonHub` CR,
   and apply with `oc replace`.

## User Scope Management

Scopes field in TektonHub CR:

```yaml
scopes:
  - name: agent:create
    users: [<username_1>, <username_2>]
  - name: catalog:refresh
    users: [<username_3>, <username_4>]
  - name: config:refresh
    users: [<username_5>, <username_6>]

default:
  scopes:
    - rating:read
    - rating:write
```

New users signing in for the first time get only default scopes. Additional
scopes require the username in the `scopes` field.

After updating users, refresh configuration:

```bash
curl -X POST -H "Authorization: <access_token>" \
    --header "Content-Type: application/json" \
    --data '{"force": true}' \
    <api_route>/system/config/refresh
```

## Checking TektonHub Status

```bash
oc get tektonhub.operator.tekton.dev
```

Expected output when ready:

```
NAME   VERSION   READY   REASON   APIURL                    UIURL
hub    v1.9.0    True             https://api.route.url/    https://ui.route.url/
```

## Disabling Authorization After Operator Upgrade (1.7 to 1.8)

When upgrading from Operator 1.7 to 1.8, login authorization is not
automatically disabled. Manual steps:

1. Delete existing API secret:

```bash
oc delete secret tekton-hub-api -n <targetNamespace>
```

2. Delete API TektonInstallerSet:

```bash
oc get tektoninstallerset -o name | grep tekton-hub-api | xargs oc delete
```

3. Wait for `READY: True`:

```bash
oc get tektonhub hub
```

4. Delete UI ConfigMap:

```bash
oc delete configmap tekton-hub-ui -n <targetNamespace>
```

5. Delete UI TektonInstallerSet:

```bash
oc get tektoninstallerset -o name | grep tekton-hub-ui | xargs oc delete
```

6. Wait for `READY: True`:

```bash
oc get tektonhub hub
```
