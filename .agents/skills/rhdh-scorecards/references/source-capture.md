# Source Capture

## Official Source

| Field | Value |
|-------|-------|
| Product family | Red Hat Developer Hub |
| Product version | 1.10 |
| Documentation category | Observability |
| Official guide | Evaluate project health using Scorecards |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/evaluate_project_health_using_scorecards/index |
| Single-page URL | https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/evaluate_project_health_using_scorecards/index |
| Capture date | 2026-07-06 |

## Captured Sections

- Chapter 1: Component health and compliance monitoring using Scorecards
  - Support posture (Developer Preview for OpenSSF, Filecheck)
  - Goals: risk identification, security standards, workflow streamlining
- Chapter 2: Available scorecard metric providers and metric IDs
  - GitHub: `github.open_prs`
  - Jira: `jira.open_issues`
  - OpenSSF: 16 metrics (`openssf.binary_artifacts` through `openssf.vulnerabilities`)
  - Filecheck: `filecheck.<key>` (dynamic per configuration)
- Chapter 3: Set up Scorecards to monitor your project health
  - 3.1 Enable Scorecards (dynamic-plugin-config.yaml)
  - 3.2 Configure RBAC using CSV file
  - 3.3 Configure RBAC using Web UI
- Chapter 4: Install and configure Scorecards to view metrics
  - 4.1 Integrate GitHub health metrics (App + token methods)
  - 4.2 Integrate Jira health metrics (direct + proxy setup)
  - 4.3 Integrate OpenSSF security metrics (Developer Preview)
  - 4.4 Configure file-level checks (Filecheck, Developer Preview)
  - 4.5 Disable specific scorecard metrics per entity
  - 4.6 Disable scorecard metrics globally
- Chapter 5: Scorecard metric thresholds
  - 5.1 Categorization rules (sequential evaluation)
  - 5.2 Supported expression syntax
  - 5.3 Threshold precedence (entity > app-config > provider defaults)
  - 5.4 Standardize thresholds across components
  - 5.5 Override entity-specific thresholds via annotations
  - 5.6 Verify logical flow in threshold rules
  - 5.7 Custom severity levels, colors, and icons
  - 5.8 Color and icon configuration formats
- Chapter 6: Monitor component health with Scorecard metrics
- Chapter 7: Monitor collective health across components
  - 7.1 Monitor portfolio health with aggregated KPIs
  - 7.2 Aggregated KPIs overview
  - 7.3 Configure aggregated KPIs
  - 7.4 View detailed drill-down metrics
  - 7.5 Schedule metrics to avoid API limits
  - 7.6 Adjust metric retention
  - 7.7 Establishing ownership in Software Catalog
  - 7.8 View aggregated metrics for owned entities
  - 7.9 Available metric data (REST API endpoints)
  - 7.10 Scorecard card configuration parameters
  - 7.11 REST API endpoints and parameters
- Chapter 8: Configure scorecard cards on the homepage
  - 8.1 Default scorecard aggregation card
  - 8.2 Status-grouped tracking type
  - 8.3 Average tracking type
  - 8.4 Customizable home page
  - 8.5 Read-only home page

## Source Boundaries

This source is authoritative for enabling, configuring, and managing the
Scorecard plugin in Red Hat Developer Hub 1.10. It covers plugin enablement,
RBAC, GitHub/Jira/OpenSSF/Filecheck metric providers, threshold configuration,
aggregated KPIs, homepage cards, REST API, scheduling, retention, and ownership.

It does **not** cover:
- General RHDH installation or Operator/Helm deployment
- Other RHDH plugins (Orchestrator, TechDocs, etc.)
- Diagnostic data collection (separate guide)
- RHDH RBAC beyond Scorecard-specific permissions

## Related Official Sources

- Red Hat Developer Hub 1.10 "Orchestrator" guide — serverless workflows
- Red Hat Developer Hub 1.10 "Collect diagnostic data" guide — must-gather
- Red Hat Developer Hub 1.10 "Dynamic Plugins Reference" — plugin versions
