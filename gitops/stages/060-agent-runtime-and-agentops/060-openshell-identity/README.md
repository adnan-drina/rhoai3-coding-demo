# OpenShell identity (`060-openshell-identity`)

This Application seeds the `openshell` realm in the existing Red Hat build of Keycloak instance. The realm is the OIDC
issuer that the OpenShell gateway (`060-openshell-runtime`) trusts for every API call. It defines the two OpenShell
roles and a first-login flow that refuses any OpenShift identity that was not enrolled in advance. Clients, the
OpenShift identity broker and the enrolled personas are added afterwards by `setup-identity.py`.

| | |
|---|---|
| Argo CD Application | `060-openshell-identity` ([manifest](../../../applications/060-openshell-identity.yaml)) |
| Deployed by | [`stages/060-agent-runtime-and-agentops/deploy.sh`](../../../../stages/060-agent-runtime-and-agentops/deploy.sh) (own deploy script, `demo.rhoai.io/deploy-script`); it then calls `deploy-runtime.sh` |
| Validated by | No dedicated validator. `deploy.sh` waits for the import condition `Done` and `setup-identity.py` asserts the realm, clients, broker and personas. [`validate.sh`](../../../../stages/060-agent-runtime-and-agentops/validate.sh) reports the whole stage as pending (exit 2). |
| Sync | Manual (documented exception in `.agents/rules/gitops.md`). The script pins it to the selected published SHA and starts a hook-strategy sync through `scripts/shared/stage_apps.py`. Annotation `compare-options: ServerSideDiff=true`. Sync options `CreateNamespace=true`, `SkipDryRunOnMissingResource=true`, `RespectIgnoreDifferences=true` (and a `ServerSideDiff=true` entry, which Argo CD ignores as a sync option). |
| Depends on | The `keycloak` Keycloak CR in namespace `keycloak` and its re-encrypt Route `keycloak` (not in this repository's Git; no Argo CD tracking). The Red Hat build of Keycloak operator 26.4. OpenShift Users `ai-admin` and `ai-developer` (cluster identity provider; Stage 010 adds them to the RHOAI groups). |
| Used by | `060-openshell-runtime`: `setup-runtime.py` derives the issuer `https://<keycloak-host>/realms/openshell` and writes it to ConfigMap `openshell/openshell-identity`; the gateway reads it as `OPENSHELL_OIDC_ISSUER`. The OpenShell CLI logs in through client `openshell-cli`. |

## Why

The OpenShell gateway authenticates callers with OIDC and maps a roles claim to its own platform-admin and user roles
(see the gateway environment in `060-openshell-runtime/chart/gateway-patch.yaml`). The upstream getting-started guide that
the RHOAI 3.5 release notes point to runs the gateway with `allowUnauthenticatedUsers=true` and warns that this is not
for shared clusters [4]. This repository keeps authentication on, so it needs an issuer that:

- issues tokens only to known OpenShift users (`ai-admin`, `ai-developer`), never to any user who can log in to OpenShift;
- carries a realm roles claim (`realm_access.roles`) with `openshell-user` or `openshell-platform-admin`;
- is separate from the platform realm used by Stage 070, so OpenShell roles cannot leak into other applications.

A dedicated realm in the existing Keycloak instance meets this. Keycloak brokers the OpenShift login through its
OpenShift 4 identity provider [2], so users authenticate with their OpenShift credentials and no password is stored
in Keycloak. The realm is seeded with a `KeycloakRealmImport` CR, the operator's declarative realm import [1]. OpenShell
sandboxing is a Developer Preview feature in OpenShift AI 3.5 [3].

## What

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| KeycloakRealmImport | `openshell-realm` | `keycloak` | Wave 1, `Prune=false`. Creates realm `openshell` (display name "Agent Runtime") with `sslRequired: all`, registration, password reset, email login and username edit disabled; realm roles `openshell-user` and `openshell-platform-admin`; top-level flow `openshell-prelinked-only` whose only step is `deny-access-authenticator`; realm attribute `openshell-managed: rhoai3-coding-demo` (ownership marker checked by the helpers). |

Objects deliberately not in Git, created by [`setup-identity.py`](../../../../stages/060-agent-runtime-and-agentops/setup-identity.py) after the import:

| Object | Where | Owner and purpose |
|---|---|---|
| Secret `openshell-auth` | `keycloak` | Generated broker and bootstrap client secrets (random, never printed). Annotated with the realm import UID. |
| OAuthClient `openshell-broker` | cluster | OpenShift OAuth client for the Keycloak broker: `grantMethod: prompt`, scope restricted to `user:info`, one redirect URI. |
| Identity provider `openshift-v4` | realm `openshell` | Keycloak OpenShift 4 broker, `syncMode: IMPORT`, first-login flow `openshell-prelinked-only`, token not stored. |
| Client `openshell-cli` | realm `openshell` | Public client, PKCE S256, device grant, loopback redirect only; scope-mapped to `openshell-user`. Audience mapper adds `openshell-gateway`. |
| Client `openshell-bootstrap` | realm `openshell` | Confidential service-account client holding `openshell-platform-admin`; used only by the setup helpers to manage workspaces. |
| Users `ai-admin`, `ai-developer` | realm `openshell` | Pre-created and pre-linked to the OpenShift User UID; role `openshell-user`; no credentials, no groups. |

## How

- **Ordering.** `deploy.sh` checks that the published branch head equals the local revision and that the scoped
  files have no local diff, refuses a foreign or busy Application, runs `setup-identity.py --preflight`, applies the
  Application pinned to the SHA, syncs and waits, waits for `keycloakrealmimport/openshell-realm` condition `Done`,
  then runs `setup-identity.py` and finally `deploy-runtime.sh`.
- **Pre-linked enrollment only.** The first-login flow denies every broker login that is not already linked. Keycloak's
  default first-login flow creates a user automatically [2]; replacing it with a deny step means only the two users
  the helper pre-creates and links (by OpenShift User UID, not by username) can sign in.
- **Import is create-only.** The Keycloak operator imports a realm only if it does not exist; it never updates or
  deletes it [1]. Changing `realm-openshell.yaml` therefore has no effect on an existing realm. Configuration after the
  first import is owned by `setup-identity.py`, which is idempotent and refuses to adopt objects without the
  `openshell-managed` marker.
- **The import CR is kept.** The operator guide recommends deleting the CR after import [1]. This repository keeps it
  (`Prune=false`) because `setup-identity.py` uses its UID as the ownership anchor for the generated Secret and
  OAuthClient.
- **Secrets.** Broker and bootstrap client secrets are generated in memory and stored only in `keycloak/openshell-auth`
  and the OAuthClient. The helper signs in to the Keycloak admin API with the operator-generated `keycloak-initial-admin` Secret (owner-checked against the Keycloak CR).
  Nothing secret is in Git.
- **Cluster-specific values.** The issuer host and the broker base URL (API server) are read from the live cluster at
  run time; no hostname is committed.

## Validation

`deploy.sh` and `setup-identity.py` are the checks. By hand (read-only):

```bash
oc get keycloakrealmimport openshell-realm -n keycloak -o jsonpath='{.status.conditions}'
oc get application 060-openshell-identity -n openshift-gitops -o jsonpath='{.status.sync.status} {.status.health.status}'
```

The first should show `Done=True` and `HasErrors=False`; the second `Synced Healthy`.

## Alignment with official guidance

| Topic | Official guidance (link) | This repository | Status |
|---|---|---|---|
| Realm creation | `KeycloakRealmImport` (`k8s.keycloak.org/v2alpha1`) in the same namespace as the Keycloak CR [1] | Same API, namespace `keycloak`, `keycloakCRName: keycloak` | Aligned |
| Realm updates | Import only creates; changes are not synced back [1] | Post-import configuration by an idempotent API helper | Aligned |
| Import CR lifecycle | Delete the CR after the import [1] | Kept with `Prune=false` as ownership anchor | Deviation (justified: helper ownership checks use its UID) |
| Who may edit realm import CRs | Restrict to namespace admins because placeholders expose environment variables [1] | No placeholders used; CR written only by Argo CD | Aligned |
| OpenShift broker | OpenShift 4 provider: client ID/secret, API base URL, matching OAuthClient and redirect URI [2], [5] | `openshift-v4` provider, OAuthClient `openshell-broker` with one redirect URI, `grantMethod: prompt` | Aligned |
| Automatic user creation | Default first-login flow creates users; can be disabled [2] | Custom flow denies every unlinked identity | Aligned (stricter) |
| OpenShell authentication | Upstream guide enables unauthenticated users; not for shared clusters [4] | OIDC required; `allowUnauthenticatedUsers: false` in the runtime chart values | Deviation (justified: shared demo cluster) |
| Support level | OpenShell integration is Developer Preview in RHOAI 3.5 [3] | Documented as Developer Preview | Aligned |
| Validation | n/a | No component validator; `validate.sh` is pending | Gap (no read-only identity check) |

## References

1. Red Hat build of Keycloak 26.4, Operator Guide, "Automating a realm import". https://docs.redhat.com/en/documentation/red_hat_build_of_keycloak/26.4/html/operator_guide/realm-import-
2. Red Hat build of Keycloak 26.4, Server Administration Guide, "Integrating identity providers" (OpenShift 4 provider; First login flow). https://docs.redhat.com/en/documentation/red_hat_build_of_keycloak/26.4/html/server_administration_guide/identity_broker
3. Red Hat OpenShift AI Self-Managed 3.5, Release notes, "Developer Preview features" (Secure agent sandboxing and policy enforcement using OpenShell). https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/developer-preview-features_relnotes
4. opendatahub-io/agent-ops, "Getting started with OpenShell on OpenShift" (pinned commit) (upstream). https://github.com/opendatahub-io/agent-ops/blob/7230605c8c0a4cec41c3e39e52e521db5c941355/guides/getting-started-openshell-openshift.md
5. OpenShift Container Platform 4.22, Authentication and authorization, "Configuring OAuth clients". https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/authentication_and_authorization/configuring-oauth-clients
