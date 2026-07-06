# Official Doc Extraction — rhdh-mcp-tools

Source: Red Hat Developer Hub 1.10 — Interacting with Model Context Protocol
tools for Red Hat Developer Hub

## Purpose

Leverage MCP server to integrate RHDH with AI clients through standardized
tools for accessing catalog, documentation, and scaffolder capabilities.

## Install MCP Server Plugin

```yaml
plugins:
  - package: oci://ghcr.io/redhat-developer/rhdh-plugin-export-overlays/backstage-plugin-mcp-actions-backend:<tag>
    disabled: false
```

Tag format: `bs_<backstage_version>__<plugin_version>`

## Install MCP Tool Plugins (Extras)

### Software Catalog MCP Extras

```yaml
- package: oci://ghcr.io/redhat-developer/rhdh-plugin-export-overlays/red-hat-developer-hub-backstage-plugin-software-catalog-mcp-extras:<tag>
  disabled: false
```

### TechDocs MCP Extras

```yaml
- package: oci://ghcr.io/redhat-developer/rhdh-plugin-export-overlays/red-hat-developer-hub-backstage-plugin-techdocs-mcp-extras:<tag>
  disabled: false
```

### Scaffolder MCP Extras

```yaml
- package: oci://ghcr.io/redhat-developer/rhdh-plugin-export-overlays/red-hat-developer-hub-backstage-plugin-scaffolder-mcp-extras:<tag>
  disabled: false
```

**Note**: Previous plugins (`software-catalog-mcp-tool`, `techdocs-mcp-tool`)
are deprecated.

## Configure Authentication and Endpoints

### Static Token (app-config.yaml)

```yaml
backend:
  auth:
    externalAccess:
      - type: static
        options:
          token: ${MCP_TOKEN}
          subject: mcp-clients
```

Generate token: `node -p 'require("crypto").randomBytes(24).toString("base64")'`

### Register Plugin Sources

```yaml
backend:
  actions:
    pluginSources:
      - software-catalog-mcp-extras
      - techdocs-mcp-extras
      - scaffolder-mcp-extras
      - catalog
      - scaffolder
```

### OpenAI Compatibility

```yaml
mcpActions:
  namespacedToolNames: false
```

## Client Configuration

### Cursor

```json
{
  "mcpServers": {
    "backstage-actions": {
      "url": "https://<my_developer_hub_domain>/api/mcp-actions/v1",
      "headers": {
        "Authorization": "Bearer <mcp_token>"
      }
    }
  }
}
```

### Continue

```yaml
mcpServers:
  - name: backstage-actions
    type: sse
    url: https://<my_developer_hub_domain>/api/mcp-actions/v1/sse
    requestOptions:
      headers:
        Authorization: "Bearer <mcp_token>"
```

### Developer Lightspeed (LCORE)

In `lightspeed-stack.yaml`:

```yaml
mcp_servers:
  - name: mcp::backstage
    provider_id: model-context-protocol
    url: https://<my_developer_hub_domain>/api/mcp-actions/v1
    authorization_headers:
      Authorization: "client"
```

In `app-config.yaml`:

```yaml
lightspeed:
  mcpServers:
  - name: mcp::backstage
    token: ${MCP_TOKEN}
```

## Software Catalog MCP Tools

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `fetch-catalog-entities` | List entities (components, APIs, resources) | `kind`, `type`, `name`, `owner`, `lifecycle`, `tags`, `verbose` |
| `catalog-register-tool` | Register entity via catalog-info.yaml URL | `url` |
| `catalog-unregister-tool` | Remove entity from catalog | `entityRef` |
| `software-template-metadata-tool` | Get template metadata | `templateRef` |

## TechDocs MCP Tools

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `fetch-techdocs` | List entities with TechDocs | `entityType`, `namespace`, `owner`, `lifecycle`, `tags` |
| `analyze-techdocs-coverage` | Calculate documentation coverage % | `entityType`, `namespace`, `owner`, `lifecycle`, `tags` |
| `retrieve-techdocs-content` | Get specific TechDocs content | `entityRef`, `pagePath` |

## Scaffolder MCP Tools

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| List actions | List installed Scaffolder actions | (none) |
| Get task logs | Retrieve task execution logs | `taskId`, `after` |
| Dry-run | Sandboxed template validation | `templateYaml`, `values`, `files` |
| Execute template | Run a Software Template | `templateRef`, `values`, `secrets` |
| List tasks | Retrieve/filter task list | `owned`, `limit`, `offset` |

## Personal Access Token Management

### Enable Encryption

```yaml
backend:
  auth:
    keys:
    - secret: ${BACKEND_SECRET}
```

### Database Configuration (PostgreSQL)

```yaml
backend:
  database:
    client: pg
    connection:
      host: localhost
      port: 5432
      user: ${POSTGRES_USER}
      password: ${POSTGRES_PASSWORD}
```

## Troubleshooting

### Verify Plugin Installation

```bash
oc logs -c install-dynamic-plugins deployment/<rhdh-deployment>
```

### Check Tool Logs

Log target names: `software-catalog-mcp-tool`, `techdocs-mcp-tool`

### Common Issues

| Issue | Resolution |
|-------|-----------|
| "Model does not support tool calling" | Switch to tool-calling compatible model |
| Tools not found after connection | Verify token, check `Bearer` format, confirm endpoint URL |
| Nonsensical output | Use larger model (7B+, 32k+ context); refine queries |
| HTTP 401 on MCP endpoint | Verify static token in `app-config.yaml`; check YAML formatting |
