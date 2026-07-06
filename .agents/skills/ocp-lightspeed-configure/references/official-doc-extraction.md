# Official Documentation Extraction

Source: Red Hat OpenShift Lightspeed 1.0 — Configure
Captured: 2026-07-06

---

## 1. Credential Secrets

All provider secrets are created in namespace `openshift-lightspeed`.
The YAML parameter is always `apitoken` regardless of what the LLM provider
calls the access details.

### OpenAI

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: openai
  namespace: openshift-lightspeed
type: Opaque
stringData:
  apitoken: <api_token>
```

### Red Hat Enterprise Linux AI

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: rhelai-api-keys
  namespace: openshift-lightspeed
type: Opaque
stringData:
  apitoken: <api_token>
```

### Red Hat OpenShift AI

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: rhoai-api-keys
  namespace: openshift-lightspeed
type: Opaque
stringData:
  apitoken: <api_token>
```

### IBM watsonx

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: watsonx-api-keys
  namespace: openshift-lightspeed
type: Opaque
stringData:
  apitoken: <api_token>
```

### Microsoft Azure OpenAI

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: azure-api-keys
  namespace: openshift-lightspeed
type: Opaque
stringData:
  apitoken: <api_token>
```

### Microsoft Azure OpenAI with Entra ID

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: azure-api-keys
  namespace: openshift-lightspeed
type: Opaque
data:
  client_id: <base64_encoded_client_id>
  client_secret: <base64_encoded_client_secret>
  tenant_id: <base64_encoded_tenant_id>
```

### Google Vertex AI

```bash
oc create secret generic llmcreds \
  --from-file=gcp-service-account.json=/path/to/service-account-key.json \
  -n openshift-lightspeed
```

### CLI creation

```bash
oc create -f /path/to/secret.yaml
```

---

## 2. OLSConfig CR — Per-Provider Examples

**apiVersion:** `ols.openshift.io/v1alpha1`
**kind:** `OLSConfig`
**metadata.name:** `cluster`

### OpenAI

```yaml
apiVersion: ols.openshift.io/v1alpha1
kind: OLSConfig
metadata:
  name: cluster
spec:
  llm:
    providers:
      - name: myOpenai
        type: openai
        credentialsSecretRef:
          name: credentials
        url: https://api.openai.com/v1
        models:
          - name: <model_name>
  ols:
    defaultModel: <model_name>
    defaultProvider: myOpenai
```

### Red Hat Enterprise Linux AI (rhelai_vllm)

```yaml
apiVersion: ols.openshift.io/v1alpha1
kind: OLSConfig
metadata:
  name: cluster
spec:
  llm:
    providers:
    - credentialsSecretRef:
        name: rhelai-api-keys
      models:
      - name: models/<model_name>
      name: rhelai
      type: rhelai_vllm
      url: <url>
  ols:
    defaultProvider: rhelai
    defaultModel: models/<model_name>
```

- `spec.llm.providers.url` must end with `v1` to be valid.
- If the endpoint does not require a token, still set apitoken to any valid
  string.

### Red Hat OpenShift AI (rhoai_vllm)

```yaml
apiVersion: ols.openshift.io/v1alpha1
kind: OLSConfig
metadata:
  name: cluster
spec:
  llm:
    providers:
    - credentialsSecretRef:
        name: rhoai-api-keys
      models:
      - name: <model_name>
      name: red_hat_openshift_ai
      type: rhoai_vllm
      url: <url>
  ols:
    defaultProvider: red_hat_openshift_ai
    defaultModel: <model_name>
```

### Microsoft Azure OpenAI

```yaml
apiVersion: ols.openshift.io/v1alpha1
kind: OLSConfig
metadata:
  name: cluster
spec:
  llm:
    providers:
      - credentialsSecretRef:
          name: azure-api-keys
        apiVersion: <api_version_for_azure_model>
        deploymentName: <azure_ai_deployment_name>
        models:
        - name: <model_name>
        name: myAzure
        type: azure_openai
        url: <azure_ai_deployment_url>
  ols:
    defaultModel: <model_name>
    defaultProvider: myAzure
```

### IBM watsonx

```yaml
apiVersion: ols.openshift.io/v1alpha1
kind: OLSConfig
metadata:
  name: cluster
spec:
  llm:
    providers:
      - name: myWatsonx
        type: watsonx
        credentialsSecretRef:
          name: watsonx-api-keys
        url: <ibm_watsonx_deployment_name>
        projectID: <ibm_watsonx_project_id>
        models:
          - name: ibm/<model_name>
  ols:
    defaultModel: ibm/<model_name>
    defaultProvider: myWatsonx
```

### Google Vertex AI (Gemini)

```yaml
apiVersion: ols.openshift.io/v1alpha1
kind: OLSConfig
metadata:
  name: cluster
spec:
  llm:
    providers:
      - name: google
        type: google_vertex
        credentialsSecretRef:
          name: llmcreds
        credentialKey: gcp-service-account.json
        googleVertexConfig:
          projectID: my-gcp-project-123
          location: us-central1
        models:
          - name: gemini-2.5-flash-lite
  ols:
    defaultModel: gemini-2.5-flash-lite
    defaultProvider: google
```

### Google Vertex AI (Anthropic / Claude)

```yaml
apiVersion: ols.openshift.io/v1alpha1
kind: OLSConfig
metadata:
  name: cluster
spec:
  llm:
    providers:
      - name: google-anthropic
        type: google_vertex_anthropic
        credentialsSecretRef:
          name: llmcreds
        credentialKey: gcp-service-account.json
        googleVertexAnthropicConfig:
          projectID: my-gcp-project-123
          location: us-east4
        models:
          - name: claude-3-sonnet
  ols:
    defaultModel: claude-3-sonnet
    defaultProvider: google-anthropic
```

### Deploy the CR

```bash
oc create -f /path/to/config-cr.yaml
# or
oc apply -f olsconfig.yaml
```

---

## 3. Custom TLS Certificates

### Backend endpoint TLS (spec.ols.tlsConfig)

```yaml
apiVersion: ols.openshift.io/v1alpha1
kind: OLSConfig
metadata:
  name: cluster
spec:
  ols:
    tlsConfig:
      keyCertSecretRef:
        name: <lightspeed_tls>
---
apiVersion: v1
kind: Secret
metadata:
  name: <lightspeed_tls>
  namespace: openshift-lightspeed
data:
  tls.crt: LS0tLS1CRUd...
  tls.key: LS0tLS1CRUd...
```

- Certificate name must be `tls.crt`, key must be `tls.key`.

### Trusted CA for LLM providers (spec.ols.additionalCAConfigMapRef)

Supported providers: RHELAI vLLM, RHOAI vLLM, OpenAI, Azure OpenAI.
IBM watsonx does **not** support custom certificates.

```bash
oc create configmap trusted-certs \
  --from-file=caCertFileName \
  --namespace openshift-lightspeed
```

```yaml
apiVersion: ols.openshift.io/v1alpha1
kind: OLSConfig
metadata:
  name: cluster
spec:
  ols:
    defaultProvider: rhelai
    defaultModel: models/<model_name>
    additionalCAConfigMapRef:
      name: trusted-certs
```

### TLS Security Profiles (spec.llm.providers[].tlsSecurityProfile)

Supported types: `Old`, `Intermediate`, `Modern`, `Custom`.
`Modern` is not yet well-adopted and not currently supported.

---

## 4. RBAC and User Access

OpenShift Lightspeed RBAC is binary. The ClusterRole is
`lightspeed-operator-query-access`. `kubeadmin` always has access.

### Grant user access (CLI)

```bash
oc adm policy add-cluster-role-to-user \
    lightspeed-operator-query-access <user_name>
```

### Grant user access (YAML)

```bash
oc adm policy add-cluster-role-to-user lightspeed-operator-query-access <user_name> -o yaml --dry-run > ols-user-access.yaml
oc apply -f ols-user-access.yaml
```

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: lightspeed-operator-query-access
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: lightspeed-operator-query-access
subjects:
- apiGroup: rbac.authorization.k8s.io
  kind: User
  name: <user_name>
```

### Grant group access (CLI)

```bash
oc adm policy add-cluster-role-to-group \
    lightspeed-operator-query-access <group_name>
```

### Grant group access (YAML)

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: lightspeed-operator-query-access
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: lightspeed-operator-query-access
subjects:
- apiGroup: rbac.authorization.k8s.io
  kind: Group
  name: <user_group>
```

### Obtain authentication token

```bash
TOKEN=$(oc whoami -t)
# or for service accounts:
TOKEN=$(kubectl create token <service_account_name> -n <namespace>)
```

### Verification

```bash
oc get clusterrolebinding lightspeed-operator-query-access
oc get clusterrolebinding lightspeed-operator-query-access -o yaml
oc get clusterrolebinding lightspeed-operator-query-access -o wide
```

---

## 5. Exposing the Service via Route

The service is internal-only `ClusterIP` by default.

```yaml
apiVersion: route.openshift.io/v1
kind: Route
metadata:
  name: lightspeed-app-server
  namespace: openshift-lightspeed
  labels:
    app: ols
spec:
  port:
    targetPort: 8443-tcp
  tls:
    insecureEdgeTerminationPolicy: Redirect
    termination: reencrypt
  to:
    kind: Service
    name: lightspeed-app-server
    weight: 100
  wildcardPolicy: None
```

Use `reencrypt` termination policy for end-to-end TLS.

```bash
oc apply -f route.yaml
OLS_HOST=$(oc get route lightspeed-app-server -n openshift-lightspeed -o jsonpath='{.spec.host}')
echo "https://${OLS_HOST}"
```

---

## 6. Query Filters (Sensitive Data Redaction)

```yaml
spec:
  ols:
    queryFilters:
      - name: ip-address
        pattern: '((25[0-5]|(2[0-4]|1\d|[1-9]|)\d)\.?\b){4}'
        replaceWith: <IP_ADDRESS>
```

**Note:** If `introspectionEnabled` is true and an MCP server is configured,
content returned by MCP tools is NOT filtered and remains visible to the LLM.

```bash
oc apply -f OLSConfig.yaml
```

---

## 7. BYO Knowledge (RAG)

### Providing custom knowledge

```bash
podman run -it --rm --device=/dev/fuse \
  -v $XDG_RUNTIME_DIR/containers/auth.json:/run/user/0/containers/auth.json:Z \
  -v <dir_tree_with_markdown_files>:/markdown:Z \
  -v <dir_for_image_tar>:/output:Z \
  registry.redhat.io/openshift-lightspeed-tech-preview/lightspeed-rag-tool-rhel9:latest

podman load < <directory_for_image_tar>/<my-byok-image.tar>
podman tag localhost/my-byok-image:latest quay.io/<username>/my-byok-image:latest
podman push quay.io/<username>/my-byok-image:latest
```

### OLSConfig RAG configuration

```yaml
apiVersion: ols.openshift.io/v1alpha1
kind: OLSConfig
metadata:
  name: cluster
spec:
  ols:
    rag:
      - image: quay.io/<username>/my-byok-image:latest
```

### Pull secrets for private registries

```yaml
spec:
  ols:
    imagePullSecrets:
      - name: <my_pull_secret_1>
      - name: <my_pull_secret_2>
```

### Disable OCP documentation RAG (BYO-only mode)

```yaml
spec:
  ols:
    byokRAGOnly: true
```

**Important:** BYO Knowledge tool is Technology Preview.

### Document metadata format

```
---
title: "Introduction to Layers {#gimp-concepts-layers}"
url: "https://docs.gimp.org/3.0/en/gimp-using-layers.html"
---
```

OpenShift Lightspeed supports automatic updates of BYO Knowledge images using
floating tags (via OpenShift ImageStream objects, checked every 15 minutes).

---

## 8. Cluster Interaction (MCP)

`spec.ols.introspectionEnabled` is `true` by default. The Observability MCP
server provides read access to the OpenShift API for cluster context.

### Disable cluster interaction

```yaml
apiVersion: ols.openshift.io/v1alpha1
kind: OLSConfig
metadata:
  name: cluster
spec:
  ols:
    introspectionEnabled: false
```

### Enable custom MCP server (Technology Preview)

Requires feature gate `MCPServer`.

```yaml
apiVersion: ols.openshift.io/v1alpha1
kind: OLSConfig
metadata:
  name: cluster
spec:
  featureGates:
    - MCPServer
  mcpServers:
  - name: mcp-server-1
    url: https://mcp.example.com
    timeout: 30
    headers:
      - name: Authorization
        valueFrom:
          type: kubernetes
  - name: mcp-server-2
    url: https://mcp.example.com
    timeout: 30
    headers:
      - name: X-Special
        valueFrom:
          type: secret
          secretRef:
            name: <secret_name>
```

Field reference for `spec.mcpServers[]`:
- `name` — MCP server name (required)
- `url` — URL path for communication
- `timeout` — response timeout in seconds
- `headers` — array of structured header objects for authentication
- `headers[].name` — header name sent to MCP server
- `headers[].valueFrom.type` — `secret`, `kubernetes` (user bearer token), or
  `client`
- `headers[].valueFrom.secretRef.name` — secret name (must have key `header`)

### MCP authentication modes

1. **File-based secrets** — static token from mounted Kubernetes secret; shared
   identity for all users.
2. **Kubernetes passthrough** — forwards user bearer token after
   `TokenReview` validation; per-user access control.

### MCP authentication examples

```yaml
# Secret-based
valueFrom:
  type: secret
  secretRef:
    name: mcp-server-token

# Kubernetes passthrough
valueFrom:
  type: kubernetes
```

---

## 9. Token Quotas

Requires PostgreSQL database access.

```yaml
apiVersion: ols.openshift.io/v1alpha1
kind: OLSConfig
metadata:
  name: cluster
spec:
  ols:
    quotaHandlersConfig:
      enableTokenHistory: true
      limitersConfig:
      - name: user_monthly_limits
        type: user_limiter
        initialQuota: 100000
        quotaIncrease: 1000
        period: 30 days
      - name: cluster_monthly_limits
        type: cluster_limiter
        initialQuota: 1000000
        quotaIncrease: 100000
        period: 30 days
```

Fields:
- `enableTokenHistory` — enable tracking in PostgreSQL
- `limitersConfig[].name` — unique limiter name
- `limitersConfig[].type` — `user_limiter` or `cluster_limiter`
- `limitersConfig[].initialQuota` — initial token count
- `limitersConfig[].quotaIncrease` — tokens added per period
- `limitersConfig[].period` — duration before quota resets/increases

### Verification

```bash
oc logs -l app.kubernetes.io/name=lightspeed-operator -n openshift-lightspeed
oc get olsconfig cluster -o jsonpath='{.spec.ols.quotaHandlersConfig}'
```

---

## 10. PostgreSQL Persistence (Technology Preview)

Disabled by default.

### Enable with defaults (1 GiB, default storage class)

```yaml
apiVersion: ols.openshift.io/v1alpha1
kind: OLSConfig
metadata:
  name: cluster
  namespace: openshift-lightspeed
spec:
  llm:
    providers:
    ...
  ols:
    storage: {}
```

### Override PVC specifications

```yaml
spec:
  ols:
    storage:
      size: 768Mi
      class: gp2-csi
```

- `spec.ols.storage.size` — total storage capacity (default: 1 GiB)
- `spec.ols.storage.class` — StorageClass name (default: cluster default)

### Verification

```bash
oc get pvc -n openshift-lightspeed
```

---

## 11. Query-Based Tool Filtering

Requires feature gate `ToolFiltering`.

```yaml
apiVersion: ols.openshift.io/v1alpha1
kind: OLSConfig
metadata:
  name: cluster
spec:
  featureGates:
    - ToolFiltering
  olsConfig:
    maxIterations: 5
    toolFilteringConfig:
      alpha: 0.8
      topK: 10
      threshold: 0.01
```

Fields:
- `spec.olsConfig.maxIterations` — LLM tool-calling rounds (default: 5)
- `spec.olsConfig.toolFilteringConfig.alpha` — weight between semantic and
  keyword matching, range 0–1 (default: 0.8)
- `spec.olsConfig.toolFilteringConfig.topK` — max tools available to LLM
  (default: 10)
- `spec.olsConfig.toolFilteringConfig.threshold` — minimum score for tool
  candidacy, range 0.01–0.1 (default: 0.01)

---

## 12. Tools Approval Configuration

```yaml
spec:
  toolsApprovalConfig:
    approvalType: tool_annotations
    approvalTimeout: 600
```

`approvalType` values:
- `never` — all tools execute without user approval
- `always` — all tool calls require user approval
- `tool_annotations` — per-tool annotations determine approval (default)

`approvalTimeout` — timeout in seconds (minimum: 1, default: 600)

---

## 13. REST API Authentication

Configured via `authentication_config.module`:
- `k8s` — default; uses Kubernetes TokenReview and SubjectAccessReview
- `noop` — disables cluster validation (insecure, not for production)
- `noop-with-token` — disables cluster validation but requires Bearer token

**Warning:** `noop` and `dev_config.disable_auth: true` bypass all access
control. Never use in production.

---

## 14. Deployment Verification

```bash
# Verify pods are running
oc get pod -n openshift-lightspeed

# Verify service is ready (Uvicorn running)
oc logs deployment/lightspeed-app-server -c lightspeed-service-api \
  -n openshift-lightspeed | grep Uvicorn

# Expected output:
# INFO: Uvicorn running on https://0.0.0.0:8443 (Press CTRL+C to quit)

# Verify OLSConfig status (Google Vertex AI)
oc get olsconfig cluster -o jsonpath='{.status.overallStatus}'
# Expected: Ready
```

---

## 15. OLSConfig API Field Reference Summary

### .spec (top-level)

| Property | Type | Description |
|----------|------|-------------|
| `featureGates` | `array (string)` | Feature gates to enable (e.g., `MCPServer`, `ToolFiltering`) |
| `llm` | `object` | LLM provider configuration (required) |
| `mcpServers` | `array` | Custom MCP server settings |
| `ols` | `object` | OLS deployment configuration (required) |
| `olsDataCollector` | `object` | Data collector configuration |
| `toolsApprovalConfig` | `object` | Tool execution approval configuration |

### .spec.llm.providers[] (required fields: credentialsSecretRef, models, name, type)

| Property | Type | Description |
|----------|------|-------------|
| `apiVersion` | `string` | API version for Azure OpenAI |
| `credentialsSecretRef` | `object` | Secret with API credentials |
| `credentialKey` | `string` | Key name in secret (default: `apitoken`) |
| `deploymentName` | `string` | Azure OpenAI deployment name |
| `googleVertexConfig` | `object` | Google Vertex AI config (`projectID`, `location`) |
| `googleVertexAnthropicConfig` | `object` | Google Vertex Anthropic config (`projectID`, `location`) |
| `models` | `array` | List of models |
| `name` | `string` | Provider name |
| `projectID` | `string` | Watsonx Project ID |
| `tlsSecurityProfile` | `object` | TLS profile for provider connection |
| `type` | `string` | Provider type |
| `url` | `string` | Provider API URL |

### .spec.llm.providers[].models[] (required: name)

| Property | Type | Description |
|----------|------|-------------|
| `contextWindowSize` | `integer` | Context window in tokens (default: 128k) |
| `name` | `string` | Model name |
| `parameters` | `object` | Model API parameters |
| `parameters.maxTokensForResponse` | `integer` | Max response tokens (default: 2048) |
| `parameters.toolBudgetRatio` | `float` | Context window ratio for tool budget (0.1–0.5, default: 0.5) |
| `url` | `string` | Model-specific API URL |

### .spec.ols (required fields: defaultModel, defaultProvider)

| Property | Type | Description |
|----------|------|-------------|
| `additionalCAConfigMapRef` | `object` | ConfigMap with additional CA certs |
| `byokRAGOnly` | `boolean` | Use only BYO RAG sources |
| `conversationCache` | `object` | Cache settings (type, postgres config) |
| `defaultModel` | `string` | Default model name |
| `defaultProvider` | `string` | Default provider name |
| `deployment` | `object` | Deployment settings (replicas, resources) |
| `imagePullSecrets` | `array` | Pull secrets for BYO Knowledge images |
| `introspectionEnabled` | `boolean` | Enable MCP introspection (default: true) |
| `logLevel` | `string` | Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `proxyConfig` | `object` | Proxy settings (proxyURL, proxyCACertificate) |
| `queryFilters` | `array` | Regex-based query filters |
| `quotaHandlersConfig` | `object` | Token quota configuration |
| `rag` | `array` | RAG database images |
| `storage` | `object` | PostgreSQL PVC config (size, class) |
| `tlsConfig` | `object` | Backend HTTPS TLS config |
| `tlsSecurityProfile` | `object` | TLS profile for API endpoints |
| `userDataCollection` | `object` | Data collection switches |

### .spec.ols.conversationCache.postgres

| Property | Type | Description |
|----------|------|-------------|
| `credentialsSecret` | `string` | Secret with postgres credentials |
| `dbName` | `string` | Database name |
| `maxConnections` | `integer` | Max connections (default: 2000) |
| `sharedBuffers` | `integer-or-string` | Shared buffers |
| `user` | `string` | Postgres user name |

### .spec.ols.deployment

| Property | Type | Description |
|----------|------|-------------|
| `api` | `object` | API container (nodeSelector, resources, tolerations) |
| `console` | `object` | Console container (caCertificate, replicas, resources) |
| `dataCollector` | `object` | Data collector container (resources) |
| `database` | `object` | Database container (nodeSelector, resources, tolerations) |
| `mcpServer` | `object` | MCP server container (resources) |
| `replicas` | `integer` | Number of OLS pods (default: 1) |

### .spec.ols.userDataCollection

| Property | Type | Description |
|----------|------|-------------|
| `feedbackDisabled` | `boolean` | Disable user feedback collection |
| `transcriptsDisabled` | `boolean` | Disable transcript collection |

### .spec.olsDataCollector

| Property | Type | Description |
|----------|------|-------------|
| `logLevel` | `string` | Log level (default: INFO) |

### .spec.mcpServers[]

| Property | Type | Description |
|----------|------|-------------|
| `args` | `array (string)` | Custom arguments for MCP server initialization |
| `name` | `string` | MCP server name (required) |
| `streamableHTTP` | `object` | Streamable HTTP transport settings |
| `valueFrom` | `object` | Authentication source configuration |
| `valueFrom.type` | `string` | Auth type: `secret`, `kubernetes`, or `client` |
| `valueFrom.secretRef` | `object` | Secret reference (when type is `secret`) |
