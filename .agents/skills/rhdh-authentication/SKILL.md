---
name: rhdh-authentication
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhdh
  docs-version: "1.10"
  skill-group: "Developer Hub"
description: >
  Use when changing or debugging sign-in to this demo's Red Hat Developer Hub:
  the OIDC provider against the Keycloak platform realm (client rhdh, redirect
  /api/auth/oidc/handler/frame), the configure hook that creates the client and
  session secrets through the stage070-rhdh-provisioner service client, the
  preferredUsernameMatchingUserEntityName resolver with static User entities
  ai-admin and ai-developer, guest login disabled, and 504 or "unable to resolve
  user identity" sign-in failures. Do NOT use for RBAC (use
  rhdh-authorization), the platform realm itself (see the identity component
  README), GitLab tokens (use rhdh-git-integration), or installation.
---

# Developer Hub authentication

Thin skill: repo decisions and pitfalls here, product behavior in the linked
Developer Hub 1.10 sections. Detailed record:
`gitops/stages/070-advanced-app-platform/070-rhdh/README.md` (How: Authentication,
Credentials) and `gitops/stages/070-advanced-app-platform/070-identity/README.md`.

## When to use

- A change touches `auth`, `signInPage` or the catalog users in Stage 070
  Developer Hub, or `070-rhdh/jobs/configure-rhdh.yaml`.
- Sign-in fails, loops, or a persona lands without catalog identity.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| OIDC provider `oidc` (`production` environment) against `https://<keycloak-host>/realms/platform`, client `rhdh`, `signInPage: oidc`, `prompt: auto` | `070-rhdh/rhdh-instance/app-config-configmap.yaml` | [Enable authentication with RHBK][rhbk] |
| `auth.environment: production`: guest login disabled | same file | [Disable the Guest login][guest] |
| Resolver `preferredUsernameMatchingUserEntityName` (documented alternative to the default `oidcSubClaimMatchingKeycloakUserId`) | same file | [Enable authentication with RHBK][rhbk] |
| Users are two static `User` entities `ai-admin`, `ai-developer` (group `ai-modernization-team`), not imported from Keycloak (Deviation: two fixed personas) | `070-rhdh/catalog/all.yaml` | [Import users from RHBK][import] |
| The `platform` realm brokers to the base `sso` realm, so users sign in with their OpenShift account | `070-identity/` (README How 4) | [Authentication overview][authn] |
| Hook `job-configure-rhdh` gets a token for `stage070-rhdh-provisioner` (only `manage-clients`), creates or updates client `rhdh` with redirect `<rhdh-url>/api/auth/oidc/handler/frame`, keeps an existing client and session secret, writes `rhdh-secrets` | `070-rhdh/jobs/configure-rhdh.yaml`, `070-identity/jobs/` | [Share a secret with RHBK][share] |

Paths are under `gitops/stages/070-advanced-app-platform/`.

## Procedure

1. Change provider or resolver config in `app-config-rhdh`; change personas in
   `070-rhdh/catalog/all.yaml` (the generator republishes the runtime catalog).
2. Never put a client or session secret in Git; the hook keeps existing
   values and generates only missing or placeholder ones on the next sync
   (the retired `rotate-credentials.py`, in git history at `82092e01`, rotated
   the GitLab and Argo CD tokens, not these).
3. Validate after the safety guard in `AGENTS.md`:

   ```bash
   ./stages/070-advanced-app-platform/validate.sh   # includes the identity client checks
   oc logs deployment/backstage-developer-hub -n rhdh -c backstage-backend --tail=200 | grep -i 'auth\|OPError'
   ```

## Pitfalls

- After a cluster suspend/resume the backend can keep stale connections and
  fail every sign-in with 504 while Keycloak is healthy; restart the
  Deployment, do not rotate secrets:
  `docs/TROUBLESHOOTING.md#red-hat-developer-hub-oidc-sign-in-fails-with-504-gateway-timeout`.
  That section's diagnosis commands still name the retired MTA Keycloak route
  and `mta` realm; check the `keycloak` Route and the `platform` realm instead.
- A signed-in user without a matching `User` entity fails with "unable to
  resolve user identity" ([Login failed][loginfail]); add the entity to
  `catalog/all.yaml`, not a resolver workaround.
- `job-configure-rhdh` must never read the master admin Secret
  (`stages/070-advanced-app-platform/validate.sh` `no_master_secret`).

## Official documentation (Developer Hub 1.10)

| Topic | Section |
|---|---|
| Concepts | [Authentication overview][authn], [User provisioning][prov] |
| Guest access | [Disable the Guest login][guest] |
| Keycloak (RHBK) | [Share a secret with RHBK][share], [Import users from RHBK][import], [Enable authentication with RHBK][rhbk] |
| Sessions | [Session management][session] |
| Troubleshooting | [Authentication issues][ts], [Login failed errors][loginfail] |
| Not used | [GitLab authentication][gitlab-auth], [Service-to-service authentication][s2s] |

## Related skills

`rhdh-authorization`, `rhdh-configure`, `rhdh-git-integration`,
`ocp-authentication-identity-providers`.

[authn]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/authentication_in_red_hat_developer_hub/index#authentication
[prov]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/authentication_in_red_hat_developer_hub/index#user-provisioning
[guest]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/authentication_in_red_hat_developer_hub/index#disable-the-guest-login_enable-or-disable-authentication-with-the-guest-user
[share]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/authentication_in_red_hat_developer_hub/index#share-a-secret-with-rhbk_share-a-secret-with-your-identity-provider
[import]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/authentication_in_red_hat_developer_hub/index#import-users-and-groups-from-rhbk_import-users-and-groups-from-your-identity-provider
[rhbk]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/authentication_in_red_hat_developer_hub/index#enable-authentication-with-rhbk_enable-authentication-with-your-identity-provider
[session]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/authentication_in_red_hat_developer_hub/index#manage-session-expiration_enable-authentication-with-external-services
[ts]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/authentication_in_red_hat_developer_hub/index#troubleshoot-authentication-issues_enable-authentication-with-external-services
[loginfail]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/authentication_in_red_hat_developer_hub/index#troubleshoot-login-failed-errors_troubleshoot-authentication-issues
[gitlab-auth]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/authentication_in_red_hat_developer_hub/index#enable-authentication-with-gitlab_enable-authentication-with-your-identity-provider
[s2s]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/authentication_in_red_hat_developer_hub/index#enable-service-to-service-authentication_enable-authentication-with-external-services
