# Official Documentation Extraction

Source: Red Hat Developer Hub 1.10 — Installing on OpenShift Container Platform
Captured: 2026-07-06

---

## 1. Installation Methods

Two methods are available:

- **Operator** — OLM-managed, automatic subscription updates via OperatorHub
- **Helm chart** — Manual install and management, available in Helm catalog

Critical requirement for both methods: Set `baseUrl` in `app-config.yaml` to
match the external URL of the Developer Hub instance.

## 2. Operator Installation

### Prerequisites

- Administrator access on OpenShift web console
- Appropriate roles and permissions to create applications
- OpenShift Container Platform 4.18 to 4.21
- System meets minimum sizing requirements

### Procedure

Install from OperatorHub with:
- **Update channel:** `fast` or `fast-1.10`
- **Installation mode:** All namespaces on the cluster (required; specific
  namespace not supported)
- **Installed namespace:** `rhdh-operator` (recommended for security isolation)

### Verification

Navigate to Ecosystem > Installed Operators; status should be `Succeeded`.

## 3. Custom Configuration Provisioning

### Create namespace

```bash
oc create namespace my-rhdh-project
```

### Provision secrets

```bash
oc create secret generic my-rhdh-secrets \
  --from-file=secrets.txt \
  --namespace=my-rhdh-project
```

### Provision app-config ConfigMap

```bash
oc create configmap my-rhdh-app-config \
  --from-file=app-config.yaml \
  --namespace=my-rhdh-project
```

### app-config.yaml baseUrl configuration

```yaml
app:
  title: Red Hat Developer Hub
  baseUrl: https://<my_developer_hub_domain>

backend:
  auth:
    externalAccess:
      - type: legacy
        options:
          subject: legacy-default-config
          secret: "${BACKEND_SECRET}"
  baseUrl: https://<my_developer_hub_domain>
  cors:
    origin: https://<my_developer_hub_domain>
```

### Provision dynamic-plugins ConfigMap

```bash
oc create configmap dynamic-plugins-rhdh \
  --from-file=dynamic-plugins.yaml \
  --namespace=my-rhdh-project
```

### dynamic-plugins.yaml example

```yaml
includes:
  - dynamic-plugins.default.yaml
plugins:
  - package: ./dynamic-plugins/dist/backstage-plugin-catalog-backend-module-github
    disabled: false
  - package: ./dynamic-plugins/dist/backstage-community-plugin-rbac
    disabled: false
```

## 4. Backstage CR (Operator Deployment)

### Minimal Backstage CR

```yaml
apiVersion: rhdh.redhat.com/v1alpha5
kind: Backstage
metadata:
  name: my-rhdh-custom-resource
spec:
  application:
    appConfig:
      mountPath: /opt/app-root/src
      configMaps:
         - name: my-rhdh-app-config
    extraEnvs:
      secrets:
         - name: <my_product_secrets>
    extraFiles:
      mountPath: /opt/app-root/src
    route:
      enabled: true
  database:
    enableLocalDb: true
```

### Full Backstage CR with external database and RBAC

```yaml
apiVersion: rhdh.redhat.com/v1alpha5
kind: Backstage
metadata:
  name: <my-rhdh-custom-resource>
spec:
  application:
    appConfig:
      mountPath: /opt/app-root/src
      configMaps:
         - name: my-rhdh-app-config
         - name: rbac-policies
    dynamicPluginsConfigMapName: dynamic-plugins-rhdh
    extraEnvs:
      secrets:
         - name: <my_product_secrets>
         - name: my-rhdh-database-secrets
    extraFiles:
      mountPath: /opt/app-root/src
      secrets:
        - name: my-rhdh-database-certificates-secrets
          key: postgres-crt.pem, postgres-ca.pem, postgres-key.key
    route:
      enabled: true
  database:
    enableLocalDb: false
```

### Apply the CR

```bash
oc apply -f my-rhdh-custom-resource.yaml -n my-rhdh-project
```

### Proxy environment variables

```yaml
spec:
  application:
    extraEnvs:
      envs:
        - name: HTTP_PROXY
          value: 'http://10.10.10.105:3128'
        - name: HTTPS_PROXY
          value: 'http://10.10.10.106:3128'
        - name: NO_PROXY
          value: 'localhost,example.org'
```

## 5. Helm Chart Installation

### From web console

Configure via Form view or YAML view. For YAML view, set:

```yaml
global:
  auth:
    backend:
      enabled: true
  clusterRouterBase: apps.<clusterName>.com
```

### From Helm CLI

```bash
NAMESPACE=rhdh
oc new-project ${NAMESPACE} || oc project ${NAMESPACE}

helm upgrade redhat-developer-hub -i \
  https://github.com/openshift-helm-charts/charts/releases/download/redhat-redhat-developer-hub-1.10.1/redhat-developer-hub-1.10.1.tgz

PASSWORD=$(oc get secret redhat-developer-hub-postgresql -o jsonpath="{.data.password}" | base64 -d)
CLUSTER_ROUTER_BASE=$(oc get route console -n openshift-console -o=jsonpath='{.spec.host}' | sed 's/^[^.]*\.//')

helm upgrade redhat-developer-hub -i \
  "https://github.com/openshift-helm-charts/charts/releases/download/redhat-redhat-developer-hub-1.10.1/redhat-developer-hub-1.10.1.tgz" \
  --set global.clusterRouterBase="$CLUSTER_ROUTER_BASE" \
  --set global.postgresql.auth.password="$PASSWORD"
```

### Verification

```bash
echo "https://redhat-developer-hub-${NAMESPACE}.${CLUSTER_ROUTER_BASE}"
```

Open the URL in a browser.

## 6. Troubleshooting

**Symptom:** Pod in `CrashLoopBackOff` with log:
```
Backend failed to start up Error: Missing required config value at 'backend.database.client'
```

**Cause:** Configuration files not accessible to the Developer Hub container.

**Resolution:** Verify config maps are correctly created and referenced in the
Backstage CR or Helm values.

## 7. Key Specifications

| Item | Value |
|------|-------|
| Backstage CR apiVersion | `rhdh.redhat.com/v1alpha5` |
| Operator namespace | `rhdh-operator` |
| Supported OCP versions | 4.18–4.21 |
| CPU architecture | AMD64/Intel 64 (`x86_64`) |
| Helm chart version | 1.10.1 |
| Helm chart URL | `https://github.com/openshift-helm-charts/charts/releases/download/redhat-redhat-developer-hub-1.10.1/redhat-developer-hub-1.10.1.tgz` |
| Update channels | `fast`, `fast-1.10` |
| Config mount path | `/opt/app-root/src` |
