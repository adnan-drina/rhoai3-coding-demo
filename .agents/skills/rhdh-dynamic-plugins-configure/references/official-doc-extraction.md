# Official Documentation Extraction

This extraction is derived from the official RHDH 1.10 guide captured in
`source-capture.md`.

## Argo CD Plugin Configuration

### App-Config

```yaml
argocd:
  appLocatorMethods:
    - type: 'config'
      instances:
        - name: argoInstance1
          url: https://argoInstance1.com
          username: ${ARGOCD_USERNAME}
          password: ${ARGOCD_PASSWORD}
```

Avoid trailing slash in `url`.

### Entity Annotations

```yaml
annotations:
  argocd/app-selector: '${ARGOCD_LABEL_SELECTOR}'
  argocd/instance-name: '${ARGOCD_INSTANCE}'  # optional, defaults to first
```

### Plugin Variants

Recommended combination: `@backstage-community/plugin-argocd` with
`@backstage-community/plugin-argocd-backend`. Do not mix Community and Roadie
plugins.

### Argo CD Rollouts

Requires `@backstage/plugin-kubernetes` installed. Add custom resources:

```yaml
kubernetes:
  customResources:
    - group: 'argoproj.io'
      apiVersion: 'v1alpha1'
      plural: 'Rollouts'
    - group: 'argoproj.io'
      apiVersion: 'v1alpha1'
      plural: 'analysisruns'
```

ClusterRole for rollouts and analysis runs requires `get`, `list` verbs on
`argoproj.io` resources.

## JFrog Artifactory Plugin Configuration

Proxy in `app-config.yaml`:

```yaml
proxy:
  endpoints:
    '/jfrog-artifactory/api':
      target: http://<hostname>:8082
      secure: true
```

Entity annotation: `jfrog-artifactory/image-name: '<IMAGE-NAME>'`

## Nexus Repository Manager Plugin Configuration

Proxy in `app-config.yaml`:

```yaml
proxy:
  '/nexus-repository-manager':
    target: 'https://<NEXUS_REPOSITORY_MANAGER_URL>'
    headers:
      X-Requested-With: 'XMLHttpRequest'
    changeOrigin: true
    secure: true
```

Annotation: `nexus-repository-manager/docker.image-name: '<ORG>/<REPO>'`

## Tekton Plugin Configuration

Requires ClusterRole with `get`, `list` for `tekton.dev` resources
(`pipelineruns`, `taskruns`), and `pods/log`.

Entity annotations:

```yaml
annotations:
  backstage.io/kubernetes-id: <BACKSTAGE_ENTITY_NAME>
  janus-idp.io/tekton: <BACKSTAGE_ENTITY_NAME>
```

Custom resources in Kubernetes plugin config:

```yaml
kubernetes:
  customResources:
    - group: 'tekton.dev'
      apiVersion: 'v1'
      plural: 'pipelineruns'
    - group: 'tekton.dev'
      apiVersion: 'v1'
      plural: 'taskruns'
```

## Topology Plugin Configuration

### Required Resources

ClusterRole for various resources depending on features:

| Feature | API Groups | Resources |
|---------|-----------|-----------|
| OpenShift Routes | `route.openshift.io` | `routes` |
| Pod logs | `""` | `pods`, `pods/log` |
| Tekton | `tekton.dev` | `pipelines`, `pipelineruns`, `taskruns` |
| Virtual machines | `kubevirt.io` | `virtualmachines`, `virtualmachineinstances` |
| Dev Spaces editor | `org.eclipse.che` | `checlusters` |

### Labels and Annotations

| Annotation/Label | Purpose |
|-----------------|---------|
| `backstage.io/kubernetes-id` | Map resources to RHDH entities |
| `backstage.io/kubernetes-namespace` | Identify resources by namespace |
| `backstage.io/kubernetes-label-selector` | Custom label selector (overrides other annotations) |
| `app.openshift.io/vcs-uri` | Link to Git repository |
| `app.openshift.io/vcs-ref` | Link to specific branch |
| `app.openshift.io/runtime` | Display runtime icon |
| `app.kubernetes.io/part-of` | Group applications in topology view |
| `app.openshift.io/connects-to` | Visual connector between resources |

## Bulk Import

Technology Preview. Requires user OAuth authentication (no fallback to
server-wide integration credentials).

Enable plugins:

```yaml
plugins:
  - package: ./dynamic-plugins/dist/red-hat-developer-hub-backstage-plugin-bulk-import-backend-dynamic
    disabled: false
  - package: ./dynamic-plugins/dist/red-hat-developer-hub-backstage-plugin-bulk-import
    disabled: false
```

RBAC permission for non-admins:

```text
p, role:default/bulk-import, bulk.import, use, allow
g, user:default/<your_user>, role:default/bulk-import
```

Supports GitHub and GitLab (TP) imports, Scaffolder template tasks, and
Orchestrator workflow integration.

## ServiceNow Integration

### Entity Linking Methods

| Method | Schema Change Required | Security |
|--------|----------------------|----------|
| Direct mapping (`backstage_entity_id` column) | Yes | High |
| Flexible mapping (custom column) | No | Medium |

### Authentication

Supports Basic auth and OAuth (client_credentials, password grant).

### Scaffolder Actions

- `servicenow:now:table:createRecord`
- `servicenow:now:table:retrieveRecord`
- `servicenow:now:table:retrieveRecords`
- `servicenow:now:table:modifyRecord`
- `servicenow:now:table:updateRecord`
- `servicenow:now:table:deleteRecord`

## Kubernetes Custom Actions

Action: `kubernetes:create-namespace`

Parameters: `namespace` (required), `clusterRef` or `url` (one required),
`token` (required), `skipTLSVerify` (optional), `caData` (optional),
`labels` (optional).

## GitHub Events Module

Technology Preview. Enables real-time catalog updates via webhooks.

HTTP endpoint config:

```yaml
events:
  http:
    topics:
      - github
  modules:
    github:
      webhookSecret: ${GITHUB_WEBHOOK_SECRET}
```

Webhook payload URL: `https://<domain>/api/events/http/github`

Events: push, repository (discovery); organization, team, membership (org data).

## Core Backend Service Overrides

Override core services by setting environment variables to `true`:

| Variable | Service ID |
|----------|-----------|
| `ENABLE_CORE_AUTH_OVERRIDE` | `core.auth` |
| `ENABLE_CORE_CACHE_OVERRIDE` | `core.cache` |
| `ENABLE_CORE_DATABASE_OVERRIDE` | `core.database` |
| `ENABLE_CORE_DISCOVERY_OVERRIDE` | `core.discovery` |
| `ENABLE_CORE_HTTPAUTH_OVERRIDE` | `core.httpAuth` |
| `ENABLE_CORE_HTTPROUTER_OVERRIDE` | `core.httpRouter` |
| `ENABLE_CORE_LIFECYCLE_OVERRIDE` | `core.lifecycle` |
| `ENABLE_CORE_LOGGER_OVERRIDE` | `core.logger` |
| `ENABLE_CORE_PERMISSIONS_OVERRIDE` | `core.permissions` |
| `ENABLE_CORE_ROOTHEALTH_OVERRIDE` | `core.rootHealth` |
| `ENABLE_CORE_ROOTHTTPROUTER_OVERRIDE` | `core.rootHttpRouter` |
| `ENABLE_CORE_ROOTLIFECYCLE_OVERRIDE` | `core.rootLifecycle` |
| `ENABLE_CORE_SCHEDULER_OVERRIDE` | `core.scheduler` |
| `ENABLE_CORE_USERINFO_OVERRIDE` | `core.userInfo` |
| `ENABLE_CORE_URLREADER_OVERRIDE` | `core.urlReader` |
| `ENABLE_EVENTS_SERVICE_OVERRIDE` | `events.service` |
| `ENABLE_CORE_ROOTCONFIG_OVERRIDE` | `core.rootConfig` |

Install the custom core service as a `BackendFeature` using dynamic plugin
functionality.
