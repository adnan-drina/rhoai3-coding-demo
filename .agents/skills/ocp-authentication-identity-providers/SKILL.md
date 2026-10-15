---
name: ocp-authentication-identity-providers
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: ocp
  docs-version: "4.22"
  skill-group: "OpenShift Platform"
description: >
  Use when reviewing or changing OpenShift authentication as this repo uses it:
  the provisioned OpenID identity provider rhbk (environment Keycloak, sso
  realm) in OAuth cluster, persona identities ai-admin and ai-developer, group
  membership set by stages/010-openshift-ai-platform-foundation/deploy.sh, persona kubeconfigs from
  stages/010-openshift-ai-platform-foundation/validate.sh --login-personas, the platform-keycloak OAuthClient in Stage 070
  identity, the Stage 060 openshell realm that brokers OpenShift login, or
  login failures. Do NOT use for RBAC bindings and SCCs (use
  ocp-security-rbac-scc), OpenShift AI admin and user groups (use
  rhoai-users-groups-access), Argo CD SSO (use ocp-gitops-operator), or
  Developer Hub sign-in (use rhdh-authentication).
---

# Authentication and identity providers

Thin skill: repo decisions and pitfalls here, product behavior in the linked
OpenShift Container Platform 4.22 and Red Hat build of Keycloak 26.4 sections.
Detailed records: `gitops/stages/010-openshift-ai-platform-foundation/010-access/README.md`,
`gitops/stages/070-advanced-app-platform/070-identity/README.md` and
`docs/OPERATIONS.md` (shared base-platform SSO).

## When to use

- A persona cannot log in, is missing from a group, or a persona check in
  Stage 010 `validate.sh` warns or fails.
- A change touches `OAuth/cluster`, an `OAuthClient`, `stages/010-openshift-ai-platform-foundation/deploy.sh` or a
  Keycloak realm import.
- Someone proposes adding htpasswd users, removing `kubeadmin`, or LDAP group sync.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| The cluster identity provider is provisioned, not Git-owned: one OpenID provider `rhbk` backed by Keycloak `keycloak/keycloak`, realm `sso`; the repo never edits `OAuth/cluster` | `stages/010-openshift-ai-platform-foundation/validate.sh` (checks `rhbk` type `OpenID` and Keycloak Ready) | [Configuring an OpenID Connect identity provider][oidc] |
| Personas are existing provider users named in the local `.env` (`RHOAI_ADMIN_USER`, `RHOAI_DEVELOPER_USER`); no passwords or users are created | `stages/010-openshift-ai-platform-foundation/deploy.sh`, `env.example` | [Understanding identity provider configuration][idp-about] |
| Group membership is runtime data: `stages/010-openshift-ai-platform-foundation/deploy.sh` adds personas to `rhods-admins` and `rhoai-developers`; Argo CD ignores `/users` of `rhoai-developers` | `stages/010-openshift-ai-platform-foundation/deploy.sh`, `gitops/applications/010-access.yaml` | [Understanding authentication][understanding] |
| Persona acceptance uses real browser logins written to separate kubeconfigs, never impersonation | `stages/010-openshift-ai-platform-foundation/validate.sh --login-personas` | [Managing OAuth access tokens][tokens] |
| OAuthClient `platform-keycloak` in Git with placeholder secret and redirect; a Sync Job writes the real values (kept for rollback of the older OpenShift-brokered path) | `gitops/stages/070-advanced-app-platform/070-identity/rhbk-instance/oauthclient.yaml` | [Configuring OAuth clients][oauth-clients] |
| Stage 070 application realm `platform` brokers directly to the base `sso` realm; OpenShift, OpenShift AI, Dev Spaces and Argo CD keep native OpenShift login | `gitops/stages/070-advanced-app-platform/070-identity/`, `docs/OPERATIONS.md` | [Keycloak identity brokering][kc-broker] |
| Stage 060 realm `openshell` brokers OpenShift login and refuses identities not enrolled in advance | `gitops/stages/060-agent-runtime-and-agentops/060-openshell-identity/realm-openshell.yaml`, `stages/060-agent-runtime-and-agentops/deploy.sh` | [Keycloak identity brokering][kc-broker] |
| `kubeadmin` is not removed by the repo; installation and admin setup use a non-`kubeadmin` privileged account | `docs/OPERATIONS.md` | [Removing the kubeadmin user][kubeadmin] |

## Procedure

1. Never commit provider secrets, client secrets or user passwords; OAuthClient
   and realm secrets are written by Sync hooks.
2. After the OpenShift safety guard in `AGENTS.md`, assign groups and refresh
   persona sessions:

   ```bash
   ./stages/010-openshift-ai-platform-foundation/deploy.sh
   stages/010-openshift-ai-platform-foundation/validate.sh --login-personas
   ./stages/010-openshift-ai-platform-foundation/validate.sh
   oc get oauth cluster -o jsonpath='{.spec.identityProviders[*].name}{"\n"}'
   oc get group rhods-admins rhoai-developers
   ```

## Pitfalls

- A User object appears only after the first provider login; group membership
  can be set earlier but stays unverified until then.
- OAuth access tokens expire; a missing or expired persona session is a
  warning (exit 2), a wrong user or cluster a failure.
- Username or email equality never authorizes linking an application account
  to an OpenShift identity; the Stage 070 identity hook checks the subject.
- Reverting a realm or hook change in Git does not undo Keycloak database
  state; use the Keycloak Admin API for rollback.
- Known symptoms: `docs/TROUBLESHOOTING.md#stage-070-shared-sso-refuses-a-user-or-sonarqube-login`,
  `docs/TROUBLESHOOTING.md#mta-openshift-login-does-not-appear`.

## Official documentation

| Topic | Section |
|---|---|
| Concepts (OCP 4.22) | [Understanding authentication][understanding], [Identity provider configuration][idp-about] |
| Providers (OCP 4.22) | [Configuring identity providers][idps], [OpenID Connect][oidc], [Direct external authentication][external-auth] |
| OAuth (OCP 4.22) | [Internal OAuth server][internal-oauth], [OAuth clients][oauth-clients], [Access tokens][tokens] |
| Users and groups (OCP 4.22) | [Removing kubeadmin][kubeadmin], [Syncing LDAP groups][ldap] |
| Keycloak 26.4 | [Identity brokering][kc-broker] |

## Related skills

`ocp-security-rbac-scc`, `rhoai-users-groups-access`, `rhoai-access-group-selection`,
`ocp-gitops-operator`, `rhdh-authentication`, `ocp-devspaces-admin`.

[understanding]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/authentication_and_authorization/index#understanding-authentication
[internal-oauth]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/authentication_and_authorization/index#configuring-internal-oauth
[oauth-clients]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/authentication_and_authorization/index#configuring-oauth-clients
[tokens]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/authentication_and_authorization/index#managing-oauth-access-tokens
[idp-about]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/authentication_and_authorization/index#understanding-identity-provider
[idps]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/authentication_and_authorization/index#configuring-identity-providers
[oidc]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/authentication_and_authorization/index#configuring-oidc-identity-provider
[external-auth]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/authentication_and_authorization/index#external-auth
[kubeadmin]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/authentication_and_authorization/index#removing-kubeadmin
[ldap]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/authentication_and_authorization/index#ldap-syncing
[kc-broker]: https://docs.redhat.com/en/documentation/red_hat_build_of_keycloak/26.4/html-single/server_administration_guide/index#identity_broker
