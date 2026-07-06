# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product | Red Hat Developer Hub |
| Product version | 1.10 |
| Book title | Audit logs in Red Hat Developer Hub |
| Book URL | https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/audit_logs_in_red_hat_developer_hub/index |
| Documentation category | Observability |
| Retrieved date | 2026-07-06 |
| Sections used | Chapter 1. Audit logs overview; Chapter 2. Configure audit logs for Developer Hub on OCP; Chapter 3. Forward RHDH audit logs to Splunk; Chapter 4. View audit logs in Developer Hub; Chapter 5. RBAC audit log events |

## Supporting Red Hat Sources

| Source | Role |
|--------|------|
| Red Hat OpenShift Container Platform — Configuring your Logging deployment | Logging deployment prerequisites |
| Red Hat OpenShift Container Platform — Configuring the logging collector | Log collector configuration for STDOUT |
| Red Hat OpenShift Container Platform — Enabling JSON log forwarding | Log forwarding prerequisites |
| Red Hat OpenShift Container Platform — Configuring log forwarding | ClusterLogForwarder endpoint and pipeline configuration |
| Red Hat OpenShift Container Platform — Forwarding logs to Splunk | Splunk-specific output configuration |

## Source Boundaries

- Product configuration truth: official Red Hat Developer Hub 1.10 Audit Logs
  book above.
- Audit log structure: `isAuditEvent` field, `eventId`, `actor`, `request`,
  `meta`, `status`, and `severityLevel` fields are authoritative from the
  official docs.
- RBAC audit events: `role-write`, `role-read`, `policy-write`, `policy-read`,
  `condition-write`, `condition-read`, `permission-evaluation`,
  `plugin-policies-read`, `plugin-ids-write` are documented event IDs.
- Demo policy: audit logging is optional until a demo step introduces it;
  external log receiver credentials are not committed.
- Not authoritative: upstream Backstage audit log plugin internals, Splunk
  configuration beyond what the RHDH docs describe, or OpenShift Logging
  Operator internals beyond ClusterLogForwarder usage.

## Unresolved Or Environment-Specific Items

- Splunk HEC token and endpoint URL are environment-specific secrets.
  Verification: obtain approved Splunk receiver credentials before applying
  ClusterLogForwarder.
- Log collector resource requests/limits depend on cluster sizing and log
  volume.
  Verification: adjust based on observed log throughput during demo.
- `containerLimit.maxRecordsPerSecond` and output `rateLimit.maxRecordsPerSecond`
  should be tuned per environment.
