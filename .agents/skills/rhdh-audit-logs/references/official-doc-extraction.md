# Official Doc Extraction

Use this reference when authoring or reviewing RHDH audit log content.

## Component Purpose

Red Hat Developer Hub audit logs provide a chronological record of user
activities, system events, and data changes. They enable security tracing,
automated compliance, and debugging of software templates and plugins.

Audit logs track:

- Scaffolder events
- RBAC system changes
- Catalog database changes
- Actor information (terminal, port, IP address, hostname)
- Event metadata (date, time, status, severity)

## Prerequisites

Before configuring audit log forwarding:

- Access to the OpenShift Container Platform web console
- `cluster-admin` privileges
- OpenShift Logging Operator installed in `openshift-logging` namespace
- For Splunk: a Splunk Cloud account or Splunk Enterprise installation

## Configuration Components

### Logging Deployment

Configure logging deployment with CPU and memory limits per the OCP
Configuring your Logging deployment documentation.

### Log Collector

Configure `spec.collection` in the `ClusterLogging` CR to collect logs from
STDOUT per the OCP Configuring the logging collector documentation.

### Log Forwarding

Configure `ClusterLogForwarder` CR with outputs and pipelines to send logs to
endpoints inside and outside the cluster.

## Splunk Forwarding

### ServiceAccount Setup

```bash
oc project openshift-logging
oc create sa log-collector
oc create clusterrolebinding log-collector \
  --clusterrole=collect-application-logs \
  --serviceaccount=openshift-logging:log-collector
```

### HEC Token Secret

```bash
oc -n openshift-logging create secret generic splunk-secret \
  --from-literal=hecToken=<HEC_Token>
```

### ClusterLogForwarder CR

Key sections of the CR:

| Section | Purpose |
|---------|---------|
| `serviceAccount.name: log-collector` | ServiceAccount for log collection |
| `inputs[].type: application` | Capture application logs from specified namespaces |
| `inputs[].application.includes[].namespace` | Target RHDH namespace |
| `inputs[].application.containerLimit.maxRecordsPerSecond` | Rate limiting |
| `outputs[].type: splunk` | Splunk output type |
| `outputs[].splunk.authentication.token.secretName` | HEC token secret reference |
| `outputs[].splunk.index` | Splunk index name |
| `outputs[].splunk.url` | Splunk instance URL |
| `filters[].type: drop` | Log filtering |
| `filters[].drop[].test[].field: .message` | Filter field |
| `filters[].drop[].test[].notMatches: isAuditEvent` | Keep only audit events |
| `pipelines[].inputRefs` | Connect inputs to pipeline |
| `pipelines[].outputRefs` | Connect outputs to pipeline |
| `pipelines[].filterRefs` | Apply filters to pipeline |

### Collector Tuning

```yaml
collector:
  resources:
    requests:
      cpu: 250m
      memory: 64Mi
      ephemeral-storage: 250Mi
    limits:
      cpu: 500m
      memory: 128Mi
      ephemeral-storage: 500Mi
tuning:
  delivery: AtLeastOnce
  compression: none
  minRetryDuration: 1s
  maxRetryDuration: 10s
```

`AtLeastOnce` delivery ensures logs read but not yet delivered are re-sent
after a crash; some log duplication may occur.

## Viewing Audit Logs in OpenShift Console

1. From Developer perspective, click Topology tab.
2. Click the target RHDH pod.
3. Click Resources tab, then View logs under Pods.
4. Enter `isAuditEvent` in the Search field to filter audit logs.

## RBAC Audit Log Events

### Event IDs

| Event ID | Description |
|----------|-------------|
| `role-write` | Creation, modification, or removal of RBAC roles via REST API, CSV, or configuration |
| `role-read` | Retrieval of one or all existing RBAC roles |
| `policy-write` | Creation, update, or deletion of permission policies |
| `policy-read` | Retrieval or listing of defined permission policies |
| `condition-write` | Modification of conditional policies via YAML or API |
| `condition-read` | Retrieval of conditional policy definitions |
| `permission-evaluation` | Evaluation of user identity against policies to allow or deny |
| `plugin-policies-read` | Listing available permission policies supported by installed plugins |
| `plugin-ids-write` | Updates to the list of plugins integrated with the permission framework |

### Metadata Fields

| Field | Description |
|-------|-------------|
| `source` | Origin: `rest`, `csv-file`, `configuration`, or `externalProviderPluginId` |
| `actionType` | Operation: `create`, `update`, `delete`, or `create_or_update` |
| `roleEntityRef` | Entity reference of the affected role |
| `members` | Users or groups associated with the role |
| `decision` | Policy decision in evaluation events: `allow` or `deny` |
| `result` | Final outcome such as `AuthorizeResult` |

### Example Log Entry

```
[backend]: 2025-03-25T17:24:17.458Z permission info permission.role-write
isAuditEvent=true eventId="role-write" severityLevel="medium"
actor={"actorId":"user:default/admin"}
request={"url":"/api/permission/roles","method":"POST"}
meta={"actionType":"create","source":"rest","roleEntityRef":"role:default/test-role"}
status="succeeded"
```

## Verification Commands

```bash
oc get pods -n openshift-logging
oc get clusterlogforwarder -n openshift-logging -o yaml
oc get sa log-collector -n openshift-logging
oc get clusterrolebinding log-collector
oc -n openshift-logging get secret/splunk-secret -o yaml
```
