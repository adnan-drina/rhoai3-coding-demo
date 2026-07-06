# Official Documentation Extraction

Source: Red Hat Developer Hub 1.10 — Adoption Insights
Captured: 2026-07-06

---

## 1. Adoption Insights Overview

The Adoption Insights plugin is preinstalled and enabled by default in RHDH.
It visualizes key metrics and trends for portal usage, helping platform
engineers make data-driven decisions.

### Dashboard cards

- Active users
- Total number of users
- Top catalog entities
- Top 3 templates
- Top 3 TechDocs
- Top 3 plugins
- Portal searches

---

## 2. Enable the Plugin

Plugin is enabled by default. If migrating from Developer Preview or after
manual installation, update configuration:

```yaml
plugins:
  - package: ./dynamic-plugins/dist/backstage-community-plugin-analytics-provider-segment
    disabled: false
```

---

## 3. Disable the Plugin

```yaml
plugins:
  - package: ./dynamic-plugins/dist/backstage-community-plugin-analytics-provider-segment
    disabled: true
```

---

## 4. Customize the Plugin

### app-config.yaml settings

```yaml
app:
  analytics:
    adoptionInsights:
      maxBufferSize: <maximum_buffer_size>
      flushInterval: <flush_interval>
      debug: <debug_value>
      licensedUsers: <licensed_users>
```

| Setting | Description | Default |
|---------|-------------|---------|
| `maxBufferSize` | Maximum buffer size for event batching | 20 |
| `flushInterval` | Flush interval in milliseconds | 5000 |
| `debug` | Enable debug logging (true/false) | false |
| `licensedUsers` | Maximum licensed users for the RHDH instance | 100 |

### RBAC for non-admin users

```yaml
p, role:default/<your_team>, adoption-insights.events.read, read, allow
g, user:default/<your_user>, role:default/<your_team>
```

---

## 5. Access Adoption Insights

Navigate: Administration > Adoption Insights

### Time range options

- Today
- Last week
- Last month
- Last 28 days (default)
- Last year
- Date range… (custom)

Select from the dropdown at the top of the dashboard.

---

## 6. Dashboard Cards

### 6.1 Active Users

Displays total active users over the selected time period:
- **Returning users:** Existing users who logged in before
- **New users:** First-time registrations and logins
- Hover over dates for exact counts
- **Export CSV:** Click "Export CSV" link

### 6.2 Total Number of Users

Compares logged-in users versus licensed users:
- **Logged-in users:** Total users (licensed + unlicensed) currently logged in
- **Licensed users:** Licensed users logged in (target set via
  `licensedUsers` in `app-config.yaml`)
- Numeric and percentage display
- Hover tooltip for percentage of logged-in among licensed

### 6.3 Top Catalog Entities

Most-viewed catalog entities and documentation entries:

| Column | Description |
|--------|-------------|
| Name | Catalog entity name |
| Kind | Entity type |
| Last used | Last access time |
| Views | Total view count |

Filterable by entity type via dropdown on the card.

### 6.4 Top 3 Templates

Most commonly used templates:

| Column | Description |
|--------|-------------|
| Name | Template name |
| Mostly in use by | User type using it most |
| Executions | Number of runs |

### 6.5 Top 3 TechDocs

Most-viewed documentation entries:

| Column | Description |
|--------|-------------|
| Name | Document title |
| Entity | Document type |
| Last used | Last view time |
| Views | Total view count |

### 6.6 Top 3 Plugins

Most commonly used plugins:

| Column | Description |
|--------|-------------|
| Name | Plugin name |
| Trend | Popularity graph |
| Views | Total view count |

### Card display conventions

- Name shows `metadata.title`; falls back to `metadata.name`
- Hover for tooltip: `entityRef | type | description`
- Long titles truncated with ellipsis

---

## 7. Change Displayed Record Count

Applicable cards: Top catalog entities, Top 3 templates, Top 3 TechDocs,
Top 3 plugins.

Options: Top 3 (default), Top 5, Top 10, Top 20.

Click down arrow next to "3 rows" on the card.

---

## 8. Filter Top Catalog Entities

By default, all entity types are shown. Use the dropdown on the Top catalog
entities card to filter by specific entity type.

---

## 9. Searches Card

Visualizes portal search trends:
- Graph of search volume over time
- Total searches for the selected period (in card title)
- Average searches per hour/day/week/month depending on time range
