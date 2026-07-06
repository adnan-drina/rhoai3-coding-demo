# Official Documentation Extraction

Source: Red Hat Developer Hub 1.10 — Orchestrator in Red Hat Developer Hub
Captured: 2026-07-06

---

## 1. Enable Orchestrator Plugins

The `{{inherit}}` attribute auto-resolves to the default plugin version for
your RHDH version.

```yaml
plugins:
  - package: "oci://registry.access.redhat.com/rhdh/red-hat-developer-hub-backstage-plugin-orchestrator:{{inherit}}"
    disabled: false
  - package: "oci://registry.access.redhat.com/rhdh/red-hat-developer-hub-backstage-plugin-orchestrator-backend:{{inherit}}"
    disabled: false
  - package: "oci://registry.access.redhat.com/rhdh/red-hat-developer-hub-backstage-plugin-scaffolder-backend-module-orchestrator:{{inherit}}"
    disabled: false
  - package: "oci://registry.access.redhat.com/rhdh/red-hat-developer-hub-backstage-plugin-orchestrator-form-widgets:{{inherit}}"
    disabled: false
  - package: "./dynamic-plugins/dist/backstage-plugin-notifications"
    disabled: false
  - package: "./dynamic-plugins/dist/backstage-plugin-signals"
    disabled: false
  - package: "./dynamic-plugins/dist/backstage-plugin-notifications-backend-dynamic"
    disabled: false
  - package: "./dynamic-plugins/dist/backstage-plugin-signals-backend-dynamic"
    disabled: false
```

### Restrict Workflows tab to Component entities

```yaml
mountPoints:
  - mountPoint: entity.page.workflows/cards
    importName: OrchestratorCatalogTab
    config:
      layout:
        gridColumn: 1 / -1
      if:
        allOf:
          - IsOrchestratorCatalogTabAvailable
          - isKind: component
```

---

## 2. Operator Installation

### Complete ConfigMap example

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: orchestrator-plugin
data:
    dynamic-plugins.yaml: |
      includes:
        - dynamic-plugins.default.yaml
      plugins:
        - package: "oci://registry.access.redhat.com/rhdh/red-hat-developer-hub-backstage-plugin-orchestrator:{{inherit}}"
          disabled: false
        - package: "oci://registry.access.redhat.com/rhdh/red-hat-developer-hub-backstage-plugin-orchestrator-backend:{{inherit}}"
          disabled: false
          dependencies:
            - ref: sonataflow
        - package: "oci://registry.access.redhat.com/rhdh/red-hat-developer-hub-backstage-plugin-scaffolder-backend-module-orchestrator:{{inherit}}"
          disabled: false
        - package: "oci://registry.access.redhat.com/rhdh/red-hat-developer-hub-backstage-plugin-orchestrator-form-widgets:{{inherit}}"
          disabled: false
```

The `ref: sonataflow` dependency triggers automatic provisioning of
SonataFlowPlatform CR and NetworkPolicies.

### Backend authentication ConfigMap and Secret

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config-rhdh
data:
  app-config.yaml: |-
    backend:
      auth:
        externalAccess:
          - type: static
            options:
              token: ${BACKEND_SECRET}
              subject: orchestrator
---
apiVersion: v1
kind: Secret
metadata:
  name: backend-auth-secret
stringData:
  BACKEND_SECRET: "<GENERATED_VALUE>"
```

### Backstage CR

```yaml
apiVersion: rhdh.redhat.com/v1alpha5
kind: Backstage
metadata:
  name: orchestrator
spec:
  application:
    appConfig:
      configMaps:
        - name: app-config-rhdh
    dynamicPluginsConfigMapName: orchestrator-plugin
    extraEnvs:
      secrets:
        - name: backend-auth-secret
```

---

## 3. External PostgreSQL — Operator

### Create database Job

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: create-sonataflow-database-developer-hub
spec:
  ttlSecondsAfterFinished: 30
  activeDeadlineSeconds: 120
  template:
    spec:
      containers:
        - name: psql
          image: quay.io/fedora/postgresql-15:latest
          envFrom:
            - secretRef:
                name: <SECRET-NAME-WITH-DB-CREDENTIALS>
          command: [ "sh", "-c" ]
          args:
            - |
              set -e
              DB_EXISTS=$(PGPASSWORD=${POSTGRES_PASSWORD} psql -h ${POSTGRES_HOST} -p ${POSTGRES_PORT} -U ${POSTGRES_USER} -tAc "SELECT 1 FROM pg_database WHERE datname='backstage_plugin_orchestrator'" postgres)
              if [ -z "$DB_EXISTS" ]; then
                PGPASSWORD=${POSTGRES_PASSWORD} psql -h ${POSTGRES_HOST} -p ${POSTGRES_PORT} -U ${POSTGRES_USER} -c "CREATE DATABASE backstage_plugin_orchestrator;" postgres
              fi
      restartPolicy: Never
```

### SonataFlowPlatform CR with external DB

```yaml
apiVersion: sonataflow.org/v1alpha08
kind: SonataFlowPlatform
metadata:
  name: sonataflow-platform
spec:
  monitoring:
    enabled: true
  services:
    dataIndex:
      enabled: true
      persistence:
        postgresql:
          secretRef:
            name: <SECRET-NAME-WITH-DB-CREDENTIALS>
            userKey: POSTGRES_USER
            passwordKey: POSTGRES_PASSWORD
          serviceRef:
            name: <SERVICE-NAME-TO-DB>
            namespace: <RHDH-NAMESPACE>
            databaseName: backstage_plugin_orchestrator
    jobService:
      enabled: true
      persistence:
        postgresql:
          secretRef:
            name: <SECRET-NAME-WITH-DB-CREDENTIALS>
            userKey: POSTGRES_USER
            passwordKey: POSTGRES_PASSWORD
          serviceRef:
            name: <SERVICE-NAME-TO-DB>
            namespace: <RHDH-NAMESPACE>
            databaseName: backstage_plugin_orchestrator
```

### Remove sonataflow dependency for external DB

```yaml
- package: "oci://registry.access.redhat.com/rhdh/red-hat-developer-hub-backstage-plugin-orchestrator-backend:{{inherit}}"
  disabled: false
  pluginConfig:
    orchestrator:
      dataIndexService:
        url: http://<SERVICE-NAME-SONATAFLOW-PLATFORM-DATA-INDEX>
  dependencies: [{}]
```

### Verification

```bash
oc get sonataflowplatform sonataflow-platform \
  -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}'
# Expected: True
```

---

## 4. Helm Installation

### Install infrastructure and RHDH

```bash
helm repo add openshift-helm-charts https://charts.openshift.io/

# Infrastructure (requires admin — installs Serverless + Logic operators)
helm install <release_name> openshift-helm-charts/redhat-developer-hub-orchestrator-infra

# RHDH with Orchestrator
helm install <release_name> openshift-helm-charts/redhat-developer-hub \
  --version 1.10.1 \
  --set orchestrator.enabled=true
```

### External PostgreSQL — Helm values

```yaml
orchestrator:
  enabled: true
  sonataflowPlatform:
    externalDBsecretRef: <SECRET-NAME-WITH-DB-CREDENTIALS>
    externalDBName: backstage_plugin_orchestrator
    externalDBHost: <SERVICE-NAME-TO-DB>
    externalDBPort: "5432"
```

### Resource limits

```yaml
orchestrator:
  enabled: true
  sonataflowPlatform:
    resources:
      limits:
        cpu: "500m"
        memory: "1Gi"
```

---

## 5. CloudEvent / Kafka Integration

### Configure Kafka connectivity

```yaml
orchestrator:
  kafka:
    clientId: my-rhdh-orchestrator
    brokers:
      - kafka-broker-1.example.com:9092
      - kafka-broker-2.example.com:9092
      - kafka-broker-3.example.com:9092
    logLevel: 4
```

`logLevel` values: 0 (NOTHING), 1 (ERROR), 2 (WARN), 4 (INFO), 5 (DEBUG).

When Kafka connectivity is configured, the **Run as Event** button appears
next to workflows in the UI.

### CloudEvent structure

```json
{
  "specversion": "1.0",
  "type": "deployment.request",
  "source": "/api/deployments",
  "id": "a234-5678-9abc-def0",
  "datacontenttype": "application/json",
  "time": "2025-08-15T14:30:00Z",
  "data": {
    "applicationName": "my-application",
    "environment": "production",
    "version": "2.1.0"
  }
}
```

---

## 6. RBAC Permissions

### Permission reference

| Permission | Resource Type | Policy | Description |
|------------|--------------|--------|-------------|
| `orchestrator.workflow` | named resource | read | List/read all workflows and instances |
| `orchestrator.workflow.[workflowId]` | named resource | read | List/read specific workflow |
| `orchestrator.workflow.use` | named resource | update | Run or abort any workflow |
| `orchestrator.workflow.use.[workflowId]` | named resource | update | Run or abort specific workflow |
| `orchestrator.workflowAdminView` | named resource | read | View definition editor and instance variables |
| `orchestrator.instanceAdminView` | named resource | read | View all instances |

### RBAC policy CSV example

```plaintext
# Minimal user role
p, role:default/workflowUser, orchestrator.workflow.greeting, read, allow
p, role:default/workflowUser, orchestrator.workflow.use.greeting, update, allow

# Support role — view only
p, role:default/workflowSupport, orchestrator.workflow, read, allow
p, role:default/workflowSupport, orchestrator.instanceAdminView, read, allow

# Full admin role
p, role:default/workflowAdmin, orchestrator.workflow, read, allow
p, role:default/workflowAdmin, orchestrator.workflow.use, update, allow
p, role:default/workflowAdmin, orchestrator.workflowAdminView, read, allow
p, role:default/workflowAdmin, orchestrator.instanceAdminView, read, allow

# Assign users
g, user:default/example_user, role:default/workflowUser
```

### Enable in app-config.yaml

```yaml
permission:
  enabled: true
  rbac:
    policies-csv-file: <absolute_path_to_policy_file>
    pluginsWithPermission:
      - orchestrator
    policyFileReload: true
    admin:
      users:
        - name: user:default/YOUR_USER
```

---

## 7. Upgrade OSL Operator for RHDH 1.10

Starting with OSL 1.37.0, subscription name changed from `logic-operator-rhel8`
to `logic-operator`.

```yaml
apiVersion: operators.coreos.com/v1alpha1
kind: Subscription
metadata:
  name: logic-operator
  namespace: openshift-serverless-logic
spec:
  channel: stable
  installPlanApproval: Automatic
  name: logic-operator
  source: redhat-operators
  sourceNamespace: openshift-marketplace
  startingCSV: logic-operator.v1.38.0
```

Do NOT delete existing SonataflowPlatform operands during the upgrade.

---

## 8. Air-Gapped Deployment

### ImageSetConfiguration for oc mirror

```yaml
apiVersion: mirror.openshift.io/v2alpha1
kind: ImageSetConfiguration
mirror:
  additionalimages:
  - name: registry.access.redhat.com/rhdh/red-hat-developer-hub-backstage-plugin-orchestrator@<digest>
  - name: registry.access.redhat.com/rhdh/red-hat-developer-hub-backstage-plugin-orchestrator-backend@<digest>
  - name: registry.access.redhat.com/rhdh/red-hat-developer-hub-backstage-plugin-scaffolder-backend-module-orchestrator@<digest>
  - name: registry.access.redhat.com/rhdh/red-hat-developer-hub-backstage-plugin-orchestrator-form-widgets@<digest>
  operators:
    - catalog: registry.redhat.io/redhat/redhat-operator-index:v<ocp-version>
      packages:
      - name: logic-operator
        channels:
        - name: stable
          minVersion: 1.38.0
          maxVersion: 1.38.0
      - name: serverless-operator
        channels:
        - name: stable
          minVersion: 1.37.1
          maxVersion: 1.37.1
```

The `--v2` flag is required for OCP 4.21+.

---

## 9. Loki Log Integration

### Enable Loki backend module

```yaml
- disabled: false
  package: oci://registry.access.redhat.com/rhdh/red-hat-developer-hub-backstage-plugin-orchestrator-backend-module-loki:{{inherit}}
```

### Configure Loki in app-config.yaml

```yaml
orchestrator:
  workflowLogProvider:
    loki:
      baseUrl: <LOKI_BASE_URL>
      token: <AUTH_TOKEN>
      rejectUnauthorized: false
```

### Get Loki base URL

```bash
LOKI_HOST=$(oc get route logging-loki -n openshift-logging -o jsonpath='{.spec.host}')
echo "https://$LOKI_HOST/api/logs/v1/application/"
```

---

## 10. JSON Structured Logging for SonataFlow

### Enable Quarkus JSON logging

```properties
quarkus.log.console.json=true
quarkus.log.console.json.pretty-print=false
quarkus.log.console.json.print-details=true
quarkus.log.category."org.kie.kogito".level=DEBUG
quarkus.log.category."io.serverlessworkflow".level=INFO
```

### Verify processInstanceId in output

```bash
oc logs <workflow_pod_name> | grep processInstanceId
# Expected: {"timestamp":"...","level":"INFO","message":"...","mdc":{"processInstanceId":"abc-123-..."}}
```

### OpenTelemetry trace correlation

```properties
quarkus.otel.enabled=true
quarkus.otel.exporter.otlp.traces.endpoint=http://jaeger-collector:4317
quarkus.otel.service.name=${workflow.name}
```
