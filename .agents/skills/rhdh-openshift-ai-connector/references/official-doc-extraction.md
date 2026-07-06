# Official Doc Extraction — rhdh-openshift-ai-connector

Source: Red Hat Developer Hub 1.10 — Accelerate AI development with OpenShift
AI Connector for Red Hat Developer Hub

## Purpose

Integrate AI models and model servers from Red Hat OpenShift AI directly into
the RHDH Catalog to provide a unified hub for discovering and consuming AI
components.

## RBAC and Credentials Setup

### ServiceAccount

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: rhdh-rhoai-connector
  namespace: ai-rhdh
```

### ClusterRole

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: rhdh-rhoai-connector
rules:
  - apiGroups: [apiextensions.k8s.io]
    resources: [customresourcedefinitions]
    verbs: [get]
  - apiGroups: [route.openshift.io]
    resources: [routes]
    verbs: [get, list, watch]
  - apiGroups: [""]
    resources: [serviceaccounts, services]
    verbs: [get, list, watch]
  - apiGroups: [serving.kserve.io]
    resources: [inferenceservices]
    verbs: [get, list, watch]
```

### ClusterRoleBinding

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: rhdh-rhoai-connector
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: rhdh-rhoai-connector
subjects:
  - kind: ServiceAccount
    name: rhdh-rhoai-connector
    namespace: ai-rhdh
```

### Role (ConfigMap access in RHDH namespace)

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: rhdh-rhoai-connector
  namespace: ai-rhdh
rules:
  - apiGroups: [""]
    resources: [configmaps]
    verbs: [get, list, watch, create, update, patch]
```

### RoleBinding (Model Registry namespace)

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: rhdh-rhoai-dashboard-permissions
  namespace: rhoai-model-registries
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: registry-user-modelregistry-public
subjects:
  - apiGroup: rbac.authorization.k8s.io
    kind: Group
    name: system:serviceaccounts:ai-rhdh
```

### ServiceAccount Token Secret

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: rhdh-rhoai-connector-token
  namespace: ai-rhdh
  annotations:
    kubernetes.io/service-account.name: rhdh-rhoai-connector
type: kubernetes.io/service-account-token
```

## Dynamic Plugins

```yaml
plugins:
  - disabled: false
    package: oci://ghcr.io/redhat-developer/rhdh-plugin-export-overlays/red-hat-developer-hub-backstage-plugin-catalog-backend-module-model-catalog:<tag>
  - disabled: false
    package: oci://ghcr.io/redhat-developer/rhdh-plugin-export-overlays/red-hat-developer-hub-backstage-plugin-catalog-techdoc-url-reader-backend:<tag>
```

## Sidecar Containers

Three sidecar containers required alongside `backstage-backend`:

| Container | Image | Port | Purpose |
|-----------|-------|------|---------|
| `location` | `quay.io/redhat-ai-dev/model-catalog-location-service` | 9090 | Serves entity data to RHDH |
| `storage-rest` | `quay.io/redhat-ai-dev/model-catalog-storage-rest` | — | ConfigMap-based bridge storage |
| `rhoai-normalizer` | `quay.io/redhat-ai-dev/model-catalog-rhoai-normalizer` | — | K8s controller, RHOAI metadata normalizer |

All sidecars require:
- `NORMALIZER_FORMAT: JsonArrayFormat`
- `POD_IP` and `POD_NAMESPACE` from field refs
- `envFrom` referencing `rhdh-rhoai-connector-token` secret
- Volume mount to `dynamic-plugins-root`

## Entity Provider Configuration

In `app-config.yaml`:

```yaml
catalog:
  providers:
    modelCatalog:
      development:
        baseUrl: http://localhost:9090
```

## Metadata Enrichment

Custom properties set in RHOAI Model Registry (Model Version Properties):

| Property Key | Entity Field | Description |
|-------------|-------------|-------------|
| `API Spec` | API Definition Tab | OpenAPI/Swagger JSON spec |
| `API Type` | API Type | Backstage API type (default: `openapi`) |
| `TechDocs` | TechDocs | Git repo URL for model card (if auto-mapping inactive) |
| `Homepage URL` | Links | Model home page |
| `Owner` | Owner | Override default OpenShift user |
| `Lifecycle` | Lifecycle | Backstage lifecycle concept |
| `How to use` | Links | Usage documentation URL |
| `License` | Links | License file URL |
| `rhdh.modelcatalog.io/model-name` | Annotations | Model name for REST API calls |

### Populating API Spec

```bash
curl -k -H "Authorization: Bearer $MODEL_API_KEY" \
  https://$MODEL_ROOT_URL_INCLUDING_PORT/openapi.json | jq > open-api.json
```

Then set `API Spec` key in RHOAI Model Registry Properties with JSON content.

## Troubleshooting

### Verify Dynamic Plugins

```bash
oc logs -c install-dynamic-plugins deployment/<rhdh-deployment>
```

Look for:
- `red-hat-developer-hub-backstage-plugin-catalog-backend-module-model-catalog`
- `red-hat-developer-hub-backstage-plugin-catalog-techdoc-url-reader-backend`

### Check Backstage Plugin Logs

| Component | Logger Target | Expected Log |
|-----------|--------------|--------------|
| Entity Provider | `ModelCatalogResourceEntityProvider` | "Discovering ResourceEntities from Model Server..." |
| TechDoc Reader | `ModelCatalogBridgeTechdocUrlReader` | "ModelCatalogBridgeTechdocUrlReader.readUrl" |

Enable debug: Set `LOG_LEVEL=debug` on `backstage-backend` container.

### Check Cached Data (ConfigMap)

```bash
oc get configmap bac-import-model -o json | jq -r '.binaryData | to_entries[] | "=== \(.key) ===\n" + (.value | @base64d | fromjson | .body | @base64d | fromjson | tostring)' | jq -R 'if startswith("=== ") then . else (. | fromjson) end'
```

### Check Location Service

```bash
oc rsh -c backstage-backend deployment/<rhdh-deployment>
curl http://localhost:9090/list
```

### Check Sidecar Logs

```bash
oc logs -c rhoai-normalizer deployment/<rhdh-deployment>
oc logs -c storage-rest deployment/<rhdh-deployment>
oc logs -c location deployment/<rhdh-deployment>
```

### Query RHOAI Model Registry

```bash
curl -k -H "Authorization: Bearer $TOKEN" \
  $RHOAI_MODEL_REGISTRY_URL/api/model_registry/v1alpha3/registered_models | jq
curl -k -H "Authorization: Bearer $TOKEN" \
  $RHOAI_MODEL_REGISTRY_URL/api/model_registry/v1alpha3/inference_services | jq
```

## Known Constraints

- Non-critical startup error (`in cluster config error: open /var/run/secrets/...`)
  is expected and resolves after initialization
- TechDocs propagation only works for models registered into model registry
  from RHOAI 2.25 model catalog
- `baseUrl: http://localhost:9090` is the only supported value in Developer Preview
