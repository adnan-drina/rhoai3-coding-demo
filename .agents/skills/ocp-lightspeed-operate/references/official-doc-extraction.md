# Official Doc Extraction

Use this extraction to keep OpenShift Lightspeed operational content grounded
in the official Operate guide. When integrating with the REST API, verify
routes and authentication against the live cluster before scripting.

## Chapter 1: Operating OpenShift Lightspeed

### Using the Chat Window

Procedure:

1. Click the Red Hat OpenShift Lightspeed icon in the lower-right corner of the
   OpenShift web console.
2. Enter a question in the "Send a message" field.
3. Click Submit.
4. Lightspeed returns information based on the question.

### About Lightspeed Conversations

Supported topic areas:

- OpenShift Container Platform
- Kubernetes
- OpenShift Virtualization
- OpenShift Service Mesh

Conversation behavior:

- Questions unrelated to target topics are ignored.
- Rephrasing improves clarity when Lightspeed misinterprets a question.
- Conversation history provides context that influences subsequent answers.
- Specific language increases response success (e.g., "How do I start a virtual
  machine in OpenShift Virtualization?" instead of "How do I start a virtual
  machine?").
- Conversation history does not persist across console page reloads.
- Reloading the console page acts the same as clicking "New Chat".
- Restarting the Lightspeed service erases all conversation history.

### Providing Feedback

Prerequisites: Lightspeed Operator installed and service deployed.

Procedure:

1. Open Lightspeed, enter a question, and click Submit.
2. On the response, click thumbs up or thumbs down.
3. Optionally enter additional text feedback.
4. Click Submit.

What is sent to Red Hat: the rating, any text entered, the question, and the
response.

### Sample Conversation Patterns

#### General Question

Example prompt: "What is an OpenShift image stream used for?"

Expected result: explanation of image streams with usage details.

#### Related Follow-Up Questions

Example flow:

1. "How are OpenShift security context constraints used?" → general information
2. "Can I control who can use a particular SCC?" → refined details
3. "Can you give me an example?" → sample code

Key behavior: follow-up questions in the same chat refine results using
conversation history as context.

#### Attaching a Resource Object

Procedure:

1. Navigate to a supported resource in the web console (e.g., Workloads > Pods
   > pod name).
2. Click the Lightspeed icon.
3. Click "Add" in the Lightspeed UI to attach a resource object.
4. Select the resource object to attach.
5. Enter a question and click Submit.

Benefit: provides specific context for data-driven troubleshooting.

#### Troubleshooting Alerts

Procedure:

1. In the web console, navigate to Observe > Alerting.
2. Expand an alert row, click the alert to view details.
3. Click the Lightspeed icon.
4. Click "Attach context" and select "Alert".
5. Enter "What should I do about this alert?" and click Submit.

The alert context is provided to Lightspeed when generating the response.

### Starting a New Chat

Procedure:

1. In the Lightspeed UI, click "Clear chat" to clear history.
2. Enter a new question and click Submit.

Lightspeed only references the new question when generating a response,
without influence from prior conversation context.

## Chapter 2: Interacting with the API

### Bearer Token Authentication

Every request to a protected endpoint requires a bearer token:

```
Authorization: Bearer <token>
```

Example curl request:

```bash
curl -H "Authorization: Bearer ${TOKEN}" \
     -H "Content-Type: application/json" \
     https://<ols_host>/v1/query \
     -d '{"query": "How do I create a deployment?"}'
```

### MCP Server Authentication

To proxy calls to Model Context Protocol (MCP) servers:

1. Discover required headers:

   ```
   GET /v1/mcp/client-auth-headers
   ```

2. Include credentials in the `mcp_headers` field:

   ```json
   {
     "query": "Show GitHub issues",
     "mcp_headers": {
       "github-mcp": {"Authorization": "Bearer <github_token>"}
     }
   }
   ```

### API Authentication Requirements

| Endpoint | Method | Auth Required | Virtual Path |
|----------|--------|---------------|--------------|
| `/v1/query` | POST | Yes | `/ols-access` |
| `/v1/streaming_query` | POST | Yes | `/ols-access` |
| `/v1/conversations` | GET, PUT, DELETE | Yes | `/ols-access` |
| `/v1/feedback` | POST | Yes | `/ols-access` |
| `/v1/mcp-apps/resources` | POST | Yes | `/ols-access` |
| `/v1/mcp-apps/tools/call` | POST | Yes | `/ols-access` |
| `/authorized` | POST | Yes | `/ols-access` |
| `/metrics` | GET | No | — |
| `/readiness` | GET | No | — |
| `/liveness` | GET | No | — |

### Direct REST API Access

All versioned API endpoints use the `/v1` path.

Concurrency limit: up to 100 concurrent connections. Behavior beyond this
limit is unsupported.

Prerequisites:

- Lightspeed installed and running via the Operator
- `oc` or `kubectl` CLI access
- `lightspeed-app-server` service exposed via an OpenShift route
- User has the `ols-user` ClusterRole

#### Authentication Procedure

The service validates identity through Kubernetes `TokenReview` and
`SubjectAccessReview` (SAR) against `/ols-access`.

Grant `ols-user` role:

```bash
# To a user
oc adm policy add-cluster-role-to-user ols-user <username>

# To a service account
oc adm policy add-cluster-role-to-user ols-user \
  system:serviceaccount:<namespace>:<service_account_name>
```

Obtain a bearer token:

```bash
# For your own user
TOKEN=$(oc whoami -t)

# For a service account
TOKEN=$(oc create token <service_account_name> -n <namespace>)
```

Verify token validity:

```bash
curl -k -X POST "https://${OLS_HOST}/authorized" \
  -H "Authorization: Bearer ${TOKEN}"
```

#### API Endpoints Reference

| Endpoint | Description |
|----------|-------------|
| `POST /v1/query` | Send a prompt. Required: `query`. Optional: `conversation_id`, `provider`, `model`, `attachments`. |
| `POST /v1/streaming_query` | SSE stream. Types: `text`, `tool_call`, `tool_result`, `approval_required`, `reasoning`, `end`. |
| `GET /v1/conversations` | List conversation IDs, summaries, and message counts. |
| `GET /v1/conversations/{id}` | Retrieve history for a specific conversation. |
| `DELETE /v1/conversations/{id}` | Delete a specific conversation history. |
| `POST /v1/feedback` | Submit sentiment (`1` or `-1`) or text feedback. Must be enabled in OLS config. |

#### Supported Attachment Formats

| Type | Content-Type | Notes |
|------|-------------|-------|
| Logs | `text/plain` | — |
| Configurations | `application/yaml` | YAML with `kind` and `metadata.name` is treated as a named Kubernetes resource. |

#### Error Handling

| Status Code | Description |
|-------------|-------------|
| 401 | Unauthorized — missing or invalid token |
| 403 | Forbidden — user lacks the `ols-user` cluster role |
| 413 | Payload too large — prompt exceeds LLM context window |
| 503 | Service unavailable — service or LLM still initializing |

Errors return JSON with a `detail` field containing `response` and `cause`.

## Chapter 3: REST API Specifications

### OpenAPI 3.1 Specification

The specification is auto-generated from route definitions. No manual
configuration of separate specification files is required.

Available endpoints (when running locally on port 8080):

| Endpoint | Purpose |
|----------|---------|
| `GET /docs` | Interactive Swagger UI API explorer |
| `GET /redoc` | ReDoc three-panel responsive documentation |
| `GET /openapi.json` | Raw machine-readable OpenAPI JSON file |

Production security: restrict network-level access to prevent `/docs` and
`/redoc` from being publicly accessible. Do not expose the service to the
public internet without `kube-rbac-proxy` authentication.

### Using the Swagger UI

Prerequisites: Lightspeed service running.

Procedure:

1. Navigate to `http://localhost:8080/docs`.
2. Expand any endpoint tag to view parameters, request body schema, and
   response codes.
3. Click "Try it out" to send live requests from the browser.
4. If authentication is enabled, click "Authorize" and provide a valid bearer
   token first. Unauthenticated requests return 401 or 403.

### Regenerating the OpenAPI Schema

The canonical version-controlled API surface is in `docs/openapi.json`.
After route, model, or version changes, regenerate to prevent schema drift:

```shell
make schema
```
