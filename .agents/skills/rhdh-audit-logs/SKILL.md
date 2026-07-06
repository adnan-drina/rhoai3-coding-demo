---
name: rhdh-audit-logs
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhdh"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Developer Hub"
description: >
  Use when configuring audit logging to track user activities, system events,
  and data changes in Red Hat Developer Hub 1.10. Covers audit log overview,
  configuring logging deployment and log forwarding on OpenShift, forwarding
  audit logs to Splunk via ClusterLogForwarder, viewing audit logs from the
  OpenShift web console, and RBAC audit log events and metadata. Do NOT use
  for general RHDH monitoring, metrics, or performance tracking; use
  rhdh-monitoring. Do NOT use for telemetry data collection or Segment
  analytics; use rhdh-telemetry.
---

# RHDH Audit Logs

Use this skill to configure, forward, and review audit logs in Red Hat
Developer Hub 1.10.

## Source Grounding

Read `references/source-capture.md` before using product configuration details.
Official Red Hat documentation is the product authority. This skill adapts
the official Audit Logs guide for this repo's demo posture.

## Scope

Audit logs are a chronological set of records documenting user activities,
system events, and data changes. They provide:

- Security traceability for scaffolder events and RBAC changes
- Automated compliance through structured log data
- Debugging information for software templates and plugins

Each audit log entry includes: event name, actor details (terminal, port, IP,
hostname), event metadata (date, time), event status (success, failure), and
severity level (info, debug, warn, error).

## Demo Policy

For this repo:

- Treat audit logging as optional until a demo step explicitly introduces it.
- Log forwarding requires the OpenShift Logging Operator in `openshift-logging`.
- Do not commit real Splunk HEC tokens or external log receiver credentials.
- Use `isAuditEvent` as the filter field to isolate audit logs from other types.
- Forward audit logs only when an external receiver is approved and reachable.

## Workflow

1. Confirm RHDH 1.10 is installed (Operator or Helm chart).
2. Configure the OpenShift logging deployment, log collector, and log
   forwarding per `references/official-doc-extraction.md`.
3. If forwarding to Splunk, create the `log-collector` ServiceAccount, bind
   `collect-application-logs`, create the HEC token secret, and apply the
   `ClusterLogForwarder` CR.
4. Filter audit logs with `isAuditEvent` in the `ClusterLogForwarder` filters
   or in the OpenShift web console Logs view.
5. Review RBAC audit events (`role-write`, `policy-write`,
   `permission-evaluation`) to verify access governance.
6. Validate with `references/official-doc-extraction.md` verification steps.

## RBAC Audit Events

Key event IDs tracked by the RBAC backend plugin:

| Event ID | Description |
|----------|-------------|
| `role-write` | Creation, modification, or removal of RBAC roles |
| `role-read` | Retrieval of existing RBAC roles |
| `policy-write` | Creation, update, or deletion of permission policies |
| `policy-read` | Retrieval of defined permission policies |
| `condition-write` | Modification of conditional policies |
| `condition-read` | Retrieval of conditional policy definitions |
| `permission-evaluation` | Evaluation of user identity against policies |
| `plugin-policies-read` | Listing available plugin permission policies |
| `plugin-ids-write` | Updates to permission framework plugin list |

RBAC audit log metadata fields include `source` (rest, csv-file,
configuration), `actionType` (create, update, delete), `roleEntityRef`,
`members`, `decision` (allow, deny), and `result`.

## Verification Commands

```bash
oc get pods -n openshift-logging
oc get clusterlogforwarder -n openshift-logging
oc get sa log-collector -n openshift-logging
oc get clusterrolebinding log-collector
oc -n openshift-logging get secret/splunk-secret -o yaml
```

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
