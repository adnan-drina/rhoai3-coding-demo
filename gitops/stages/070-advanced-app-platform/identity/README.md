# Platform identity (`070-identity`)

This Application connects the Stage 070 developer services to the Keycloak service that already runs in the environment (`Keycloak/keycloak` in namespace `keycloak`, Red Hat build of Keycloak 26.4 operator). It declares the application realm `platform`, links that realm to the base `sso` realm that OpenShift already uses, registers the SonarQube SAML client in `sso`, and issues four realm-scoped service credentials that later components use to configure their own clients. It does not deploy a Keycloak server.

| | |
|---|---|
| Argo CD Application | `070-identity` ([manifest](../../../argocd/app-of-apps/070-advanced-app-platform/identity.yaml)) |
| Deployed by | `stages/070-advanced-app-platform/deploy.sh` → `application.py deploy` (deploy-order 2) |
| Validated by | `stages/070-advanced-app-platform/validate.sh` (Keycloak and realm checks, `security-status.py`); `validate.sh --static` (`sso-alignment.test.py`, `correction-package.test.py`, `stage070-upgrade.test.py`) |
| Sync | Automated, `prune: true`, `selfHeal: true`; `CreateNamespace`, `SkipDryRunOnMissingResource`, `RespectIgnoreDifferences`, `ClientSideApplyMigration=false`; compare-option `ServerSideDiff=true`; `ignoreDifferences` on OAuthClient `platform-keycloak` (`/secret`, `/redirectURIs`) and on `/data` of the four provisioner Secrets |
| Depends on | The environment's Keycloak `keycloak/keycloak` (Ready, with the `sso` realm), OpenShift `OAuth/cluster` with the OpenID provider `rhbk` pointing at `sso`, users `ai-admin` and `ai-developer` in `sso`; the target namespaces `gitlab-system`, `rhdh`, `openshift-mta` and `trusted-artifact-signer` (from `070-namespaces`) |
| Used by | `070-gitlab` (OIDC client and integrations), `070-rhdh`, `070-mta` (platform SSO jobs), `070-pipelines` (TAS signing bootstrap), `070-sonarqube` (SAML client in `sso`); `rotate-credentials.py` |

## Why

Developer Hub, GitLab, MTA and Trusted Artifact Signer already have OIDC clients and user subjects in the `platform` realm. Keeping that realm preserves those subjects, memberships and roles. The realm now brokers sign-in straight to the base `sso` realm through an OpenID Connect identity provider [2], and its browser flow redirects to that provider by default [2]. Users therefore sign in once with the same account they use for OpenShift. No second Keycloak deployment or password store is added.

`KeycloakRealmImport` only creates a realm. It never updates or deletes an existing one [1]. So Git declares only the realm shell. A Sync-hook Job applies everything that depends on the cluster or must be idempotent (identity provider, links, clients) through the Keycloak Admin REST API.

Only this Job uses the master administration credential. Every other component gets a confidential service client in `platform` whose service account holds only the named `realm-management` roles it needs [3]. That keeps master authority in one place and out of application namespaces. Identity is deployed right after `070-namespaces` because every other component that signs users in reads one of these credentials.

## What

### `rhbk-instance/`: realm and legacy OAuth client

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| KeycloakRealmImport | `platform-realm` | `keycloak` | Creates realm `platform` on `keycloakCRName: keycloak` (`k8s.keycloak.org/v2alpha1`, the API the RHBK 26.4 operator serves); registration off, `sslRequired: external`. Wave 0, `SkipDryRunOnMissingResource` |
| OAuthClient | `platform-keycloak` | cluster-scoped | OpenShift OAuth client for the realm's earlier `openshift` identity provider, now disabled and kept for rollback. Git holds placeholders; the live `secret` and `redirectURIs` are ignored (wave 0) |

### `jobs/`: identity hook and its permissions

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| ServiceAccount | `job-configure-platform-identity` | `keycloak` | Identity of the hook (wave 1) |
| Role, RoleBinding | `job-configure-platform-identity` | `keycloak` | `get` on Secret `keycloak-initial-admin` only (wave 1) |
| ClusterRole, ClusterRoleBinding | `job-configure-platform-identity` | cluster-scoped | Read-only: `get` routes, `get` `oauths`/`ingresses` named `cluster`, `get` users and identities (wave 1) |
| ConfigMap | `stage070-scm-identity-<hash>` | `keycloak` | Generated from `secret_writer.py`, `configure-base-sso.py`, `configure-scm-identity.py` |
| Job | `job-configure-platform-identity` | `keycloak` | Sync hook, wave 1, `BeforeHookCreation,HookSucceeded`, `backoffLimit: 6`, 30 min deadline, digest-pinned `ose-cli` image. Runs `configure-base-sso.py` |
| Role, RoleBinding | `stage070-scm-identity` | `gitlab-system` | Lets the hook `get`/`patch` Secret `stage070-scm-provisioner` only (wave 1) |

### `jobs/platform-clients.yaml`: provisioner credentials

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| Secret (placeholder) | `stage070-scm-provisioner` | `gitlab-system` | Filled by the hook; read by GitLab bootstrap and OIDC jobs |
| Secret (placeholder) + Role/RoleBinding `stage070-platform-client-writer` | `stage070-rhdh-provisioner` | `rhdh` | Filled by the hook; read by the Developer Hub configuration job |
| Secret (placeholder) + Role/RoleBinding `stage070-platform-client-writer` | `stage070-mta-provisioner` | `openshift-mta` | Filled by the hook; read by the MTA platform SSO job |
| Secret (placeholder) + Role/RoleBinding `stage070-platform-client-writer` | `stage070-signing-provisioner` | `trusted-artifact-signer` | Filled by the hook; read by the TAS signing bootstrap |

All placeholders are wave 0, carry `argocd.argoproj.io/sync-options: ServerSideApply=true` (kustomize patch), and have no `data` in Git. Each writer Role grants `get`/`patch` on one Secret name.

Not in Git: the base Keycloak, the `sso` realm and its users, the broker and SAML clients, the identity provider `base-sso`, user links and the generated client secrets. The hook creates or updates them in Keycloak.

## How

1. **Order.** `application.py` syncs this Application after `070-namespaces` and waits for Succeeded, Synced and Healthy before `070-devspaces`. Inside the Application, wave 0 creates the realm, the OAuth client and the Secret placeholders. Wave 1 creates the RBAC, then the Sync hook runs (Argo CD orders by wave, then kind [5]).
2. **Preconditions (refuse before writing).** The hook reads the `keycloak` Route and `OAuth/cluster`. It requires exactly one OpenID provider `rhbk` [8] whose issuer is `https://<keycloak-host>/realms/sso`. It reads at most 1000 users from each realm. Every non-service user in `platform`, plus `ai-admin` and `ai-developer`, must match exactly one enabled `sso` user. An existing user is linked only after its OpenShift `Identity` (`rhbk:<subject>`) and stored OpenShift link agree. A username match alone never links an account. Existing `base-sso` providers, broker clients and the SonarQube client must carry the owner attribute `rhoai3.owner`, or the hook stops.
3. **Base realm (`sso`).** It creates or updates the confidential client `stage070-platform-broker` with the authorization-code flow only: an exact broker callback, an exact post-logout callback, `fullScopeAllowed: false` and no service account. It also creates or updates the SAML client `sonarqube`, which signs responses and assertions with RSA-SHA256, uses persistent NameID and maps `login`, `name` and `email`. Before the SonarQube Route exists, the callback uses the default Route host `sonarqube-sonarqube.<apps-domain>`. Any other lookup failure stops the hook.
4. **Application realm (`platform`).** It sets the OIDC provider `base-sso` with signature validation through JWKS, `trustEmail: false`, `syncMode: IMPORT` and the base realm's endpoints. It creates missing users and adds `base-sso` links. It sets the browser-flow Identity Provider Redirector default to `base-sso` [2]. It disables the old `openshift` provider but keeps its links for rollback.
5. **Service clients.** `configure-scm-identity.py` creates or updates four `platform` clients with client credentials only (`standardFlowEnabled: false`, `directAccessGrantsEnabled: false`, `fullScopeAllowed: false`). It assigns these `realm-management` roles and matching scope mappings:

   | Client | Roles |
   |---|---|
   | `stage070-scm-provisioner` | `manage-clients`, `view-users` |
   | `stage070-rhdh-provisioner` | `manage-clients` |
   | `stage070-mta-provisioner` | `manage-clients`, `manage-realm`, `view-realm`, `manage-users` |
   | `stage070-signing-provisioner` | `manage-clients` |

   It refuses if a client has unexpected `realm-management` roles. It writes `client_id` and `client_secret` to the Secret of the same name through `secret_writer.py`. That helper creates or merge-patches the Secret and never leaves a `last-applied-configuration` copy.
6. **Credentials.** The master token is minted inside the Job from `keycloak-initial-admin` and passed only to the child script's environment. Generated secrets exist only in Keycloak and in the Secrets above. `/data` is ignored, so Argo CD keeps the placeholder and never overwrites the generated values (`RespectIgnoreDifferences` [4]). Rotation of the SCM client is in `stages/070-advanced-app-platform/rotate-credentials.py`.

Rollback, refusals and recovery are in [OPERATIONS: shared base-platform SSO](../../../../docs/OPERATIONS.md#shared-base-platform-sso) and [TROUBLESHOOTING: shared SSO refuses a user or SonarQube login](../../../../docs/TROUBLESHOOTING.md#stage-070-shared-sso-refuses-a-user-or-sonarqube-login).

## Validation

`validate.sh` (live):

- `Reused Keycloak Ready` and `Platform realm imported` (`KeycloakRealmImport` condition `Done=True`).
- `Stage 070 corrected security boundaries` runs `security-status.py`. For this component it checks the following:
  - `no_credential_annotation:gitlab-system/stage070-scm-provisioner` and `no_retained_secret_annotation:<ns>`.
  - `no_master_secret:<ns>/<sa>`: the RHDH, MTA and signing job accounts cannot read `keycloak-initial-admin`.
  - `scoped_client_can_read_its_platform_configuration:<secret>` and `scoped_client_cannot_administer:<secret>/{sso,master}` for the RHDH, MTA and signing provisioner clients.

`validate.sh --static`:

- `sso-alignment.test.py`, `IdentityPreservation`: subject preservation and refusal of unbound, stale, conflicting, duplicate or disabled identities and of a foreign issuer. `test_broker_has_no_base_realm_management_authority`, `test_broker_logout_allows_only_its_exact_response_endpoint`, `test_cluster_identity_configuration_is_read_only`.
- `sso-alignment.test.py`, `test_keycloak_signs_assertions_and_uses_exact_callback` (SonarQube client).
- `correction-package.test.py`: `test_client_roles_stay_in_platform_and_keep_secret`, `test_downstream_jobs_have_no_master_secret_access`, `SecretLifecycle` (`secret_writer.py`).
- `stage070-upgrade.test.py`, `test_reused_keycloak_served_import_api`.

By hand (read-only):

```bash
oc get keycloakrealmimport platform-realm -n keycloak -o jsonpath='{.status.conditions[?(@.type=="Done")].status}'
oc get secret stage070-scm-provisioner -n gitlab-system -o name
oc get secret stage070-rhdh-provisioner -n rhdh -o name
oc get secret stage070-mta-provisioner -n openshift-mta -o jsonpath='{.metadata.annotations}'   # metadata only
```

## Alignment with official guidance

| Topic | Official guidance | This repository | Status |
|---|---|---|---|
| Realm import | `KeycloakRealmImport` creates a realm and never updates or deletes an existing one [1] | Realm shell only; mutable settings applied by the hook through the Admin API | Aligned |
| Import API version | Use the API the installed operator serves [1] | `k8s.keycloak.org/v2alpha1` on RHBK operator 26.4 | Aligned |
| Brokering to another IdP | OIDC v1.0 identity provider in the realm [2] | `base-sso` OIDC provider with JWKS signature validation | Aligned |
| Default login redirect | Set Default Identity Provider on the Identity Provider Redirector [2] | Hook sets `defaultProvider: base-sso` on the single redirector | Aligned |
| Trust Email | When ON, Keycloak trusts IdP email addresses [2] | `trustEmail: false`; links require a verified subject | Aligned (stricter) |
| Service accounts and token scope | Confidential client with a service account and role mappings; role scope limits token content [3] | Client-credentials-only clients, `fullScopeAllowed: false`, explicit role and scope mappings | Aligned |
| Admin credential | The operator's `<cr>-initial-admin` Secret works for the Admin REST API; change default admin credentials before production [7] | Used only by this hook, readable only by its service account | Deviation (justified: the environment owns its Keycloak admin lifecycle; downstream jobs never get it) |
| OAuth client registration | `OAuthClient` with `secret`, `redirectURIs`, `grantMethod` [6] | `platform-keycloak`, `grantMethod: auto`, placeholders in Git | Gap: no current code writes the placeholders, and the only consumer is the disabled `openshift` provider |
| Hook ordering and cleanup | Order is phase, wave, kind, name; `BeforeHookCreation`/`HookSucceeded` delete policies [5] | RBAC and hook in wave 1, Job deleted on success | Aligned |
| Secret ownership | Ignored fields are excluded from sync with `RespectIgnoreDifferences`; per-resource `ServerSideApply` annotation [4] | Placeholders server-side applied without `data`; `/data` ignored | Aligned |
| Namespace creation | `CreateNamespace` creates only `spec.destination.namespace` [4] | Writes into `gitlab-system`, `rhdh`, `openshift-mta`, `trusted-artifact-signer`, which come from `070-namespaces`, deployed first | Aligned |

## References

1. Operator guide, 3.1 "Importing a Red Hat build of Keycloak Realm", Red Hat build of Keycloak 26.4. https://docs.redhat.com/en/documentation/red_hat_build_of_keycloak/26.4/html/operator_guide/realm-import-
2. Server administration guide, chapter 9 "Integrating identity providers" (9.2 "Default Identity Provider", 9.3 general configuration, 9.5 "OpenID Connect v1.0 identity providers"), Red Hat build of Keycloak 26.4. https://docs.redhat.com/en/documentation/red_hat_build_of_keycloak/26.4/html/server_administration_guide/identity_broker
3. Server administration guide, "Managing OpenID Connect and SAML Clients" (13.1.8 "Using a service account", 13.1.9 "Role mappings in the token", 13.6 "Client scopes"), Red Hat build of Keycloak 26.4. https://docs.redhat.com/en/documentation/red_hat_build_of_keycloak/26.4/html/server_administration_guide/assembly-managing-clients_server_administration_guide
4. Sync options (`CreateNamespace`, `RespectIgnoreDifferences`, per-resource `ServerSideApply`), Argo CD (upstream). https://argo-cd.readthedocs.io/en/stable/user-guide/sync-options/
5. Sync phases and waves, Argo CD (upstream). https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/
6. Configuring OAuth clients, "Register an additional OAuth client", OpenShift Container Platform 4.22. https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/authentication_and_authorization/configuring-oauth-clients
7. Operator guide, 2.1.4 "Accessing the Admin Console", Red Hat build of Keycloak 26.4. https://docs.redhat.com/en/documentation/red_hat_build_of_keycloak/26.4/html/operator_guide/basic-deployment-
8. Configuring identity providers, 7.9 "Configuring an OpenID Connect identity provider", OpenShift Container Platform 4.22. https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/authentication_and_authorization/configuring-identity-providers

Repository: [Stage 070 README](../../../../stages/070-advanced-app-platform/README.md), [OPERATIONS: identity component](../../../../docs/OPERATIONS.md#stage-070--identity-identity-component), [OPERATIONS: shared base-platform SSO](../../../../docs/OPERATIONS.md#shared-base-platform-sso).
