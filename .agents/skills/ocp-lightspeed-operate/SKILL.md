---
name: ocp-lightspeed-operate
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "ocp"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when using or operating Red Hat OpenShift Lightspeed 1.0, including
  accessing the AI assistant, asking questions, understanding responses,
  conversation management, and day-2 operations. Do NOT use for concepts
  (use ocp-lightspeed-about), installing (use ocp-lightspeed-install),
  configuring (use ocp-lightspeed-configure), or troubleshooting
  (use ocp-lightspeed-troubleshoot).
---

# OCP Lightspeed Operate

Use this skill to ground OpenShift Lightspeed operational and usage guidance
in the official Red Hat OpenShift Lightspeed 1.0 Operate guide.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority. This skill covers end-user interaction
patterns, conversation management, resource attachments, alert troubleshooting,
and REST API access; it does not replace installation, configuration, concept,
or troubleshooting skills.

## Using the Chat Window

- Access Lightspeed by clicking the OpenShift Lightspeed icon in the
  lower-right corner of the OpenShift web console.
- Enter a question in the "Send a message" field and click Submit.
- Lightspeed answers questions about OpenShift, Kubernetes, and specialized
  components (OpenShift Virtualization, OpenShift Service Mesh, etc.).
- Questions unrelated to target topics are ignored. Rephrase for clarity if
  results are poor.
- Use specific language (e.g., "How do I start a virtual machine in OpenShift
  Virtualization?" rather than "How do I start a virtual machine?").

## Conversation Management

- Conversation history provides context for follow-up questions within the
  same chat session.
- Ask follow-up questions in the same chat to refine results and build context.
- History does not persist across console page reloads. Reloading acts the same
  as clicking "New Chat".
- Restarting the Lightspeed service erases all conversation history.
- Click "Clear chat" to start a new conversation without prior context
  influencing replies.

## Resource Attachments and Alert Analysis

- Navigate to a supported resource (e.g., Workloads > Pods > pod name), then
  open Lightspeed and click "Add" to attach the resource object.
- Attachments give Lightspeed specific context for data-driven troubleshooting.
- For alerts: navigate to Observe > Alerting, expand and select an alert, open
  Lightspeed, click "Attach context" and select "Alert", then ask about the
  alert.

## Feedback

- Click thumbs up or thumbs down on any response to rate it.
- Optionally enter text feedback before submitting.
- The rating, text, question, and response are sent to Red Hat for review.

## REST API Access

Direct API access supports up to 100 concurrent connections. All versioned
endpoints use the `/v1` path. Authentication uses bearer tokens validated
through Kubernetes `TokenReview` and `SubjectAccessReview` against `/ols-access`.

Key endpoints:

- `POST /v1/query` — send a prompt (required: `query`; optional:
  `conversation_id`, `provider`, `model`, `attachments`)
- `POST /v1/streaming_query` — SSE stream (types: `text`, `tool_call`,
  `tool_result`, `approval_required`, `reasoning`, `end`)
- `GET /v1/conversations` — list conversation IDs, summaries, message counts
- `GET /v1/conversations/{id}` — retrieve specific conversation history
- `DELETE /v1/conversations/{id}` — delete a conversation
- `POST /v1/feedback` — submit sentiment (`1` or `-1`) or text feedback
- Unauthenticated endpoints: `/metrics`, `/readiness`, `/liveness`

MCP server proxy authentication uses `GET /v1/mcp/client-auth-headers` to
discover required headers, then passes credentials in the `mcp_headers` field
of the request body.

Attachment formats: `text/plain` for logs, `application/yaml` for
configurations (YAML with `kind` and `metadata.name` is treated as a named
Kubernetes resource).

See `references/official-doc-extraction.md` for full API details, error codes,
authentication procedures, and OpenAPI specification access.

## Day-2 Operations

- Grant API access: `oc adm policy add-cluster-role-to-user ols-user <user>`
- Obtain token: `TOKEN=$(oc whoami -t)` or
  `TOKEN=$(oc create token <sa> -n <ns>)`
- Verify token: `curl -k -X POST "https://${OLS_HOST}/authorized" -H "Authorization: Bearer ${TOKEN}"`
- Access Swagger UI at `/docs`, ReDoc at `/redoc`, raw OpenAPI at `/openapi.json`
- Restrict `/docs` and `/redoc` access in production environments.
- Do not expose the service to the public internet without `kube-rbac-proxy`
  authentication.

## Workflow

1. Read `references/official-doc-extraction.md`.
2. Identify whether the task concerns:
   - Chat window usage and conversation patterns
   - Resource attachment or alert troubleshooting workflows
   - Feedback submission
   - REST API authentication and token management
   - API endpoint usage, MCP proxy headers, or attachments
   - OpenAPI specification access or regeneration
3. For API integration, verify the Lightspeed service route and authentication
   before calling endpoints.
4. For live operations, use the repo environment guard and confirm cluster
   context with `oc whoami`.

## Related Skills

- `ocp-lightspeed-about` — Lightspeed concepts, architecture, and capabilities
- `ocp-lightspeed-install` — Operator installation and service deployment
- `ocp-lightspeed-configure` — OLSConfig, providers, models, and integrations
- `ocp-lightspeed-operate` — this skill (usage, conversations, API access)
- `ocp-lightspeed-troubleshoot` — diagnostics and recovery
- `ocp-lightspeed-release-notes` — version history and known issues

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
