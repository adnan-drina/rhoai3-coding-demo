---
name: rhdh-adoption-insights
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhdh"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Developer Hub"
description: >
  Use when configuring adoption analytics, engagement metrics, and portal usage
  insights in Red Hat Developer Hub 1.10. Covers the Adoption Insights plugin
  (enable, disable, customize), dashboard cards (active users, total users,
  top catalog entities, templates, TechDocs, plugins, searches), RBAC
  permissions, and CSV export. Do NOT use for TechDocs documentation lifecycle
  (use rhdh-techdocs-manage) or Software Catalog workflows
  (use rhdh-develop).
---

# RHDH Adoption Insights

Use this skill for Adoption Insights configuration and usage in Red Hat
Developer Hub 1.10 grounded in official product documentation.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority. This skill covers the Adoption Insights
plugin lifecycle and dashboard analytics.

## Key Capabilities

1. **Adoption Insights plugin** — Preinstalled and enabled by default via
   `backstage-community-plugin-analytics-provider-segment`. Can be disabled
   in `dynamic-plugins.yaml`.
2. **Dashboard cards** — Active users, total number of users, top catalog
   entities, top 3 templates, top 3 TechDocs, top 3 plugins, searches.
3. **Configuration** — Buffer size, flush interval, debug mode, licensed users
   count, and RBAC permissions in `app-config.yaml`.
4. **Data export** — Active users data exportable in CSV format.
5. **Time range selection** — Today, last week, last month, last 28 days
   (default), last year, custom date range.
6. **Record count** — Configurable display: top 3, 5, 10, or 20 records.

## Plugin Configuration

### Enable (default state)

```yaml
plugins:
  - package: ./dynamic-plugins/dist/backstage-community-plugin-analytics-provider-segment
    disabled: false
```

### Disable

```yaml
plugins:
  - package: ./dynamic-plugins/dist/backstage-community-plugin-analytics-provider-segment
    disabled: true
```

### Customize settings

```yaml
app:
  analytics:
    adoptionInsights:
      maxBufferSize: 20          # event batching buffer (default: 20)
      flushInterval: 5000        # flush interval in ms (default: 5000)
      debug: false               # debug logging (default: false)
      licensedUsers: 100         # licensed user cap (default: 100)
```

### RBAC for non-admin users

```yaml
p, role:default/<your_team>, adoption-insights.events.read, read, allow
g, user:default/<your_user>, role:default/<your_team>
```

## Dashboard Cards

| Card | Data shown |
|------|-----------|
| Active users | Returning + new users over time; CSV export |
| Total number of users | Logged-in vs licensed users (numeric + %) |
| Top catalog entities | Name, kind, last used, views |
| Top 3 templates | Name, mostly in use by, executions |
| Top 3 TechDocs | Name, entity type, last used, views |
| Top 3 plugins | Name, trend graph, views |
| Searches | Search volume trends, total, averages |

### Card display details

- Name column shows `metadata.title`; falls back to `metadata.name`
- Hover for tooltip: `entityRef | type | description`
- Long titles truncated with ellipsis
- Down arrow next to "3 rows" changes record count (3, 5, 10, 20)
- Top catalog entities filterable by entity type via dropdown

## Access

Navigate: Administration > Adoption Insights

## Workflow

1. Read `references/official-doc-extraction.md` for exact configuration.
2. Identify the task:
   - Enabling or disabling the Adoption Insights plugin
   - Customizing buffer, flush, debug, or licensed user settings
   - Granting RBAC access to non-admin users
   - Viewing dashboard cards and metrics
   - Exporting active user data to CSV
   - Changing time range or record count
3. Use exact plugin package path and `app-config.yaml` keys.
4. Validate via Administration > Adoption Insights dashboard.

## Related Skills

- `rhdh-develop` — Software Catalog and template workflows
- `rhdh-techdocs-manage` — TechDocs documentation lifecycle

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
