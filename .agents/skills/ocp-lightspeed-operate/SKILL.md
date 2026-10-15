---
name: ocp-lightspeed-operate
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: ocp_lightspeed
  docs-version: "1.0"
  skill-group: "OpenShift Platform"
description: >
  Use when using OpenShift Lightspeed on the demo cluster: the console chat,
  attaching resources or alerts to a question, feedback and data collection,
  or calling the Lightspeed REST API. Do NOT use for OLSConfig changes (use
  ocp-lightspeed-configure) or errors and unready pods (use
  ocp-lightspeed-troubleshoot).
---

# Operating OpenShift Lightspeed

Thin skill: repo posture here, usage and API details in the linked sections.

## When to use

- Showing the console assistant during a session, or answering how a user
  reaches it.
- Calling the REST API from a script or tool.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Lightspeed is not part of any workshop stage path; demo flows use the governed MaaS models, not Lightspeed | `README.md` (stages); `docs/OPERATIONS.md` | [Using the chat window][chat] |
| No repo script or tool calls the Lightspeed REST API | — | [Interacting with the API][api] |

## Procedure

1. Check service health first (`ocp-lightspeed-troubleshoot`); a Succeeded
   operator with an unready API returns errors in the chat.
2. Use the chat or the API per the linked sections. For API calls, take the
   token and endpoint from the documented authentication flow; never paste
   tokens into Git or chat.

## Pitfalls

- Feedback and transcripts may be collected; check
  [disabling data collection][datacollection] before demoing with sensitive
  content.
- An API call can fail for authentication or RBAC reasons that look like
  service faults; read [API authentication requirements][authmatrix] and
  [error handling][errors].

## Official documentation (OpenShift Lightspeed, "1.0" set)

| Topic | Section |
|---|---|
| Chat | [Using the chat window][chat], [conversations and context][conversations] |
| Attaching context | [Attaching a resource][attach], [troubleshooting alerts][alerts] |
| Data collection | [Disabling data collection][datacollection] |
| API access | [Authenticate API requests][apiauth], [authentication requirements][authmatrix] |
| API reference | [Endpoints][endpoints], [error handling][errors], [REST API specifications][spec] |

## Related skills

`ocp-lightspeed-configure`, `ocp-lightspeed-troubleshoot`, `ocp-web-console`.

[chat]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/operate/index#ols-initiating-chat-using-chat-window_ols-using-openshift-lightspeed
[conversations]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/operate/index#ols-about-lightspeed-conversations_ols-using-openshift-lightspeed
[attach]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/operate/index#ols-attaching-a-resource-object-to-your-query_ols-using-openshift-lightspeed
[alerts]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/operate/index#ols-using-lightspeed-to-troubleshoot-alerts_ols-using-openshift-lightspeed
[datacollection]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/operate/index#ols-disabling-data-collection-operator_ols-using-openshift-lightspeed
[api]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/operate/index#ols-interacting-with-the-api
[apiauth]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/operate/index#ols-authenticate-api-requests_ols-interacting-with-the-api
[authmatrix]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/operate/index#ols-api-authentication-matrix_ols-interacting-with-the-api
[endpoints]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/operate/index#ols-ref-api-endpoints-reference_ols-interacting-with-the-api
[errors]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/operate/index#ols-ref-api-error-handling_ols-interacting-with-the-api
[spec]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/operate/index#ols-con-openshift-lightspeed-rest-api-specifications_ols-interacting-with-the-openshift-lightspeed-rest-api
