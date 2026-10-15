---
name: ocp-lightspeed-troubleshoot
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: ocp_lightspeed
  docs-version: "1.0"
  skill-group: "OpenShift Platform"
description: >
  Use when OpenShift Lightspeed on the demo cluster misbehaves: OLSConfig
  NotReady or ApiReady=False, unready API pods, provider authentication
  failures (for example Azure AADSTS700016), 502 errors in the console, API
  401/403, prompt-too-long or truncated answers, or the operator missing from
  the catalog. Do NOT use for concepts (use ocp-lightspeed-about) or planned
  configuration changes (use ocp-lightspeed-configure).
---

# OpenShift Lightspeed troubleshooting

Thin skill: repo findings and routing here, product fixes in the linked
sections. Repo records: `docs/TROUBLESHOOTING.md` and `docs/OPERATIONS.md`.

## When to use

- The fresh-environment baseline or a user reports Lightspeed not answering.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Lightspeed faults are routed to the provisioner (owner of the operator, OLSConfig and provider Secret); the repo does not mutate them | `docs/TROUBLESHOOTING.md` ("A fresh cluster is available but the baseline has exceptions") | [Troubleshooting][troubleshoot] |
| Recorded finding (2026-10-05, 1.1.4): API unready, readiness 503, Azure OpenAI provider failing Entra authentication with `AADSTS700016` | `docs/TROUBLESHOOTING.md` ("Lightspeed API unready: Azure application identity not found") | [API authentication failures][apiauth] |

## Procedure

1. Pass the OpenShift safety guard in `AGENTS.md`, then read status only:
   the OLSConfig conditions and the API deployment, using the read-only
   commands in `docs/TROUBLESHOOTING.md`. Do not read Secret values.
2. Match the symptom to a section below; for provider identity errors, follow
   the repo record and hand the owner the finding.
3. After the owner's fix, verify `ApiReady=True`, an available API deployment
   and one bounded authenticated question.

## Pitfalls

- A Succeeded CSV and nonempty Secret keys prove neither credential validity
  nor service health.
- 502 errors right after a configuration change can be a pod still starting;
  see [502 Bad Gateway][502] before changing anything.
- Do not switch providers, bypass readiness or patch the operator-generated
  deployment to hide a failure.

## Official documentation (OpenShift Lightspeed, "1.0" set)

| Symptom | Section |
|---|---|
| 502 in the console | [502 Bad Gateway errors][502] |
| Operator not in the catalog | [Operator missing from OperatorHub][operatorhub] |
| Reasoning tags in answers | [Delineator prompt][delineator] |
| API 401/403 | [API authentication failures][apiauth] |
| Prompt too long, cut answers | [Prompt is too long][toolong], [truncated responses][truncated] |
| Lost history | [Conversation history issues][history] |

## Related skills

`ocp-lightspeed-configure`, `ocp-lightspeed-release-notes`, `inspect-cluster`.

[troubleshoot]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/troubleshoot/index#ols-troubleshooting-openshift-lightspeed
[502]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/troubleshoot/index#ols-502-bad-gateway-errors_ols-troubleshooting-openshift-lightspeed
[operatorhub]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/troubleshoot/index#ols-operator-missing-from-operatorhub-list_ols-troubleshooting-openshift-lightspeed
[delineator]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/troubleshoot/index#ols-reasoning-model-generates-delineator-prompt_ols-troubleshooting-openshift-lightspeed
[apiauth]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/troubleshoot/index#ols-troubleshoot-api-authentication-failures_ols-troubleshooting-openshift-lightspeed
[toolong]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/troubleshoot/index#ols-proc-error-prompt-is-too-long_ols-troubleshooting-openshift-lightspeed
[truncated]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/troubleshoot/index#ols-proc-resolving-truncated-responses_ols-troubleshooting-openshift-lightspeed
[history]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/troubleshoot/index#ols-proc-resolving-issues-with-conversation-history_ols-troubleshooting-openshift-lightspeed
