---
name: rhoai-central-authentication-service
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when someone proposes configuring the OpenShift AI centralized
  authentication service for an external OIDC provider (GatewayConfig
  spec.oidc, data-science-gateway, kube-auth-proxy, service token auth), or
  asks whether this demo's Keycloak login needs it. Do NOT use for the
  OpenShift login provider rhbk (use ocp-authentication-identity-providers),
  dashboard groups (use rhoai-users-groups-access), MaaS API keys or MaaS
  external OIDC (use rhoai-maas-governance), or certificates in general (use
  rhoai-certificate-management).
---

# RHOAI central authentication service

Thin skill. Not deployed in this demo: the cluster keeps the built-in OpenShift
OAuth server with Keycloak as identity provider `rhbk`, so the external-OIDC
mode of the OpenShift AI gateway is not configured. Product behavior is in the
linked OpenShift AI 3.5 sections.

## When to use

- A proposal to switch the cluster to direct external OIDC authentication.
- A `GatewayConfig`, `data-science-gateway` or `kube-auth-proxy` question.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Login stays on the OpenShift OAuth server; identity provider `rhbk` (Keycloak realm `sso`) comes from the environment, not GitOps; Stage 010 validates it is present | `stages/010-openshift-ai-platform-foundation/README.md`, `stages/010-openshift-ai-platform-foundation/validate.sh` | [Centralized authentication service][about] |
| No `GatewayConfig` OIDC settings and no OIDC client Secret in Git | none under `gitops/` | [Configure OIDC][oidc] |
| Exposing the dashboard on an `rh-ai.*` hostname through `data-science-gateway` is open work | `BACKLOG.md` ("Dashboard Route") | — |

## When it would apply

The chapter requires the OpenShift cluster to be configured for direct
authentication with an external OIDC provider first ([Configure OIDC][oidc]).
Only then:

1. Put the `GatewayConfig` change in a Stage 010 GitOps component and verify
   the live object name and schema first (`oc get gatewayconfig`,
   `oc explain gatewayconfig.spec.oidc`).
2. Keep the OIDC client Secret (in `openshift-ingress`) out of Git: create it
   from the local `.env` in a deploy script, as other stages do with
   `load_env`.
3. Add a custom CA only if the provider needs one
   ([Configure custom CA certificates][ca]).
4. Update `ocp-authentication-identity-providers`, `rhoai-users-groups-access`
   and the Stage 010 README in the same change.

## Pitfalls

- Switching the cluster to direct OIDC replaces the OAuth login used by every
  persona and every Stage 070 tool that signs in through OpenShift OAuth;
  treat it as a platform redesign, not a setting.
- Read-only checks after the OpenShift safety guard in `AGENTS.md`:
  `oc get oauth cluster -o jsonpath='{.spec.identityProviders[*].name}'`.
  Failures of the gateway path are listed in the
  [troubleshooting reference][trouble].

## Official documentation (OpenShift AI 3.5)

| Topic | Section |
|---|---|
| Chapter | [Configure a central authentication service for an external OIDC provider][chapter] |
| Concepts | [Centralized authentication service][about], [Authentication methods][methods] |
| Procedures | [Configure OIDC][oidc], [Service token auth][token], [Custom CA certificates][ca] |
| Troubleshooting | [Troubleshooting reference][trouble] |

## Related skills

`ocp-authentication-identity-providers`, `rhoai-users-groups-access`,
`rhoai-certificate-management`, `ocp-ingress-gateway-routes`,
`rhoai-maas-governance`.

[chapter]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#configuring-external-oidc-provider_managing-rhoai
[about]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#about-centralized-auth-oidc_managing-rhoai
[methods]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#authentication_methods_for_the_centralized_authentication_service
[oidc]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#configuring-oidc-auth-gateway-api_managing-rhoai
[token]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#configuring-service-token-auth-gateway-api_managing-rhoai
[ca]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#configuring-custom-ca-certs-oidc_managing-rhoai
[trouble]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#troubleshooting-common-problems-gateway-api_managing-rhoai
