---
name: rhdh-scorecards
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhdh"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Developer Hub"
description: >
  Use when setting up, configuring, and managing customizable Project Health
  Scorecards in Red Hat Developer Hub 1.10. Covers enabling the Scorecard
  plugin, configuring GitHub/Jira/OpenSSF/Filecheck metric providers, RBAC
  permissions, threshold customization, aggregated KPIs, homepage cards, and
  the Scorecard REST API. Do NOT use for general RHDH installation (use
  rhdh-install), Orchestrator workflows (use rhdh-orchestrator), or
  diagnostic data collection (use rhdh-diagnostic-data).
---

# RHDH Scorecards

Use this skill to configure and manage Project Health Scorecards in
Red Hat Developer Hub 1.10 grounded in official product documentation.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority.

## Support Posture

The Scorecard plugin has mixed support levels:
- **GitHub and Jira metric providers** — fully supported with configurable
  thresholds.
- **OpenSSF, Filecheck, and Dependabot providers** — Developer Preview (not
  production-ready, no SLA).

## Key Capabilities

1. **Enable the Scorecard plugin** — frontend and backend OCI packages in
   `dynamic-plugin-config.yaml`.
2. **RBAC** — permission `scorecard.metric.read` via CSV policy or Web UI;
   conditional policies using `HAS_METRIC_ID` rule.
3. **GitHub metrics** — `github.open_prs` via GitHub App or token; requires
   `github.com/project-slug` and `backstage.io/source-location` annotations.
4. **Jira metrics** — `jira.open_issues` via Cloud or Data Center; direct or
   proxy setup; requires `jira/project-key` annotation.
5. **OpenSSF metrics** — 16 fixed-threshold security scores (Developer Preview);
   requires `openssf/scorecard-location` annotation.
6. **Filecheck metrics** — boolean file-existence checks (Developer Preview);
   relies on `backstage.io/source-location` annotation.
7. **Threshold customization** — global in `app-config.yaml`, per-entity via
   `scorecard.io/` annotations; sequential evaluation, most-restrictive first.
8. **Custom severity levels** — custom keys, colors (hex/rgb/theme palette),
   and icons (Material Design, Backstage system, SVG, URL).
9. **Disable metrics** — per-entity via `scorecard.io/disabled-metrics`
   annotation; globally via `scorecard.disabledMetrics`.
10. **Aggregated KPIs** — `statusGrouped` or `average` types under
    `scorecard.aggregationKPIs`; homepage cards via `ScorecardHomepageCard`.
11. **Metric scheduling** — per-metric cron via
    `scorecard.plugins.<source>.<metric>.schedule`.
12. **Data retention** — `scorecard.dataRetentionDays` (default: 365).
13. **Scorecard REST API** — `GET /metrics`, `GET /metrics/catalog/:kind/:namespace/:name`,
    `GET /aggregations/:aggregationId`.

## Plugin Packages

| Component | OCI Package |
|-----------|-------------|
| Frontend | `red-hat-developer-hub-backstage-plugin-scorecard` |
| Backend | `red-hat-developer-hub-backstage-plugin-scorecard-backend` |
| GitHub module | `red-hat-developer-hub-backstage-plugin-scorecard-backend-module-github` |
| Jira module | `red-hat-developer-hub-backstage-plugin-scorecard-backend-module-jira` |
| OpenSSF module | `red-hat-developer-hub-backstage-plugin-scorecard-backend-module-openssf` |
| Filecheck module | `red-hat-developer-hub-backstage-plugin-scorecard-backend-module-filecheck` |

All packages use format `bs_<backstage_version>__<plugin_version>` tags from
`ghcr.io/redhat-developer/rhdh-plugin-export-overlays/`.

## Catalog Entity Annotations

| Annotation | Provider | Required |
|------------|----------|----------|
| `github.com/project-slug` | GitHub | Yes |
| `backstage.io/source-location` | GitHub, Filecheck | Yes |
| `jira/project-key` | Jira | Yes |
| `jira/component`, `jira/label`, `jira/team`, `jira/custom-filter` | Jira | No |
| `openssf/scorecard-location` | OpenSSF | Yes |
| `scorecard.io/disabled-metrics` | All | No |
| `scorecard.io/<metricId>.thresholds.rules.<key>` | Configurable | No |

## Workflow

1. Read `references/official-doc-extraction.md` for exact YAML patterns.
2. Identify the task: enable plugin, configure a provider, set RBAC, customize
   thresholds, configure aggregated KPIs, or add homepage cards.
3. Use exact OCI package references with `bs_<version>__<version>` tags.
4. Validate with the verification steps documented per section.
5. Never invent plugin config fields not documented in the official source.

## Related Skills

- `rhdh-diagnostic-data` — must-gather diagnostic data collection
- `rhdh-orchestrator` — Orchestrator serverless workflows

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
