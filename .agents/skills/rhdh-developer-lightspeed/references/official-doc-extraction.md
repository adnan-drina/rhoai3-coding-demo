# Official Doc Extraction — rhdh-developer-lightspeed

Source: Red Hat Developer Hub 1.10 — Interacting with Red Hat Developer
Lightspeed for Red Hat Developer Hub

## Purpose

AI-powered virtual assistant for RHDH providing chat assistance, grounded
responses via RAG embeddings, private Notebook research, and model evaluation.

## Configuration via Operator

### Secret for LLM Credentials

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: lightspeed-auth-secrets
type: Opaque
stringData:
  ENABLE_VLLM: "true"
  VLLM_URL: "https://<api_endpoint>/v1"
  VLLM_API_KEY: "<api_key>"
  ENABLE_VALIDATION: "true"
  VALIDATION_PROVIDER: "vllm"
  VALIDATION_MODEL_NAME: "llama3.1"
```

### Backstage CR

```yaml
apiVersion: rhdh.redhat.com/v1alpha5
kind: Backstage
metadata:
  name: lightspeed-rhdh
spec:
  application:
    extraEnvs:
      secrets:
        - name: lightspeed-auth-secrets
          containers:
            - lightspeed-core
```

### Custom ConfigMap for Persistent Settings

```yaml
    extraFiles:
      configMaps:
        - name: "my-custom-config"
          mountPath: /app-root
          key: lightspeed-stack.yaml
          containers:
            - lightspeed-core
```

### RBAC for Non-Admin Access

```plaintext
p, role:default/<team>, lightspeed.chat.read, read, allow
p, role:default/<team>, lightspeed.chat.create, create, allow
```

## Configuration via Helm Chart

### Reference Custom Secret in values.yaml

```yaml
global:
  lightspeed:
    secret:
      create: false
      name: "my-custom-secret"
```

### Custom ConfigMap Override

```yaml
global:
  lightspeed:
    configMaps:
      - name: stack
        create: false
        nameOverride: "my-custom-stack"
        mountPath: /app-root/lightspeed-stack.yaml
        subPath: lightspeed-stack.yaml
        sourceFile: lightspeed-stack.yaml
        optional: false
```

## Disable Lightspeed

### Via Operator

```yaml
apiVersion: rhdh.redhat.com/v1alpha5
kind: Backstage
metadata:
  name: lightspeed-disabled
spec:
  flavours:
    - name: lightspeed
      enabled: false
```

### Via Helm

```yaml
global:
  lightspeed:
    enabled: false
```

## Customization

### System Prompt

```yaml
lightspeed:
  systemPrompt: "You are a helpful assistant focused on Red Hat Developer Hub development."
```

### User Feedback Collection

```yaml
user_data_collection:
  feedback_enabled: true
  feedback_storage: "/tmp/data/feedback"
  transcripts_enabled: true
  transcripts_storage: "/tmp/data/transcripts"
```

### Chat History (Persistent PostgreSQL)

```yaml
conversation_cache:
  type: "postgres"
  postgres:
    host: <your_database_host>
    port: <your_database_port>
    db: <your_database_name>
    user: <your_user_name>
    password: <postgres_password>
```

### Chat History (Default SQLite — non-persistent)

```yaml
conversation_cache:
  type: "sqlite"
  sqlite:
    db_path: '/tmp/cache.db'
```

## Notebooks (Developer Preview)

### Enable Notebooks

```yaml
lightspeed:
  notebooks:
    enabled: true
    queryDefaults:
      model: ${NOTEBOOKS_QUERY_MODEL}
      provider_id: ${NOTEBOOKS_QUERY_PROVIDER_ID}
```

### RBAC for Notebooks

```plaintext
p, role:default/<team>, lightspeed.notebooks.use, update, allow
g, user:default/<user>, role:default/<team>
```

### Constraints

- File size: 20MB per file or URL
- Notebook capacity: 100k tokens per session
- Private access only (no sharing)
- Manual uploads only (no URL ingestion)
- Ephemeral by default (requires PV for persistence)

## Safety Guards

- Default: Llama Guard as safety shield
- Override: Define custom safety provider in `run.yaml`
- Disable: Use `run-no-guard.yaml` (development environments only)

## LLM Provider Requirements

- **vLLM**: Append `/v1` to URL; used for RHOAI-hosted models
- **OpenAI**: Direct API connection
- **Ollama**: Must be network-accessible (not localhost for cluster deployments)
- **Vertex AI**: Limited testing; requires `GOOGLE_APPLICATION_CREDENTIALS`

## Air-Gapped Mirroring

### Operator Deployments

```bash
BUNDLE_IMAGE="registry.redhat.io/rhdh/rhdh-operator-bundle:1.10"
CONTAINER_ID=$(podman create "${BUNDLE_IMAGE}")
podman cp $CONTAINER_ID:/manifests/rhdh-flavour-lightspeed-config_v1_configmap.yaml ./lightspeed-config.yaml
podman rm $CONTAINER_ID
```

### Helm Deployments (OpenShift)

```bash
helm show values redhat-developer-hub --repo https://charts.openshift.io/ --version 1.10.1 > values.default.yaml
LS_RAG_IMAGE=$(yq '.global.lightspeed.initContainer.image | .registry + "/" + .repository' values.default.yaml)
LS_CORE_IMAGE=$(yq '.global.lightspeed.sidecar.image | .registry + "/" + .repository' values.default.yaml)
```

## Validation Checklist

1. FAB (floating action button) appears on RHDH home page
2. Chat window initializes when FAB is clicked
3. LCORE container is running in pod spec
4. RAG init container completes successfully
5. No errors in backstage-backend logs for lightspeed
