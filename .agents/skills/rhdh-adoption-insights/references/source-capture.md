# Source Capture

## Official Source

| Field | Value |
|-------|-------|
| Product family | Red Hat Developer Hub |
| Product version | 1.10 |
| Documentation category | Observability |
| Official guide | Adoption Insights in Red Hat Developer Hub |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/adoption_insights_in_red_hat_developer_hub/index |
| Single-page URL | https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/adoption_insights_in_red_hat_developer_hub/index |
| Capture date | 2026-07-06 |

## Captured Sections

- Chapter 1: Adoption Insights overview
- Chapter 2: Enable the Adoption Insights plugin
- Chapter 3: Disable the Adoption Insights plugin
- Chapter 4: Customize the Adoption Insights plugin in Red Hat Developer Hub
- Chapter 5: Use Adoption Insights in Red Hat Developer Hub
  - 5.1 Set the duration of data metrics
- Chapter 6: View the Adoption Insights card
  - 6.1 View the active users
  - 6.2 View the total number of users
  - 6.3 View the top catalog entities
  - 6.4 View the top 3 templates
  - 6.5 View the top 3 TechDocs documents
  - 6.6 View the top 3 plugins
- Chapter 7: Change the number of displayed records
- Chapter 8: Filter records to display specific catalog entities in Top catalog entities
- Chapter 9: View searches

## Source Boundaries

This source is authoritative for Adoption Insights plugin configuration and
dashboard analytics in RHDH 1.10, including enable/disable, customization
(buffer, flush, debug, licensed users), RBAC permissions, dashboard cards,
time range selection, record count, entity filtering, and CSV export.

It does **not** cover:
- Software Catalog or Bulk Import workflows (separate guide)
- TechDocs documentation lifecycle (separate guide)
- Plugin installation framework (separate guide)
- Segment analytics provider internals
- RBAC policy management (separate guide)

## API Versions Documented

No Kubernetes resources documented in this guide. Configuration is via
`app-config.yaml` and `dynamic-plugins.yaml`.

## Related Official Sources to Add Later

- Red Hat Developer Hub 1.10 "Streamline software development and management" — Catalog and template workflows
- Red Hat Developer Hub 1.10 "Manage and consume technical documentation" — TechDocs lifecycle
- Red Hat Developer Hub 1.10 "Authorization" — RBAC policies
