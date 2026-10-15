---
name: mta-install
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: mta
  docs-version: "8.3"
  skill-group: "Application Modernization"
description: >
  Use when reviewing or changing how this demo installs Migration Toolkit for
  Applications 8.3 in openshift-mta: the mta-operator Subscription and its
  InstallPlan approver, the Tackle CR (auth, storage, AI flags), Hub OIDC and
  the platform-sso IdentityProvider, the ConsoleLink, the agentic-controller
  VPA sizing, and install verification. Do NOT use for the Developer
  Lightspeed proxy or LLM settings (use mta-lightspeed), native Hub Agents and
  UI workflows (use mta-ui), the workspace CLI (use mta-cli), or release
  posture (use mta-release-notes).
---

# MTA install

Thin skill: repo decisions and pitfalls here, product procedure in the linked
MTA 8.3 sections. Detailed record:
`gitops/stages/070-advanced-app-platform/070-mta/README.md`.

## When to use

- A change touches `gitops/stages/070-advanced-app-platform/070-mta/` (operator,
  instance, SSO hook, controller sizing).
- `070-mta` fails to sync, the Tackle instance is not ready, or MTA login does
  not redirect to the platform realm.
- An MTA z-stream update is being reviewed.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Operator in `openshift-mta`, own-namespace OperatorGroup, channel `stable-v8.3`, `installPlanApproval: Manual`, `startingCSV: mta-operator.v8.3.1` | `gitops/stages/070-advanced-app-platform/070-mta/mta-operator/` | [Install the MTA Operator][op] |
| A Sync-hook Job approves the InstallPlan only when every CSV is on its allowlist (`mta-operator.v8.3.1`); `validate.sh` expects exactly that CSV | `070-mta/mta-operator/approve-installplan.yaml`, `stages/070-advanced-app-platform/validate.sh` | — (repo policy; the guide gives no channel guidance) |
| `Tackle mta`: `feature_auth_required: true`, `idp_primary: true`, `rwx_supported: "false"`, `kai_database_volume_size: 5Gi`; AI flags owned by `mta-lightspeed` and `mta-ui` | `070-mta/mta-instance/tackle.yaml` | [Custom resource settings][crs], [Authentication fields][authfields] |
| All volumes RWO on the default class; `deploy.sh` refuses unless `gp3-csi` is the default StorageClass | `stages/070-advanced-app-platform/deploy.sh` | [Persistent volume requirements][pv] |
| Platform SSO: hook ensures `role.*` realm roles, client `mta-hub`, `+role.<name>` optional scopes, Secret `mta-idp-client-secret` (key `clientSecret`), `IdentityProvider` `platform-sso` (primary), restarts the Hub on change | `070-mta/jobs/configure-mta-platform-sso.yaml` | [IdP client secret][idpsecret], [IdentityProvider CR][idpcr], [URI templating][uri], [Roles and personas][roles] |
| PostSync hook publishes `MTA_HUB_URL` to ConfigMap `mta-hub-config` in the three `wksp-*` namespaces | `070-mta/jobs/mta-hub-workspace-config.yaml` | — |
| `agentic-controller` memory sized by an OpenShift VPA (`Recreate`, memory only, one container) instead of a Tackle field or Deployment patch | `070-mta/controller-sizing/` | see `docs/OPERATIONS.md#mta-native-agents-and-controller-memory-sizing` |

## Procedure

1. Change Git only. A z-stream update edits the Subscription `startingCSV`,
   the approver allowlist and the validator expectation together
   (`stages/070-advanced-app-platform/tests/correction-package.test.py`
   checks they agree).
2. Deploy and validate after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   ./stages/070-advanced-app-platform/deploy.sh
   ./stages/070-advanced-app-platform/validate.sh
   ./stages/070-advanced-app-platform/validate.sh --static
   ```

3. Read-only checks:

   ```bash
   oc get subscription mta-operator -n openshift-mta -o jsonpath='{.status.installedCSV}{"\n"}'
   oc get tackle,identityprovider -n openshift-mta
   oc get deployment,vpa,pvc -n openshift-mta
   ```

## Pitfalls

- The Tackle schema preserves unknown fields: a dry run accepts a misspelled
  or guessed parameter. `product-schemas.test.py`
  (`test_tackle_parameters_are_implemented_by_the_downstream_operator`) checks
  fields against the downstream operator.
- MTA 8.3 has no supported RWO storage-class parameter; a non-default class
  leaves Hub claims Pending.
- The operator hardcodes the `agentic-controller` 128Mi limit; removing the
  VPA brings the OOMKill back on the next pod recreation:
  `docs/TROUBLESHOOTING.md#mta-83-solution-server-crashes-or-its-agentic-controller-oomkills`.
- Login without the platform realm redirect:
  `docs/TROUBLESHOOTING.md#mta-openshift-login-does-not-appear` (that entry
  still names Stage 130 and an older Job; the SSO hook now lives in `070-mta`).
- The operator owns the Hub, UI, `kai-db`, `llm-proxy`, `agentic-controller`,
  the Route and its NetworkPolicies; never add them to Git.

## Official documentation (MTA 8.3)

| Topic | Section |
|---|---|
| Operator install, instance, CR settings | [Install the Operator][op], [Create an instance][inst], [Custom resource settings][crs] |
| Storage | [Persistent volume requirements][pv] |
| Hub OIDC and Keycloak | [Authentication and authorization][oidc], [Enable authentication in Tackle][authcr], [RHBK][rhbk] |
| External IdP | [IdP client secret][idpsecret], [IdentityProvider CR][idpcr], [Authentication fields][authfields], [URI templating][uri] |
| CLI install (workspace image, see `mta-cli`) | [Install the CLI][cli] |

## Related skills

`mta-lightspeed`, `mta-ui`, `mta-cli`, `mta-release-notes`,
`ocp-authentication-identity-providers`, `rhoai-maas-governance`.

[op]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/installing_the_migration_toolkit_for_applications/index#installing-mta-operator_installing-mta-ui
[inst]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/installing_the_migration_toolkit_for_applications/index#creating-mta-instance_installing-mta-ui
[crs]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/installing_the_migration_toolkit_for_applications/index#custom-resource-settings_installing-mta-ui
[pv]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/installing_the_migration_toolkit_for_applications/index#persistent-volume-requirements_installing-mta-ui
[oidc]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/installing_the_migration_toolkit_for_applications/index#hub-oidc-authentication_installing-mta-title
[authcr]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/installing_the_migration_toolkit_for_applications/index#enable-authentication-cr_hub-oidc-authentication
[rhbk]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/installing_the_migration_toolkit_for_applications/index#red-hat-build-of-keycloak_installing-mta-title
[roles]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/installing_the_migration_toolkit_for_applications/index#roles-personas-users-permissions_red-hat-build-of-keycloak
[idpsecret]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/installing_the_migration_toolkit_for_applications/index#create-secret-idp-client_identity-provider-authentication
[idpcr]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/installing_the_migration_toolkit_for_applications/index#configure-identity-provider-cr_identity-provider-authentication
[authfields]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/installing_the_migration_toolkit_for_applications/index#authentication-fields-tackle-cr_installing-mta-title
[uri]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/installing_the_migration_toolkit_for_applications/index#uri-templating-wildcard-patterns_installing-mta-title
[cli]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/installing_the_migration_toolkit_for_applications/index#installing-mta-cli_installing-mta-title
