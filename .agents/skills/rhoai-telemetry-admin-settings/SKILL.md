---
name: rhoai-telemetry-admin-settings
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when documenting, reviewing, or configuring Red Hat OpenShift AI
  administrator telemetry settings: usage data collection notice, enabling or
  disabling Red Hat usage data collection from Cluster settings, dashboard
  `disableTracking`, MaaS telemetry in the Tenant custom resource, token and
  request usage metrics, Usage dashboard, CSV export, and showback boundaries.
  Do NOT use for the central observability stack (use rhoai-observability),
  TrustyAI monitoring (use rhoai-monitoring-trustyai), MaaS subscriptions and
  authorization policy design (use rhoai-maas-governance), or generic OCP
  telemetry (use ocp-observability).
---

# RHOAI Telemetry Admin Settings

Use this skill for administrator-facing telemetry settings and usage-data
collection posture.

## Source Grounding

1. Read `docs/PLATFORM_BASELINE.md`.
2. Read `.agents/rules/rhoai.md`.
3. Use `references/source-capture.md` for source provenance.
4. Use `references/official-doc-extraction.md` for supported behavior.
5. Use `references/validation-checklist.md` before finalizing telemetry
   content.

## Scope

- Red Hat usage data collection in OpenShift AI Cluster settings.
- Usage data collection notice and privacy posture.
- Dashboard `disableTracking` behavior.
- MaaS telemetry settings and usage dashboard handoff.
- Showback and cost-attribution caveats.

## Demo Policy

- Be explicit when usage data collection is enabled or disabled in a demo
  environment.
- Do not claim billing-grade metering from MaaS usage dashboards.
- Treat telemetry settings as administrator decisions, not hidden defaults.
- Keep central observability stack setup in `rhoai-observability`.

## Workflow

1. Decide whether the task is Red Hat product usage data collection, MaaS usage
   telemetry, or observability stack setup.
2. For Red Hat usage data collection, use the managing resources source and
   dashboard settings.
3. For MaaS token/request usage metrics, use the MaaS source and route platform
   prerequisites to `rhoai-observability`.
4. Validate dashboard or CR settings through official docs and live schema
   checks before authoring GitOps.

## Related Skills

- `rhoai-observability` for Prometheus, OpenTelemetry Collector, Alertmanager,
  Tempo, and dashboard enablement.
- `rhoai-maas-governance` for MaaS subscriptions, model references, API keys,
  auth policies, and external model governance.
- `rhoai-dashboard-customization` for broad `OdhDashboardConfig` options.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/telemetry-review-pattern.md`
