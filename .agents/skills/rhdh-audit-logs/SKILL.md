---
name: rhdh-audit-logs
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhdh
  docs-version: "1.10"
  skill-group: "Developer Hub"
description: >
  Use when someone asks about Red Hat Developer Hub 1.10 audit logs: what they
  contain, configuring their collection on OpenShift, forwarding to Splunk,
  viewing them, and the RBAC audit events. Not used in this repo: no audit-log
  forwarding is configured. Do NOT use for log levels and metrics (use
  rhdh-monitoring) or RBAC policy changes (use rhdh-authorization).
---

# Developer Hub audit logs

Thin skill, link-only stub: the feature is not used in this repo. Product
behavior lives in the linked Developer Hub 1.10 sections.

## When to use

- Someone needs who-did-what evidence from the portal, or log forwarding for it.

## Not used in this repo

The repo configures no audit-log collection or forwarding for the `rhdh`
namespace. Read them from the `backstage-developer-hub` pod logs in `rhdh`;
forwarding needs a cluster log collector, which this repo does not deploy.

Adopting it is a Stage 070 change: record the decision in
`gitops/stages/070-advanced-app-platform/070-rhdh/README.md` and convert this stub
to a full thin skill.

## Official documentation (Developer Hub 1.10)

| Topic | Section |
|---|---|
| Audit logs overview | [Audit logs overview][l1] |
| Configure audit logs on OpenShift | [Configure audit logs on OpenShift][l2] |
| Forward to Splunk | [Forward to Splunk][l3] |
| View audit logs | [View audit logs][l4] |
| RBAC audit log events | [RBAC audit log events][l5] |

## Related skills

`rhdh-monitoring`, `rhdh-authorization`, `ocp-observability`.

[l1]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/audit_logs_in_red_hat_developer_hub/index#audit-logs-overview_audit-logs-in-rhdh
[l2]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/audit_logs_in_red_hat_developer_hub/index#configure-audit-logs-for-rhdh-on-ocp_audit-logs-in-rhdh
[l3]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/audit_logs_in_red_hat_developer_hub/index#forward-rhdh-audit-logs-to-splunk_audit-logs-in-rhdh
[l4]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/audit_logs_in_red_hat_developer_hub/index#view-audit-logs-in-rhdh_audit-logs-in-rhdh
[l5]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/audit_logs_in_red_hat_developer_hub/index#rbac-audit-log-events_audit-logs-in-rhdh
