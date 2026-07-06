---
name: ocp-lightspeed-troubleshoot
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "ocp"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when troubleshooting Red Hat OpenShift Lightspeed 1.0 issues, including
  must-gather data collection, pod failures, LLM provider connectivity,
  authentication errors, and known issues. Do NOT use for concepts
  (use ocp-lightspeed-about), installing (use ocp-lightspeed-install),
  configuring (use ocp-lightspeed-configure), or operations
  (use ocp-lightspeed-operate).
---

# OCP Lightspeed Troubleshoot

Use this skill to ground OpenShift Lightspeed troubleshooting guidance in the
official Red Hat OpenShift Lightspeed 1.0 troubleshoot guide for the active
baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority.

## 502 Bad Gateway Errors

After deploying OpenShift Lightspeed, the web console interface may return
502 Bad Gateway errors while service pods are still starting. Wait a few minutes
and retry. No configuration change is required.

## Operator Not Visible in OperatorHub

The OpenShift Lightspeed Operator only appears in OperatorHub on supported
architectures. It is filtered out on anything other than `x86_64`.

## Reasoning Model Delineator Prompt

Reasoning models may emit tags such as `THOUGHT` or `reasoning` to separate
inner logic from the final answer. OpenShift Lightspeed does not control these
tags. To suppress them:

- Use a model-specific keyword in your prompt (e.g., `/nothink`).
- Disable the delineator feature in the inference server configuration.

Consult the model or inference server documentation for specifics.

## API Authentication Failures

Use status codes to diagnose authentication issues with the OpenShift
Lightspeed API:

| Status | Cause | Example Detail |
|--------|-------|----------------|
| 401 | Missing, malformed, or non-Bearer `Authorization` header | `Unauthorized: No auth header found` |
| 403 | Invalid/expired token or missing RBAC for `/ols-access` | `Forbidden: User does not have access` |
| 500 | Unexpected error in Kubernetes `TokenReview` | `Forbidden: Unable to Review Token` |

## Prompt Too Long Errors

The `Prompt is too long` error occurs when total tokens (input query, RAG
context, expected response) exceed the model context window.

1. Verify the context window value is correct for the model and provider.
2. Lower the maximum response tokens to leave room for input and context.
3. Shorten the query or reduce attached file size.

## Truncated Responses

Truncated or incomplete responses occur when the model reaches its response
token limit.

1. Verify the model supports a higher response token limit.
2. Increase the token limit in the OLSConfig CR.
3. Type `continue` as a follow-up query to retrieve remaining text.

Set the response token value in reasonable proportion to the context window;
too high a value limits input query size.

## Conversation History Issues

Earlier dialogue may be truncated when the model reaches its context limit.

1. Verify the context window is correctly set for the model and provider.
2. Lower the max response tokens to increase space for conversation history.

## Google Vertex AI Configuration Errors

Common `OLSConfig` CR validation errors for Google Vertex AI:

| Error | Resolution |
|-------|------------|
| `googleVertexConfig is required for google_vertex provider` | Provide the `googleVertexConfig` object with `projectID` and `location`. |
| `googleVertexConfig may only be set when type is google_vertex` | Remove `googleVertexConfig`; for `google_vertex_anthropic`, use `googleVertexAnthropicConfig`. |
| `credentialKey must not be empty or whitespace` | Provide a valid key name, or omit the field to default to `apitoken`. |

## Workflow

1. Confirm the active OpenShift baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Identify the troubleshooting category:
   - 502 Bad Gateway or pod startup delays
   - Operator visibility in OperatorHub
   - Reasoning model delineator output
   - API authentication failures (401, 403, 500)
   - Prompt too long errors
   - Truncated or incomplete responses
   - Conversation history truncation
   - Google Vertex AI OLSConfig validation errors
4. Use exact error messages, status codes, and procedures from the extraction.
5. If the issue is not covered here, check the official documentation URL in
   `references/source-capture.md` for updates.

## Related Skills

- Use `ocp-lightspeed-about` for OpenShift Lightspeed concepts and architecture.
- Use `ocp-lightspeed-install` for installing the OpenShift Lightspeed Operator.
- Use `ocp-lightspeed-configure` for OLSConfig CR and provider configuration.
- Use `ocp-lightspeed-operate` for operational procedures and day-2 management.
- Use `ocp-lightspeed-release-notes` for release notes and known issues.
- Use `ocp-lightspeed-troubleshoot` (this skill) for diagnostics and resolution.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
