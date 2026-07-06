# Official Documentation Extraction

Source: Red Hat Developer Hub 1.10 — Evaluate project health using Scorecards
Captured: 2026-07-06

---

## 1. Enable the Scorecard Plugin

### Frontend and backend (dynamic-plugin-config.yaml)

```yaml
plugins:
  - package: oci://ghcr.io/redhat-developer/rhdh-plugin-export-overlays/red-hat-developer-hub-backstage-plugin-scorecard:bs_1.49.4__2.7.7
    disabled: false
    pluginConfig:
      dynamicPlugins:
        frontend:
          red-hat-developer-hub.backstage-plugin-scorecard:
            entityTabs:
              - path: '/scorecard'
                title: Scorecard
                mountPoint: entity.page.scorecard
            mountPoints:
              - mountPoint: entity.page.scorecard/cards
                importName: EntityScorecardContent
                config:
                  layout:
                    gridColumn: 1 / -1
                  if:
                    allOf:
                      - isKind: component
  - package: oci://ghcr.io/redhat-developer/rhdh-plugin-export-overlays/red-hat-developer-hub-backstage-plugin-scorecard-backend:<tag>
    disabled: false
```

Tag format: `bs_<backstage_version>__<plugin_version>` (double underscore).

---

## 2. RBAC Configuration

### CSV file method

Prerequisites: RBAC enabled; `scorecard` added to
`permission.rbac.pluginsWithPermission`.

```yaml
g, user:default/<YOUR_USERNAME>, role:default/scorecard-viewer
p, role:default/scorecard-viewer, scorecard.metric.read, read, allow
p, role:default/scorecard-viewer, catalog.entity.read, read, allow
```

### Conditional policies (restrict to specific metrics)

```yaml
result: CONDITIONAL
roleEntityRef: "role:default/scorecard-viewer"
pluginId: scorecard
resourceType: scorecard-metric
permissionMapping:
  - read
conditions:
  rule: HAS_METRIC_ID
  resourceType: scorecard-metric
  params:
    metricIds: [<your_metric_id>]
```

---

## 3. GitHub Integration

### GitHub App — app-config.yaml

```yaml
integrations:
  github:
    - host: ${GITHUB_INTEGRATION_HOST_DOMAIN}
      apps:
        - appId: ${GITHUB_INTEGRATION_APP_ID}
          clientId: ${GITHUB_INTEGRATION_CLIENT_ID}
          clientSecret: ${GITHUB_INTEGRATION_CLIENT_SECRET}
          privateKey: |
            ${GITHUB_INTEGRATION_PRIVATE_KEY_FILE}
```

### GitHub token — app-config.yaml

```yaml
integrations:
  github:
    - host: github.com
      token: ${GITHUB_TOKEN}
```

### Enable GitHub Scorecard module

```yaml
plugins:
  - package: oci://ghcr.io/redhat-developer/rhdh-plugin-export-overlays/red-hat-developer-hub-backstage-plugin-scorecard-backend-module-github:bs_1.49.4__2.7.7
    disabled: false
```

### Catalog entity annotations

```yaml
apiVersion: backstage.io/v1alpha1
kind: Component
metadata:
  name: my-service
  annotations:
    github.com/project-slug: myorg/my-service
    backstage.io/source-location: url:https://github.com/myorg/my-service
spec:
  type: service
  lifecycle: production
  owner: <your_team_name>
```

### GitHub threshold customization

```yaml
scorecard:
  plugins:
    github:
      open_prs:
        thresholds:
          rules:
            - key: success
              expression: '<10'
            - key: warning
              expression: '10-50'
            - key: error
              expression: '>50'
```

---

## 4. Jira Integration

### Enable Jira module (direct setup)

```yaml
plugins:
  - package: oci://ghcr.io/redhat-developer/rhdh-plugin-export-overlays/red-hat-developer-hub-backstage-plugin-scorecard-backend-module-jira:bs_1.49.4__2.7.7
    disabled: false
```

### Direct setup — app-config.yaml

```yaml
jira:
  baseUrl: ${JIRA_BASE_URL}
  token: ${JIRA_TOKEN}
  product: <cloud|datacenter>
```

### Proxy setup — app-config.yaml

```yaml
proxy:
  endpoints:
    '/jira/api':
      target: ${JIRA_BASE_URL}
      headers:
        Accept: 'application/json'
        Content-Type: 'application/json'
        X-Atlassian-Token: 'no-check'
        Authorization: ${JIRA_TOKEN}
jira:
  proxyPath: /jira/api
  product: cloud
```

### Jira catalog entity annotations

```yaml
metadata:
  annotations:
    jira/project-key: PROJECT
    jira/component: Component        # optional
    jira/label: UI                   # optional
    jira/team: <team_id>             # optional
    jira/custom-filter: '<JQL>'      # optional
```

### Jira threshold and filter customization

```yaml
scorecard:
  plugins:
    jira:
      open_issues:
        thresholds:
          rules:
            - key: success
              expression: '<10'
            - key: warning
              expression: '10-50'
            - key: error
              expression: '>50'
        options:
          mandatoryFilter: Type = Task AND Resolution = Unresolved
          customFilter: priority in ("Critical", "Blocker")
```

---

## 5. OpenSSF Integration (Developer Preview)

```yaml
plugins:
  - package: oci://ghcr.io/redhat-developer/rhdh-plugin-export-overlays/red-hat-developer-hub-backstage-plugin-scorecard-backend-module-openssf:bs_1.49.4__0.2.11
    disabled: false
```

Annotation: `openssf/scorecard-location: https://api.securityscorecards.dev/projects/github.com/<owner>/<repo>`

Fixed thresholds: Error < 2, Warning 2-7, Success > 7 (not configurable).

---

## 6. Filecheck Integration (Developer Preview)

```yaml
plugins:
  - package: oci://ghcr.io/redhat-developer/rhdh-plugin-export-overlays/red-hat-developer-hub-backstage-plugin-scorecard-backend-module-filecheck:bs_1.49.4__0.1.8
    disabled: false
```

```yaml
scorecard:
  plugins:
    filecheck:
      files:
        license: LICENSE
        codeowners: CODEOWNERS
        contributing: CONTRIBUTING.md
        readme: README.md
      schedule:
        frequency:
          cron: '0 6 * * *'
        timeout:
          minutes: 5
        initialDelay:
          seconds: 5
```

File paths must be relative (no leading `/`, `./`, or `../`).
Fixed boolean thresholds: exist = success, missing = error.

---

## 7. Disable Metrics

### Per-entity

```yaml
metadata:
  annotations:
    scorecard.io/disabled-metrics: openssf.maintained,filecheck.readme,filecheck.license
```

### Globally

```yaml
scorecard:
  disabledMetrics:
    - openssf.packaging
  entityAnnotations:
    disabledMetrics:
      enabled: true
      except:
        - openssf.maintained
```

---

## 8. Threshold Configuration

### Precedence (highest to lowest)

1. Entity annotations (`catalog-info.yaml`)
2. App configuration (`app-config.yaml`)
3. Provider defaults (backend plugin code)

### Entity-level override annotation format

`scorecard.io/<providerId>.thresholds.rules.<key>: '<expression>'`

Example:

```yaml
metadata:
  annotations:
    scorecard.io/jira.open_issues.thresholds.rules.warning: '10-15'
    scorecard.io/jira.open_issues.thresholds.rules.error: '>15'
```

### Custom severity levels with colors and icons

```yaml
scorecard:
  plugins:
    myDatasource:
      myMetric:
        thresholds:
          rules:
            - key: ideal
              expression: '<10'
              color: '#5CE65C'
              icon: star
            - key: warning
              expression: '10-50'
              color: 'rgb(233, 213, 2)'
              icon: monitor
            - key: critical
              expression: '>50'
              color: error.main
              icon: scorecardErrorStatusIcon
```

Supported color formats: theme palette (`success.main`), hex (`#5CE65C`),
rgb/rgba (`rgb(233, 213, 2)`).

Supported icon formats: Backstage system (`kind:component`), Material Design
(`star`, `monitor`), inline SVG, external URL, data URI.

---

## 9. Aggregated KPIs

### Configure KPIs (app-config.yaml)

```yaml
scorecard:
  aggregationKPIs:
    openIssuesKpi:
      title: 'Jira open issues KPI'
      description: 'Open issues across entities you own, grouped by status.'
      type: statusGrouped
      metricId: jira.open_issues
```

### Average tracking type with statusScores

```yaml
scorecard:
  aggregationKPIs:
    portfolio-average-health:
      title: "Portfolio Health KPI"
      description: "Weighted average score across portfolio components"
      type: average
      metricId: github.open_prs
      options:
        statusScores:
          success: 100
          warning: 50
          error: 0
```

### Homepage card mount (dynamic-plugin-config.yaml)

```yaml
- mountPoint: home.page/cards
  importName: ScorecardHomepageCard
  config:
    props:
      aggregationId: "github.open_prs"
    layouts:
      xl: { w: 3, h: 6, x: 3 }
      lg: { w: 4, h: 6, x: 4 }
      md: { w: 6, h: 6, x: 6 }
      sm: { w: 12, h: 6 }
      xs: { w: 12, h: 6 }
      xxs: { w: 12, h: 6 }
```

---

## 10. Scheduling and Retention

### Custom schedule per metric

```yaml
scorecard:
  plugins:
    my_datasource:
      example_metric:
        schedule:
          frequency:
            cron: '0 6 * * *'
          timeout:
            minutes: 5
          initialDelay:
            minutes: 1
```

### Data retention

```yaml
scorecard:
  dataRetentionDays: 12
```

Default: 365 days.

---

## 11. REST API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /metrics` | List all available metrics (filter: `metricIds` or `datasource`) |
| `GET /metrics/catalog/:kind/:namespace/:name` | Latest metric values for entity |
| `GET /aggregations/:aggregationId` | Aggregated KPI summary (active) |
| `GET /metrics/:metricId/catalog/aggregations` | Aggregated summary (deprecated) |

Required permissions: `scorecard.metric.read`, `catalog.entity.read`.

---

## 12. Ownership for Aggregation

### Group entity

```yaml
apiVersion: backstage.io/v1alpha1
kind: Group
metadata:
  name: <example_team>
  namespace: <your_namespace>
spec:
  type: team
  children: [user:<your_namespace>/userName]
```

### User entity

```yaml
apiVersion: backstage.io/v1alpha1
kind: User
metadata:
  name: userName
  title: Example User
spec:
  profile:
    displayName: Example User
  memberOf: [group:<your_namespace>/example-team]
```
